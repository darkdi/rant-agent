# Installation (English)

Rant Agent is a single-user local application. Its UI is currently Russian. Start with one model route; neither Ollama nor MLX is mandatory.

## Prerequisites

- macOS or Linux; Python 3.12+ with `venv`, Node.js 22.13+ with npm, Git.
- A browser for the UI; Chrome 120+ only if you want the browser agent.
- Internet for first-time package/model downloads. No automatic weight downloads.
- API mode does not require a GPU. Local model memory requirements depend on weights and context. Native Windows and WSL are not validated in this alpha.

Install prerequisites from [Python](https://www.python.org/downloads/), [Node.js](https://nodejs.org/en/download), and [Git](https://git-scm.com/downloads). Linux users may need the distribution's `python3-venv` package.

```bash
git clone https://github.com/darkdi/rant-agent.git
cd rant-agent
./start.sh
```

Open http://127.0.0.1:4311. Keep the terminal running. Ctrl+C stops the app. The launcher caches dependency/build fingerprints and rebuilds when source changes.

Other options:

```bash
./start.sh --check
./start.sh --no-open --no-browser
./start.sh --port 4321 --preview-port 4322
./start.sh --rebuild
```

## Model routes

Click the model name, then **Добавить модель** (Add model).

- **Ollama:** install and open [Ollama](https://ollama.com/download), run `ollama pull qwen3:4b`. Choose the Ollama preset (`http://127.0.0.1:11434/v1`), fetch the model list, select the downloaded model, save. Normal local Ollama does not need a key. [Official compatibility reference](https://docs.ollama.com/api/openai-compatibility).
- **LM Studio:** download/load a model, start its Developer server. Choose LM Studio (`http://127.0.0.1:1234/v1`), fetch models and save. Add a key only if server authentication is enabled. [Official server setup](https://lmstudio.ai/docs/developer/core/server).
- **API:** select a provider or **Другой сервис**, provide the base URL, your key and exact model ID. Use the API format the provider supports. Save-and-test performs a real, potentially billable request. Save alone only stores configuration.

For built-in **Qwen3.5-9B-4bit on Apple Silicon**, after the first base installation:

```bash
.venv/bin/pip install -r requirements-mlx.txt
.venv/bin/python scripts/setup_model.py --download
./start.sh
```

The explicit download uses `~/Models/Qwen3.5-9B-4bit`. To reuse existing MLX weights instead:

```bash
.venv/bin/python scripts/setup_model.py --path "$HOME/Models/Qwen3.5-9B-4bit"
```

Use `--replace` to change an existing registration. The built-in runtime does not accept GGUF. The first chat loads the weights; following requests reuse them. **Выгрузить Qwen из памяти** unloads the model. Weight/model licenses are separate from Rant's MIT license.

## Browser extension

Start Rant first. In Chrome, open `chrome://extensions`, enable Developer mode and load unpacked `sever-ide/chrome-extension` from **this checkout**. Open **Rant Agent Local — браузер**, approve the requested Chrome permissions, then enable the browser inside Rant's **Настройки и возможности → Доступы** and save. Switch the composer to browser mode.

Pairing tokens and ports are generated per installation. After updating, reload that extension in Chrome. Do not overwrite or disable extensions belonging to another installation. Passwords and one-time codes should be entered manually in Chrome.

## Media

**Создать картинку** / **Создать видео** on the welcome screen (or sidebar) opens the media studio. Configure an independent media provider. [Media guide](MEDIA.md) covers Images API, Replicate and local ComfyUI. Chat models are not media-generation engines.

## Data, updates and troubleshooting

Settings, chats, media and keys live under `sever-ide/.local`. Projects normally live under `sever-ide/projects`; external project folders remain where you selected them. Stop the app and back these up privately before updates. Keys have filesystem permissions but are not encrypted. Never publish these directories.

```bash
git pull --ff-only
./start.sh
```

If a port is occupied, use the alternative-port command above. If a model fails, check it in Ollama/LM Studio directly or inspect Qwen's setup error. API errors usually require checking endpoint, model identifier, format or provider credentials. For full troubleshooting and screenshots of UI labels, use the [Russian guide](INSTALL_RU.md). See [security](../SECURITY.md) before enabling external tools.

## Browser, desktop and MCP connectors

[Chrome, Rant Connect Local and MCP — setup guide](CONNECTORS.md). Personal connector archives are available in **Инструменты и приложения**. Desktop control requires a vision/tool-capable model and explicit activation in the visible companion window.
