'use client';
import { t, useLanguage } from '@/lib/i18n';
import {useEffect,useState} from 'react';
import {Button} from '@/components/ui/button';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from '@/components/ui/dialog';
type Memory={documents:Record<string,string>;folder:string;note:string};
type Props={open:boolean;onClose:()=>void;api:<T>(path:string,data?:unknown)=>Promise<T>;disabled:boolean};
const sections=[['user','USER.md · Обо мне'],['project','PROJECT.md · Проект'],['notes','NOTES.md · Правила']];
export default function AgentMemory({open,onClose,api,disabled}:Props){
 useLanguage();
 const [memory,setMemory]=useState<Memory|null>(null),[key,setKey]=useState('user'),[draft,setDraft]=useState(''),[error,setError]=useState(''),[saving,setSaving]=useState(false),[notice,setNotice]=useState('');
 useEffect(()=>{if(open){setError('');setNotice('');api<Memory>('memory').then(m=>{setMemory(m);setKey('user');setDraft(m.documents.user)}).catch(e=>setError(e.message))}},[open,api]);
 const dirty=!!memory&&draft!==memory.documents[key];
 function select(next:string){if(dirty){setError(t("Сохрани изменения или нажми «Отменить правки»."));return}setKey(next);setDraft(memory?.documents[next]||'');setError('');setNotice('')}
 function close(){if(dirty){setError(t("Сохрани изменения или нажми «Отменить правки»."));return}onClose()}
 async function save(){if(!memory)return;setSaving(true);setError('');try{const m=await api<Memory>('memory',{key,content:draft,previous:memory.documents[key]});setMemory(m);setNotice(t("Сохранено. Агент получит этот файл в следующем сообщении."))}catch(e){setError(e instanceof Error?e.message:t("Не удалось сохранить"))}finally{setSaving(false)}}
 return <Dialog open={open} onOpenChange={v=>{if(!v)close()}}><DialogContent className="settings-dialog memory-dialog"><DialogHeader><DialogTitle>{t("Файлы контекста проекта")}</DialogTitle><DialogDescription>{t("Эти Markdown-файлы создаются в папке проекта и автоматически читаются перед каждой задачей. Правила общие для всех чатов проекта.")}</DialogDescription></DialogHeader><div className="memory-sections">{sections.map(([id,label])=><Button key={id} variant={key===id?'default':'outline'} onClick={()=>select(id)}>{t(label)}</Button>)}</div><label htmlFor="agent-memory-content">{t(sections.find(x=>x[0]===key)?.[1]||'')}</label><textarea id="agent-memory-content" className="memory-editor" value={draft} maxLength={8000} disabled={!memory||saving} onChange={e=>{setDraft(e.target.value);setNotice('')}} placeholder={t("Например: общайся со мной по-русски; работай в одной вкладке; цель проекта… Не добавляй пароли и API-ключи.")}/><small>{draft.length}{t(" / 8000 · Длинные файлы могут передаваться частично; агент может сам прочитать полный раздел инструментом.")}</small>{memory&&<p className="memory-path">{t("Файлы: ")}{memory.folder}<br/>{t("CHAT.md — полный архив текущего разговора, обновляется автоматически.")}</p>}{error&&<p role="alert" className="message error">{t(error)}</p>}{notice&&<p role="status" className="message notice">{t(notice)}</p>}<div className="memory-actions"><Button variant="outline" onClick={()=>{setDraft(memory?.documents[key]||'');setError('')}} disabled={!dirty||saving}>{t("Отменить правки")}</Button><Button onClick={save} disabled={!dirty||saving||disabled}>{t("Сохранить файл")}</Button></div></DialogContent></Dialog>
}
