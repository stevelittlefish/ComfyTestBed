# GPU Power Comparison — RTX 3090, three power/board configurations

A field report from the ship's computer. This documents changes in the render
core's **hardware and power budget**, not its software — and what they did to our
timings.

## The three rigs

| | Rig A | Rig B | Rig C |
|---|---|---|---|
| **Card** | MSI GeForce RTX 3090 **Gaming X Trio** | RTX 3090 **Founders Edition** | MSI GeForce RTX 3090 **Gaming X Trio** |
| **Power limit** | Restricted to **250 W** | Unrestricted, **400 W** | Unrestricted, **380 W** |
| **Board class** | Third-party (aftermarket cooler) | Reference (Founders Edition) | Third-party (aftermarket cooler) |

Rig A and Rig C are the **same physical card** — the MSI Trio — first strangled to
250 W, then let off the leash. Rig B is the Founders Edition running flat out.
Everything else — the ComfyUI server, the workflows, the seeds policy, the warm-up
discipline — was unchanged across all three. The only variables that moved were the
GPU and its power budget.

**Why the two "unrestricted" ceilings differ (400 W vs 380 W):** there is no single
"maximum" for an RTX 3090. Each board partner ships its own VBIOS with its own power
target and slider limit. The Founders Edition tops out at 400 W here; MSI's Gaming X
Trio VBIOS tops out at 380 W. "Unrestricted" just means "as high as that particular
board's firmware will allow" — and that figure is set by the vendor, not the GPU die.

## Method

- **Metric:** `generation_seconds` from each result's `metadata.json` (wall-clock
  for a single render, cold-start excluded — the runner fires a discarded warm-up
  per workflow before timing anything).
- **Rig A (250 W Trio):** mean over **27** prompts.
- **Rig B (400 W FE):** mean over **8** prompts (`birch_branch`,
  `kodama_forest_spirit`, and the character batch: `knight_plate_armour`,
  `space_marine_soldier`, `demolition_robot`, `mushroom_forest_god_head`,
  `eyeball_creature`, `woodkin_forest_spirit`).
- **Rig C (380 W Trio):** mean over **4** prompts (`colour_binding_objects`,
  `leaping_dog_splash`, `three_animals_riverbank`, `tpose_female_character`).
- **`krea2_turbo_llm` is excluded from the table below** and handled separately —
  see the note after the results. Its per-render time is dominated by an LLM
  prompt-rewrite step, which is text processing, not image generation.

## Results

Times in seconds; lower is faster.

| Workflow | Trio @ 250 W (n=27) | FE @ 400 W (n=8) | Trio @ 380 W (n=4) |
|---|--:|--:|--:|
| `Flux_Schnell` | 9.3 | 8.2 | 8.2 |
| `SD35_large` | 39.7 | 33.8 | 34.2 |
| `SD35_medium` | 15.5 | 13.4 | 13.3 |
| `SDXL` | 10.2 | 9.2 | 9.3 |
| `chroma` | 62.3 | 54.0 | 54.1 |
| `cyberrealistic_pony` | 10.3 | 9.3 | 9.3 |
| `flux1_krea_dev` | 26.8 | 23.5 | 23.5 |
| `flux2_klein_4b` | 26.4 | 22.6 | 22.7 |
| `flux2_klein_9b` | 53.8 | 46.3 | 46.9 |
| `flux_dev` | 26.6 | 23.8 | 23.5 |
| `hassaku_xl` | 10.3 | 9.2 | 9.3 |
| `illustrious_xl` | 10.3 | 9.3 | 9.3 |
| `juggernaut_xi` | 10.3 | 9.3 | 9.3 |
| `krea2_turbo` | 17.4 | 15.4 | 15.4 |
| `pony_realism` | 10.3 | 9.4 | 9.3 |
| `qwen_image` | 58.1 | 50.6 | 51.0 |
| `sd15` | 2.1 | 2.2 | 2.1 |
| `sd21` | 3.1 | 3.2 | 3.1 |
| `sd35_large_turbo` | 6.2 | 5.3 | 5.2 |
| `z_image` | 54.6 | 44.1 | 44.7 |
| `z_image_turbo_int8` | 5.6 | 5.2 | 5.2 |
| **Fleet mean (of per-model averages)** | **22.3** | **19.4** | **19.5** |

## What it means

- **Both unrestricted cards are about 13% faster than the power-restricted one.**
  Fleet mean drops from 22.3 s at 250 W to 19.4 s (FE @ 400 W) and 19.5 s
  (Trio @ 380 W). For a compute-bound diffusion workload that tracks: more power
  sustained = higher clocks held for longer = shorter renders.
- **The two unrestricted rigs are indistinguishable — within 0.4% of each other.**
  Despite the 20 W ceiling gap and the different board (reference vs aftermarket),
  the Founders Edition at 400 W and the Trio at 380 W turn in the same wall-clock.
  Past ~380 W this workload is no longer power-starved; the extra 20 W buys nothing
  measurable.
- **The clean same-card result:** the *very same* MSI Trio, unleashed from 250 W to
  380 W, gains ~13%. Same silicon, same cooler, same everything but the power slider
  — so this delta is a power effect, not a board-lottery effect.
- **The heavy models gain the most in wall-clock terms.** `z_image` (~−10 s),
  `chroma` (~−8 s), `flux2_klein_9b` (~−7 s) and `qwen_image` (~−7 s) each shed the
  better part of a coffee sip when unrestricted. The bigger the compute bill, the
  more the watts pay off — `z_image` leads proportionally at roughly −19%.
- **The tiny/turbo models barely move, and that's expected.** `sd15` (2.1 s),
  `sd21` (3.1 s), `z_image_turbo_int8` (5.2–5.6 s) are so short that fixed
  per-render overhead (scheduling, VAE decode, I/O) dominates the actual GPU crunch.
  Their sub-0.15-second wobbles between rigs are noise, not signal.

## The `krea2_turbo_llm` outlier — measured, not mysterious

| Workflow | Trio @ 250 W (n=27) | FE @ 400 W (n=8) | Trio @ 380 W (n=4) |
|---|--:|--:|--:|
| `krea2_turbo_llm` | 35.5 | 35.9 | 36.0 |

This workflow shows essentially **no power scaling** — flat across all three rigs.
That is not a hardware finding. Before it generates anything, this workflow runs a
local LLM to rewrite the prompt, and that step's duration is set by the LLM (and the
prompt), not by the diffusion GPU load. The rewrite time swamps and masks whatever
the image render is doing. It is excluded from the fleet table above precisely
because it measures something other than image generation; the figures are kept here
for completeness.

## Caveats — read before quoting these numbers

- **Sample sizes differ.** Rig A is a 27-prompt average, Rig B is 8, Rig C is 4.
  Treat the per-model deltas as indicative, not precise — especially Rig C's.
- **Prompt content is confounded with the hardware change.** The three rigs used
  *different prompts*. In practice render time is driven by steps/resolution/model
  rather than prompt wording, and the consistent ~10–15% drop across almost every
  model points squarely at the power budget — but this is not a strict like-for-like.
- **To make it airtight:** `python3 run.py --force` a shared set of prompts on each
  rig and compare identical prompt+seed triples across the three configurations.
  Until then, the honest headline is: *unrestricting the card is worth roughly 13%
  on the fleet mean, most of it on the heavy models, and above ~380 W this workload
  stops caring about extra watts.*

## Reproducing this table

Timings live in `results/<workflow>/<prompt>/metadata.json` under
`generation_seconds`. The figures above were aggregated straight from those files;
re-run the aggregation any time the results change.
