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

# The review queue's verdicts live here: {"workflow/prompt": "good"|"censored"|
# "inappropriate"}. It's a working aid, not part of the ship — git-ignored — so the
# Captain can triage without every keystroke landing in a commit.
STATUS_FILE = os.path.join(ROOT, "review_status.json")
VALID_STATUSES = ("good", "censored", "inappropriate")


def load_status():
    """Read the verdict map. A missing or corrupt file means 'nothing reviewed
    yet' rather than a crash — this thing must never block the airlock."""
    try:
        with open(STATUS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_status(status):
    """Write verdicts atomically (temp file + rename) so a crash mid-write can't
    shred the log of what you've already cleared."""
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, sort_keys=True)
    os.replace(tmp, STATUS_FILE)


# Workflow display order: roughly by model release date (oldest first), with
# ties broken by simplicity/quality (simplest first). Edit this list to reorder
# the gallery columns and sidebar. Any workflow not listed here sorts to the end,
# alphabetically — so new imports show up without breaking anything.
WORKFLOW_ORDER = [
    "sd15",                 # SD 1.5 (v1-5-pruned-emaonly) — Oct 2022 (eldest)
    "sd21",                 # SD 2.1 (v2-1_768-ema-pruned) — Dec 2022
    "SDXL",                 # SD XL base 1.0 — Jul 2023
    # --- SDXL fine-tunes, grouped with their base rather than by exact date ---
    "juggernaut_xi",        # Juggernaut XI (RunDiffusion) — SDXL photoreal
    "cyberrealistic_pony",  # CyberRealistic Pony v8 — SDXL/Pony (score_ handshake)
    "pony_realism",         # Pony Realism v2.2 — SDXL/Pony (score_ handshake)
    "illustrious_xl",       # Illustrious XL v0.1 — SDXL anime
    "hassaku_xl",           # Hassaku XL Illustrious v13 — SDXL anime
    # --- end SDXL family ---
    "Flux_Schnell",         # FLUX.1 schnell — Aug 2024 (distilled, simplest)
    "flux_dev",             # FLUX.1 dev — Aug 2024 (fuller, after schnell)
    # --- SD 3.5 family, all Oct 2024; medium (smaller) -> large -> turbo shortcut ---
    "SD35_medium",          # SD 3.5 Medium — Oct 2024 (2.5B, triple-CLIP)
    "SD35_large",           # SD 3.5 Large — Oct 2024 (8B, fuller)
    "sd35_large_turbo",     # SD 3.5 Large Turbo — Oct 2024 (distilled shortcut)
    # --- end SD 3.5 family ---
    "chroma",               # Chroma — 2025
    "z_image_turbo_int8",   # Z-Image Turbo — 2025 (distilled, simplest)
    "z_image",              # Z-Image base (bf16) — 2025 (fuller, after turbo)
    "krea2_turbo",          # Krea2 turbo — 2025 (plain)
    "krea2_turbo_llm",      # Krea2 turbo — 2025 (+ LLM prompt rewrite; more complex)
    "qwen_image",           # Qwen-Image — 2025
    "flux2_klein_4b",       # FLUX.2 Klein 4B — Nov 2025 (smaller, simpler)
    "flux2_klein_9b",       # FLUX.2 Klein 9B — Nov 2025 (newest)
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
  /* No top/left padding: a sticky header pinned to top:0/left:0 inside a padded
     scroll container leaves a gap where scrolling content peeks past the pinned
     header (rows above the column head, images left of the row head). Keep only
     right/bottom padding for breathing room. */
  main {{ flex: 1; padding: 0 20px 20px 0; min-width: 0; overflow: auto; }}
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
  #lbfig {{ margin: 0; display: flex; flex-direction: column; align-items: center;
           gap: 8px; cursor: default; }}
  #lbimg {{ max-width: 82vw; max-height: 86vh; }}
  #lbcap {{ font-size: 13px; color: #cdd6f4; text-align: center; }}
  #lbcap .wf {{ color: #89b4fa; }}
  #lbcap .pr {{ color: #a6e3a1; }}
  #lbcap .pos {{ color: #6c7394; }}
  .lbnav {{ position: fixed; top: 50%; transform: translateY(-50%);
           background: rgba(31,36,48,.7); color: #cdd6f4; border: 1px solid #313747;
           border-radius: 50%; width: 48px; height: 48px; font-size: 26px;
           line-height: 1; cursor: pointer; user-select: none; z-index: 51; }}
  .lbnav:hover {{ background: rgba(49,55,71,.9); }}
  #lbprev {{ left: 16px; }}
  #lbnext {{ right: 16px; }}
</style>
</head>
<body>
<header>
  <h1>ComfyTestBed — Ship's Gallery</h1>
  <p>{count} result(s) surveyed from the galaxy of possibilities.
     <a href="/review" style="color:#89b4fa">&rarr; Review queue</a> {empty_note}</p>
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
<div id="lb">
  <button id="lbprev" class="lbnav" aria-label="Previous (left arrow)">&lsaquo;</button>
  <figure id="lbfig"><img id="lbimg" alt=""><figcaption id="lbcap"></figcaption></figure>
  <button id="lbnext" class="lbnav" aria-label="Next (right arrow)">&rsaquo;</button>
</div>
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
  saveFilters();
  render();
}}
// Lightbox state: the current row's images (same prompt, across the visible
// workflow columns, in order) plus which one we're looking at.
let LB = {{ items: [], idx: 0 }};
function lbShow() {{
  const it = LB.items[LB.idx];
  if (!it) return;
  document.getElementById('lbimg').src = it.src;
  document.getElementById('lbcap').innerHTML =
    '<span class="pr">' + esc(it.prompt) + '</span> / ' +
    '<span class="wf">' + esc(it.workflow) + '</span> ' +
    '<span class="pos">(' + (LB.idx + 1) + '/' + LB.items.length + ')</span>';
}}
function openLightbox(items, idx) {{
  LB.items = items; LB.idx = idx;
  document.getElementById('lb').style.display = 'flex';
  lbShow();
}}
function lbStep(delta) {{
  if (!LB.items.length) return;
  LB.idx = (LB.idx + delta + LB.items.length) % LB.items.length;  // wrap around
  lbShow();
}}
function lbClose() {{ document.getElementById('lb').style.display = 'none'; }}
function esc(s) {{ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }}
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
    // Collect this row's images (visible columns, in order) so the lightbox can
    // page prev/next through the same prompt across workflows.
    const rowItems = [];
    for (const w of cols) {{
      const td = document.createElement('td');
      td.className = 'cell';
      const it = (LOOKUP[p] || {{}})[w];
      if (it && it.images.length) {{
        const src = it.images[0];
        const secs = it.meta.generation_seconds;
        const myIdx = rowItems.length;
        rowItems.push({{ src: src, workflow: w, prompt: p }});
        const wrap = document.createElement('div');
        wrap.className = 'cellwrap';
        const img = document.createElement('img');
        img.loading = 'lazy'; img.src = src; img.alt = p + ' / ' + w;
        img.addEventListener('click', () => openLightbox(rowItems, myIdx));
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
// Persist filter state across refreshes. We store the *unchecked* boxes per
// class, so a freshly-imported workflow/prompt (unknown to storage) still
// defaults to visible rather than hiding itself the moment it appears.
const FILTER_KEY = 'comfytestbed.filters';
function saveFilters() {{
  const off = {{}};
  ['wf', 'pr'].forEach(cls => {{
    off[cls] = [...document.querySelectorAll('.' + cls + ':not(:checked)')].map(c => c.value);
  }});
  try {{ localStorage.setItem(FILTER_KEY, JSON.stringify(off)); }} catch (e) {{}}
}}
function restoreFilters() {{
  let off;
  try {{ off = JSON.parse(localStorage.getItem(FILTER_KEY) || '{{}}'); }} catch (e) {{ return; }}
  if (!off) return;
  ['wf', 'pr'].forEach(cls => {{
    const hide = new Set(off[cls] || []);
    document.querySelectorAll('.' + cls).forEach(c => {{ if (hide.has(c.value)) c.checked = false; }});
  }});
}}
document.querySelectorAll('.wf, .pr').forEach(c => c.addEventListener('change', () => {{ saveFilters(); render(); }}));

// Lightbox controls: buttons, backdrop-to-close, and arrow keys.
document.getElementById('lbprev').addEventListener('click', e => {{ e.stopPropagation(); lbStep(-1); }});
document.getElementById('lbnext').addEventListener('click', e => {{ e.stopPropagation(); lbStep(1); }});
document.getElementById('lbfig').addEventListener('click', e => e.stopPropagation());
document.getElementById('lb').addEventListener('click', lbClose);
document.addEventListener('keydown', e => {{
  if (document.getElementById('lb').style.display !== 'flex') return;
  if (e.key === 'ArrowLeft') {{ e.preventDefault(); lbStep(-1); }}
  else if (e.key === 'ArrowRight') {{ e.preventDefault(); lbStep(1); }}
  else if (e.key === 'Escape') {{ lbClose(); }}
}});
restoreFilters();
render();
</script>
</body>
</html>
"""


def render_review_page():
    """One-at-a-time triage station. Items are ordered like the gallery columns
    (workflow order, then prompt) so the queue reads sensibly."""
    items = scan_results()
    items.sort(key=lambda it: (wf_sort_key(it["workflow"]), it["prompt"]))
    payload = {
        "items": [{
            "key": it["workflow"] + "/" + it["prompt"],
            "workflow": it["workflow"],
            "prompt": it["prompt"],
            "src": it["images"][0] if it["images"] else "",
        } for it in items if it["images"]],
        "status": load_status(),
    }
    # Same anti-</script> hygiene as the gallery: neutralise "<" inside the blob.
    data_json = json.dumps(payload).replace("<", "\\u003c")
    return REVIEW_TEMPLATE.replace("__PAYLOAD__", data_json)


# Plain string (NOT str.format): the JS below is brace-heavy, so we inject the
# payload with a single .replace() and spare ourselves an ocean of {{ }}.
REVIEW_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ComfyTestBed — Review Queue</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
         background: #0b0e14; color: #cdd6f4;
         height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
  header { flex: none; padding: 12px 20px; border-bottom: 1px solid #1f2430;
           display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; }
  header h1 { margin: 0; font-size: 16px; }
  header a { color: #89b4fa; font-size: 13px; text-decoration: none; }
  header a:hover { text-decoration: underline; }
  #counts { font-size: 12px; color: #6c7394; margin-left: auto; }
  #counts b { color: #cdd6f4; }
  #counts .g { color: #a6e3a1; } #counts .c { color: #f9e2af; } #counts .x { color: #f38ba8; }
  .toggle { font-size: 12px; color: #6c7394; cursor: pointer; }
  main { flex: 1; min-height: 0; display: flex; flex-direction: column;
         align-items: center; justify-content: center; gap: 12px; padding: 16px; }
  #stage { flex: 1; min-height: 0; display: flex; align-items: center;
           justify-content: center; width: 100%; }
  #img { max-width: 90vw; max-height: 62vh; border: 1px solid #1f2430;
         background: #060810; }
  #cap { font-size: 13px; text-align: center; }
  #cap .pr { color: #a6e3a1; } #cap .wf { color: #89b4fa; } #cap .pos { color: #6c7394; }
  #verdict { font-size: 12px; min-height: 18px; }
  .badge { padding: 2px 8px; border-radius: 4px; font-weight: bold; }
  .badge.good { background: #1e3a1e; color: #a6e3a1; }
  .badge.censored { background: #3a341e; color: #f9e2af; }
  .badge.inappropriate { background: #3a1e26; color: #f38ba8; }
  .controls { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
  .controls button { border: 1px solid #313747; border-radius: 8px; padding: 10px 18px;
                     font-size: 14px; font-family: inherit; cursor: pointer;
                     background: #1f2430; color: #cdd6f4; }
  .controls button kbd { opacity: .6; font-size: 11px; }
  button.good:hover { background: #1e3a1e; border-color: #a6e3a1; }
  button.censored:hover { background: #3a341e; border-color: #f9e2af; }
  button.inappropriate:hover { background: #3a1e26; border-color: #f38ba8; }
  .nav { display: flex; gap: 10px; align-items: center; font-size: 12px; color: #6c7394; }
  .nav button { background: #11151f; color: #cdd6f4; border: 1px solid #313747;
                border-radius: 6px; padding: 4px 12px; cursor: pointer; font-family: inherit; }
  #done { color: #a6e3a1; font-size: 15px; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>Review Queue</h1>
  <a href="/">&larr; back to gallery</a>
  <label class="toggle"><input type="checkbox" id="onlyunrev" checked> only unreviewed</label>
  <span id="counts"></span>
</header>
<main>
  <div id="stage"><img id="img" alt=""><div id="done" style="display:none"></div></div>
  <div id="cap"></div>
  <div id="verdict"></div>
  <div class="controls">
    <button class="good" onclick="mark('good')">Good <kbd>(g)</kbd></button>
    <button class="censored" onclick="mark('censored')">Censored <kbd>(c)</kbd></button>
    <button class="inappropriate" onclick="mark('inappropriate')">Inappropriate <kbd>(x)</kbd></button>
    <button onclick="mark(null)">Clear <kbd>(u)</kbd></button>
  </div>
  <div class="nav">
    <button onclick="step(-1)">&lsaquo; prev</button>
    <span id="navinfo"></span>
    <button onclick="step(1)">next &rsaquo;</button>
  </div>
</main>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const P = JSON.parse(document.getElementById('payload').textContent);
const ITEMS = P.items;
const STATUS = P.status || {};
let pos = 0;

function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function reviewed(it){ return !!STATUS[it.key]; }

function updateCounts(){
  let g=0,c=0,x=0;
  for(const it of ITEMS){ const s=STATUS[it.key]; if(s==='good')g++; else if(s==='censored')c++; else if(s==='inappropriate')x++; }
  const done=g+c+x, total=ITEMS.length;
  document.getElementById('counts').innerHTML =
    '<b>'+done+'</b>/'+total+' reviewed &nbsp; '+
    '<span class="g">'+g+' good</span> &nbsp; '+
    '<span class="c">'+c+' censored</span> &nbsp; '+
    '<span class="x">'+x+' inappropriate</span> &nbsp; '+
    '<b>'+(total-done)+'</b> left';
}

function show(){
  const img=document.getElementById('img'), done=document.getElementById('done');
  if(!ITEMS.length){ img.style.display='none'; done.style.display='block';
    done.textContent='No images to review yet, Captain.'; document.getElementById('cap').textContent=''; return; }
  const it=ITEMS[pos];
  img.style.display=''; done.style.display='none';
  img.src=it.src; img.alt=it.prompt+' / '+it.workflow;
  document.getElementById('cap').innerHTML =
    '<span class="pr">'+esc(it.prompt)+'</span> / <span class="wf">'+esc(it.workflow)+'</span> '+
    '<span class="pos">('+(pos+1)+'/'+ITEMS.length+')</span>';
  const s=STATUS[it.key];
  document.getElementById('verdict').innerHTML = s
    ? 'verdict: <span class="badge '+s+'">'+s+'</span>'
    : '<span class="pos">unreviewed</span>';
  document.getElementById('navinfo').textContent = (pos+1)+' / '+ITEMS.length;
  updateCounts();
}

function setPos(p){ pos=Math.max(0,Math.min(ITEMS.length-1,p)); show(); }

function step(delta){
  const only=document.getElementById('onlyunrev').checked;
  let p=pos;
  for(let i=0;i<ITEMS.length;i++){
    p+=delta;
    if(p<0||p>=ITEMS.length) return;              // stop at the ends
    if(!only || !reviewed(ITEMS[p])){ pos=p; show(); return; }
  }
}

function advanceAfterMark(){
  // Always jump to the next still-unreviewed item, wrapping once, so a marking
  // spree flows straight down the queue.
  for(let p=pos+1;p<ITEMS.length;p++){ if(!reviewed(ITEMS[p])){ pos=p; show(); return; } }
  for(let p=0;p<ITEMS.length;p++){ if(!reviewed(ITEMS[p])){ pos=p; show(); return; } }
  show();  // everything's reviewed — just refresh the badge in place
}

function mark(s){
  if(!ITEMS.length) return;
  const it=ITEMS[pos];
  if(s) STATUS[it.key]=s; else delete STATUS[it.key];
  fetch('/api/status',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({key:it.key,status:s})}).catch(()=>{
    document.getElementById('verdict').innerHTML='<span class="badge inappropriate">save failed — check the server</span>';
  });
  updateCounts();
  if(s) advanceAfterMark(); else show();
}

document.getElementById('onlyunrev').addEventListener('change', show);
document.addEventListener('keydown', e=>{
  if(e.key==='g') mark('good');
  else if(e.key==='c') mark('censored');
  else if(e.key==='x'||e.key==='i') mark('inappropriate');
  else if(e.key==='u') mark(null);
  else if(e.key==='ArrowLeft'){ e.preventDefault(); step(-1); }
  else if(e.key==='ArrowRight'){ e.preventDefault(); step(1); }
});

// Start at the first unreviewed item so you pick up where you left off.
for(let p=0;p<ITEMS.length;p++){ if(!reviewed(ITEMS[p])){ pos=p; break; } }
show();
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
            return self._send_html(render_page())
        if path == "/review":
            return self._send_html(render_review_page())
        if path == "/api/status":
            return self._send_json(load_status())
        if path.startswith("/results/"):
            return self.serve_result_file(path)
        self.send_error(404, "Nothing here. Much like the ship's trophy cabinet.")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/status":
            self.send_error(404, "No such airlock control.")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            key = payload["key"]
        except (ValueError, KeyError, TypeError):
            self.send_error(400, "Malformed review verdict.")
            return
        status = payload.get("status")
        data = load_status()
        if status in VALID_STATUSES:
            data[key] = status
        else:  # unknown/None/empty -> clear the verdict
            data.pop(key, None)
        save_status(data)
        self._send_json({"ok": True, "key": key, "status": data.get(key)})

    def _send_html(self, text):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
