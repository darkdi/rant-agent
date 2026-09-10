# Roadmap

Rant should help a person complete a small, useful task with their own model and understand what happened. This is a direction, not a delivery promise.

## Current alpha

Local chats/projects, user-owned API connections, Ollama/LM Studio presets, optional Qwen/MLX, bounded file editing and diffs, Chrome bridge, media adapters and setup documentation. UI is Russian. Review limitations in README before relying on a workflow.

## Next: first successful task

- A guided connection check that separates server, model, chat, tool and vision capabilities.
- A small set of reproducible examples: summarize a PDF, improve a text, edit a static page, compare public pages, produce a media asset.
- On-screen context/memory usage and explicit recovery after model/bridge failures.
- Smaller modules and broader regression tests before expanding the agent's powers.
- English interface and keyboard/accessibility checks.

## Next: dependable local work

- Reconnection diagnostics and extension installation guidance for multiple local copies.
- Media profile editing, resume/check-existing-job actions, recoverable gallery cleanup and workflow templates.
- Explicit model capability discovery and ComfyUI workflow validation.
- Portable installers after validating macOS/Linux; evaluate Windows as a separate effort.
- Better context retrieval with evidence that summaries preserve important details.

## Evaluate later

More local runtimes, additional provider adapters, richer project editing and a sandboxed execution environment. Any shell, SSH, team access or deployment feature needs its own permission and isolation design.

## How to help decide

Report a real task, the model/hardware used, what you expected, what happened and where you got stuck. A clean reproduction is more useful than a long wishlist. Do not include private data or credentials.
