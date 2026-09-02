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


# Workflow display order: roughly by model release date (oldest first), with
# ties broken by simplicity/quality (simplest first). Edit this list to reorder
# the gallery columns and sidebar. Any workflow not listed here sorts to the end,
# alphabetically — so new imports show up without breaking anything.
WORKFLOW_ORDER = [
    "SDXL",                 # SD XL base 1.0 — Jul 2023
    "Flux_Schnell_Simple",  # FLUX.1 schnell — Aug 2024
    "z_image_turbo_int8",   # Z-Image Turbo — 2025
    "krea2_turbo",          # Krea2 turbo — 2025 (plain)
    "krea2_turbo_llm",      # Krea2 turbo — 2025 (+ LLM prompt rewrite; more complex)
    "flux2_klein_9b",       # FLUX.2 Klein — Nov 2025 (newest)
]


def wf_sort_key(name):
    """Sort by position in WORKFLOW_ORDER; unlisted workflows go to the end,
    alphabetically. Returns a tuple so Python's stable sort does the rest."""
    try:
        return (0, WORKFLOW_ORDER.index(name), "")
    except ValueError:
        return (1, 0, name)


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
    workflows = sorted({it["workflow"] for it in items}, key=wf_sort_key)
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
        wf_order=json.dumps(WORKFLOW_ORDER),
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
  /* Full-height column layout so the matrix area scrolls internally and its
     sticky headers actually stick, instead of the whole window scrolling. */
  html, body {{ height: 100%; }}
  body {{ margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
         background: #0b0e14; color: #cdd6f4;
         height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
  header {{ flex: none; padding: 16px 20px; border-bottom: 1px solid #1f2430; }}
  header h1 {{ margin: 0; font-size: 18px; }}
  header p {{ margin: 4px 0 0; color: #6c7394; font-size: 13px; }}
  .layout {{ flex: 1; min-height: 0; display: flex; align-items: stretch; }}
  aside {{ width: 240px; flex: none; padding: 16px 20px;
          border-right: 1px solid #1f2430; overflow: auto; }}
  aside h2 {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
             color: #6c7394; margin: 18px 0 8px; }}
  aside label {{ display: block; font-size: 13px; padding: 2px 0; cursor: pointer; }}
  aside .btnrow {{ margin-top: 8px; }}
  aside button {{ background: #1f2430; color: #cdd6f4; border: 1px solid #313747;
                 border-radius: 6px; padding: 4px 8px; font-size: 12px; cursor: pointer; }}
  /* No top padding: a sticky header pinned to top:0 inside a padded scroll
     container leaves a gap where scrolling rows peek out above the header. */
  main {{ flex: 1; padding: 0 20px 20px; min-width: 0; overflow: auto; }}
  /* The comparison matrix: prompts down the rows, workflows across the columns. */
  table.matrix {{ border-collapse: separate; border-spacing: 0; }}
  table.matrix th, table.matrix td {{ padding: 6px; border: 1px solid #1f2430; }}
  /* Column headers (workflows) stick to the top; the corner and row headers stick left. */
  table.matrix thead th {{ position: sticky; top: 0; z-index: 3; background: #11151f;
                          color: #89b4fa; font-size: 13px; white-space: nowrap;
                          vertical-align: bottom; }}
  table.matrix tbody th {{ position: sticky; left: 0; z-index: 2; background: #11151f;
                          color: #a6e3a1; font-size: 12px; text-align: right;
                          white-space: nowrap; max-width: 220px; overflow: hidden;
                          text-overflow: ellipsis; }}
  table.matrix thead th.corner {{ left: 0; z-index: 4; color: #6c7394; }}
  td.cell {{ width: 200px; height: 200px; background: #060810; text-align: center;
            vertical-align: middle; }}
  td.cell img {{ width: 200px; height: 200px; object-fit: cover; display: block;
                cursor: zoom-in; }}
  td.cell .missing {{ color: #45495c; font-size: 12px; }}
  td.cell .time {{ display: block; font-size: 10px; color: #6c7394; margin-top: 2px; }}
  .cellwrap {{ position: relative; }}
  .cellwrap .time {{ position: absolute; bottom: 0; left: 0; right: 0;
                    background: rgba(6,8,16,.7); color: #cdd6f4; font-size: 10px;
                    padding: 1px 0; }}
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
  <main id="main"></main>
</div>
<div id="lb" onclick="this.style.display='none'"><img id="lbimg" alt=""></div>
<script id="payload" type="application/json">{data}</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
// Workflow column order: release date, ties simplest-first (see WORKFLOW_ORDER).
const WF_ORDER = {wf_order};
function wfKey(w) {{ const i = WF_ORDER.indexOf(w); return i < 0 ? [1, 0, w] : [0, i, '']; }}
function wfCmp(a, b) {{
  const ka = wfKey(a), kb = wfKey(b);
  return ka[0] - kb[0] || ka[1] - kb[1] || (ka[2] < kb[2] ? -1 : ka[2] > kb[2] ? 1 : 0);
}}

// Index the flat result list into lookup[prompt][workflow] = item, and gather
// the full sorted axes so empty cells still show up as gaps in the matrix.
const LOOKUP = {{}};
const ALL_WF = new Set(), ALL_PR = new Set();
for (const it of DATA) {{
  ALL_WF.add(it.workflow); ALL_PR.add(it.prompt);
  (LOOKUP[it.prompt] = LOOKUP[it.prompt] || {{}})[it.workflow] = it;
}}

function selected(cls) {{
  return new Set([...document.querySelectorAll('.' + cls + ':checked')].map(c => c.value));
}}
function setAll(cls, on) {{
  document.querySelectorAll('.' + cls).forEach(c => c.checked = on);
  render();
}}
function openLightbox(src) {{
  document.getElementById('lbimg').src = src;
  document.getElementById('lb').style.display = 'flex';
}}
function render() {{
  const wfSel = selected('wf'), prSel = selected('pr');
  const cols = [...ALL_WF].sort(wfCmp).filter(w => wfSel.has(w));
  const rows = [...ALL_PR].sort().filter(p => prSel.has(p));
  const main = document.getElementById('main');

  if (!cols.length || !rows.length) {{
    main.innerHTML = '<p class="empty">Nothing matches those filters. ' +
                     'Bold curatorial choice.</p>';
    return;
  }}

  const table = document.createElement('table');
  table.className = 'matrix';

  // Header row: a corner cell, then one column per workflow.
  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  const corner = document.createElement('th');
  corner.className = 'corner';
  corner.textContent = 'prompt \\\\ workflow';
  hr.appendChild(corner);
  for (const w of cols) {{
    const th = document.createElement('th');
    th.textContent = w;
    hr.appendChild(th);
  }}
  thead.appendChild(hr);
  table.appendChild(thead);

  // Body: one row per prompt, one image cell per workflow.
  const tbody = document.createElement('tbody');
  for (const p of rows) {{
    const tr = document.createElement('tr');
    const rh = document.createElement('th');
    rh.textContent = p;
    rh.title = p;
    tr.appendChild(rh);
    for (const w of cols) {{
      const td = document.createElement('td');
      td.className = 'cell';
      const it = (LOOKUP[p] || {{}})[w];
      if (it && it.images.length) {{
        const src = it.images[0];
        const secs = it.meta.generation_seconds;
        const wrap = document.createElement('div');
        wrap.className = 'cellwrap';
        const img = document.createElement('img');
        img.loading = 'lazy'; img.src = src; img.alt = p + ' / ' + w;
        img.addEventListener('click', () => openLightbox(src));
        wrap.appendChild(img);
        if (secs != null) {{
          const t = document.createElement('span');
          t.className = 'time'; t.textContent = secs + 's';
          wrap.appendChild(t);
        }}
        td.appendChild(wrap);
      }} else {{
        td.innerHTML = '<span class="missing">—</span>';
      }}
      tr.appendChild(td);
    }}
    tbody.appendChild(tr);
  }}
  table.appendChild(tbody);

  main.innerHTML = '';
  main.appendChild(table);
}}
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
