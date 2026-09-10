'use client';
import { t, useLanguage } from '@/lib/i18n';
import { useState, isValidElement, Children, type ReactNode } from 'react';
import { Copy, Check } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
function plain(node: ReactNode): string {
  return Children.toArray(node)
    .map((x) =>
      isValidElement<{ children?: ReactNode }>(x)
        ? plain(x.props.children)
        : typeof x === 'string' || typeof x === 'number'
          ? String(x)
          : '',
    )
    .join('');
}
function CodeBlock({ children }: { children?: ReactNode }) {
 useLanguage();
  const [copied, setCopied] = useState(false);
  const code = Children.toArray(children).find((x) => isValidElement(x));
  const language = isValidElement<{ className?: string }>(code)
    ? code.props.className?.replace('language-', '') || t("Код")
    : t("Код");
  return (
    <div className="answer-code">
      <div className="code-block-header">
        <span>{language}</span>
        <button
          aria-label={t("Скопировать код")}
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(
                plain(children).replace(/\n$/, ''),
              );
              setCopied(true);
              setTimeout(() => setCopied(false), 1800);
            } catch {
              setCopied(false);
            }
          }}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}{' '}
          {copied ? t("Скопировано") : t("Копировать")}
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}
export default function ModelAnswer({ text }: { text: string }) {
 useLanguage();
  return (
    <div className="model-answer markdown-answer">
      <Markdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          pre: CodeBlock,
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
          img: ({ alt }) => (
            <span>{alt ? t("[Изображение: ") + alt + ']' : t("[Изображение]")}</span>
          ),
        }}
      >
        {text}
      </Markdown>
    </div>
  );
}
