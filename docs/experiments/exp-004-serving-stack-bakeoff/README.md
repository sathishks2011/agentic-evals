# exp-004 — Serving-stack bake-off: Ollama vs llama.cpp vs MLX, per tier

> Numbering note: planned before exp-005 but executed after it — exp-005
> produced the routing golden set and baselines this experiment reuses.

## Claim

IRIS serves every tier through Ollama. The exp-001 series measured strong
results on MLX (TurboQuant KV compression, 100+ tok/s on 30–35B MoE), and
raw llama.cpp exposes capabilities Ollama hides — most notably
**grammar/JSON-schema-constrained decoding**, which could structurally
eliminate the router parse-fallback problem exp-005 measured at 8–47%
across every model. The folk claim: "just switch the serving stack and
everything gets better."

**Thesis:** *For at least one IRIS tier workload, an alternative serving
stack (raw llama.cpp or MLX) beats Ollama on the tier's deciding metric
(accuracy × latency × memory, weighted per tier) by enough to justify the
operational change — measured on IRIS's real workloads, not synthetic
benchmarks.*

The output is a per-tier serving decision with evidence, not a wholesale
migration verdict.

## Fixed setup

| Item | Value |
|---|---|
| Hardware | Apple Silicon (M4 Max, 36 GB), same box as exp-001/002/003/005 |
| Stacks | Ollama 0.30.7 (baseline, measured in exp-005), llama.cpp (`llama-server`, Homebrew), MLX (`mlx_lm` ≥0.31) |
| Models | Shared weights where possible — llama.cpp reads Ollama's GGUF blobs directly (no re-quantization drift); MLX uses mlx-community quants of the same models (noted as a quantization confound) |
| Workloads | exp-005 routing golden set (77 cases); tool-calling task (exp-001 harness); email-summary task; triage corpus (project-iris) |
| Sampling | Production tier settings per workload (router: temp 0.1, 256 out) |

## Variations / spikes

1. **Grammar-constrained router (llama.cpp)** — JSON-schema-constrained
   decoding with the intent↔agent consistency guard *encoded in the schema*
   (valid pairs as `oneOf` consts). Does parse-fallback go to 0%, what does
   accuracy do without the fallback crutch, and what does constraint cost
   in latency? Models: llama3.2:3b (production router), granite4 (best
   exp-005 LLM).
2. **Same-model cross-stack** — granite4 / qwen2.5:7b on Ollama vs
   llama.cpp vs MLX: routing + summary accuracy, prefill/decode tok/s,
   peak memory.
3. **The cliff rule in-harness** — TurboQuant buffer rule on MLX serving
   IRIS-shaped prompts: does exp-001's recommendation survive contact with
   the production workload?
4. **Operability** — model-swap latency, multi-tier serving topology, and
   failure behavior per stack (notes + measurements, not vibes).

## Expected range (priors)

- Spike 1: fallback 0% by construction; accuracy within ±5 points of the
  unconstrained score (constrained decoding can help — no invalid tokens —
  or hurt — forced commitment); latency overhead 0–30%.
- Spike 2: MLX prefill faster on Apple Silicon; decode within ±20%;
  memory comparable at same quant width.
- Spike 3: cliff position shifts with prompt structure; rule survives
  with margin or needs a new constant.

## Metrics & outputs

Per stack × model × workload: accuracy (graded), p50/p95 latency,
prefill/decode tok/s where exposed, peak memory, fallback rate, and
qualitative ops notes. Outputs: `results/` JSONL + leaderboard, spike
REPORTs, consolidated REPORT.md, RECOMMENDATIONS.md with the per-tier
serving decision for `llm_tiers.yaml`.

## Iteration budget

5 spikes (4 planned + 1 contingency).

## Success / Reject criteria

- **ACCEPT (per tier)** when an alternative stack beats Ollama on the
  tier's deciding metric by ≥10% (or eliminates a failure class outright,
  e.g. parse-fallback → 0% at ≤1.5× latency) with n≥3 on the headline.
- **REJECT (per tier)** otherwise — Ollama stays for that tier.

## Stop conditions

All four planned spikes decided, or budget exhausted, or a stack proves
inoperable for multi-tier serving (documented, then dropped).
