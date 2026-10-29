'use strict';
/* Poll only discovery status and inbox counts. Never reset profile/editor drafts. */
(() => {
 let enabled=false, busy=false, rendered='', loaded='', timer;
 const date=value=>value?new Date(value).toLocaleString():'';
 const names={scanning:'Scanning now',needs_setup:'Setup needed',paused:'Source paused',cooldown:'Waiting for next allowed scan',queued:'Queued'};
 function render(data){
  enabled=data.enabled;
  $('auto-toggle').disabled=!data.available;$('auto-check').disabled=!data.available||!enabled;
  $('auto-toggle').textContent=enabled?'Pause discovery':'Resume discovery';
  if(!data.available){$('auto-heading').textContent='Manual discovery mode';$('auto-summary').textContent='Start normally with python run_local.py serve for automatic starter feeds.';return;}
  const failures=data.sources.filter(s=>['failed','blocked','access_blocked','rate_limited','interrupted'].includes(s.health)).length;
  const active=data.sources.find(s=>s.state==='scanning');
  $('auto-heading').textContent=!enabled?'Discovery is paused':active?'Finding opportunities for you…':data.total_jobs?data.total_jobs+' opportunities, ready to explore':data.phase==='error'?'Discovery needs attention':'Checking your public job feeds…';
  $('auto-badge').textContent=!enabled?'PAUSED · YOUR JOBS ARE KEPT':active?'AUTOMATIC DISCOVERY · SCANNING':'AUTOMATIC DISCOVERY';
  if(!enabled)$('auto-summary').textContent='Your pause is saved, including after a restart. An in-flight request may finish, but its cancelled results are not imported.';
  if(enabled)$('auto-summary').textContent=data.error||(active?active.label+' is being checked. Results appear here automatically.':(data.last_cycle?'Feeds refresh when due while this server runs.':'Starting the first bounded scan. No setup needed.')+(failures?' '+failures+' source'+(failures===1?' needs':'s need')+' attention. Other feeds continue.':''));
  $('auto-scope').textContent=data.scope;
  const signature=JSON.stringify(data.sources);
  if(signature!==rendered){rendered=signature;$('auto-sources').replaceChildren(...data.sources.map(s=>{
   const card=node('article',undefined,'auto-source');card.append(node('h3',s.label));
   const failed=['failed','blocked','access_blocked','rate_limited','interrupted'].includes(s.health);
   card.append(node('p',failed?'Access or response problem':names[s.state]||s.state,failed?'source-error':'source-state'));
   if(s.last_completed_at)card.append(node('p',s.new_jobs+' new jobs in last scan · '+(s.health==='partial'?'bounded page, more may be available':'scan complete')));
   if(s.error)card.append(node('p',s.error,'muted'));
   if(s.next_allowed_at)card.append(node('p','Next allowed: '+date(s.next_allowed_at),'muted'));
   if(!s.approved)card.append(node('p','Review this source in Discovery before enabling it again.','muted'));
   return card;
  }));}
  if(data.last_cycle&&data.total_jobs===0&&failures&&!$('auto-details').dataset.opened){$('auto-details').open=true;$('auto-details').dataset.opened='1';}
 }
 async function update(){
  if(busy)return;busy=true;
  try{
   const data=await api('/api/automatic');render(data);
   const stamp=[data.total_jobs,data.revision].join(':');
   if(stamp!==loaded&&!document.querySelector('dialog[open]')){
    const summary=await api('/api/summary');$('total').textContent=summary.total_jobs;$('matched').textContent=summary.matched_jobs;
    $('progress').textContent=['reviewing','preparing','ready'].reduce((n,k)=>n+(summary.status_counts[k]||0),0);$('applied').textContent=summary.status_counts.applied||0;
    await loadJobs();loaded=stamp;
   }
  }catch(e){$('auto-heading').textContent='Workspace connection interrupted';$('auto-summary').textContent='Retrying shortly. Keep the Python server running and the forwarded port private.';}
  finally{busy=false;}
 }
 $('auto-toggle').onclick=safe(async()=>{await api('/api/automatic',{enabled:!enabled});await update();});
 $('auto-check').onclick=safe(async()=>{await api('/api/automatic-check',{});await update();});
 update();timer=setInterval(update,2000);
 window.addEventListener('pagehide',()=>clearInterval(timer));
 window.addEventListener('pageshow',event=>{if(event.persisted){update();timer=setInterval(update,2000);}});
})();
