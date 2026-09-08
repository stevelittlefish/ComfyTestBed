# GPU Power Comparison — 3090 @ 250 W vs 3090 @ 400 W

A field report from the ship's computer. This documents a change in the render
core's **hardware**, not its software — and what it did to our timings.

## The two rigs

| | Previous runs | This run (birch + kodama) |
|---|---|---|
| **Card** | RTX 3090 **Founders Edition** | RTX 3090, third-party (non-FE) board |
| **Power limit** | Restricted to **250 W** | Unrestricted, **400 W** |
| **Max board power** | Lower (FE ceiling) | Higher than the FE |

Everything else — the ComfyUI server, the workflows, the seeds policy, the
warm-up discipline — was unchanged. The only variable that moved was the GPU and
its power budget. So the timing shift below is a clean read on **what ~60% more
watts (and a higher ceiling) buys you.**

## Method

- **Metric:** `generation_seconds` from each result's `metadata.json` (wall-clock
  for a single render, cold-start excluded — the runner fires a discarded warm-up
  per workflow before timing anything).
- **"250 W avg":** mean over the **27** prompts each model was run on under the
  restricted Founders Edition.
- **"400 W":** the two new prompts — `birch_branch` and `kodama_forest_spirit` —
  run on the unrestricted card, plus their average.
- **Change:** the 400 W average versus the 250 W average, per model.

## Results

| Workflow | 250 W avg (s) | n | 400 W birch (s) | 400 W kodama (s) | 400 W avg (s) | Change |
|---|--:|--:|--:|--:|--:|--:|
| `Flux_Schnell` | 9.3 | 27 | 8.2 | 8.2 | 8.2 | -11.4% |
| `SD35_large` | 39.7 | 27 | 32.6 | 34.7 | 33.6 | -15.2% |
| `SD35_medium` | 15.5 | 27 | 13.3 | 13.4 | 13.3 | -14.0% |
| `SDXL` | 10.2 | 27 | 8.2 | 9.2 | 8.7 | -14.8% |
| `chroma` | 62.3 | 27 | 53.9 | 54.3 | 54.1 | -13.2% |
| `cyberrealistic_pony` | 10.3 | 27 | 9.2 | 9.2 | 9.2 | -10.2% |
| `flux1_krea_dev` | 26.8 | 27 | 23.4 | 23.4 | 23.4 | -12.5% |
| `flux2_klein_4b` | 26.4 | 27 | 22.5 | 22.6 | 22.5 | -14.7% |
| `flux2_klein_9b` | 53.8 | 27 | 46.1 | 46.8 | 46.5 | -13.6% |
| `flux_dev` | 26.6 | 27 | 23.8 | 23.6 | 23.7 | -10.7% |
| `hassaku_xl` | 10.3 | 27 | 9.2 | 9.2 | 9.2 | -10.4% |
| `illustrious_xl` | 10.3 | 27 | 9.2 | 9.2 | 9.2 | -10.3% |
| `juggernaut_xi` | 10.3 | 27 | 9.2 | 9.2 | 9.2 | -10.4% |
| `krea2_turbo` | 17.4 | 27 | 15.3 | 15.3 | 15.3 | -12.1% |
| `krea2_turbo_llm` | 35.5 | 27 | 27.0 | 25.4 | 26.2 | -26.1% |
| `pony_realism` | 10.3 | 27 | 9.6 | 9.2 | 9.4 | -8.5% |
| `qwen_image` | 58.1 | 27 | 50.0 | 50.8 | 50.4 | -13.3% |
| `sd15` | 2.1 | 27 | 2.5 | 2.1 | 2.3 | +8.8% |
| `sd21` | 3.1 | 27 | 3.1 | 3.1 | 3.1 | +0.1% |
| `sd35_large_turbo` | 6.2 | 27 | 5.2 | 5.4 | 5.3 | -14.0% |
| `z_image` | 54.6 | 27 | 43.8 | 44.8 | 44.3 | -18.8% |
| `z_image_turbo_int8` | 5.6 | 27 | 5.2 | 5.2 | 5.2 | -6.9% |
| **Fleet mean (of per-model averages)** | **22.9** | | | | **19.7** | **-14.3%** |

## What it means

- **The unrestricted 400 W card is faster nearly across the board — about 14%
  quicker on average.** For a compute-bound diffusion workload that tracks: more
  power sustained = higher clocks held for longer = shorter renders.
- **The heavy models gain the most in wall-clock terms.** `z_image` (−10.3s),
  `chroma` (−8.2s), `flux2_klein_9b` (−7.3s) and `qwen_image` (−7.7s) each shed
  the better part of a coffee sip. The bigger the compute bill, the more the extra
  watts pay off. `krea2_turbo_llm` is the proportional champion at **−26%**.
- **The tiny/turbo models barely move, and that's expected.** `sd15` (2.1s),
  `sd21` (3.1s), `z_image_turbo_int8` (5.6s) are so short that fixed per-render
  overhead (scheduling, VAE decode, I/O) dominates the actual GPU crunch — there's
  little sustained compute for extra power to accelerate. `sd15`'s apparent **+8.8%**
  is a swing of ~0.2s on a 2-second render: noise, not a regression.

## Caveats — read before quoting these numbers

- **Sample sizes differ.** The 250 W column is a 27-prompt average; the 400 W
  column is **two** renders per model. Small-n on the new side, so treat the
  per-model deltas as indicative, not precise.
- **Prompt content is confounded with the hardware change.** The old and new
  timings use *different prompts*. In practice render time is driven by
  steps/resolution/model rather than prompt wording, and the consistent ~10–15%
  drop across almost every model points squarely at the hardware — but this is not
  a strict like-for-like.
- **To make it airtight:** `python3 run.py --force` a handful of the *old* prompts
  on the 400 W card and compare identical prompt+seed pairs across the two power
  limits. Until then, the honest headline is: *the unrestricted card is clearly
  faster, by roughly 14% on the fleet mean, most of it on the heavy models.*

## Reproducing this table

Timings live in `results/<workflow>/<prompt>/metadata.json` under
`generation_seconds`. The figures above were aggregated straight from those files;
re-run the aggregation any time the results change.
