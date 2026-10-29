"""Opt-in CPU sentence embeddings from provisioned local safetensors only.

Separate comparison artifact, never suitability/eligibility or a lexical override.
No model is installed/downloaded. An optional vector cache is sensitive local data.
"""
from contextlib import contextmanager
import hashlib
import importlib.util
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sqlite3
import time

VERSION='local-semantic-comparison-1'

def runtime_signature():
    versions={}
    for name in ('sentence-transformers','transformers','torch','safetensors'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]='not installed'
    return versions

MAX_JOBS=200
MAX_TEXT=6000
MAX_MODEL_BYTES=2*1024**3
MAX_MODEL_FILES=256
ALLOWED_MODULES={'sentence_transformers.models.Transformer','sentence_transformers.models.Pooling','sentence_transformers.models.Normalize'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def hardware():
    total=available=None
    try:
        if os.name=='nt':
            import ctypes
            class Memory(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ('total','available','total_page','avail_page','total_virtual','avail_virtual','extended')]
            m=Memory();m.length=ctypes.sizeof(Memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):total=m.total;available=m.available
        else:
            total=os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
            mem=Path('/proc/meminfo')
            if mem.exists():
                for line in mem.read_text().splitlines():
                    if line.startswith('MemAvailable:'):available=int(line.split()[1])*1024
    except (OSError,ValueError,AttributeError):pass
    # Linux container limits may be much smaller than host /proc/meminfo.
    try:
        limit=Path('/sys/fs/cgroup/memory.max').read_text().strip()
        used=int(Path('/sys/fs/cgroup/memory.current').read_text().strip())
        if limit!='max':
            limit=int(limit);total=min(total,limit) if total else limit
            free=max(0,limit-used);available=min(available,free) if available else free
    except (OSError,ValueError):pass
    return {'platform':platform.system(),'logical_cpus':os.cpu_count(),'total_memory_bytes':total,'available_memory_bytes':available,
            'device_policy':'CPU only; no GPU/CUDA requirement or probe','measured_inference':False}


def status():
    present=importlib.util.find_spec('sentence_transformers') is not None
    return {'semantic_version':VERSION,'dependency_present':present,'runtime_versions':runtime_signature(),'hardware':hardware(),
            'ready':False,'reason':'A validated, user-provisioned local model and explicit semantic-rank command are required.',
            'downloads_enabled':False,'cloud_enabled':False,'notice':'Dependency presence is not proof of compatible installation or working inference.'}


def model_identity(directory):
    root=Path(directory)
    if root.is_symlink() or not root.is_dir():raise ValueError('Supply an existing, non-symlink local model directory; no model IDs or downloads')
    root=root.resolve();files=[];size=0;digest=hashlib.sha256()
    for folder,dirs,names in os.walk(root,followlinks=False):
        for name in dirs:
            if (Path(folder)/name).is_symlink():raise ValueError('Model symlinks are not supported')
        for name in names:
            p=Path(folder)/name
            if p.is_symlink() or not p.is_file():raise ValueError('Model special files are not supported')
            rel=p.relative_to(root)
            if p.suffix.lower() in ('.py','.pyc','.pkl','.pickle','.bin','.pt','.pth','.so','.dll','.exe'):
                raise ValueError('Model requires unsupported code/pickle/native files; use a trusted safetensors sentence model')
            files.append(p);size+=p.stat().st_size
            if len(files)>MAX_MODEL_FILES or size>MAX_MODEL_BYTES:raise ValueError('Local model exceeds the 256-file / 2-GiB checkpoint bound')
    if not any(p.suffix=='.safetensors' for p in files):raise ValueError('A provisioned safetensors model is required')
    module_file=root/'modules.json'
    if not module_file.is_file() or module_file.stat().st_size>65536:raise ValueError('A standard local sentence-transformers modules.json is required')
    try:modules=json.loads(module_file.read_text(encoding='utf-8'))
    except (ValueError,UnicodeError):raise ValueError('Invalid local model module configuration') from None
    if not isinstance(modules,list) or not 1<=len(modules)<=10:raise ValueError('Unsupported local model modules')
    for m in modules:
        if not isinstance(m,dict) or m.get('type') not in ALLOWED_MODULES:raise ValueError('Custom model modules are not allowed')
        value=m.get('path','')
        if not isinstance(value,str) or '\\' in value or Path(value).is_absolute() or '..' in Path(value).parts:
            raise ValueError('Model module path must remain inside the local model')
        if not (root/value).is_dir():raise ValueError('Local model module directory is missing')
    for p in sorted(files,key=lambda p:str(p.relative_to(root))):
        digest.update(str(p.relative_to(root)).encode());digest.update(b'\0')
        with p.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
    return {'path':root,'fingerprint':digest.hexdigest(),'bytes':size,'files':len(files)}


@contextmanager
def offline_environment():
    settings={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','TOKENIZERS_PARALLELISM':'false'}
    prior={k:os.environ.get(k) for k in settings}
    os.environ.update(settings)
    try:yield
    finally:
        for k,v in prior.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v


def load_encoder(path,threads):
    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError:raise ValueError('Optional local semantic dependencies are unavailable; provision a trusted compatible CPU sentence-transformers runtime separately. Nothing was downloaded.') from None
    try:
        torch.set_num_threads(threads)
        encoder=SentenceTransformer(str(path),device='cpu',trust_remote_code=False,local_files_only=True)
        encoder.max_seq_length=min(int(encoder.max_seq_length),512)
        return encoder
    except Exception:raise ValueError('Local semantic model could not load; no fallback score, model download or remote-code execution was attempted') from None


def vector(value):
    if hasattr(value,'tolist'):value=value.tolist()
    if not isinstance(value,(list,tuple)) or not 1<=len(value)<=4096:raise ValueError('Invalid semantic vector dimensions')
    if any(type(x) not in (float,int) or not math.isfinite(x) or abs(x)>1e10 for x in value):raise ValueError('Semantic vectors must contain bounded finite numbers')
    norm=math.sqrt(sum(x*x for x in value))
    if norm<=1e-12:raise ValueError('Zero semantic vector is not comparable')
    return [x/norm for x in value]


def cosine(a,b):
    if len(a)!=len(b):raise ValueError('Semantic vector dimension mismatch')
    return max(-1.0,min(1.0,sum(x*y for x,y in zip(a,b))))


def candidate_text(profile):
    # Names, CV paths, unverified facts, contact details/preferences are not added.
    text='\n'.join(profile.get('skills',[])+[x['text'] for x in profile.get('facts',[]) if x.get('verified') is True])
    if not text.strip():raise ValueError('Record explicit skills or verified facts before semantic comparison')
    return text[:MAX_TEXT],len(text)>MAX_TEXT


def rank(store,model_dir,profile_id='default',limit=50,threads=2,cache=None,_encoder_factory=None):
    from .matching import match_job
    if type(limit) is not int or not 1<=limit<=MAX_JOBS:raise ValueError('Semantic limit must be 1–200')
    if type(threads) is not int or not 1<=threads<=8:raise ValueError('Semantic CPU threads must be 1–8')
    started=time.monotonic();profile=store.profile(profile_id);query,query_truncated=candidate_text(profile)
    model=model_identity(model_dir);hw=hardware()
    # Conservative gate, not a guarantee or a model-specific peak-memory estimate.
    required=max(4*1024**3,model['bytes']*4+2*1024**3)
    if hw['available_memory_bytes'] is None:raise ValueError('Available RAM could not be assessed; use lexical matching in this environment')
    if hw['available_memory_bytes']<required:
        raise ValueError('Available RAM is below the conservative local-semantic gate; use lexical matching or a separately provisioned smaller runtime')
    jobs=store.jobs(profile_id=profile_id,limit=limit)
    specs=[];excluded=[]
    for job in jobs:
        lexical=match_job(job,profile)
        if lexical['eligibility']=='excluded_by_config':
            excluded.append({'job_id':job['id'],'reason':'excluded_by_config'});continue
        raw=job['title']+'\n'+job.get('location','')+'\n'+job.get('description','')
        specs.append((job,raw[:MAX_TEXT],len(raw)>MAX_TEXT))
    if not specs:raise ValueError('No non-excluded jobs in the bounded selected slice; no encoder was loaded')
    texts=[query]+[x[1] for x in specs]
    runtime=runtime_signature()
    keys=[fingerprint({'version':VERSION,'runtime':runtime,'profile_id':profile_id,'threads':threads,'model':model['fingerprint'],'text':text,'max_tokens':512,'max_chars':MAX_TEXT,'normalize':True}) for text in texts]
    db=None;cached={};new={};vectors=[];encoder=None;hits=0
    if cache is not None:
        cp=Path(cache)
        if cp.resolve()==store.path.resolve() or cp.is_symlink() or cp.resolve().is_relative_to(model['path']):raise ValueError('Use a separate non-symlink vector cache outside the model directory and canonical database')
        cp.parent.mkdir(parents=True,exist_ok=True);existing=cp.exists()
        try:
            db=sqlite3.connect(cp,timeout=15)
            if existing and db.execute('PRAGMA application_id').fetchone()[0]!=0x4a485345:
                db.close();raise ValueError('Existing file is not a JobHunter semantic cache; use a new filename')
        except sqlite3.DatabaseError:
            if db:db.close()
            raise ValueError('Local semantic cache could not open; preserve it and use a new filename') from None
    try:
        if db:
            if not existing:
                db.execute('PRAGMA application_id=1246253893')
                db.execute('CREATE TABLE semantic_vectors(key TEXT PRIMARY KEY, vector TEXT NOT NULL)')
                db.commit()
            else:
                db.execute('SELECT key,vector FROM semantic_vectors LIMIT 0')
            for key in set(keys):
                row=db.execute('SELECT vector FROM semantic_vectors WHERE key=?',(key,)).fetchone()
                if row:
                    try:cached[key]=vector(json.loads(row[0]))
                    except (ValueError,TypeError):raise ValueError('Invalid semantic cache vector; preserve the cache and retry with a new filename') from None
        with offline_environment():
            for key,text in zip(keys,texts):
                if key in cached:hits+=1;vectors.append(cached[key]);continue
                if key in new:vectors.append(new[key]);continue
                if encoder is None:encoder=(_encoder_factory or load_encoder)(model['path'],threads)
                try:
                    encoded=encoder.encode([text],batch_size=1,show_progress_bar=False,convert_to_numpy=True,normalize_embeddings=True)
                    if len(encoded)!=1:raise ValueError('Invalid embedding count')
                    v=vector(encoded[0])
                except Exception:raise ValueError('Local semantic encoding failed; no score was substituted and no new vectors were committed') from None
                new[key]=v;vectors.append(v)
        scores=[]
        for (job,_,truncated),v in zip(specs,vectors[1:]):
            score=cosine(vectors[0],v)
            scores.append({'job_id':job['id'],'title':job['title'],'company':job['company'],'url':job['url'],
                           'cosine_similarity':round(score,6),'input_char_truncated':truncated,
                           'job_fingerprint':fingerprint(job),'eligibility':'needs_review'})
        scores.sort(key=lambda x:(-x['cosine_similarity'],x['job_id']))
        if db:
            current=db.execute('SELECT COUNT(*) FROM semantic_vectors').fetchone()[0]
            if current+len(new)>50000:raise ValueError('Semantic cache reached its 50,000-vector bound; use a new filename')
            with db:db.executemany('INSERT OR REPLACE INTO semantic_vectors VALUES(?,?)',[(k,json.dumps(v,allow_nan=False)) for k,v in new.items()])
        return {'method':VERSION,'runtime_versions':runtime,'model_fingerprint':model['fingerprint'],'profile_fingerprint':fingerprint(profile),
                'results':scores,'excluded':excluded,'selected_jobs':len(jobs),'selection_limit':limit,
                'selection_scope':'Most recently seen local jobs, bounded before exclusions; not all jobs or a complete ranking.',
                'cache_hits':hits,'new_vectors':len(new),'vector_cache_enabled':cache is not None,'query_char_truncated':query_truncated,
                'token_limit':512,'token_truncation_possible':True,'elapsed_seconds':round(time.monotonic()-started,3),'hardware':hw,
                'inference_executed':encoder is not None,'downloads_enabled':False,'cloud_enabled':False,
                'notice':'Cosine comparison only, not suitability, percent fit, proof of skills or legal eligibility. Hard exclusions are omitted, never overridden. Existing lexical matches, notification scores and UAA records are unchanged. Vectors in an optional cache are sensitive derived evidence.'}
    except sqlite3.DatabaseError:raise ValueError('Local semantic cache operation failed; preserve it and use a new cache filename') from None
    finally:
        if db:db.close()
