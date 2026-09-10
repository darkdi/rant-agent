'use client';
import { useSyncExternalStore } from 'react';
import translations from './translations.json';
export type Language = 'en' | 'ru';
let language: Language = 'en';
const listeners = new Set<() => void>();
const catalog: Record<string, string> = translations;
const reverse = Object.fromEntries(Object.entries(catalog).map(([ru,en])=>[en,ru]));
export function setLanguage(next: Language) {
 language=next;
 if(typeof document!=='undefined') { document.documentElement.lang=next; document.title=next==='en'?'Rant Agent — your assistant':'Rant Agent — твой ассистент'; }
 try { localStorage.setItem('rant-language',next); } catch {}
 listeners.forEach(fn=>fn());
}
export function getLanguage(): Language { return language; }
export function useLanguage() {
 return useSyncExternalStore(fn=>{listeners.add(fn);return()=>{listeners.delete(fn)}},()=>language,()=> 'en' as Language);
}
/** Translate interface copy only. Never call this on conversation or file content. */
export function t(value: string): string {
 const key=value.replace(/\s+/g,' ').trim();
 const result=language==='en'?catalog[key]:reverse[key];
 if(!result)return value;
 const start=value.match(/^\s*/)?.[0]||'',end=value.match(/\s*$/)?.[0]||'';
 return start+result+end;
}
