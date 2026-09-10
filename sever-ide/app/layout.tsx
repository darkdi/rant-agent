import type { Metadata } from 'next';
import './globals.css';
import LanguageProvider from '@/components/language-provider';
import AccountGate from '@/components/account-gate';
export const metadata: Metadata = {
  title: 'Rant Agent — your assistant',
  icons: { icon: [{ url: '/favicon.svg', type: 'image/svg+xml' }, { url: '/favicon.ico', sizes: 'any' }], apple: '/apple-touch-icon.png' },
  description:
    'Chat, work with files, and delegate tasks to your AI assistant.',
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: "try{document.documentElement.dataset.theme=localStorage.getItem('rant-theme')==='light'?'light':'dark'}catch(e){}" }} /></head>
      <body><LanguageProvider><AccountGate>{children}</AccountGate></LanguageProvider></body>
    </html>
  );
}
