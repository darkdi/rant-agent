# Rant Connect Local

Visible, opt-in desktop connector for the same macOS/Linux computer running the open-source Rant Agent. This package does not connect to ai.rant.ae.

Install Python 3.12+ with Tk. On macOS run `Start.command`; on Linux/X11 run `sh Start.command` after installing python3-tk, python3-venv, python3-dev, scrot and xclip. First launch installs PyAutoGUI, pyperclip and Pillow in this folder's `.venv`.

The archive downloaded from Rant includes `server.json` with the local application's address. A source checkout defaults to http://127.0.0.1:4311; override with `RANT_LOCAL_URL`. Only loopback HTTP origins with an explicit port are accepted. The configured Python can be selected with `PYTHON_BIN`.

Create a one-time code in Rant → Инструменты и приложения → Rant Connect Local, paste it here, then explicitly enable control. On macOS grant Screen Recording and Accessibility permissions to the Python/Terminal used to run it. Use a model supporting vision and tool calls. The bundled text-only MLX path is not supported for desktop control.

The window remains visible. Control is off on startup and on connection errors. Close the window or click Stop to disarm. Move the mouse to the upper-left corner for PyAutoGUI's fail-safe. Only the primary monitor is supported. Do not run concurrently with another automation controlling the same desktop.

No action is automatically redelivered. If the result could not be uploaded, inspect the screen before trying again. Tokens live in ~/.rant-connect-local, separate from this package. Screenshots may be sent to your selected model provider. There is no shell/SSH API, background install, or signed native installer in this alpha.

Full guide: https://github.com/darkdi/rant-agent/blob/main/docs/CONNECTORS.md
