'use strict';
/* Backend evaluation receipts only. No browser scoring or provider keys. */
(() => {
 let target=null, busy=false;
 function render(r){
  const out=$('detail-evaluation-result');out.replaceChildren();
  if(!r){out.append(node('p','Evaluation pending — no persisted evaluation for this opportunity.'));return;}
  out.append(node('p','Status: '+r.status+' · actual method: '+(r.method||'not executed')+(r.stale?' · STALE: inputs changed; evaluate again':'')));
  out.append(node('p','Scale: '+(r.score_scale||'no score')+(r.score!==null?' · score: '+r.score:'')+(r.classification?' · '+r.classification:'')));
  if(r.ai){out.append(node('p',r.ai.summary||''),node('p','Provider/model: '+(r.ai.model_used||'not reported')),node('p','German policy: '+r.ai.german_policy+' · threshold: '+r.threshold));
   for(const [name,value] of Object.entries(r.ai.scores||{}))out.append(node('p',name.replaceAll('_',' ')+': '+value+'/5'));}
  if(r.local)out.append(node('p',r.local.explanation||r.local.method),node('p','Local constraint outcome: '+r.local.eligibility));
  if(r.error)out.append(node('p',r.error.code+': '+r.error.message,'notice'));
  for(const warning of r.warnings||[])out.append(node('p',warning,'notice'));
  out.append(node('p','Started: '+r.started_at+' · Finished: '+r.finished_at,'muted'));
 }
 window.loadEvaluation=async job=>{target=job.id;$('evaluation-consent').checked=false;const id=target;render(null);try{const r=await api('/api/evaluation?id='+encodeURIComponent(id));if(target===id)render(r);}catch(e){if(target===id)$('detail-evaluation-result').textContent='Evaluation could not be loaded: '+e.message;}};
 $('evaluate-job').onclick=safe(async()=>{
  if(busy||!target)return;const id=target;busy=true;$('evaluate-job').disabled=true;
  $('detail-evaluation-result').textContent='Waiting for backend evaluation. No completion or score is assumed.';
  try{const r=await api('/api/evaluate',{id,options:{method:$('evaluation-method').value,allow_provider:$('evaluation-consent').checked,fallback:$('evaluation-fallback').checked,threshold:Number($('evaluation-threshold').value),german_policy:$('evaluation-german').value}});if(target===id)render(r);}
  finally{busy=false;$('evaluate-job').disabled=false;}
 });
})();
