'use client';
import { t, useLanguage } from '@/lib/i18n';
import {useEffect,useState} from 'react';
import {Monitor,Download,Link2,Trash2,Copy} from 'lucide-react';
type Device={id:string;name:string;armed:boolean;online:boolean};
type Api=<T>(path:string,data?:unknown)=>Promise<T>;
export default function DevicesPanel({api}:{api:Api}){
 useLanguage();
 const [devices,setDevices]=useState<Device[]>([]),[pair,setPair]=useState<{code:string;expires:number}|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){try{setDevices(await api<Device[]>('devices'))}catch(e){setError((e as Error).message)}}
 useEffect(()=>{void load();const t=setInterval(()=>void load(),5000);return()=>clearInterval(t)},[]);
 async function create(){setBusy(true);setError('');try{setPair(await api('device-pair',{}))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function revoke(id:string){setBusy(true);try{await api('device-revoke',{id});await load()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 return <section className="device-panel"><header><h3><Monitor size={18}/>{t("Твои компьютеры ")}<small>{t("Эксперимент")}</small></h3><a href="/downloads/rant-connect.zip"><Download size={16}/>{t("Скачать Rant Connect")}</a></header><p>{t("Установи Python 3.12+, распакуй Rant Connect и запусти Start.bat на Windows или Start.command на Mac. Вставь код, затем включи управление в окне программы.")}</p><button disabled={busy} onClick={()=>void create()}><Link2 size={16}/>{t("Создать код подключения")}</button>{pair&&<div className="device-code"><code>{pair.code}</code><button aria-label={t("Скопировать код")} onClick={()=>void navigator.clipboard.writeText(pair.code)}><Copy size={16}/></button><small>{t("Действует до ")}{new Date(pair.expires*1000).toLocaleTimeString(document.documentElement.lang==='ru'?'ru-RU':'en-US',{hour:'2-digit',minute:'2-digit'})}{t(". Не передавай код посторонним.")}</small></div>}<div>{devices.map(d=><div className="device-row" key={d.id}><Monitor size={18}/><span><b>{d.name}</b><small>{!d.online?t("Не в сети"):d.armed?t("Управление включено"):t("В сети · управление выключено")}</small></span><button disabled={busy} aria-label={t("Отозвать доступ ")+d.name} onClick={()=>void revoke(d.id)}><Trash2 size={17}/></button></div>)}</div><p>{t("Поручи действие в обычном чате, например: «На моём компьютере открой браузер». Работает с основным монитором. Для остановки нажми кнопку в Rant Connect или «Стоп» в чате. Экстренный стоп — мышь в верхний левый угол.")}</p>{error&&<p role="alert" className="cloud-error">{t(error)}</p>}</section>
}
