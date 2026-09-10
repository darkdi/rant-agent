# Browser, desktop and MCP connectors

These instructions are for the open-source local app on macOS/Linux. A Rant account or subscription is not required. Your chosen API provider may charge for model usage. The local connectors are separate from the cloud version for ai.rant.ae.

## Chrome

1. Start Rant and open **Tools and apps → Your Chrome**.
2. Click **Download extension for this installation**. This ZIP contains a personal pairing key and this installation's ports. Do not publish or share it.
3. Extract to a permanent folder. Open `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and select the folder containing `manifest.json`.
4. Open **Rant Agent Local** from Chrome's extension menu and grant browser access. In Rant settings, open **Permissions** and enable the browser agent.
5. The connector should show **Connected**. Try **Use the browser** with a small task on a public HTTPS page.

The extension reads pages, navigates, clicks and fills forms for your tasks. Page content may be sent to your model provider. Enter passwords and verification codes yourself. The cloud extension does not pair with the local app automatically.

If disconnected, keep Rant running, click **Check connection**, and reload the extension in Chrome. After reinstalling Rant, download the archive again. The bridge selects a free port pair without stopping unrelated processes. Downloading the extension starts the bridge even after launching with `--no-browser`.

## Rant Connect Local

This experimental companion controls the **same computer running Rant**. It does not connect to ai.rant.ae, open an inbound port, or install a background service. Connecting another computer over a network is outside this local package's scope.

### Install

Use Python 3.12+ with Tk. Check with `python3 -c "import tkinter"`. On Mac, install a Python distribution including Tcl/Tk from [python.org](https://www.python.org/downloads/macos/) or the Tk package matching your Python version.

In **Tools and apps → Rant Connect Local**, download and extract the archive. Run `Start.command` on Mac. If needed:

```bash
chmod +x Start.command
./Start.command
```

Choose another Python with `PYTHON_BIN=/full/path/to/python3 ./Start.command`. First launch creates a separate `.venv` and installs dependencies. It downloads no models.

On Debian/Ubuntu with a graphical X11 session:

```bash
sudo apt-get install python3-venv python3-tk python3-dev scrot xclip
sh Start.command
```

Wayland and a native Windows Rant host are not supported in this alpha.

### Pair and use

1. Check that the companion shows the same local address as Rant, for example `http://127.0.0.1:4321`.
2. In Rant click **Create pairing code**, then enter it in the companion. The code expires in five minutes and can be used once.
3. On Mac grant **Screen Recording** and **Accessibility** permissions to the Python/Terminal running the companion, then restart it if required.
4. Explicitly enable control in the companion window. It starts with control off every time.
5. Choose an API or local API-server model supporting both **images and tool calls**. The built-in text-only MLX path does not support desktop tools yet.
6. Start with a simple request, such as asking which window is visible, then try a small task in a test document.

Connect can capture the main monitor, click, type, send shortcuts and scroll. Screenshots go to your chosen model, including its external provider when using a remote API. Model-specific vision accuracy needs local testing. This is not a shell or SSH interface.

### Stop and revoke

Stop in the companion or close its window to disable execution. **Stop** in chat ends the task and cancels pending commands; it cannot undo an action already performed. Move the mouse to the main monitor's top-left corner for PyAutoGUI's fail-safe at the next control call. Remove a computer in Rant to revoke its token; pairing again requires a new code.

On connection errors, control turns off. Received commands are not automatically redelivered. If a response is lost, an action may have happened: inspect the screen before repeating it. Only one paired computer may be armed at once.

Tokens live under `~/.rant-connect-local/`, separately for each local address. The downloaded companion ZIP has an address but no pairing token. If you change ports, download it again or set `RANT_LOCAL_URL=http://127.0.0.1:NEW_PORT` and pair again.

## MCP

Enter a name, public HTTPS MCP Streamable HTTP endpoint and optional token in **Tools and apps**. Click **Check and list actions**, then allow only the actions you need. Connection discovery does not automatically grant tool access.

Text results and Bearer tokens are supported; OAuth and local stdio transport are not. MCP works with API-connected models, including compatible local servers, that support tool calls. You can revoke permissions or remove the connection at any time.

## Verification

Automated tests cover one-use/expired codes, revocation, cancellation, no command redelivery, coordinate conversion and HTTP relay/downloads with a synthetic client. They do not operate the real desktop. Test your selected model and OS permissions locally. This release provides source launchers, not signed native installers.
