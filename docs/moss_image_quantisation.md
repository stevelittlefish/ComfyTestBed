# MOSS-Image — bf16 vs int8

A field report from the ship's computer. The same model in two quantisations,
flown side by side to find out whether the heavier one earns its keep.
It didn't. The bf16 workflow and its images have been jettisoned. Only int8
(`moss_image_int8`) remains aboard.

## The two variants

| | `moss_image_bf16` (removed) | `moss_image_int8` (kept) |
|---|---|---|
| **UNet** | `moss_image_sft_bf16.safetensors` | `moss_image_sft_int8_convrot.safetensors` |

That was the only difference. Both workflows used the same text encoder
(`qwen3.5_9b_w4a8_gptq`), VAE, sampler (`er_sde` / `simple`, 25 steps, cfg 2.5),
negative prompt and resolution (1 MP square). Both ran the prompt through the same
LLM ghostwriter, with its sampling seed pinned at 0.

## Method

- **Seeds:** run with `--seed-per-prompt`, so each prompt's seed was derived from
  its text. All **53** prompt pairs had matching seeds, and the two models started
  from identical noise.
- **Metric:** `generation_seconds` from each result's `metadata.json`. That's the
  wall-clock time for one render. Each workflow fired a discarded warm-up render
  first, so model loading isn't counted. These times include the ghostwriter's
  LLM pass, which is the same for both variants.

## Speed

| | bf16 | int8 |
|---|---|---|
| **Mean** | 43.2 s | 19.4 s |
| **Median** | 43.1 s | 19.4 s |
| **Fastest** | 42.5 s | 18.9 s |
| **Slowest** | 43.8 s | 19.9 s |
| **Total, 53 renders** | 2288 s (~38 min) | 1030 s (~17 min) |

bf16 was **2.22×** slower on average. Per prompt, the ratio stayed between 2.18× and
2.26×, so the gap held steady for every prompt.

## Quality

The Captain compared the 53 pairs by eye. They were **mostly the same**. bf16 was
sometimes slightly better, and slightly more accurate to the prompt, but **never by a
significant margin**.

## Verdict

bf16 took more than twice as long for a difference you have to hunt for. int8 keeps
its berth. To recover the bf16 workflow, look in git history: it was imported in
`0a24299`.
