# Image and video generation

Open **Create an image** or **Create a video** on the welcome screen, or Images / Video in the sidebar. Add a connection separately for each media type. Saving a connection makes no generation request. Your provider charges for API generation; Rant adds no credits or billing layer. Local workflows use your hardware, but custom workflow nodes may call paid APIs.

## Images API

Choose **Images API · OpenAI-compatible**, enter a connection name, the provider's base URL (usually ending in `/v1`), API key, and exact image model ID. This adapter sends `POST /images/generations` with `model`, `prompt`, and `n: 1`. It accepts a base64 image or result URL. It does not turn a chat-only model into an image model.

Under Model parameters, paste a JSON object of parameters supported by that model, such as size or quality. Do not put credentials in this object. The prompt comes from your description; model and count are controlled by the app. Arbitrary multipart image-editing APIs are not supported.

## Replicate images or video

Select Replicate, use `https://api.replicate.com/v1`, and enter your own token. Set the model to `owner/model` for an official model, or `owner/model:version` with its full version hash. Set duration, aspect ratio and other supported inputs in Model parameters. Consult the selected model's input schema: there is no universal parameter set for every model.

The adapter creates one prediction and polls its status. It expects an image/video URL or a list of URLs and keeps the first result. Video must be MP4 or WebM. The job ID is shown for checking its status in Replicate. See the [Replicate HTTP API](https://replicate.com/docs/reference/http/).

## Local ComfyUI

Install [ComfyUI](https://docs.comfy.org/) separately, add the model weights and nodes your workflow needs, and first confirm that the workflow runs successfully in ComfyUI itself. Rant does not install model weights or build workflows automatically. Qwen/Ollama chat models do not generate images/video through this adapter.

1. Start ComfyUI locally, normally at `http://127.0.0.1:8188`.
2. Export a working workflow in **API format**, not the ordinary visual-editor format.
3. Replace its positive prompt text with `__PROMPT__`. Keep the negative prompt unchanged.
4. In Rant choose ComfyUI, enter the local address and paste the workflow JSON. An API key is optional.
5. Save the connection, enter your description, and generate.

An image workflow must save PNG/JPEG/WebP. A video workflow must save MP4/WebM in an output reported under images, gifs, or videos. Install any custom nodes required by your workflow. Rant uses `/prompt`, `/history/{id}`, and `/view`; see [ComfyUI routes](https://docs.comfy.org/development/comfyui-server/comms_routes). Only loopback ComfyUI endpoints are supported.

## Results, limits and recovery

Results are stored under `sever-ide/.local/media` and can be downloaded from the gallery. They persist after closing the dialog. Keep Rant running while generation is active. The current limits are one active job, 60 gallery entries, approximately 1 GB of saved results, a 100 MB downloaded result, and a 32-megapixel image. Images are normalized to PNG. Back up the files you need before clearing the media folder while Rant is stopped.

Generation requests are never automatically resubmitted. If the app restarts or loses a response, the job is marked for review: it may have completed at the provider. Check the provider dashboard or ComfyUI history before generating again. Repeating a paid request may incur another charge. A provider's progress bar or quality cannot be inferred from a connection being saved.

API keys are stored separately from connection metadata in a private local directory; they are not encrypted. Output downloads do not receive provider credentials. Use only trusted providers and workflows.

Adapter contract tests cover synthetic responses. A real paid generation or your particular ComfyUI model still needs verification after setup.
