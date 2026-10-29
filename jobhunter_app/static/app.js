'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="csrf-token"]').content;
let jobs = [], states = [], selected = null, offset = 0, poll = null;
function node(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if(cls)e.className=cls; return e; }
function message(text, error=false) { const e=$('message');e.hidden=false;e.textContent=text;e.className=error?'error':'';if(error&&$('post-dialog')?.open){const local=$('review-error');local.hidden=false;local.textContent=text;local.scrollIntoView({block:'start'});} }
async function api(url, data) {
 const response = await fetch(url, data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-JobHunter-Token':token},body:JSON.stringify(data)});
 const result=await response.json(); if(!response.ok)throw new Error(result.error||'Request failed'); return result;
}
function safe(fn) {return async event=>{try {await fn(event);}catch(e){message(e instanceof SyntaxError?'Invalid JSON. Check the array, quotation marks and commas; nothing was saved.':e.message,true);}};}
function showTab(name) {
 document.querySelectorAll('main>.panel').forEach(e=>e.hidden=e.id!==name);
 document.querySelectorAll('nav button').forEach(e=>{const active=e.dataset.tab===name;e.classList.toggle('active',active);if(active)e.setAttribute('aria-current','page');else e.removeAttribute('aria-current');});
}
document.querySelectorAll('[data-tab]').forEach(e=>e.onclick=()=>showTab(e.dataset.tab));
function empty(container,title,text,action) {container.replaceChildren();const e=node('div',undefined,'empty');e.append(node('h3',title),node('p',text));if(action){const b=node('button','Import opportunities');b.onclick=()=>showTab('tools');e.append(b);}container.append(e);}
async function refresh() {
 const summary=await api('/api/summary');states=summary.states;
 $('total').textContent=summary.total_jobs;$('matched').textContent=summary.matched_jobs;
 $('progress').textContent=['reviewing','preparing','ready'].reduce((n,k)=>n+(summary.status_counts[k]||0),0);$('applied').textContent=summary.status_counts.applied||0;
 for(const id of ['status','detail-status']){const s=$(id),value=s.value;s.replaceChildren();if(id==='status')s.append(new Option('All statuses',''));states.forEach(x=>s.append(new Option(x.replaceAll('_',' '),x)));s.value=value;}
 await loadJobs();if(window.refreshSavedSearches)await window.refreshSavedSearches();renderSources(summary.sources);await loadLearning();if(window.refreshLearningProgress)await window.refreshLearningProgress();if(window.refreshWorkflow)await window.refreshWorkflow();if(window.refreshDiscovery)await window.refreshDiscovery();
}
async function loadJobs(){
 jobs=await api('/api/jobs?q='+encodeURIComponent($('query').value)+'&status='+encodeURIComponent($('status').value)+'&offset='+offset);
 const list=$('job-list');list.replaceChildren();
 if(!jobs.length){const filtered=$('query').value||$('status').value||offset;empty(list,filtered?'No opportunities match these filters.':'Your first opportunities are on their way.',filtered?'Try a different keyword or status, or return to the previous page.':'Automatic discovery checks the starter feeds when this server is running. See feed status above for progress, pauses or access problems.',false);}
 for(const job of jobs){const card=node('article',undefined,'job'),body=node('div',undefined,'job-main');body.append(node('h3',job.title),node('p',job.company+(job.location?' · '+job.location:'')));const tags=node('div',undefined,'tags');tags.append(node('span',job.status,'tag'));
 if(job.match){tags.append(node('span',job.match.score_percent===null?'Profile skills not set':job.match.score_percent+'% skill mentions','tag blue'));if(job.match.eligibility==='excluded_by_config')tags.append(node('span','Excluded by your settings','tag'));}
 else tags.append(node('span','Browse now · profile optional','tag'));if(job.match?.ranking?.score_percent!==null&&job.match?.ranking?.score_percent!==undefined)tags.append(node('span',job.match.ranking.score_percent+'% weighted lexical preferences','tag'));body.append(tags);if(job.attribution){const a=node('a','Source: '+job.attribution+' ↗');a.href=job.url;a.target='_blank';a.rel='noopener noreferrer';body.append(a);}const b=node('button','Review opportunity');b.onclick=safe(()=>openJob(job));card.append(body,b);list.append(card);}
 $('previous').disabled=offset===0;$('next').disabled=jobs.length<200;$('page-label').textContent=jobs.length?(offset+1)+'–'+(offset+jobs.length):'No results';
}
$('search-form').onsubmit=safe(async e=>{e.preventDefault();offset=0;await loadJobs();});
$('previous').onclick=safe(async()=>{offset=Math.max(0,offset-200);await loadJobs();});$('next').onclick=safe(async()=>{offset+=200;await loadJobs();});
async function openJob(job){if(window.confirmEvidenceSwitch&&!window.confirmEvidenceSwitch())return;selected=job;$('detail-title').textContent=job.title;$('detail-company').textContent=job.company+(job.location?' · '+job.location:'');$('detail-url').href=job.url;
 $('detail-description').textContent=job.description||'No description supplied. Eligibility and keyword evidence remain incomplete.';
 $('detail-match').textContent=job.match?job.match.explanation+' '+job.match.uncertainties.join(' '):'You can browse and apply using the original listing without a profile. Add your skills under Your evidence only if you want optional local keyword matching. Eligibility is not inferred.';
 if(job.match?.requirements){$('detail-match').textContent+='\n\nContextual skill clauses (rule-based; review required):\n'+job.match.requirements.map(r=>r.skill+' · '+r.classification+' · '+r.candidate_evidence+'\n“'+r.evidence+'”').join('\n');$('detail-match').textContent+='\n\nConstraint checks:\n'+(job.match.hard_constraint_checks.map(c=>c.kind+': '+c.term+' → '+c.state).join('\n')||'None configured.');}const context=job.match?.eligibility_context;
 if(context){$('detail-match').textContent+='\n\nEligibility review — not assessed:\n'+context.notice+(context.truncated?'\nWARNING: Evidence is truncated. Review the complete original listing.':'');
 for(const category of context.categories){const evidence=context.evidence.filter(r=>r.category===category.category);$('detail-match').textContent+='\n\n'+category.category.replaceAll('_',' ')+' · '+category.listing_state+'\n'+category.review_question+'\n'+evidence.map(r=>r.field+' ['+r.start+':'+r.end+'] · '+r.cue_classification+'\n“'+r.evidence+'”').join('\n');}}
 const k=job.match?.keywords;$('detail-keywords').textContent=k?'Supported keyword mentions: '+(k.supported.join(', ')||'None recorded')+'. Learning gaps: '+(k.learning_gaps.join(', ')||'None observed')+'. '+k.notice:'No keyword analysis yet.';
 $('detail-status').value=job.status;$('detail-notes').value=job.notes;$('detail-deadline').value=job.deadline;await history(job.id);if(window.loadOrigins)await window.loadOrigins(job);if(window.loadPackVersions)await window.loadPackVersions(job);$('job-dialog').showModal();}
async function history(id){const rows=await api('/api/history?id='+encodeURIComponent(id));$('history').replaceChildren(...rows.map(r=>node('li',(r.old_status||'untracked')+' → '+r.new_status+' · '+new Date(r.changed_at).toLocaleString())));}
$('close-dialog').onclick=()=>$('job-dialog').close();
$('job-form').onsubmit=safe(async e=>{e.preventDefault();await api('/api/status',{id:selected.id,status:$('detail-status').value,notes:$('detail-notes').value,deadline:$('detail-deadline').value});$('job-dialog').close();message('Progress saved. No application was submitted.');await refresh();});
$('followup-open').onclick=safe(async()=>{const job=selected;$('job-dialog').close();showTab('workflow');await window.planFollowup(job);});
$('pack').onclick=safe(async()=>{if(window.createPackVersion)await window.createPackVersion(selected);});
$('match').onclick=safe(async()=>{const b=$('match');b.disabled=true;try{const r=await api('/api/match',{});message('Matched '+r.evaluated+' jobs using transparent lexical evidence.');await refresh();}finally{b.disabled=false;}});
async function loadProfile(){const p=await api('/api/profile');$('candidate-name').value=p.name||'';$('skills').value=(p.skills||[]).join(', ');$('languages').value=(p.languages||[]).join(', ');$('exclusions').value=(p.excluded_title_terms||[]).join(', ');$('facts').value=JSON.stringify(p.facts||[],null,2);$('matching-settings').value=JSON.stringify(p.matching||{},null,2);}
const parts=id=>$(id).value.split(',').map(x=>x.trim()).filter(Boolean);
$('profile-form').onsubmit=safe(async e=>{e.preventDefault();await api('/api/profile',{profile:{name:$('candidate-name').value,skills:parts('skills'),languages:parts('languages'),excluded_title_terms:parts('exclusions'),facts:JSON.parse($('facts').value||'[]'),matching:JSON.parse($('matching-settings').value||'{}')}});message('Evidence saved. Automatic discovery refreshes local matching when enabled; you can also use Refresh matches under workspace activity.');await refresh();});
async function loadLearning(){const data=await api('/api/learning');window.renderLearning(data);}

function renderSources(sources){const list=$('source-list');list.replaceChildren();if(!sources.length)empty(list,'Choose your first source.','Register a supported public source above. Nothing runs until you request a scan.');sources.forEach(s=>{const card=node('article',undefined,'job'),body=node('div');body.append(node('h3',s.id),node('p',(s.approved?'Approved':'Not approved')+' · '+s.health+(s.last_error?' · '+s.last_error:'')));const b=node('button','Scan now');b.disabled=!s.approved;b.onclick=safe(async()=>{await api('/api/scan',{source_id:s.id});message('Manual scan requested.');startPolling();});const revoke=node('button',s.approved?'Pause source':'Approve after terms review');revoke.onclick=safe(async()=>{if(!s.approved&&!confirm('Have you reviewed the applicable source terms and confirmed permission for this use?'))return;await api('/api/source',{kind:s.kind,identifier:s.identifier,approved:!s.approved});await refresh();});const actions=node('div',undefined,'actions');actions.append(b,revoke);card.append(body,actions);list.append(card);});}
function startPolling(){if(poll)return;poll=setInterval(safe(async()=>{const t=await api('/api/task');$('task-state').textContent=t.running?'Scanning. You can request a safe stop.':t.error||scanSummary(t.result);if(!t.running){clearInterval(poll);poll=null;if(t.error)message(t.error,true);await refresh();}}),1000);}
$('stop').onclick=safe(async()=>{const r=await api('/api/stop',{});message(r.notice);});
// CSV parser supports quoted fields, escaped quotes, commas and newlines.
function parseCSV(text){let rows=[],row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){let c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){row.push(cell);cell='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x))rows.push(row);row=[];cell='';}else cell+=c;}if(quoted)throw new Error('Unterminated CSV quote');if(cell||row.length){row.push(cell);rows.push(row);}const header=rows.shift()||[];return rows.map(r=>Object.fromEntries(header.map((key,i)=>[key,r[i]||''])));}
$('import-form').onsubmit=safe(async e=>{e.preventDefault();const f=$('import-file').files[0];if(!f)throw new Error('Choose a file');if(f.size>10*1024*1024)throw new Error('Import exceeds 10 MiB');const text=(await f.text()).replace(/^\uFEFF/,'');const ext=f.name.split('.').pop().toLowerCase();let rows;if(ext==='json')rows=JSON.parse(text);else if(ext==='jsonl')rows=text.split(/\r?\n/).filter(x=>x.trim()).map(x=>JSON.parse(x));else if(ext==='csv')rows=parseCSV(text);else throw new Error('Use JSON, JSONL or CSV');const r=await api('/api/import',{jobs:rows,dry_run:$('preview').checked});$('import-result').textContent=JSON.stringify(r,null,2);message(r.dry_run?'Preview only. Uncheck preview to save valid records.':'Import completed. Invalid rows were reported separately.');await refresh();});
$('backup').onclick=safe(async()=>{const r=await api('/api/backup',{});message('Consistent database backup saved: '+r.backup);});
(async()=>{try{await loadProfile();await refresh();startPolling();}catch(e){message(e instanceof SyntaxError?'Invalid JSON. Check the array, quotation marks and commas; nothing was saved.':e.message,true);}})();

function scanSummary(result){
 if(!result)return 'No active scan';
 const items=result.results||[{result}];
 return items.map(item=>{const r=item.result||{};return (item.source?item.source+': ':'')+(item.error|| (r.cancelled?'Cancelled; checkpoint unchanged.':r.staged!==undefined?r.staged+' posts staged; review required.':(r.new_unique_jobs??r.inserted??0)+' new unique jobs; '+(r.existing_job_observations??r.updated??0)+' existing observations.'))+(r.source_scope?(r.listing_pass_exhausted?' Listing route exhausted; whole-site coverage unverified.':' Bounded route; inspect health and resume manually when due.'):r.bounded_selection?' More pages remain; resume manually when due.':'');}).join('\n');
}
