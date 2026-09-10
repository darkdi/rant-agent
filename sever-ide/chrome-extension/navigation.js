/* Browser navigation is independent of the page bridge: moving to another origin
   never disconnects the agent. Chrome's persisted host grant is the authority. */
class RantBrowser {
 constructor(api,onChange=()=>{}){this.api=api;this.onChange=onChange;this.selected=null;this.created=new Set();}
 url(value){
  const u=new URL(value),h=u.hostname.toLowerCase().replace(/^\[|\]$/g,'');
  if(u.protocol!=='https:'||u.username||u.password||u.port||h==='localhost'||h.endsWith('.localhost')||h.endsWith('.local')||!h.includes('.')||/^(127\.|10\.|0\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(h)||h.includes(':'))throw Error('Доступны публичные HTTPS-сайты. Служебные страницы Chrome и локальная сеть не поддерживаются.');
  return u;
 }
 async get(id){let timer;try{return await Promise.race([this.api.tabs.get(id),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Chrome не ответил при выборе вкладки. Повтори чтение.')),2000);})]);}finally{clearTimeout(timer);}}
 async fullAccess(){return this.api.permissions.contains({origins:['https://*/*']});}
 async requireAccess(url,{current=false}={}){
  const u=this.url(url);
  if(await this.api.permissions.contains({origins:[u.origin+'/*']}))return u;
  if(current&&this.selected?.origin===u.origin)return u; // Explicit activeTab grant, legacy connection only.
  throw Error('Доступ ко всем сайтам ещё не выдан. В расширении нажми «Разрешить Chrome» один раз. Открывать сайт вручную не нужно.');
 }
 async select(tab){
  const u=this.url(tab.url);this.selected={id:tab.id,url:u.href,title:tab.title||'',origin:u.origin};
  await this.api.storage.session.set({selectedTab:this.selected});await this.onChange(this.selected);return this.selected;
 }
 async restore(){
  const saved=(await this.api.storage.session.get('selectedTab')).selectedTab;
  if(saved){try{const tab=await this.get(saved.id);this.selected=saved;await this.requireAccess(tab.url,{current:true});await this.select(tab);return;}catch{this.selected=null;}}
  if(await this.fullAccess()){
   const list=await this.api.tabs.query({});
   for(const tab of [...list.filter(t=>t.active),...list.filter(t=>!t.active)]){try{this.url(tab.url);await this.select(tab);return;}catch{}}
  }
 }
 async tab(){
  if(!this.selected)return null;
  try{return await this.get(this.selected.id);}catch(e){if(!/No tab|closed|not found|Invalid tab/i.test(e.message))throw e;this.selected=null;await this.api.storage.session.remove('selectedTab');await this.onChange(null);return null;}
 }
 async list(){
  const tabs=[];
  for(const tab of await this.api.tabs.query({})){try{await this.requireAccess(tab.url,{current:tab.id===this.selected?.id});tabs.push({tab_id:String(tab.id),url:tab.url,title:tab.title||'',active:tab.id===this.selected?.id});}catch{}}
  return {tabs:tabs.slice(0,50),truncated:tabs.length>50};
 }
 async waitReady(id){
  const end=Date.now()+12000;let tab;
  do{tab=await this.get(id);if(tab.status!=='loading')return tab;await new Promise(r=>setTimeout(r,150));}while(Date.now()<end);
  return tab; // A slow page may still expose a useful DOM; don't repeat the navigation.
 }
 async open(value,newTab=false){
  const u=await this.requireAccess(value,{current:!newTab});let tab=await this.tab();
  if(newTab||!tab){tab=await this.api.tabs.create({url:u.href,active:true});this.created.add(tab.id);}
  else tab=await this.api.tabs.update(tab.id,{url:u.href,active:true});
  await this.select({...tab,url:u.href});tab=await this.waitReady(tab.id);
  await this.requireAccess(tab.url,{current:true});await this.select(tab);return {ok:true,tab_id:String(tab.id),url:tab.url};
 }
 async switchTo(id){
  if(!/^\d+$/.test(String(id)))throw Error('Выбери tab_id из browser_tabs.');
  const tab=await this.get(Number(id));await this.requireAccess(tab.url,{current:tab.id===this.selected?.id});
  await this.api.tabs.update(tab.id,{active:true});await this.select(tab);return {ok:true,tab_id:String(tab.id),url:tab.url};
 }
 async changed(id,change){
  if(this.selected?.id!==id||!change.url&&!change.title)return;
  const tab=await this.tab();if(!tab)return;
  // Keep the transport alive on redirects; actual page access is checked separately.
  try{await this.requireAccess(tab.url,{current:true});await this.select(tab);}catch{await this.onChange({...this.selected,url:tab.url||'',title:tab.title||''});}
 }
 async removed(id){if(this.selected?.id!==id)return;this.selected=null;await this.api.storage.session.remove('selectedTab');await this.onChange(null);}
}
globalThis.RantBrowser=RantBrowser;
