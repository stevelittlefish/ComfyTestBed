# GPU Power Comparison — 3090 @ 250 W vs 3090 @ 400 W

A field report from the ship's computer. This documents a change in the render
core's **hardware**, not its software — and what it did to our timings.

## The two rigs

| | Previous runs | This run (400 W batch) |
|---|---|---|
| **Card** | MSI GeForce RTX 3090 **Gaming X Trio** | RTX 3090 **Founders Edition** |
| **Power limit** | Restricted to **250 W** | Unrestricted, **400 W** |
| **Board class** | Third-party (aftermarket cooler) | Reference (Founders Edition) |

Everything else — the ComfyUI server, the workflows, the seeds policy, the
warm-up discipline — was unchanged. The only variable that moved was the GPU and
its power budget. So the timing shift below is a clean read on **what ~60% more
watts (and a higher ceiling) buys you.**

## Method

- **Metric:** `generation_seconds` from each result's `metadata.json` (wall-clock
  for a single render, cold-start excluded — the runner fires a discarded warm-up
  per workflow before timing anything).
- **"250 W avg":** mean over the **27** prompts each model was run on under the
  restricted MSI Gaming X Trio.
- **"400 W avg":** mean over the **8** prompts run on the unrestricted card —
  `birch_branch` and `kodama_forest_spirit`, plus the latest batch
  (`knight_plate_armour`, `space_marine_soldier`, `demolition_robot`,
  `mushroom_forest_god_head`, `eyeball_creature`, `woodkin_forest_spirit`).
- **Change:** the 400 W average versus the 250 W average, per model.

## Results

| Workflow | 250 W avg (s) | n | 400 W avg (s) | n | Change |
|---|--:|--:|--:|--:|--:|
| `Flux_Schnell` | 9.3 | 27 | 8.2 | 8 | -11.1% |
| `SD35_large` | 39.7 | 27 | 33.8 | 8 | -14.8% |
| `SD35_medium` | 15.5 | 27 | 13.4 | 8 | -13.6% |
| `SDXL` | 10.2 | 27 | 9.2 | 8 | -10.1% |
| `chroma` | 62.3 | 27 | 54.0 | 8 | -13.3% |
| `cyberrealistic_pony` | 10.3 | 27 | 9.3 | 8 | -9.3% |
| `flux1_krea_dev` | 26.8 | 27 | 23.5 | 8 | -12.3% |
| `flux2_klein_4b` | 26.4 | 27 | 22.6 | 8 | -14.4% |
| `flux2_klein_9b` | 53.8 | 27 | 46.3 | 8 | -13.9% |
| `flux_dev` | 26.6 | 27 | 23.8 | 8 | -10.6% |
| `hassaku_xl` | 10.3 | 27 | 9.2 | 8 | -10.8% |
| `illustrious_xl` | 10.3 | 27 | 9.3 | 8 | -9.3% |
| `juggernaut_xi` | 10.3 | 27 | 9.3 | 8 | -9.3% |
| `krea2_turbo` | 17.4 | 27 | 15.4 | 8 | -11.9% |
| `krea2_turbo_llm` | 35.5 | 27 | 35.9 | 8 | +1.3% |
| `pony_realism` | 10.3 | 27 | 9.4 | 8 | -8.7% |
| `qwen_image` | 58.1 | 27 | 50.6 | 8 | -13.0% |
| `sd15` | 2.1 | 27 | 2.2 | 8 | +3.3% |
| `sd21` | 3.1 | 27 | 3.2 | 8 | +1.9% |
| `sd35_large_turbo` | 6.2 | 27 | 5.3 | 8 | -13.4% |
| `z_image` | 54.6 | 27 | 44.1 | 8 | -19.1% |
| `z_image_turbo_int8` | 5.6 | 27 | 5.2 | 8 | -6.7% |
| **Fleet mean (of per-model averages)** | **22.9** | | **20.1** | | **-12.1%** |

## What it means

- **The unrestricted 400 W card is faster nearly across the board — about 12%
  quicker on average.** For a compute-bound diffusion workload that tracks: more
  power sustained = higher clocks held for longer = shorter renders.
- **The heavy models gain the most in wall-clock terms.** `z_image` (−10.5s),
  `chroma` (−8.3s), `flux2_klein_9b` (−7.5s) and `qwen_image` (−7.5s) each shed
  the better part of a coffee sip. The bigger the compute bill, the more the extra
  watts pay off — `z_image` leads the proportional field at **−19%**.
- **`krea2_turbo_llm` is the cautionary tale.** On the old two-prompt sample it
  looked like the champion at −26%; with eight prompts it regressed to **roughly
  flat (+1.3%)**. That model runs an LLM prompt-rewrite step whose duration swings
  wildly with the prompt and has nothing to do with GPU power — the small early
  sample simply caught two fast rewrites. A clean example of why n=2 lies.
- **The tiny/turbo models barely move, and that's expected.** `sd15` (2.1s),
  `sd21` (3.1s), `z_image_turbo_int8` (5.6s) are so short that fixed per-render
  overhead (scheduling, VAE decode, I/O) dominates the actual GPU crunch — there's
  little sustained compute for extra power to accelerate. `sd15`'s **+3.3%** and
  `sd21`'s **+1.9%** are sub-0.1s swings on 2–3 second renders: noise, not
  regressions.

## Caveats — read before quoting these numbers

- **Sample sizes still differ.** The 250 W column is a 27-prompt average; the
  400 W column is now **8** renders per model. Better than the original two, but
  still the smaller side — treat the per-model deltas as indicative, not precise.
- **Prompt content is confounded with the hardware change.** The old and new
  timings use *different prompts*. In practice render time is driven by
  steps/resolution/model rather than prompt wording, and the consistent ~10–15%
  drop across almost every model points squarely at the hardware — but this is not
  a strict like-for-like. (`krea2_turbo_llm` is the exception that proves the rule:
  its per-prompt LLM step makes it genuinely prompt-sensitive.)
- **To make it airtight:** `python3 run.py --force` a handful of the *old* prompts
  on the 400 W card and compare identical prompt+seed pairs across the two power
  limits. Until then, the honest headline is: *the unrestricted card is clearly
  faster, by roughly 12% on the fleet mean, most of it on the heavy models.*

## Reproducing this table

Timings live in `results/<workflow>/<prompt>/metadata.json` under
`generation_seconds`. The figures above were aggregated straight from those files;
re-run the aggregation any time the results change.
