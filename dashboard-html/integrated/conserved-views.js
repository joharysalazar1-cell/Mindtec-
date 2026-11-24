/* Isolate historical scripts so their identifiers and filters cannot replace current KPI state. */
(()=>{
const node=document.getElementById('conserved-views-data');if(!node)return;
const entries=JSON.parse(node.textContent),frames=new Map(),busy=new Map(),status=document.getElementById('conserved-status');let active=null;
async function open(key){const entry=entries.find(v=>v.key===key);if(!entry)return;active=key;
 document.querySelectorAll('[data-conserved]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.conserved===key)));
 for(const [k,frame]of frames)frame.hidden=k!==key;
 document.getElementById('conserved-scope').textContent=entry.scope;status.textContent=frames.has(key)?'Vista conservada abierta.':'Cargando la vista conservada…';
 if(frames.has(key))return;
 if(busy.has(key))return busy.get(key);
 const task=(async()=>{try{
  const frame=document.createElement('iframe');frame.title=entry.label;frame.className='conserved-frame';frame.hidden=active!==key;
  if(entry.payload){
   const bytes=Uint8Array.from(atob(entry.payload),c=>c.charCodeAt(0));
   const raw=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
   const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),b=>b.toString(16).padStart(2,'0')).join('');
   if(digest!==entry.sha256)throw Error('La huella de la vista no coincide con la fuente conservada.');
   let html=new TextDecoder().decode(raw);
   // These are navigation links only; data and original calculations remain unchanged.
   html=html.replaceAll('href="/','href="https://mindtec-intelligence-audit.ablazemarch.chatgpt.site/');
   frame.srcdoc=html;
  }else if(entry.route)frame.src=entry.route;else throw Error('Esta vista está incluida en la entrega HTML local integrada.');
  frame.hidden=active!==key;frame.addEventListener('load',()=>{if(active===key)status.textContent='Vista completa abierta; conserva su propio corte, filtros y resultados.';},{once:true});
  frames.set(key,frame);document.getElementById('conserved-frames').appendChild(frame);
 }catch(error){if(active===key)status.textContent='No se pudo abrir: '+error.message;}finally{busy.delete(key);}})();busy.set(key,task);return task;
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-conserved]');if(b)open(b.dataset.conserved);});
function firstView(){if(location.hash==='#vistas-conservadas'&&!active)open('historico');}window.addEventListener('hashchange',firstView);firstView();
})();
