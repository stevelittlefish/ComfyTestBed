#!/usr/bin/env python3
"""ComfyTestBed results browser.

A deliberately simple web app for staring at the images we've generated, arranged
in a grid, with filters for workflows and prompts. Standard library only — it's an
http.server and some HTML I typed by hand like an animal. No virtualenv shall pass.

Usage:
    python3 web.py            # serve on http://127.0.0.1:8000
    python3 web.py --port N   # serve somewhere else
"""

import argparse
import html
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(ROOT, "results")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def scan_results():
    """Walk results/<workflow>/<prompt>/ and gather what we've got.

    Returns a list of dicts. Missing metadata is tolerated, because someone
    always deletes the one file that mattered."""
    items = []
    if not os.path.isdir(RESULTS_DIR):
        return items
    for wf in sorted(os.listdir(RESULTS_DIR)):
        wf_dir = os.path.join(RESULTS_DIR, wf)
        if not os.path.isdir(wf_dir):
            continue
        for pr in sorted(os.listdir(wf_dir)):
            pr_dir = os.path.join(wf_dir, pr)
            if not os.path.isdir(pr_dir):
                continue
            images = sorted(f for f in os.listdir(pr_dir)
                            if f.lower().endswith(IMAGE_EXTS))
            if not images:
                continue
            meta = {}
            meta_path = os.path.join(pr_dir, "metadata.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:  # noqa: BLE001
                    meta = {}
            items.append({
                "workflow": wf,
                "prompt": pr,
                "images": [f"/results/{urllib.parse.quote(wf)}/"
                           f"{urllib.parse.quote(pr)}/{urllib.parse.quote(img)}"
                           for img in images],
                "meta": meta,
            })
    return items


def render_page():
    items = scan_results()
    workflows = sorted({it["workflow"] for it in items})
    prompts = sorted({it["prompt"] for it in items})

    # Embed JSON in a <script>. Inside a script element the browser does NOT
    # HTML-decode, so the only thing that can hurt us is the literal "</script>"
    # (and "<!--"). Neutralise "<" and we're safe. No html.escape here — that
    # would leave &quot; litter all over our lovely JSON.
    data_json = json.dumps(items).replace("<", "\\u003c")

    if not items:
        empty_note = ("<p class='empty'>No results yet, Captain. The gallery is as "
                      "empty as the ship's fuel tank. Run <code>python3 run.py</code> "
                      "first.</p>")
    else:
        empty_note = ""

    wf_opts = "".join(f"<label><input type='checkbox' class='wf' value='{html.escape(w)}' checked> {html.escape(w)}</label>"
                      for w in workflows)
    pr_opts = "".join(f"<label><input type='checkbox' class='pr' value='{html.escape(p)}' checked> {html.escape(p)}</label>"
                      for p in prompts)

    return PAGE_TEMPLATE.format(
        data=data_json, wf_opts=wf_opts, pr_opts=pr_opts,
        empty_note=empty_note, count=len(items),
    )


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ComfyTestBed — Ship's Gallery</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
         background: #0b0e14; color: #cdd6f4; }}
  header {{ padding: 16px 20px; border-bottom: 1px solid #1f2430; }}
  header h1 {{ margin: 0; font-size: 18px; }}
  header p {{ margin: 4px 0 0; color: #6c7394; font-size: 13px; }}
  .layout {{ display: flex; align-items: flex-start; }}
  aside {{ width: 240px; padding: 16px 20px; border-right: 1px solid #1f2430;
          position: sticky; top: 0; max-height: 100vh; overflow: auto; }}
  aside h2 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
             color: #6c7394; margin: 18px 0 8px; }}
  aside label {{ display: block; font-size: 13px; padding: 2px 0; cursor: pointer; }}
  aside .btnrow {{ margin-top: 8px; }}
  aside button {{ background: #1f2430; color: #cdd6f4; border: 1px solid #313747;
                 border-radius: 6px; padding: 4px 8px; font-size: 12px; cursor: pointer; }}
  main {{ flex: 1; padding: 16px 20px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
          gap: 16px; }}
  .card {{ background: #11151f; border: 1px solid #1f2430; border-radius: 10px;
          overflow: hidden; }}
  .card img {{ width: 100%; display: block; aspect-ratio: 1; object-fit: cover;
              background: #060810; cursor: zoom-in; }}
  .card .cap {{ padding: 8px 10px; font-size: 12px; }}
  .card .cap .wf {{ color: #89b4fa; }}
  .card .cap .pr {{ color: #a6e3a1; }}
  .card .cap .time {{ color: #6c7394; }}
  .empty {{ color: #6c7394; padding: 24px; }}
  #lb {{ position: fixed; inset: 0; background: rgba(0,0,0,.9); display: none;
        align-items: center; justify-content: center; cursor: zoom-out; z-index: 50; }}
  #lb img {{ max-width: 94vw; max-height: 94vh; }}
</style>
</head>
<body>
<header>
  <h1>ComfyTestBed — Ship's Gallery</h1>
  <p>{count} result(s) surveyed from the galaxy of possibilities. {empty_note}</p>
</header>
<div class="layout">
  <aside>
    <h2>Workflows</h2>
    <div id="wfs">{wf_opts}</div>
    <div class="btnrow"><button onclick="setAll('wf', true)">all</button>
      <button onclick="setAll('wf', false)">none</button></div>
    <h2>Prompts</h2>
    <div id="prs">{pr_opts}</div>
    <div class="btnrow"><button onclick="setAll('pr', true)">all</button>
      <button onclick="setAll('pr', false)">none</button></div>
  </aside>
  <main><div class="grid" id="grid"></div></main>
</div>
<div id="lb" onclick="this.style.display='none'"><img id="lbimg" alt=""></div>
<script id="payload" type="application/json">{data}</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);

function selected(cls) {{
  return new Set([...document.querySelectorAll('.' + cls + ':checked')].map(c => c.value));
}}
function setAll(cls, on) {{
  document.querySelectorAll('.' + cls).forEach(c => c.checked = on);
  render();
}}
function render() {{
  const wf = selected('wf'), pr = selected('pr');
  const grid = document.getElementById('grid');
  grid.innerHTML = '';
  let shown = 0;
  for (const it of DATA) {{
    if (!wf.has(it.workflow) || !pr.has(it.prompt)) continue;
    for (const src of it.images) {{
      shown++;
      const secs = it.meta.generation_seconds;
      const t = (secs != null) ? secs + 's' : '';
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML =
        '<img loading="lazy" src="' + src + '" alt="">' +
        '<div class="cap"><span class="wf">' + esc(it.workflow) + '</span> / ' +
        '<span class="pr">' + esc(it.prompt) + '</span> ' +
        '<span class="time">' + t + '</span></div>';
      card.querySelector('img').addEventListener('click', () => {{
        document.getElementById('lbimg').src = src;
        document.getElementById('lb').style.display = 'flex';
      }});
      grid.appendChild(card);
    }}
  }}
  if (shown === 0) grid.innerHTML =
    '<p class="empty">Nothing matches those filters. Bold curatorial choice.</p>';
}}
function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}
document.querySelectorAll('.wf, .pr').forEach(c => c.addEventListener('change', render));
render();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - name fixed by base class
        pass  # the default logging is noisier than the Captain during re-entry.

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/" or path == "/index.html":
            body = render_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith("/results/"):
            return self.serve_result_file(path)
        self.send_error(404, "Nothing here. Much like the ship's trophy cabinet.")

    def serve_result_file(self, path):
        rel = urllib.parse.unquote(path[len("/results/"):])
        # No wandering off up the directory tree, thank you.
        full = os.path.normpath(os.path.join(RESULTS_DIR, rel))
        if not full.startswith(RESULTS_DIR + os.sep) or not os.path.isfile(full):
            self.send_error(404, "That file isn't where you think it is.")
            return
        ctype = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif",
        }.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    ap = argparse.ArgumentParser(description="Browse ComfyTestBed results.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Ship's gallery open at http://{args.host}:{args.port}  "
          "(Ctrl-C to close the viewport)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nViewport closed. Mind the airlock on your way out.")


if __name__ == "__main__":
    main()
