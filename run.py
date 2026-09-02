#!/usr/bin/env python3
"""ComfyTestBed harness runner.

Fires every prompt at every workflow, collects the resulting images, and writes
them into results/ so we can commit the evidence. Pure standard library, because
the Captain would rather be sucked into a black hole than create a virtualenv.

Usage:
    python3 run.py            # generate everything not yet generated
    python3 run.py --force    # regenerate everything, even if it exists
    python3 run.py --list     # show the plan and do nothing (the coward's option)
"""

import argparse
import json
import os
import random
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
PROMPTS_DIR = os.path.join(ROOT, "prompts")
WORKFLOWS_DIR = os.path.join(ROOT, "workflows")
RESULTS_DIR = os.path.join(ROOT, "results")
CONFIG_PATH = os.path.join(ROOT, "config.toml")


def holly(msg):
    """Print something. With feeling. Mostly disappointment."""
    print(msg, flush=True)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        holly("There's no config.toml. I can't talk to a server I don't know about. "
              "I'm good, but I'm not psychic.")
        sys.exit(1)
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def load_prompts():
    """Every .txt in prompts/ is a prompt. Revolutionary stuff."""
    out = {}
    if not os.path.isdir(PROMPTS_DIR):
        return out
    for name in sorted(os.listdir(PROMPTS_DIR)):
        if name.endswith(".txt"):
            with open(os.path.join(PROMPTS_DIR, name), encoding="utf-8") as f:
                out[name[:-4]] = f.read().strip()
    return out


def load_workflows():
    """Every .json in workflows/ is a ComfyUI API export. We hope."""
    out = {}
    if not os.path.isdir(WORKFLOWS_DIR):
        return out
    for name in sorted(os.listdir(WORKFLOWS_DIR)):
        if name.endswith(".json"):
            with open(os.path.join(WORKFLOWS_DIR, name), encoding="utf-8") as f:
                out[name[:-5]] = f.read()  # kept as raw text for placeholder swaps
    return out


def result_dir(workflow_name, prompt_name):
    return os.path.join(RESULTS_DIR, workflow_name, prompt_name)


def already_done(workflow_name, prompt_name):
    """A combo is 'done' if it has metadata and at least one image. Anything less
    is a half-finished job, and we don't do those. Well, we try not to."""
    d = result_dir(workflow_name, prompt_name)
    meta = os.path.join(d, "metadata.json")
    if not os.path.exists(meta):
        return False
    return any(f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
               for f in os.listdir(d))


def fill_placeholders(raw_workflow, cfg, prompt_text):
    """Swap the placeholder tokens for real values and parse to JSON.

    We do the swap on the raw text so a stray quote in the prompt doesn't
    detonate the JSON structure — we escape it properly via json.dumps first."""
    gen = cfg.get("generation", {})
    prompt_ph = gen.get("prompt_placeholder", "%PROMPT%")
    seed_ph = gen.get("seed_placeholder", "%SEED%")
    configured_seed = gen.get("seed", -1)

    seed = random.randint(0, 2**32 - 1) if configured_seed == -1 else int(configured_seed)

    # json.dumps gives us a quoted, escaped string; strip the outer quotes so it
    # slots into the existing quotes in the workflow JSON.
    safe_prompt = json.dumps(prompt_text)[1:-1]

    filled = raw_workflow.replace(prompt_ph, safe_prompt).replace(seed_ph, str(seed))
    return json.loads(filled), seed


def api_post(base, path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def api_get(base, path):
    with urllib.request.urlopen(base + path) as r:
        return r.read()


def submit_and_wait(base, workflow_json, client_id, timeout):
    """Queue the prompt, then poll /history until ComfyUI admits it's finished."""
    resp = api_post(base, "/prompt", {"prompt": workflow_json, "client_id": client_id})
    prompt_id = resp["prompt_id"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        history = json.loads(api_get(base, f"/history/{prompt_id}"))
        if prompt_id in history:
            return prompt_id, history[prompt_id]
        time.sleep(1.0)
    raise TimeoutError(f"ComfyUI never finished prompt {prompt_id}. Typical.")


def collect_images(base, history_entry):
    """Pull every output image out of the history entry and download the bytes."""
    images = []
    outputs = history_entry.get("outputs", {})
    for node_output in outputs.values():
        for img in node_output.get("images", []):
            qs = urllib.parse.urlencode({
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            })
            data = api_get(base, f"/view?{qs}")
            images.append((img["filename"], data))
    return images


def run(force=False, list_only=False):
    cfg = load_config()
    server = cfg.get("server", {})
    # Prefer an explicit base url; fall back to host/port for the nostalgic.
    if server.get("url"):
        base = server["url"].rstrip("/")
    else:
        base = f"http://{server.get('host', '127.0.0.1')}:{server.get('port', 8188)}"
    timeout = server.get("timeout", 600)

    prompts = load_prompts()
    workflows = load_workflows()

    if not prompts:
        holly("No prompts. The galaxy of possibilities is, right now, a single "
              "empty room. Add a .txt to prompts/ and try to dream a little bigger.")
        return
    if not workflows:
        holly("No workflows. I've got things to say and no mouth to say them with. "
              "Drop an API-format export into workflows/.")
        return

    # Work out the flight plan: every combo not yet generated.
    plan = []
    for wf in workflows:
        for pr in prompts:
            if force or not already_done(wf, pr):
                plan.append((wf, pr))

    total = len(workflows) * len(prompts)
    holly(f"{len(workflows)} workflow(s) x {len(prompts)} prompt(s) = {total} combos. "
          f"{len(plan)} to generate, {total - len(plan)} already in the can.")

    if list_only:
        for wf, pr in plan:
            holly(f"  would generate: {wf} / {pr}")
        holly("That's the plan. I did nothing, as requested. Restful, isn't it.")
        return

    if not plan:
        holly("Nothing to do. Everything's already generated. I'll just sit here then.")
        return

    client_id = str(uuid.uuid4())
    done = 0
    failed = 0

    for wf, pr in plan:
        prompt_text = prompts[pr]
        holly(f"[{done + failed + 1}/{len(plan)}] Plotting course: {wf} / {pr} ...")
        started = time.time()
        try:
            workflow_json, seed = fill_placeholders(workflows[wf], cfg, prompt_text)
            _, history_entry = submit_and_wait(base, workflow_json, client_id, timeout)
            images = collect_images(base, history_entry)
        except urllib.error.URLError as e:
            failed += 1
            holly(f"    Couldn't reach the engine core at {base}. Is ComfyUI actually "
                  f"running? ({e}). Skipping.")
            continue
        except Exception as e:  # noqa: BLE001 - we genuinely want to survive anything
            failed += 1
            holly(f"    That went about as well as the ship's last MOT: {e}. Skipping.")
            continue

        elapsed = time.time() - started

        if not images:
            failed += 1
            holly("    ComfyUI finished but produced no images. A bold artistic "
                  "statement. Skipping.")
            continue

        d = result_dir(wf, pr)
        os.makedirs(d, exist_ok=True)
        saved = []
        for i, (fname, data) in enumerate(images):
            ext = os.path.splitext(fname)[1] or ".png"
            out_name = "image" + ext if len(images) == 1 else f"image_{i}{ext}"
            with open(os.path.join(d, out_name), "wb") as f:
                f.write(data)
            saved.append(out_name)

        meta = {
            "workflow": wf,
            "prompt": pr,
            "prompt_text": prompt_text,
            "seed": seed,
            "images": saved,
            "generation_seconds": round(elapsed, 2),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(os.path.join(d, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        done += 1
        holly(f"    Done in {elapsed:.1f}s. {len(saved)} image(s). "
              "Another triumph of automation over the man at the wheel.")

    holly(f"Finished. {done} generated, {failed} failed. "
          + ("Not bad for a ship held together with hope." if failed == 0
             else "Some failed. Check the wailing above."))


def main():
    ap = argparse.ArgumentParser(description="Fire prompts at ComfyUI workflows.")
    ap.add_argument("--force", action="store_true",
                    help="Regenerate everything, even combos already done.")
    ap.add_argument("--list", action="store_true", dest="list_only",
                    help="Show the plan and generate nothing.")
    args = ap.parse_args()
    run(force=args.force, list_only=args.list_only)


if __name__ == "__main__":
    main()
