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

**Do not placeholder the negative prompt.** A negative is a model-specific setting,
like `cfg` or `steps`, and is part of how that particular model should be run. Leave
whatever the export ships with in place — an empty `ConditioningZeroOut` (as the turbo
model uses) or a real negative such as `"blurry, deformed, watermark"`. We hold the
*positive* prompt constant across models; the negative belongs to the workflow.

Example snippet inside a CLIPTextEncode node:

```json
"inputs": {
  "text": "%PROMPT%",
  "clip": ["4", 1]
}
```

The filename (minus `.json`) is the workflow's name and shows up in results. Name them
something you'll recognise, not `workflow(3)(final)(FINAL)(2).json`.
