const tabId=Number(new URL(location.href).searchParams.get('tab'));
const status=document.querySelector('#status');let stopped=false,session,lastId;
async function api(path,data){const r=await fetch(SEVER_BRIDGE_HTTP+'/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Sever-Extension':SEVER_TOKEN},body:JSON.stringify(data)});if(!r.ok)throw Error('Нет связи. Запусти Connect-Chrome.command и подключи вкладку снова.');return r.json();}
async function page(action,args){await chrome.scripting.executeScript({target:{tabId},files:['page.js']});const [r]=await chrome.scripting.executeScript({target:{tabId},func:(action,args)=>globalThis.__severPage?.(action,args),args:[action,args]});if(!r?.result)throw Error('Нажми расширение на вкладке заново.');if(r.result.error)throw Error(r.result.error);return r.result;}
async function tick(){if(stopped)return;try{
 const {command:c}=await api('poll',{session});
 if(c&&c.id!==lastId){lastId=c.id;let value,error;try{
 if(Date.now()/1000>c.expires)throw Error('Срок действия команды истёк');
 if(c.action==='open'){
 const target=new URL(c.args.url),tab=await chrome.tabs.get(tabId);
 if(target.protocol!=='https:'||target.origin!==new URL(tab.url).origin)throw Error('Открой этот сайт вручную и подключи вкладку заново: '+c.args.url);
 await chrome.tabs.update(tabId,{url:target.href});await new Promise(r=>setTimeout(r,1200));await chrome.scripting.executeScript({target:{tabId},files:['page.js']});value={ok:true};
 }else {value=await page(c.action,c.args);if(['click','type','select','scroll'].includes(c.action))await new Promise(r=>setTimeout(r,650));}
 }catch(e){error=e.message;}await api('result',{session,id:c.id,value,error});}
 status.textContent='Подключена выбранная вкладка. Можно давать задание в IDE.';
 }catch(e){status.textContent=e.message;stopped=true;}if(!stopped)setTimeout(tick,500);}
document.querySelector('#stop').onclick=async()=>{stopped=true;await api('disconnect',{session}).catch(()=>{});status.textContent='Отключено. Вкладка осталась открытой.';};
(async()=>{try{({session}=await api('connect',{}));await tick();}catch(e){status.textContent=e.message;}})();
