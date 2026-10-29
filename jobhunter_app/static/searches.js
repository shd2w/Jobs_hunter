"use strict";
(()=>{
 let items=[],busy=false;
 const pick=()=>items.find(x=>x.id===$('saved-search-select').value);
 function render(){const item=pick();for(const id of ['saved-search-apply','saved-search-update','saved-search-delete'])$(id).disabled=busy||!item;$('saved-search-form').querySelector('[type=submit]').disabled=busy;$('saved-search-select').disabled=busy;$('saved-search-name').disabled=busy;$('saved-search-summary').textContent=item?'Saved keyword: '+(item.query||'(any)')+' · Status: '+(item.status||'all')+'. Opening this search uses current local data.':'Save as new creates a filter from the keyword and status shown above.';}
 async function refresh(){const chosen=$('saved-search-select').value;items=await api('/api/saved-searches');const select=$('saved-search-select');select.replaceChildren(new Option('New saved search',''));items.forEach(x=>select.append(new Option(x.name,x.id)));select.value=items.some(x=>x.id===chosen)?chosen:'';render();}
 async function action(fn){if(busy)return;busy=true;render();try{await fn();}catch(e){$('saved-search-message').textContent=e.message;}finally{busy=false;render();}}
 function filters(){return {name:$('saved-search-name').value,query:$('query').value,status:$('status').value};}
 $('saved-search-select').onchange=()=>{$('saved-search-name').value=pick()?.name||'';$('saved-search-message').textContent='';render();};
 $('saved-search-form').onsubmit=e=>{e.preventDefault();action(async()=>{const item=await api('/api/saved-search',{search:filters()});await refresh();$('saved-search-select').value=item.id;render();$('saved-search-message').textContent='Saved current filters. No scan or notification started.';});};
 $('saved-search-update').onclick=()=>action(async()=>{const id=pick().id;await api('/api/saved-search',{id,search:filters()});await refresh();$('saved-search-message').textContent='Replaced selected saved search with current filters.';});
 $('saved-search-apply').onclick=()=>action(async()=>{const item=pick();$('query').value=item.query;$('status').value=item.status;offset=0;await loadJobs();$('saved-search-message').textContent='Opened “'+item.name+'” using current local opportunities. No collection was started.';});
 $('saved-search-delete').onclick=()=>action(async()=>{const item=pick();if(!window.confirm('Delete saved search “'+item.name+'”? Opportunities and progress will not be deleted.'))return;await api('/api/saved-search-delete',{id:item.id,confirmed:true});$('saved-search-name').value='';await refresh();$('saved-search-message').textContent='Deleted saved search. Opportunities and progress are unchanged.';});
 window.refreshSavedSearches=refresh;
})();
