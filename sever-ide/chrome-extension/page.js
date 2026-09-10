(()=>{
 if(globalThis.__severPageVersion===9)return;
 globalThis.__severPageVersion=9;
 let entries=new Map(),serial=0,lastAction=null;
 const documentId=crypto.randomUUID().slice(0,8);
 function readableLabel(el){
  const ids=(el.getAttribute('aria-labelledby')||'').split(/\s+/);
  const explicit=el.getAttribute('aria-label')||ids.map(id=>document.getElementById(id)?.innerText||'').join(' ').trim()||[...(el.labels||[])].map(x=>x.innerText).join(' ')||el.getAttribute('placeholder')||el.innerText;
  if(explicit?.trim())return explicit.trim().slice(0,180);
  if(['INPUT','TEXTAREA','SELECT'].includes(el.tagName)){
   for(let node=el,depth=0;node&&depth<3;node=node.parentElement,depth++){const previous=node.previousElementSibling?.innerText?.trim();if(previous&&previous.length<220)return previous;}
  }
  return el.tagName;
 }
 function describe(el){
 const r=el.getBoundingClientRect(),s=getComputedStyle(el),type=el.type||'',label=readableLabel(el);
 const hints=[type,el.autocomplete,el.name,el.id,label].join(' ');
 const sensitive=/password|passwd|парол|secret|token|токен|one.?time|otp|verification|security.?code|cvc|cvv|cc-|card.?number|номер.?карт|код.?подтверж/i.test(hints);
 return {label,tag:el.tagName.toLowerCase(),type,href:el.getAttribute('href')||'',sensitive,value:!sensitive&&['input','textarea'].includes(el.tagName.toLowerCase())&&!/password|radio|checkbox|hidden|file|submit|button/.test(type)?el.value.slice(0,300):undefined,disabled:!!el.disabled,checked:['checkbox','radio'].includes(type)?el.checked:undefined,filled:['input','textarea'].includes(el.tagName.toLowerCase())&&!/password|radio|checkbox|hidden|file|submit|button/.test(type)?!!el.value:undefined,required:el.required||undefined,visible:el.isConnected&&r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight&&s.visibility!=='hidden'&&s.display!=='none',options:el.tagName==='SELECT'?[...el.options].slice(0,15).map(x=>({value:x.value,label:x.label})):undefined};
 }
 globalThis.__severPage=(action,args={})=>{try{
 if(args.deadline&&Date.now()>args.deadline)throw Error('Срок действия команды истёк до выполнения');
 if(location.protocol!=='https:')throw Error('Разрешены только HTTPS-страницы');
 if(action==='snapshot'){
 let found=[];
 if(args.find_text){
  const query=String(args.find_text).trim().toLocaleLowerCase();if(!query||query.length>200)throw Error('Текст поиска: от 1 до 200 символов');
  const nodes=[...document.querySelectorAll('a,button,h1,h2,h3,label,p,legend,input,textarea,[role=heading]')].filter(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&readableLabel(el).toLocaleLowerCase().includes(query);});
  const index=Number(args.match_index||0);if(!Number.isInteger(index)||index<0)throw Error('Некорректный номер совпадения');
  found=nodes.slice(0,20).map((el,i)=>({index:i,text:readableLabel(el)}));
  if(nodes[index])nodes[index].scrollIntoView({block:'center',behavior:'instant'});
 }
 entries.clear();const controls=[];
 const shown=x=>{const r=x.getBoundingClientRect(),s=getComputedStyle(x);return r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight&&s.visibility!=='hidden'&&s.display!=='none'&&!x.closest('[aria-hidden=true]');};
 // Query each priority separately: a combined selector follows document order,
 // which previously selected the tiny header search form before <main>.
 const dialog=[...document.querySelectorAll('[role=dialog],dialog[open]')].filter(shown).at(-1);
 const main=[...document.querySelectorAll('main,[role=main]')].find(shown);
 const scope=args.scope==='page'?document.body:dialog||main||document.body;
 const selector='a[href],button,input:not([type=hidden]),textarea,select,[role=button],[role=link],[contenteditable=true]';
 const candidates=[...scope.querySelectorAll(selector)];
 for(const el of [...new Set(candidates)]){
 const info=describe(el);if(!info.visible)continue;
 const id=documentId+'-'+String(++serial);entries.set(id,{el,signature:JSON.stringify(info),url:location.href});const container=el.closest('fieldset,article,li,[role=listitem],tr,section');
 let context=(container?.innerText||'').trim();
 if(!context||context.length>1600){
  context='';for(let parent=el.parentElement,depth=0;parent&&parent!==scope&&depth<6;parent=parent.parentElement,depth++){
   const text=parent.innerText?.trim()||'';if(text.length>info.label.length+20&&text.length<=1600)context=text;
  }
 }
 context=context.slice(0,400);
 controls.push({id,...info,context});if(controls.length>=30||JSON.stringify(controls).length>6500)break;
 }
 return {find_matches:args.find_text?found:undefined,ready_state:document.readyState,last_action:lastAction,url:location.href,title:document.title.slice(0,300),note:'Controls include nearby card text when available. IDs belong to this document and snapshot. A click alone does not prove submission.',text:(scope?.innerText||'').slice(0,2200),controls,untrusted_content:true};
 }
 if(action==='scroll'){if(!['up','down'].includes(args.direction))throw Error('Неверное направление');scrollBy(0,args.direction==='down'?650:-650);entries.clear();return {ok:true};}
 if(!['click','type','select'].includes(action))throw Error('Неизвестная команда');
 const entry=entries.get(args.element_id);if(!entry)throw Error('Обнови снимок страницы');
 const {el}=entry,info=describe(el);
 if(location.href!==entry.url||JSON.stringify(info)!==entry.signature)throw Error('Элемент изменился. Обнови снимок и подтверди действие заново.');
 if(info.sensitive||info.disabled||info.type==='file')throw Error('Для этого элемента нужен ручной ввод');
 if(args.operation_id&&lastAction?.id===args.operation_id)return lastAction.status==='done'?{ok:true}: {error:'Предыдущий результат неизвестен; действие не повторено'};
 if(action==='click'){
 if(args.expected_label&&args.expected_label.trim()!==info.label.trim())throw Error('Подпись элемента не совпадает с ожидаемой; обнови снимок');
 if(info.type==='radio'&&info.checked)return {ok:true,already_selected:true};
 if(el.closest('a[download]'))throw Error('Скачивание требует ручного действия');
 if(info.href&& !new URL(info.href,location.href).href.startsWith('https://'))throw Error('Ссылка требует ручного открытия');
 // Visible action marker, not a fake operating-system cursor.
 const ring=document.createElement('div'),rect=el.getBoundingClientRect();
 ring.setAttribute('aria-hidden','true');ring.style.cssText=`position:fixed;pointer-events:none;z-index:2147483647;border:3px solid #3978ff;border-radius:8px;left:${rect.left-3}px;top:${rect.top-3}px;width:${rect.width}px;height:${rect.height}px;box-sizing:content-box`;
 document.documentElement.appendChild(ring);setTimeout(()=>ring.remove(),650);
 lastAction={id:args.operation_id,status:'started',action};
 const anchor=el.closest('a[href]'),form=el.form||el.closest('form');
 const target=anchor?.getAttribute('target'),formTarget=form?.getAttribute('target'),submitTarget=el.getAttribute('formtarget');
 // Keep ordinary links and form submissions in the user's connected tab.
 if(anchor)anchor.setAttribute('target','_self');if(form)form.setAttribute('target','_self');if(submitTarget!==null)el.setAttribute('formtarget','_self');
 try{el.click();}finally{
  if(anchor){if(target===null)anchor.removeAttribute('target');else anchor.setAttribute('target',target);}
  if(form){if(formTarget===null)form.removeAttribute('target');else form.setAttribute('target',formTarget);}
  if(submitTarget!==null)el.setAttribute('formtarget',submitTarget);
 }
 lastAction={id:args.operation_id,status:'done',action};
 }else if(action==='type'){
 if(typeof args.text!=='string'||args.text.length>6000)throw Error('Лимит: 6000 символов');
 if(!['textarea','input'].includes(info.tag)||['hidden','file','submit','button','checkbox','radio'].includes(info.type))throw Error('Это не текстовое поле');
 const proto=info.tag==='input'?HTMLInputElement.prototype:HTMLTextAreaElement.prototype;
 lastAction={id:args.operation_id,status:'started',action};
 Object.getOwnPropertyDescriptor(proto,'value').set.call(el,args.text);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));lastAction={id:args.operation_id,status:'done',action};
 }else{
 if(info.tag!=='select'||!info.options.some(x=>x.value===args.value))throw Error('Нет такого варианта');lastAction={id:args.operation_id,status:'started',action};el.value=args.value;el.dispatchEvent(new Event('change',{bubbles:true}));
 lastAction={id:args.operation_id,status:'done',action};}entries.clear();return {ok:true};
 }catch(e){return {error:e.message};}};
})();
