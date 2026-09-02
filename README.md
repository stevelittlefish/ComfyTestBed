# ComfyTestBed

For firing prompts at different image generators to compare the results.

Or, as the ship's records have it: a harness for exploring the galaxy of possible
images that [ComfyUI](https://github.com/comfyanonymous/ComfyUI) can generate,
one prompt-and-workflow combination at a time.

There is **no database**. Everything is files in this git repository, so the results
get committed and the whole expedition is version-controlled. Revolutionary, I know.

## What's in the ship

```
prompts/       one .txt file per prompt (the filename is the prompt's name)
workflows/     ComfyUI API-format exports, with %PROMPT% (and optional %SEED%) placeholders
config.toml    server URL and generation settings
results/       results/<workflow>/<prompt>/ -> image(s) + metadata.json
run.py         the runner: generates every combo not yet generated
web.py         a dead-simple browser for the results (grid + filters)
```

## Requirements

Python 3.11 or newer. **That's it.** No `pip install`, no `requirements.txt`, and
absolutely, categorically, **no virtualenv**. Everything runs on the standard library
because the Captain would rather walk home through hard vacuum than manage Python
dependencies. If a feature ever needs a third-party package, we rewrite it in Go instead.

## Usage

1. **Add prompts.** Drop text files into `prompts/`. Example: `prompts/astronaut_cat.txt`.

2. **Add workflows.** Export from ComfyUI in **API format** (Settings → enable Dev mode,
   then "Save (API Format)") into `workflows/`. Put `%PROMPT%` in the positive-prompt
   text node. See `workflows/README.md` for details.

3. **Point at your ComfyUI.** Edit `config.toml`:

   ```toml
   [server]
   url = "https://comfy.seaslug.ai"
   ```

4. **Generate.** This walks every prompt x workflow combination and generates the ones
   that don't have results yet:

   ```bash
   python3 run.py            # generate what's missing
   python3 run.py --list     # show the plan, generate nothing
   python3 run.py --force    # regenerate everything
   ```

   Results land in `results/<workflow>/<prompt>/` as image file(s) plus a
   `metadata.json` recording the prompt text, seed, image list, generation time,
   and timestamp.

   The runner processes **all prompts for one workflow consecutively**, and fires a
   single **discarded warm-up render** before each workflow's real prompts. This
   loads the model into VRAM so the first real render's timing isn't inflated by
   cold-start loading — making `generation_seconds` fair across models. The warm-up
   prompt is deliberately ridiculous and is never saved.

5. **Browse.** Launch the gallery:

   ```bash
   python3 web.py            # http://127.0.0.1:8000
   ```

   Grid of every result, with checkboxes to filter by workflow and prompt, and
   click-to-zoom. Reads straight from `results/` — no build step, no bundler,
   no nonsense.

## Committing (protocol: raw-dog-3000)

Code changes go straight to `main`. No branches unless asked. Generated **images**:
check before committing — we may want to regenerate them first. `config.toml` is
committed (there's no auth on the server and nobody's going to want the AI slop anyway).

## A note on tone

The code talks back. The runner and the gallery are staffed by a mildly disappointed
ship's computer in the tradition of Holly from Red Dwarf. This is a feature. Do not
"fix" it.
