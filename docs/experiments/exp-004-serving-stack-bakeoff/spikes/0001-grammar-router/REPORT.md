# Spike 0001 — Grammar-constrained router: guaranteed-valid ≠ correct

**Question:** Does JSON-schema-constrained decoding on llama.cpp fix the
LLM router? exp-005 measured 8–47% parse-fallback across every model; the
schema (with intent↔agent consistency encoded as `oneOf` const-pairs)
makes invalid output *impossible*. Expectation: fallback → 0%, accuracy
roughly unchanged, modest latency cost.

**Answer: fallback → 0% and latency *halved* — but accuracy dropped 6–10
points. The constraint is a strict loss for routing accuracy.** The
expectation was wrong in the most instructive way.

## Setup

llama-server (Homebrew, b-latest) reading **Ollama's own GGUF blobs**
(zero re-quantization drift), `--jinja -c 2048`, port 8088, temp 0.1,
max 256 tokens — production router sampling. Same golden set, same
vendored parser/grader as exp-005. A/B on identical server + weights:
schema-constrained vs unconstrained.

## Results (77-case golden set)

| Config | Accuracy | clear | adversarial | p50 | Fallback |
|---|---|---|---|---|---|
| keyword baseline (exp-005) | **88.3%** | 100% | 43% | ~0ms | — |
| granite4, unconstrained | 84.4% | 90% | 57% | 293ms | 18% |
| granite4, **schema** | 77.9% | 85% | 43% | **170ms** | **0%** |
| llama3.2:3b, unconstrained | 74.0% | 78% | 57% | 253ms | 27% |
| llama3.2:3b, **schema** | 63.6% | 72% | 14% | **159ms** | **0%** |

Cross-engine sanity: unconstrained llama.cpp ≈ Ollama on the same weights
(granite4 84.4% vs 83.8 ± 1.7; llama3.2 74.0% vs 75.3%) — same engine
underneath, as expected. llama.cpp is moderately faster (253–293ms vs
301–359ms) and the constrained runs are faster still (the schema forces
minimal output — no preamble tokens to generate).

## The finding: the fallback was never a crutch — it's an ensemble

Removing parse failures removed the *rescue path*, and the rescue path
was doing quiet, high-quality work. When an unconstrained model rambles,
emits bad JSON, or picks an inconsistent pair, the keyword classifier
answers instead — and the keyword classifier is *good* (88.3%). The
schema converts every would-have-failed case into a **forced commitment**
by a model whose unassisted judgment is measurably worse (63.6–77.9%).

In ensemble terms: `LLM + keyword-on-failure` is a two-member ensemble
where failure-to-parse acts as a (crude but real) confidence signal.
Constrained decoding deletes the signal. Schema-constrained granite4 is
granite4 *alone*; unconstrained granite4 was granite4 *plus* the regex
table covering its confused cases.

Corollary worth keeping: **exp-005's "fallback impersonates accuracy"
finding has a flip side** — fallback also *manufactures* accuracy. Both
framings are true; what's dishonest is only reporting the blended number
without the rate.

## Secondary observations

1. **Constrained decoding is fast.** 159–170ms p50 — the fastest LLM
   routing measured in this whole program, ~2× Ollama's p50 on the same
   weights, because the schema eliminates every non-JSON token.
2. **Adversarial cases suffer most under constraint** (llama3.2: 57% →
   14%): exactly the cases where the model would have hedged into a parse
   failure now get a confident wrong pair.
3. **Ollama's blobs serve directly in llama-server** — no re-download,
   no re-quantization. The two stacks can share one model store.

## Verdict input (per exp-004 criteria)

For the **router tier**: REJECT. The criterion allowed "eliminates a
failure class at ≤1.5× latency" — parse-failure is eliminated at *0.6×*
latency, but the tier's deciding metric is accuracy, and accuracy fell
6–10 points further below the keyword baseline. Schema-constrained
decoding remains interesting for tiers where output *shape* matters more
than marginal judgment (tool-argument emission, structured extraction) —
that's spike 2+ territory.
