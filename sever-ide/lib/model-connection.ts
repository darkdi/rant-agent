export function isLocalEndpoint(baseUrl?: string): boolean {
  try {
    const url = new URL(baseUrl || '');
    return ['http:', 'https:'].includes(url.protocol) &&
      ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  } catch {
    return false;
  }
}

export function needsApiKey(profile?: { kind: string; base_url?: string; has_key?: boolean }): boolean {
  return !profile || (profile.kind !== 'local' && !profile.has_key && !isLocalEndpoint(profile.base_url));
}
