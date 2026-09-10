const status=document.querySelector('#status'),connect=document.querySelector('#connect'),update=document.querySelector('#update');
let busy=false,recovering=false,reportedError='';
const outdated=()=>chrome.runtime.getManifest().version!=='0.6.0';
async function refresh(){if(busy)return;update.hidden=!outdated();connect.hidden=outdated();if(outdated()){status.textContent='Готово обновление: агент сможет сам открывать сайты и вкладки. Нажми «Обновить расширение», затем снова открой этот значок.';return;}const s=await chrome.runtime.sendMessage({type:'status'});status.textContent=reportedError||s?.text||'Разреши Chrome один раз — дальше агент сам выбирает сайты и вкладки.';connect.textContent=s?.allSites?'Подключить Chrome':'Разрешить Chrome';if(s?.allSites&&!s?.ready&&!recovering&&(await chrome.storage.local.get('browserEnabled')).browserEnabled!==false){recovering=true;const result=await chrome.runtime.sendMessage({type:'connect'});if(result?.error)reportedError=result.error;}}
update.onclick=()=>chrome.runtime.reload();
connect.onclick=async()=>{busy=true;reportedError='';try{
 // Chrome requires this request to be made directly from the user's button click.
 const granted=await chrome.permissions.request({origins:['https://*/*']});
 if(!granted)throw Error('Chrome не получил разрешение. Можно включить его этой кнопкой позже.');
 const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
 const result=await chrome.runtime.sendMessage({type:'connect',tabId:tab?.id});if(result?.error)throw Error(result.error);
 busy=false;await refresh();
}catch(e){status.textContent=e.message;busy=false;}};
document.querySelector('#stop').onclick=async()=>{await chrome.runtime.sendMessage({type:'disconnect'});await refresh();};refresh();setInterval(refresh,1000);
