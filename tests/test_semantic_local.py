"""Fake encoders test contracts/math, NOT real model inference quality."""
import json
from pathlib import Path
import sqlite3
import types
import sys
import pytest
from jobhunter_app.semantic import rank,model_identity,vector,cosine,hardware,status,load_encoder
from jobhunter_app.store import Store

PROFILE={'name':'PRIVATE NAME','skills':['Python'],'facts':[{'text':'SQL project','source':'Synthetic','verified':True},{'text':'DO NOT INCLUDE UNVERIFIED','source':'Synthetic','verified':False}]}
JOB={'title':'Python Engineer','company':'Fixture','url':'https://example.org/semantic/1','description':'Python required','location':'Cairo'}
@pytest.fixture
def store(tmp_path):
    s=Store(tmp_path/'canonical.db');s.save_profile(PROFILE);s.ingest([JOB]);return s
@pytest.fixture
def model(tmp_path):
    p=tmp_path/'model';p.mkdir();(p/'model.safetensors').write_bytes(b'SYNTHETIC NOT A REAL MODEL')
    (p/'modules.json').write_text(json.dumps([{'idx':0,'name':'0','path':'','type':'sentence_transformers.models.Transformer'}]))
    return p
@pytest.fixture(autouse=True)
def ample_memory(monkeypatch):
    monkeypatch.setattr('jobhunter_app.semantic.hardware',lambda:{'available_memory_bytes':32*1024**3,'measured_inference':False})

class Encoder:
    def __init__(self):self.seen=[]
    def encode(self,texts,**kwargs):
        self.seen.extend(texts);assert kwargs=={'batch_size':1,'show_progress_bar':False,'convert_to_numpy':True,'normalize_embeddings':True}
        return [[1.,0.] if 'Python' in texts[0] else [0.,1.]]

def factory(encoder):return lambda path,threads:encoder

def test_rank_local_separate_from_lexical_no_network(monkeypatch,store,model):
    monkeypatch.setattr('socket.create_connection',lambda *a,**k:pytest.fail('No network'))
    store.evaluate();before=store.jobs()[0]['match'];e=Encoder();r=rank(store,model,_encoder_factory=factory(e))
    assert r['results'][0]['cosine_similarity']==1 and not r['cloud_enabled'] and not r['downloads_enabled']
    assert store.jobs()[0]['match']==before
    assert not any('PRIVATE NAME' in text or 'UNVERIFIED' in text for text in e.seen)
    assert 'SQL project' in e.seen[0]
    assert 'SQL project' not in json.dumps(r) and 'vector' not in r['results'][0]

def test_hard_exclusions_omit_before_encoder(store,model):
    store.ingest([{**JOB,'company':'Blocked','url':'https://example.org/semantic/2'}]);store.save_profile({**PROFILE,'matching':{'excluded_companies':['Blocked']}})
    r=rank(store,model,_encoder_factory=factory(Encoder()))
    assert len(r['results'])==1 and len(r['excluded'])==1 and r['results'][0]['company']=='Fixture'

def test_all_excluded_no_encoder(store,model):
    store.save_profile({**PROFILE,'excluded_title_terms':['Engineer']})
    with pytest.raises(ValueError,match='No non-excluded'):rank(store,model,_encoder_factory=lambda *a:pytest.fail('No load'))

@pytest.mark.parametrize('value',[[],[0.,0.],[float('nan'),1],[float('inf')],[True,1],['1'],[1e11], [1.]*4097])
def test_invalid_vector(value):
    with pytest.raises(ValueError):vector(value)

def test_cosine_bounds_and_mismatch():
    assert cosine(vector([1,0]),vector([0,1]))==0
    assert cosine(vector([1,1]),vector([1,1]))==pytest.approx(1)
    assert cosine(vector([1,0]),vector([-1,0]))==-1
    with pytest.raises(ValueError):cosine([1],[1,0])

@pytest.mark.parametrize('limit',[0,201,True,1.5])
def test_job_bound(store,model,limit):
    with pytest.raises(ValueError):rank(store,model,limit=limit)
@pytest.mark.parametrize('threads',[0,9,True,1.5])
def test_thread_bound(store,model,threads):
    with pytest.raises(ValueError):rank(store,model,threads=threads)

def test_no_candidate_evidence(store,model):
    store.save_profile({'name':'Not evidence'})
    with pytest.raises(ValueError,match='explicit skills'):rank(store,model)

def test_memory_gate_no_encoder(monkeypatch,store,model):
    monkeypatch.setattr('jobhunter_app.semantic.hardware',lambda:{'available_memory_bytes':1024})
    with pytest.raises(ValueError,match='Available RAM'):rank(store,model,_encoder_factory=lambda *a:pytest.fail('No load'))

def test_cache_hit_and_profile_text_model_job_invalidation(store,model,tmp_path):
    cache=tmp_path/'vectors.sqlite3';e=Encoder()
    a=rank(store,model,cache=cache,_encoder_factory=factory(e));assert a['new_vectors']==2 and a['cache_hits']==0
    b=rank(store,model,cache=cache,_encoder_factory=lambda *a:pytest.fail('Cached'));assert b['cache_hits']==2 and not b['inference_executed']
    store.save_profile({**PROFILE,'skills':['SQL']});c=rank(store,model,cache=cache,_encoder_factory=factory(e));assert c['new_vectors']==1
    store.ingest([{**JOB,'description':'Changed Python requirement'}]);d=rank(store,model,cache=cache,_encoder_factory=factory(e));assert d['new_vectors']==1
    (model/'model.safetensors').write_bytes(b'CHANGED SYNTHETIC MODEL')
    z=rank(store,model,cache=cache,_encoder_factory=factory(e));assert z['new_vectors']==2 and z['model_fingerprint']!=a['model_fingerprint']

def test_cache_rejects_canonical_or_other_sqlite(store,model,tmp_path):
    with pytest.raises(ValueError,match='separate'):rank(store,model,cache=store.path,_encoder_factory=factory(Encoder()))
    other=tmp_path/'other.sqlite3'
    with sqlite3.connect(other) as db:db.execute('CREATE TABLE original(value)')
    before=other.read_bytes()
    with pytest.raises(ValueError,match='not a JobHunter'):rank(store,model,cache=other,_encoder_factory=factory(Encoder()))
    assert other.read_bytes()==before

def test_bad_vector_rolls_back_new_cache_rows(store,model,tmp_path):
    class Bad(Encoder):
        def encode(self,texts,**kw):
            self.seen.extend(texts)
            return [[1.,0.]] if len(self.seen)==1 else [[float('nan'),0]]
    cache=tmp_path/'bad.sqlite3'
    with pytest.raises(ValueError,match='no new vectors'):rank(store,model,cache=cache,_encoder_factory=factory(Bad()))
    with sqlite3.connect(cache) as db:assert db.execute('SELECT COUNT(*) FROM semantic_vectors').fetchone()[0]==0

def test_vector_dimension_mismatch_no_cache_commit(store,model,tmp_path):
    class Bad(Encoder):
        def encode(self,texts,**kw):
            self.seen.extend(texts);return [[1.]] if len(self.seen)==1 else [[1.,0.]]
    cache=tmp_path/'mismatch.sqlite3'
    with pytest.raises(ValueError,match='dimension mismatch'):rank(store,model,cache=cache,_encoder_factory=factory(Bad()))
    with sqlite3.connect(cache) as db:assert db.execute('SELECT COUNT(*) FROM semantic_vectors').fetchone()[0]==0

def test_encoding_exception_sanitized_environment_restored(monkeypatch,store,model):
    class Bad:
        def encode(self,*a,**k):raise RuntimeError('SENSITIVE CANDIDATE DATA')
    monkeypatch.setenv('HF_HUB_OFFLINE','prior')
    def load(path,threads):
        import os
        assert os.environ['HF_HUB_OFFLINE']=='1' and os.environ['TRANSFORMERS_OFFLINE']=='1';return Bad()
    with pytest.raises(ValueError) as exc:rank(store,model,_encoder_factory=load)
    assert 'SENSITIVE' not in str(exc.value)
    import os
    assert os.environ['HF_HUB_OFFLINE']=='prior'

@pytest.mark.parametrize('suffix',['.py','.bin','.pt','.pkl','.dll'])
def test_model_rejects_code_and_pickle(model,suffix):
    (model/('unsafe'+suffix)).write_bytes(b'x')
    with pytest.raises(ValueError,match='unsupported'):model_identity(model)

def test_model_rejects_custom_modules_and_path_escape(model):
    p=model/'modules.json';p.write_text(json.dumps([{'type':'evil.Code','path':''}]))
    with pytest.raises(ValueError,match='Custom'):model_identity(model)
    p.write_text(json.dumps([{'type':'sentence_transformers.models.Transformer','path':'../outside'}]))
    with pytest.raises(ValueError,match='inside'):model_identity(model)

def test_model_symlink_rejected(model,tmp_path):
    link=tmp_path/'link';link.symlink_to(model,target_is_directory=True)
    with pytest.raises(ValueError,match='non-symlink'):model_identity(link)

def test_model_requires_safetensors_and_modules(model):
    (model/'model.safetensors').unlink()
    with pytest.raises(ValueError,match='safetensors'):model_identity(model)

def test_input_bounds_disclosed(store,model):
    store.save_profile({**PROFILE,'facts':[{'text':'x'*2000,'source':'Synthetic','verified':True} for _ in range(5)]})
    store.ingest([{**JOB,'description':'Python '+('x'*7000)}]);e=Encoder();r=rank(store,model,_encoder_factory=factory(e))
    assert r['query_char_truncated'] and r['results'][0]['input_char_truncated']
    assert all(len(x)<=6000 for x in e.seen) and r['token_truncation_possible']

def test_missing_dependency_is_explicit(monkeypatch,model):
    monkeypatch.setitem(sys.modules,'sentence_transformers',None)
    with pytest.raises(ValueError,match='Nothing was downloaded'):load_encoder(model,2)

def test_loader_uses_local_cpu_safe_options(monkeypatch,model):
    calls=[]
    fake_torch=types.SimpleNamespace(set_num_threads=lambda n:calls.append(n))
    class Fake:
        max_seq_length=2048
        def __init__(self,path,**kw):calls.append(kw)
    monkeypatch.setitem(sys.modules,'torch',fake_torch);monkeypatch.setitem(sys.modules,'sentence_transformers',types.SimpleNamespace(SentenceTransformer=Fake))
    e=load_encoder(model,2)
    assert calls==[2,{'device':'cpu','trust_remote_code':False,'local_files_only':True}] and e.max_seq_length==512

def test_cache_profile_scope_and_runtime_version_invalidation(monkeypatch,store,model,tmp_path):
    cache=tmp_path/'scoped.sqlite3';rank(store,model,cache=cache,_encoder_factory=factory(Encoder()))
    store.save_profile(PROFILE,'other')
    r=rank(store,model,profile_id='other',cache=cache,_encoder_factory=factory(Encoder()))
    assert r['new_vectors']==2 and r['cache_hits']==0
    monkeypatch.setattr('jobhunter_app.semantic.runtime_signature',lambda:{'encoder':'changed'})
    r=rank(store,model,cache=cache,_encoder_factory=factory(Encoder()))
    assert r['new_vectors']==2 and r['cache_hits']==0

def test_cache_invalid_json_is_not_reset(store,model,tmp_path):
    cache=tmp_path/'broken.sqlite3';rank(store,model,cache=cache,_encoder_factory=factory(Encoder()))
    with sqlite3.connect(cache) as db:db.execute("UPDATE semantic_vectors SET vector='broken'")
    before=cache.read_bytes()
    with pytest.raises(ValueError,match='Invalid semantic cache'):rank(store,model,cache=cache,_encoder_factory=factory(Encoder()))
    assert cache.read_bytes()==before

def test_cli_semantic_output_is_complete_no_overwrite(monkeypatch,store,model,tmp_path,capsys):
    from run_local import main
    monkeypatch.setattr('jobhunter_app.semantic.rank',lambda *a,**k:{'method':'fixture','results':[]})
    out=tmp_path/'semantic.json'
    args=['--db',str(store.path),'semantic-rank','--model-dir',str(model),'--output',str(out)]
    assert main(args)==0 and json.loads(out.read_text())['method']=='fixture'
    before=out.read_bytes();assert main(args)==2 and out.read_bytes()==before
    assert 'new filename' in capsys.readouterr().err

def test_status_cli_never_opens_database(monkeypatch,tmp_path,capsys):
    from run_local import main
    monkeypatch.setattr('run_local.Store',lambda *a,**k:pytest.fail('No DB needed for status'))
    assert main(['--db',str(tmp_path/'should-not-exist.db'),'semantic-status'])==0
    r=json.loads(capsys.readouterr().out)
    assert not r['ready'] and not r['downloads_enabled']
    assert not (tmp_path/'should-not-exist.db').exists()

def test_unknown_available_ram_fails_clearly(monkeypatch,store,model):
    monkeypatch.setattr('jobhunter_app.semantic.hardware',lambda:{'available_memory_bytes':None})
    with pytest.raises(ValueError,match='could not be assessed'):rank(store,model,_encoder_factory=lambda *a:pytest.fail('No load'))

def test_wrong_cache_format_is_preserved(store,model,tmp_path):
    p=tmp_path/'not-cache.sqlite3';p.write_bytes(b'not a database; preserve me')
    before=p.read_bytes()
    with pytest.raises(ValueError,match='cache could not open'):rank(store,model,cache=p,_encoder_factory=factory(Encoder()))
    assert p.read_bytes()==before

def test_model_disk_and_file_count_bounds(monkeypatch,model):
    monkeypatch.setattr('jobhunter_app.semantic.MAX_MODEL_BYTES',1)
    with pytest.raises(ValueError,match='bound'):model_identity(model)
    monkeypatch.setattr('jobhunter_app.semantic.MAX_MODEL_BYTES',2*1024**3)
    monkeypatch.setattr('jobhunter_app.semantic.MAX_MODEL_FILES',1)
    with pytest.raises(ValueError,match='bound'):model_identity(model)

def test_nested_model_symlink_rejected(model,tmp_path):
    outside=tmp_path/'outside';outside.mkdir();(model/'linked').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='symlinks'):model_identity(model)

def test_malformed_module_configuration(model):
    (model/'modules.json').write_text('not json')
    with pytest.raises(ValueError,match='Invalid local model'):model_identity(model)

def test_negative_cosine_sorted_but_never_fit_percentage(store,model):
    store.ingest([{**JOB,'url':'https://example.org/semantic/negative','description':'Other text','title':'Other Engineer'}])
    class Directed:
        def encode(self,texts,**kw):return [[-1.,0.]] if 'Other' in texts[0] else [[1.,0.]]
    r=rank(store,model,_encoder_factory=factory(Directed()))
    assert [x['cosine_similarity'] for x in r['results']]==[1.,-1.]
    assert all('score_percent' not in x for x in r['results'])

def test_selection_bound_is_explicit(store,model):
    store.ingest([{**JOB,'url':f'https://example.org/semantic/bounded/{n}'} for n in range(3)])
    r=rank(store,model,limit=2,_encoder_factory=factory(Encoder()))
    assert r['selected_jobs']==2 and r['selection_limit']==2 and 'not all jobs' in r['selection_scope']
