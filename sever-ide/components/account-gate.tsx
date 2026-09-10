'use client';
import { createContext, useContext, useEffect, useState, type ReactNode, type FormEvent } from 'react';
import { ArrowLeft, ArrowUpRight, Check, ChevronDown, Eye, EyeOff, Loader2, LogOut, Mail, Moon, Sun } from 'lucide-react';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from '@/components/ui/dropdown-menu';

type User = { id: string; name: string; email: string };
type Account = { cloud: boolean; user: User | null; logout: () => Promise<void> };
const AccountContext = createContext<Account>({ cloud: false, user: null, logout: async () => {} });
export const useAccount = () => useContext(AccountContext);

export function useRantTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');
  useEffect(() => {
    const update = () => setTheme(document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');
    update(); window.addEventListener('rant-theme-change', update);
    return () => window.removeEventListener('rant-theme-change', update);
  }, []);
  return theme;
}

export function ThemeSwitch() {
  const [theme, setTheme] = useState('dark');
  useEffect(() => {
    function read() {
      let saved = 'dark';
      try { saved = localStorage.getItem('rant-theme') === 'light' ? 'light' : 'dark'; } catch {}
      document.documentElement.dataset.theme = saved;
      setTheme(saved);
    }
    read(); window.addEventListener('rant-theme-change', read);
    return () => window.removeEventListener('rant-theme-change', read);
  }, []);
  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('rant-theme', next); } catch {}
    document.documentElement.dataset.theme = next; setTheme(next);
    window.dispatchEvent(new Event('rant-theme-change'));
  }
  return <button type="button" className="theme-toggle" aria-label={theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'} title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'} onClick={toggle}>{theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>;
}

export function RantCharacter({ small = false }: { small?: boolean }) {
  return <span className={'rant-character' + (small ? ' small' : '')} aria-hidden="true"><span className="character-face"><i /><i /></span><span className="character-smile" /></span>;
}

export function AccountMenu() {
  const { user, logout } = useAccount();
  if (!user) return null;
  return <DropdownMenu><DropdownMenuTrigger className="account-button" aria-label="Мой аккаунт"><span className="account-avatar">{(user.name || user.email).slice(0, 1).toUpperCase()}</span><span><b>{user.name || 'Мой аккаунт'}</b><small>{user.email}</small></span><ChevronDown size={15} /></DropdownMenuTrigger><DropdownMenuContent side="top" align="start"><div className="account-menu-info">{user.email}</div><DropdownMenuItem onClick={() => void logout()}><LogOut size={16} /> Выйти из аккаунта</DropdownMenuItem></DropdownMenuContent></DropdownMenu>;
}

export default function AccountGate({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<{ cloud: boolean; user: User | null } | null>(null);
  const [view, setView] = useState('login');
  const [token, setToken] = useState('');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [repeat, setRepeat] = useState('');
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sent, setSent] = useState(false);
  const [retryAt, setRetryAt] = useState(0);
  const [seconds, setSeconds] = useState(0);
  async function refresh() {
    try {
      const response = await fetch('/auth/session', { cache: 'no-store' });
      if (!response.ok) throw Error('Не удалось связаться с сервером. Попробуй ещё раз.');
      setAccount(await response.json());
      setError('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Нет соединения с сервером.'); }
  }
  useEffect(() => {
    const params = new URLSearchParams(location.hash.slice(1));
    if (['verify', 'reset'].includes(params.get('auth') || '') && params.get('token')) {
      setView(params.get('auth')!); setToken(params.get('token')!);
      history.replaceState(null, '', location.pathname + location.search);
    }
    void refresh();
    const expired = () => { setAccount({ cloud: true, user: null }); setNotice('Войди снова, чтобы продолжить. Твои чаты сохранены.'); };
    window.addEventListener('rant-session-expired', expired);
    return () => window.removeEventListener('rant-session-expired', expired);
  }, []);
  useEffect(() => {
    const update = () => setSeconds(Math.max(0, Math.ceil((retryAt - Date.now()) / 1000)));
    update(); const timer = setInterval(update, 1000); return () => clearInterval(timer);
  }, [retryAt]);
  function change(next: string) { setView(next); setError(''); setNotice(''); setSent(false); setPassword(''); setRepeat(''); }
  async function request(path: string, data: unknown) {
    const response = await fetch('/auth/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    const result = await response.json() as { error?: string; user: User; message: string };
    if (!response.ok) throw Error(result.error || 'Не удалось выполнить действие.');
    return result;
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      if (view === 'login') {
        const result = await request('login', { email, password });
        setAccount({ cloud: true, user: result.user }); setPassword('');
      } else if (view === 'verify' || view === 'reset') {
        if (password !== repeat) throw Error('Пароли не совпадают.');
        const result = await request(view, { token, name, password });
        change('login'); setToken(''); setNotice(result.message);
      } else {
        await request(view === 'register' ? 'register' : 'forgot', { email });
        setSent(true); setRetryAt(Date.now() + 60000);
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось выполнить действие.'); }
    finally { setBusy(false); }
  }
  async function logout() {
    try {
      await request('logout', {});
      for (const key of Object.keys(localStorage)) if (key.startsWith('rant-draft:')) localStorage.removeItem(key);
      setAccount({ cloud: true, user: null }); change('login');
    } catch (e) { setError(e instanceof Error ? e.message : 'Не удалось выйти.'); }
  }
  if (account && (!account.cloud || account.user) && !token) return <AccountContext.Provider value={{ ...account, logout }}>{children}</AccountContext.Provider>;
  if (!account) return <main className="account-loading"><RantCharacter /><p>{error || 'Открываем Rant…'}</p>{error ? <button onClick={() => void refresh()}>Попробовать снова</button> : <Loader2 size={20} className="spin" />}</main>;
  const settingPassword = view === 'verify' || view === 'reset';
  const title = sent ? 'Проверь свою почту' : ({ login: 'С возвращением', register: 'Давай знакомиться', forgot: 'Забыл пароль?', verify: 'Остался один шаг', reset: 'Новый пароль' }[view]);
  const subtitle = sent ? `Если адрес ${email} подходит для этого действия, на него придёт письмо со ссылкой. Проверь также папку «Спам».` : ({ login: 'Твои разговоры, идеи и задачи уже ждут.', register: 'Создай аккаунт. Начнём с твоей почты.', forgot: 'Пришлём ссылку, чтобы задать новый пароль.', verify: 'Как тебя зовут? Придумай пароль для входа.', reset: 'Выбери длинный пароль, который легко запомнить.' }[view]);
  return <main className="auth-page">
    <div className="auth-theme"><ThemeSwitch /></div>
    <a className="auth-brand" href="/" aria-label="Rant Agent, главная"><span className="rant-symbol">r</span> Rant <span>Agent</span></a>
    <div className="auth-stage">
      <section className="auth-story"><div className="auth-orbit"><RantCharacter /><span className="orbit-star star-one">✦</span><span className="orbit-star star-two">✧</span></div><div className="auth-eyebrow"><span /> Твой AI, в твоём ритме</div><h1>Большие идеи.<br /><span>Один разговор.</span></h1><p>Задавай вопросы, создавай новое<br />и возвращайся к важному.</p><div className="auth-story-note"><span className="mini-message">Есть идея…</span><span className="mini-answer"><Check size={14} /> Давай сделаем.</span></div></section>
      <section className="auth-card" aria-labelledby="auth-title">
        {view !== 'login' && <button type="button" className="auth-back" onClick={() => { setToken(''); change('login'); }}><ArrowLeft size={17} /> Ко входу</button>}
        <div className="auth-card-icon">{sent ? <Mail size={26} /> : <RantCharacter small />}</div>
        <h2 id="auth-title">{title}</h2><p className="auth-subtitle">{subtitle}</p>
        <form onSubmit={submit}>
          {!sent && <>
            {!settingPassword && <label>Почта<input autoComplete="email" name="email" type="email" placeholder="you@example.com" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)} /></label>}
            {view === 'verify' && <label>Как тебя называть<input autoComplete="name" name="name" placeholder="Твоё имя" maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label>}
            {(view === 'login' || settingPassword) && <label>Пароль<div className="password-field"><input autoComplete={view === 'login' ? 'current-password' : 'new-password'} name="password" type={visible ? 'text' : 'password'} minLength={settingPassword ? 8 : undefined} maxLength={256} required placeholder={settingPassword ? 'От 8 символов' : 'Твой пароль'} value={password} onChange={e => setPassword(e.target.value)} /><button type="button" aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label>}
            {settingPassword && <label>Повтори пароль<input autoComplete="new-password" name="repeat" type={visible ? 'text' : 'password'} required value={repeat} onChange={e => setRepeat(e.target.value)} /></label>}
            {view === 'login' && <button type="button" className="forgot-link" onClick={() => change('forgot')}>Не помню пароль</button>}
          </>}
          {error && <p className="auth-error" role="alert">{error}</p>}
          {notice && <p className="auth-notice" role="status">{notice}</p>}
          <button className="auth-submit" type="submit" disabled={busy || (sent && seconds > 0)}>{busy ? <><Loader2 size={18} className="spin" /> Секунду…</> : sent ? seconds > 0 ? `Отправить ещё раз через ${seconds} с` : 'Отправить письмо ещё раз' : <>{view === 'login' ? 'Войти' : settingPassword ? 'Сохранить пароль' : 'Продолжить с почтой'}<ArrowUpRight size={19} /></>}</button>
        </form>
        {view === 'login' && <p className="auth-switch">Первый раз здесь? <button onClick={() => change('register')}>Создать аккаунт</button></p>}
        {view === 'register' && !sent && <p className="auth-switch">Уже есть аккаунт? <button onClick={() => change('login')}>Войти</button></p>}
      </section>
    </div>
    <footer className="auth-footer"><a href="/help.html">Как пользоваться</a><a href="mailto:support@rant.ae">Нужна помощь?</a></footer>
  </main>;
}
