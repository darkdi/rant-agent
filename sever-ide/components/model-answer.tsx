'use client';
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
  const [copied, setCopied] = useState(false);
  const code = Children.toArray(children).find((x) => isValidElement(x));
  const language = isValidElement<{ className?: string }>(code)
    ? code.props.className?.replace('language-', '') || 'Код'
    : 'Код';
  return (
    <div className="answer-code">
      <div className="code-block-header">
        <span>{language}</span>
        <button
          aria-label="Скопировать код"
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
          {copied ? 'Скопировано' : 'Копировать'}
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}
export default function ModelAnswer({ text }: { text: string }) {
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
            <span>{alt ? '[Изображение: ' + alt + ']' : '[Изображение]'}</span>
          ),
        }}
      >
        {text}
      </Markdown>
    </div>
  );
}
