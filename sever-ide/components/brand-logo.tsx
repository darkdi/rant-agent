export function BrandLogo() {
  return <span className="brand-wordmark" role="img" aria-label="Rant Agent">
    <img className="brand-on-dark" src="/brand/rant-agent-dark-transparent.svg" alt="" />
    <img className="brand-on-light" src="/brand/rant-agent-white-transparent.svg" alt="" />
  </span>;
}

export function BrandMark({ className = '' }: { className?: string }) {
  return <img className={'brand-mark ' + className} src="/favicon.svg" alt="" aria-hidden="true" />;
}
