import type { Metadata } from 'next';
import './globals.css';
import AccountGate from '@/components/account-gate';
export const metadata: Metadata = {
  title: 'Rant Agent — твой ассистент',
  icons: { icon: [{ url: '/favicon.svg', type: 'image/svg+xml' }, { url: '/favicon.ico', sizes: 'any' }], apple: '/apple-touch-icon.png' },
  description:
    'Общайся, работай с материалами и поручай задачи своему AI-ассистенту.',
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: "try{document.documentElement.dataset.theme=localStorage.getItem('rant-theme')==='light'?'light':'dark'}catch(e){}" }} /></head>
      <body><AccountGate>{children}</AccountGate></body>
    </html>
  );
}
