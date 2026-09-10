'use client';
import { useEffect, type ReactNode } from 'react';
import { getLanguage, setLanguage, useLanguage } from '@/lib/i18n';
export default function LanguageProvider({children}:{children:ReactNode}) {
 useLanguage();
 useEffect(()=>{
  let saved: 'en'|'ru'='en';try{saved=localStorage.getItem('rant-language')==='ru'?'ru':'en'}catch{}
  setLanguage(saved);
  const sync=(event:StorageEvent)=>{if(event.key==='rant-language')setLanguage(event.newValue==='ru'?'ru':'en')};
  window.addEventListener('storage',sync);return()=>window.removeEventListener('storage',sync);
 },[]);
 return children;
}
export function LanguageSwitch() {
 const language=useLanguage();
 return <select className="language-switch" aria-label={language==='en'?'Interface language':'Язык интерфейса'} value={language} onChange={e=>setLanguage(e.target.value==='ru'?'ru':'en')}><option value="en">EN</option><option value="ru">RU</option></select>;
}
