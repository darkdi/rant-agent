# Security and privacy

Rant Agent is an experimental, single-user local application. Bind it only to loopback. Do not put it behind a public reverse proxy or use it as a multi-user server.

## Data boundaries

- API keys, bridge tokens, chats, media and internal notes are under `.local`; the local model path is in `local-assistant/model-9b.json`. They are ignored by Git.
- Keys use restrictive filesystem permissions, but are not encrypted and are accessible to your OS account. Protect local backups.
- An API model receives the task, relevant conversation/context and attachments/tool results enabled for that task. Remote MCP tools can send data to their own service. Local ComfyUI graphs may contain external API nodes.
- Browser permission lets the agent read and act in enabled Chrome pages. Enter passwords, payment details and one-time codes manually. Revoke access in Rant/Chrome when no longer needed.
- Web content and model output are untrusted. The file worker restricts paths, symlinks, file types and sizes and journals edits. It is not a general secure code-execution sandbox.
- Previewed project JavaScript runs in a browser on a separate local origin. Only preview projects you trust.
- Media creation POSTs are not automatically retried. An uncertain job can still have been accepted and billed upstream. Check the provider before resubmitting.

## Reporting

Do not post secrets, exploit payloads against someone else's installation or private histories in public issues. Use the repository's private vulnerability reporting feature when enabled: https://github.com/darkdi/rant-agent/security/advisories/new. If unavailable, open an issue asking for a private channel without vulnerability details.

## Before sharing a fork or release

Run `python3 scripts/check_release.py`. Review the staged file list and keep `.local`, project folders, credentials, extension `config.js`, environment files and model weights out of source control. The checker is a guardrail, not a comprehensive secret scanner or security audit. Review dependencies and the threat model before production use.
