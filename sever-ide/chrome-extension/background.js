importScripts('config.js','navigation.js');
let socket=null,enabled=false,connecting=false,heartbeat=null,reconnect=null,serial=Promise.resolve(),connectionSession=null,generation=0,selection=null;
const cancelled=new Set();
const timeout=(promise,ms,label)=>{let timer;return Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label)),ms);})]).finally(()=>clearTimeout(timer));};
const browser=new RantBrowser(chrome,async()=>{await publishState();});
async function status(text,ready=false){await chrome.storage.session.set({connectionStatus:{text,ready,tab:browser.selected?.title||'',allSites:await browser.fullAccess()}});await chrome.action.setBadgeText({text:enabled?(ready?'ON':'!'):''});await chrome.action.setBadgeBackgroundColor({color:ready?'#286b45':'#bd5535'});}
function send(value){if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(value));}
async function browserState(){return {tab:browser.selected?{url:browser.selected.url,title:browser.selected.title}:null,capabilities:{tabs:true,navigation:true,all_sites:await browser.fullAccess()}};}
async function publishState(){send({type:'browser_state',...await browserState()});}
async function page(action,args){
 const tab=await browser.tab();
 if(!tab){if(action==='snapshot')return {url:'',title:'Нет выбранной вкладки',text:'Открой нужный сайт через browser_new_tab с HTTPS URL. Не проси пользователя создавать вкладку.',controls:[],untrusted_content:true};throw Error('Нет текущей вкладки. Используй browser_new_tab.');}
 await browser.requireAccess(tab.url,{current:true});await browser.select(tab);
 await timeout(chrome.scripting.executeScript({target:{tabId:tab.id},files:['page.js']}),8000,'Chrome не ответил при чтении страницы.');
 const [r]=await timeout(chrome.scripting.executeScript({target:{tabId:tab.id},func:(action,args)=>globalThis.__severPage?.(action,args),args:[action,args]}),8000,'Страница не ответила.');
 if(!r?.result)throw Error('Не удалось прочитать страницу. Повтори только снимок.');if(r.result.error)throw Error(r.result.error);return {...r.result,tab_id:String(tab.id)};
}
async function command(c,epoch){
 if(cancelled.has(c.id)||epoch!==generation)return;
 const saved=(await timeout(chrome.storage.session.get('commandJournal'),2000,'Не удалось прочитать очередь Chrome')).commandJournal||{};
 if(saved[c.id]){send(saved[c.id].result||{type:'result',id:c.id,error:'Прошлая попытка прервалась. Выполнение неизвестно; проверь страницу, не повторяй отправку.',uncertain:true});return;}
 if(Date.now()/1000>c.expires){send({type:'result',id:c.id,error:'Срок команды истёк до выполнения.'});return;}
 saved[c.id]={started:Date.now()};const keys=Object.keys(saved);for(const k of keys.slice(0,Math.max(0,keys.length-12)))delete saved[k];
 await timeout(chrome.storage.session.set({commandJournal:saved}),2000,'Не удалось сохранить очередь Chrome');
 let value,error,uncertain=false;
 try{
  if(cancelled.has(c.id)||epoch!==generation||Date.now()/1000>c.expires)throw Error('Задача остановлена до выполнения');
  if(c.action==='open'||c.action==='new_tab')value=await browser.open(c.args.url,c.action==='new_tab');
  else if(c.action==='tabs')value=await browser.list();
  else if(c.action==='switch')value=await browser.switchTo(c.args.tab_id);
  else value=await page(c.action,{...c.args,deadline:c.expires*1000});
  if(['click','type','select','scroll'].includes(c.action))await new Promise(r=>setTimeout(r,250));
 }catch(e){error=e.message;uncertain=/не ответил|не ответила/.test(error)&&['click','type','select','open','new_tab','switch'].includes(c.action);}
 const result={type:'result',id:c.id,value,error,uncertain};saved[c.id]={result};await timeout(chrome.storage.session.set({commandJournal:saved}),2000,'Не удалось сохранить результат');send(result);
}
async function connect(){
 if(connecting||socket||!enabled)return;connecting=true;await status('Подключаюсь к IDE…');
 const ws=new WebSocket(SEVER_BRIDGE_WS);socket=ws;
 const opening=setTimeout(()=>{if(ws.readyState!==WebSocket.OPEN)ws.close();},5000);
 ws.onopen=async()=>{clearTimeout(opening);send({type:'hello',protocol:3,token:SEVER_TOKEN,selection,version:chrome.runtime.getManifest().version,...await browserState()});};
 ws.onmessage=async(event)=>{
  const m=JSON.parse(event.data);
  if(m.type==='ready'){
   connectionSession=m.session;connecting=false;await status('Chrome подключён. Сайты и вкладки агент открывает сам.',true);clearInterval(heartbeat);heartbeat=setInterval(()=>send({type:'ping'}),10000);
   const j=(await chrome.storage.session.get('commandJournal')).commandJournal||{};for(const entry of Object.values(j))if(entry.result)send(entry.result);
  }else if(m.type==='command'){
   if(m.session!==connectionSession){send({type:'result',id:m.id,error:'Команда относится к прошлому подключению'});return;}
   send({type:'received',id:m.id});const epoch=generation;
   serial=serial.then(()=>timeout(command(m,epoch),22000,'Очередь Chrome не завершила команду')).catch(e=>{cancelled.add(m.id);send({type:'result',id:m.id,error:e.message,uncertain:['click','type','select','open','new_tab','switch'].includes(m.action)});});
  }else if(m.type==='cancel')cancelled.add(m.id);
 };
 ws.onclose=()=>{clearTimeout(opening);clearInterval(heartbeat);if(socket!==ws)return;socket=null;connecting=false;if(enabled){status('Нет связи с IDE. Переподключаюсь…');clearTimeout(reconnect);reconnect=setTimeout(connect,2000);}};
 ws.onerror=()=>ws.close();
}
async function disconnect(){generation++;serial=Promise.resolve();connectionSession=null;enabled=false;browser.selected=null;clearTimeout(reconnect);clearInterval(heartbeat);send({type:'disconnect'});const old=socket;socket=null;connecting=false;old?.close();await chrome.storage.session.remove(['selectedTab','commandJournal']);await chrome.storage.local.set({browserEnabled:false});await chrome.alarms.clear('sever-reconnect');await status('Chrome отключён.');}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{
 if(sender.id!==chrome.runtime.id||!sender.url?.startsWith(chrome.runtime.getURL('popup.html')))return;
 (async()=>{
  if(m.type==='connect'){
   if(!await browser.fullAccess())throw Error('Сначала разреши доступ к сайтам Chrome.');
   if(m.tabId){const tab=await chrome.tabs.get(m.tabId);try{await browser.requireAccess(tab.url);await browser.select(tab);}catch{await browser.restore();}}
   else await browser.restore();
   enabled=true;selection=selection||crypto.randomUUID();await chrome.storage.local.set({browserEnabled:true});await chrome.storage.session.set({browserSelection:selection});await chrome.alarms.create('sever-reconnect',{periodInMinutes:.5});await connect();await publishState();
  }else if(m.type==='disconnect')await disconnect();
  else if(m.type==='status')return {...(await chrome.storage.session.get('connectionStatus')).connectionStatus,allSites:await browser.fullAccess(),version:chrome.runtime.getManifest().version};
  return {ok:true};
 })().then(reply,e=>{status(e.message);reply({error:e.message});});return true;
});
chrome.tabs.onUpdated.addListener((id,change)=>{browser.changed(id,change).catch(e=>status(e.message));});
chrome.tabs.onRemoved.addListener(id=>{browser.removed(id).catch(()=>{});});
chrome.permissions.onAdded.addListener(async()=>{if(await browser.fullAccess()){enabled=true;selection=selection||crypto.randomUUID();await chrome.storage.local.set({browserEnabled:true});await browser.restore();await chrome.alarms.create('sever-reconnect',{periodInMinutes:.5});await connect();await publishState();}});
chrome.permissions.onRemoved.addListener(()=>{publishState();status('Доступ изменён в Chrome. При необходимости нажми «Разрешить Chrome».');});
chrome.alarms.onAlarm.addListener(a=>{if(a.name==='sever-reconnect')connect();});
chrome.runtime.onStartup.addListener(async()=>{await chrome.storage.session.remove(['selectedTab','commandJournal']);await browser.restore();await publishState();});
(async()=>{const old=await chrome.storage.session.get(['selectedTab','browserSelection']);const saved=await chrome.storage.local.get('browserEnabled');enabled=typeof saved.browserEnabled==='boolean'?saved.browserEnabled:!!old.selectedTab||await browser.fullAccess();selection=old.browserSelection||crypto.randomUUID();await chrome.storage.session.set({browserSelection:selection});await browser.restore();if(enabled){await chrome.storage.local.set({browserEnabled:true});await chrome.alarms.create('sever-reconnect',{periodInMinutes:.5});await connect();}})();
