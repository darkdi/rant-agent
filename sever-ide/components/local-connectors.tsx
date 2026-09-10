'use client';
import { useEffect, useState } from 'react';
import { Monitor, Globe, Download, RefreshCw, Copy, Trash2 } from 'lucide-react';
type Api = <T>(path: string, data?: unknown) => Promise<T>;
type Device = { id: string; name: string; online: boolean; armed: boolean };
type Browser = { running?: boolean; connected?: boolean; extension_path?: string; reason?: string };
export default function LocalConnectors({ api, token }: { api: Api; token: string }) {
 const [devices,setDevices]=useState<Device[]>([]),[browser,setBrowser]=useState<Browser>({});
 const [pair,setPair]=useState<{code:string;expires:number}|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 useEffect(()=>{let alive=true;async function refresh(){try{const [d,b]=await Promise.all([api<Device[]>('devices'),api<Browser>('browser-status')]);if(alive){setDevices(d);setBrowser(b)}}catch(e){if(alive)setError((e as Error).message)}}void refresh();const timer=setInterval(()=>void refresh(),3000);return()=>{alive=false;clearInterval(timer)}},[api]);
 async function safe(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function download(kind:'desktop'|'browser'){
  const response=await fetch('/bridge/connector-download?kind='+kind,{headers:{'X-Sever-Token':token}});
  if(!response.ok){const body=await response.json();throw Error(body.error||'Не удалось скачать подключение')}
  const url=URL.createObjectURL(await response.blob()),link=document.createElement('a');link.href=url;link.download=kind==='desktop'?'rant-connect-local.zip':'rant-browser-local.zip';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  setNotice(kind==='browser'?'Архив расширения подготовлен для этой установки. Распакуй в постоянную папку и загрузи в Chrome.':'Rant Connect подготовлен с адресом этого приложения. Распакуй и запусти Start.command.');
 }
 return <div className="local-connectors">
  <section className="device-panel"><header><h3><Globe size={18}/>Твой Chrome</h3><b>{browser.connected?'Подключён':browser.running?'Ожидает расширение':'Подключение не запущено'}</b></header>
   <p>Чтение страниц, поиск, переходы и заполнение форм через твою установленную копию Chrome.</p>
   <button disabled={busy} onClick={()=>void safe(()=>download('browser'))}><Download size={16}/>Скачать расширение для этой установки</button>
   <p>Распакуй архив в постоянную папку. Открой chrome://extensions → «Режим разработчика» → «Загрузить распакованное». Выбери эту папку, затем открой значок Rant Agent Local и разреши Chrome. В настройках Rant включи «Браузерный агент».</p>
   <button disabled={busy} onClick={()=>void safe(async()=>{setBrowser(await api<Browser>('browser-reconnect',{}))})}><RefreshCw size={16}/>Проверить подключение</button>
   <p>Архив содержит персональное подключение. Не публикуй его. Для ai.rant.ae используй отдельное облачное расширение.</p>
  </section>
  <section className="device-panel"><header><h3><Monitor size={18}/>Rant Connect Local <small>Эксперимент</small></h3></header>
   <p>Управление экраном, мышью и клавиатурой этого компьютера. Требуется Python 3.12+ с Tk и модель с поддержкой изображений и вызовов инструментов. Встроенная Qwen через MLX пока не управляет экраном.</p>
   <button disabled={busy} onClick={()=>void safe(()=>download('desktop'))}><Download size={16}/>Скачать Rant Connect Local</button>
   <p>Распакуй архив и запусти Start.command на Mac или Linux. Затем создай код здесь, вставь его в Rant Connect Local и нажми «Включить управление». Приложение Rant должно оставаться запущенным.</p>
   <button disabled={busy} onClick={()=>void safe(async()=>setPair(await api('device-pair',{})))}>Создать код подключения</button>
   {pair&&<div className="device-code"><code>{pair.code}</code><button aria-label="Скопировать код" onClick={()=>void safe(async()=>navigator.clipboard.writeText(pair.code))}><Copy size={16}/></button><small>До {new Date(pair.expires*1000).toLocaleTimeString('ru-RU')}. Код одноразовый, не передавай его посторонним.</small></div>}
   {devices.map(d=><div className="device-row" key={d.id}><Monitor size={18}/><span><b>{d.name}</b><small>{!d.online?'Не в сети':d.armed?'Управление включено':'В сети · управление выключено'}</small></span><button disabled={busy} aria-label={'Отключить '+d.name} onClick={()=>void safe(async()=>{await api('device-revoke',{id:d.id});setDevices(await api<Device[]>('devices'))})}><Trash2 size={16}/></button></div>)}
   <p>Управление включается вручную при каждом запуске. Остановка — в окне Connect или кнопкой «Стоп» в чате; экстренная остановка — мышь в верхний левый угол. Снимки получает выбранная модель. Для Mac нужны «Запись экрана» и «Универсальный доступ».</p>
   <a href="/help.html#connectors" target="_blank" rel="noreferrer">Подробная установка и проверка →</a>
  </section>
  {notice&&<p role="status" className="integration-help">{notice}</p>}{error&&<p role="alert" className="cloud-error">{error}</p>}
 </div>;
}
