'use strict';
const keys=new Set(), allowed=new Set(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown']);
const canvas=document.getElementById('screen'), context=canvas.getContext('2d');
context.imageSmoothingEnabled=false;
let sequence=Date.now()*100, alive=true, lastStage='';
const buttons=[...document.querySelectorAll('[data-key]')];
function paintKeys(){for(const button of buttons)button.classList.toggle('active',keys.has(button.dataset.key));}
function send(){paintKeys();return fetch('/api/input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keys:[...keys],sequence:++sequence}),keepalive:true}).catch(()=>{});}
function release(){keys.clear();send();}
window.addEventListener('keydown',event=>{if(!allowed.has(event.key)||event.target.closest('input,textarea,select'))return;event.preventDefault();if(!keys.has(event.key)){keys.add(event.key);send();}});
window.addEventListener('keyup',event=>{if(!allowed.has(event.key))return;event.preventDefault();keys.delete(event.key);send();});
window.addEventListener('blur',release);
document.addEventListener('visibilitychange',()=>{if(document.hidden)release();});
window.addEventListener('pagehide',()=>{alive=false;release();});
for(const button of buttons){
 button.addEventListener('pointerdown',event=>{event.preventDefault();button.setPointerCapture(event.pointerId);keys.add(button.dataset.key);send();});
 for(const type of ['pointerup','pointercancel','lostpointercapture'])button.addEventListener(type,()=>{keys.delete(button.dataset.key);send();});
}
setInterval(()=>{if(!document.hidden&&alive)send();},110);
document.getElementById('scale').addEventListener('click',event=>{const actual=canvas.classList.toggle('actual');event.currentTarget.setAttribute('aria-pressed',String(actual));event.currentTarget.textContent=actual?'Enlarge display':'View at 1× pixels';event.currentTarget.blur();});
document.getElementById('reset').addEventListener('click',async event=>{const button=event.currentTarget;release();await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});button.blur();});
async function refresh(){
 try{
  const response=await fetch('/api/frame');if(!response.ok)throw new Error('Receiver unavailable');
  const {state,frame}=await response.json();const image=new Image();image.src='data:image/png;base64,'+frame;await image.decode();context.drawImage(image,0,0,240,135);
  document.getElementById('loading').classList.add('hidden');
  document.getElementById('progress').textContent=state.messages.length+' / 2 records';
  const stage=state.stage;
  if(stage!==lastStage){document.getElementById('instruction').textContent=stage==='tuning'?'Left/right: frequency. Up/down: amplitude. Release when matched to acquire.':stage==='recovered'?'Test record A recovered. Release the controls, then press Right for the Moon record.':'Both diagnostic records recovered. Use Up / Down to review them and solve the decoder.';lastStage=stage;}
 }catch(error){const loading=document.getElementById('loading');loading.textContent='Receiver disconnected. Check that the simulator is running.';loading.classList.remove('hidden');release();}
 if(alive)setTimeout(refresh,85);
}
refresh();
