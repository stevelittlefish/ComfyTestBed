# Workflows

Drop your **ComfyUI API-format** workflow exports in here, one `.json` per model/setup.

To export one: in ComfyUI, enable dev mode (Settings → "Enable Dev mode Options"),
then use **"Save (API Format)"**. This is *not* the same as the normal Save — the
normal one produces a file the harness will stare at blankly and refuse to run.

## Placeholders

Somewhere in the JSON, in the positive-prompt text node, put the placeholder token
(default `%PROMPT%`, configurable in `config.toml`). The harness substitutes the
prompt text there before submitting.

Optionally, put `%SEED%` where the KSampler seed goes if you want reproducible-ish
runs controlled from `config.toml`.

Example snippet inside a CLIPTextEncode node:

```json
"inputs": {
  "text": "%PROMPT%",
  "clip": ["4", 1]
}
```

The filename (minus `.json`) is the workflow's name and shows up in results. Name them
something you'll recognise, not `workflow(3)(final)(FINAL)(2).json`.
