'use client';
import {useEffect,useRef,useState} from 'react';
import {Paperclip,X,FileText,Loader2} from 'lucide-react';
export type Attachment={id:string;name:string;size:number;mime:string;warning?:string};
type Api=<T>(path:string,data?:unknown)=>Promise<T>;
export function AttachmentPicker({items,onChange,api,disabled,onError,onBusy}:{items:Attachment[];onChange:(a:Attachment[])=>void;api:Api;disabled:boolean;onError:(s:string)=>void;onBusy:(v:boolean)=>void}){
 const input=useRef<HTMLInputElement>(null);const [busy,setBusy]=useState(false);
 async function add(files:FileList|null){if(!files?.length)return;if(items.length+files.length>3){onError('До 3 вложений на сообщение');return}setBusy(true);onBusy(true);const next=[...items];try{for(const file of Array.from(files)){if(file.size>8*1024*1024)throw Error('Файл '+file.name+': максимум 8 МБ');const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('Не удалось прочитать файл'));reader.readAsDataURL(file)});next.push(await api<Attachment>('attachment-upload',{name:file.name,data}));onChange([...next])}}catch(e){onError(e instanceof Error?e.message:'Не удалось прикрепить файл')}finally{setBusy(false);onBusy(false);if(input.current)input.current.value=''}}
 return <><input ref={input} className="attachment-input" type="file" hidden tabIndex={-1} aria-hidden="true" multiple accept=".png,.jpg,.jpeg,.webp,.pdf,.txt,.md,.csv,.json,.html,.css,.js,.ts,.tsx,.jsx,.py,.php,.yaml,.yml,.xml,.sql,.log" onChange={e=>add(e.target.files)}/><button className="attach-button" type="button" aria-label="Прикрепить файлы" title="Картинки, PDF, текст и код · до 3 файлов по 8 МБ" disabled={disabled||busy||items.length>=3} onClick={()=>input.current?.click()}>{busy?<Loader2 size={18} className="spin"/>:<Paperclip size={18}/>}</button></>
}
export function AttachmentCards({items,token,onRemove}:{items:Attachment[];token:string;onRemove?:(id:string)=>void}){
 return <div className="attachment-cards">{items.map(item=><AttachmentCard key={item.id} item={item} token={token} onRemove={onRemove}/>)}</div>
}
function AttachmentCard({item,token,onRemove}:{item:Attachment;token:string;onRemove?:(id:string)=>void}){
 const [url,setUrl]=useState(''),[error,setError]=useState('');
 useEffect(()=>{if(!item.mime.startsWith('image/'))return;let disposed=false,objectUrl='';const abort=new AbortController();fetch('/bridge/attachment?id='+item.id,{headers:{'X-Sever-Token':token},signal:abort.signal}).then(r=>{if(!r.ok)throw Error('Предпросмотр недоступен');return r.blob()}).then(blob=>{if(!disposed){objectUrl=URL.createObjectURL(blob);setUrl(objectUrl)}}).catch(e=>{if(!disposed)setError(e.message)});return()=>{disposed=true;abort.abort();if(objectUrl)URL.revokeObjectURL(objectUrl)}},[item.id,item.mime,token]);
 async function download(){try{const response=await fetch('/bridge/attachment?id='+item.id,{headers:{'X-Sever-Token':token}});if(!response.ok)throw Error('Файл недоступен');const u=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=u;a.download=item.name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}catch(e){setError(e instanceof Error?e.message:'Ошибка')}}
 return <div className="attachment-card">{url?<img src={url} alt={item.name}/>:<FileText size={22}/>}<button onClick={download} type="button" title={item.warning||item.name}><b>{item.name}</b><small>{Math.max(1,Math.round(item.size/1024))} КБ{item.warning?' · '+item.warning:''}{error?' · '+error:''}</small></button>{onRemove&&<button type="button" className="remove-attachment" aria-label={'Убрать '+item.name} onClick={()=>onRemove(item.id)}><X size={14}/></button>}</div>
}
