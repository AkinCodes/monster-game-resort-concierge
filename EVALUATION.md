# Evaluation & Ablation Studies

Evaluation of the Monster Game Resort Concierge: retrieval quality, hallucination detection and the CI eval check.

> **Status:** the retrieval ablation and the hallucination-detector experiments are real measurements with saved reports. There's no end-to-end eval of the real concierge yet: the eval harness and the DeepEval CI check both run on a mock pipeline. The conversation-memory experiments exist as a script, but their results aren't saved. The cost analysis is a simulation (see [Cost Analysis](#cost-analysis)).

---

## Retrieval Quality (Ground Truth Evaluation)

13 queries are evaluated against a ground-truth answer key (`evals/retrieval_ground_truth.json`). Each query goes through the retrieval pipeline, and the check is whether the retrieved chunks contain the expected snippets.

The saved, real measurement is the [Retrieval Ablation](#retrieval-ablation) below (`reports/retrieval_ablation.json`). For the full pipeline (BM25 + dense candidates, reranked by a cross-encoder): MRR 0.756 and Precision@5 0.308.

Per query, 9 of 13 rank a relevant chunk first and 10 of 13 have one in the top 2. Two queries find nothing relevant (Werewolf spa, Frankenstein dining). Both are amenity lookups, and a likely cause, not yet confirmed, is the chunker splitting the relevant section across chunk boundaries. Fix path: parent-document retrieval or overlapping chunk windows.

```bash
# Run against the live RAG pipeline (overwrites reports/retrieval_metrics.json; the committed copy is an older 8-query mock run)
python evals/eval_retrieval.py --live

# Run against the mock corpus (fast, reproducible, no ML deps; tests the metric code, not the pipeline)
python evals/eval_retrieval.py

# Compare against the previous run
python evals/eval_retrieval.py --compare-last
```

---

## Retrieval Ablation

How much does each retrieval stage contribute? BM25, dense vectors, fusion and reranking, isolated on the same 13 queries (`scripts/ablation_retrieval.py`, `reports/retrieval_ablation.json`):

| Config | MRR | Precision@5 | Avg Latency (ms) |
|--------|-----|-------------|------------------|
| BM25 only | 0.449 | 0.169 | 0.1 |
| Dense only | 0.718 | 0.308 | 7.9 |
| Hybrid (BM25 + dense, weighted RRF, no reranker) | 0.718 | **0.338** | 8.4 |
| Full pipeline (BM25 + dense candidates, cross-encoder reranker) | **0.756** | 0.308 | 736.9 |

> Run `python scripts/ablation_retrieval.py` to reproduce. Measured on CPU (hardware not recorded).

**Key finding:** the full pipeline has the best MRR, but only by +0.04 over dense-only. With 13 queries, that gap comes down to 4 of them and isn't significance-tested. It's also ~90x slower. Hybrid without the reranker matches dense on MRR and has the best Precision@5 at single-digit milliseconds, which makes it the best accuracy/latency point on this small corpus. The reranker should help more on a larger, noisier corpus (not measured).

An earlier 8-query run of the original config (`bm25_weight=0.4`, RRF-truncated candidates fed to the reranker, cold cross-encoder inside the timed loop) was slower and had a lower MRR than dense-only. What changed is written up in [`docs/blog/reranker-war-story.md`](docs/blog/reranker-war-story.md).

---

## Conversation Memory

`scripts/test_context_management.py` runs context-management experiments: with vs without history, prompt-token growth over a conversation, and how much a short window forgets (for example, a dietary restriction mentioned early). It needs an OpenAI key and only prints to the terminal. No output is saved yet, so no results are published here.

### Auto-Summarisation (how it works today)

- **Trigger:** fires at 12 messages in a conversation.
- **Mechanism:** an LLM summary if `MRC_OPENAI_API_KEY` or `OPENAI_API_KEY` is set, otherwise a regex summary. All 12 messages are then deleted and the summary is saved in the database, keeping the last 5 summaries. Later planner, knowledge, clarify and chitchat prompts get it, after a prompt-injection check, plus up to the latest 5 messages since then.
- **Trade-off:** a summary is lossy. The regex fallback keeps only intents and names, so a detail like a shellfish allergy in message 2 can still be lost after a clear.

---

## Hallucination Detection

A two-tier system on every knowledge (RAG) response: fast heuristic scoring first, then NLI claim verification when the heuristic's confidence isn't HIGH.

### Tier 1: Heuristic Scoring

**Intent Pre-Checks (no ML, runs first):**

| Check | Condition | Result |
|-------|-----------|--------|
| Refusal detection | Response contains "I don't know", "I cannot find", etc. | HIGH (1.0): honest uncertainty is safe |
| Chitchat detection | Short reply with no real context | MEDIUM (0.5): grounding not applicable |

If neither pre-check fires, the response goes through the full scoring pipeline.

**Signal Weights:**

| Signal | Weight | Method |
|--------|--------|--------|
| Source attribution | 60% | Sentence-level grounding: fraction of response claims with >= 30% token overlap against the pooled tokens of all retrieved chunks |
| Token overlap | 20% | Token-level intersection ratio (response tokens vs. context tokens) |
| Semantic similarity | 20% | Max cosine similarity between response and context embeddings (`all-MiniLM-L6-v2`) |

Attribution is weighted highest because it measures whether each claim traces back to a source, not just whether the response "sounds like" the context.

**Confidence Thresholds:**

| Level | Threshold | Interpretation |
|-------|-----------|----------------|
| HIGH | >= 0.7 | Response is well-grounded in retrieved context |
| MEDIUM | >= 0.4 | Partially grounded; some claims may not be in the knowledge base |
| LOW | < 0.4 | Significant portions of the response are not supported by retrieved context |

### Tier 2: NLI Claim Verification

Claim-level entailment checking via `cross-encoder/nli-deberta-v3-small`. This layer targets the failure mode where a response uses the right vocabulary but states wrong facts.

1. The response is split into atomic claims (abbreviation-safe sentence splitting + clause conjunction splitting on ", and/but/yet...")
2. Each claim is checked against every context chunk via NLI (entailment / contradiction / neutral)
3. The best entailment score across all contexts decides the verdict per claim

**Output:** `ClaimVerification` with per-claim verdicts (SUPPORTED / NOT_SUPPORTED / CONTRADICTED), grounding ratio and latency.

The orchestrator runs it automatically when Tier 1 isn't HIGH. It can also be called directly via `verify_claims()`, or together with Tier 1 via `score_response_with_claims()`. Its latency isn't measured yet.

### Experiment Results (Before vs. After Upgrade)

| Experiment | Old Score | Old Level | New Score | New Level | Fix |
|------------|-----------|-----------|-----------|-----------|-----|
| Faithful Paraphrase | 0.69 | MEDIUM | 0.83 | HIGH | Attribution reweight (60%) |
| Confident Fabrication | 0.29 | LOW | 0.13 | LOW | Already caught |
| Style Mimic (wrong facts) | 0.56 | MEDIUM | 0.58 | MEDIUM | Known gap: the NLI tier is meant to catch it (not yet measured) |
| Honest Refusal | 0.13 | LOW | 1.00 | HIGH | Refusal pre-check |
| Pure Chitchat | 0.00 | LOW | 0.50 | MEDIUM | Chitchat pre-check |

The "new" scores match `reports/hallucination_history.jsonl` (30/04/2026, 4 of 5 at the expected level). The "old" scores are from before the reweight, and that run wasn't saved. 3 of the 4 original failures are fixed (Style Mimic is still MEDIUM, expected LOW). Run `python -m evals.hallucination_experiments` to reproduce.

### Remaining Gaps

- **Style mimic (Exp 3):** factually wrong responses that reuse context vocabulary still score MEDIUM on the heuristic. The NLI tier is the intended mitigation (it checks entailment, not word overlap), but its effect on this case isn't measured yet.
- **Multi-hop reasoning:** answers combining facts from several chunks can score lower on semantic similarity (max over single chunks) and fail NLI (each claim is checked against one chunk at a time). Attribution pools all chunks, so it isn't affected.
- **NLI latency:** claim verification runs automatically whenever Tier 1 isn't HIGH, which adds inference time (not measured).

---

## CI Eval Check (DeepEval)

An offline DeepEval check (`tests/test_evals_deepeval.py`, workflow `.github/workflows/evals.yml`) wraps the 20 cases in `data/eval_cases.json` as DeepEval `LLMTestCase`s and asserts metric thresholds.

**What it really tests:** the responses and contexts come from the deterministic `MockPipelineRunner` in `scripts/eval_harness.py`, not the real concierge. The only real app code it runs is the hallucination detector's heuristic scorer (`app/validation/hallucination.py`), wrapped as a custom DeepEval `BaseMetric`. So it catches changes to that scorer or to the eval cases, not regressions in retrieval, prompts, the planner or tools. Running it against the real pipeline is the next step.

The optional LLM-as-judge metrics (`AnswerRelevancyMetric`, `FaithfulnessMetric`) are gated behind `RUN_LIVE_EVALS=1` + `OPENAI_API_KEY` and are skipped otherwise.

### What it checks (offline, runs on pushes to main/develop and PRs to main)

| Metric | Type | Scope | Floor | Baseline (mock run) |
|--------|------|-------|-------|---------------------|
| Hallucination grounding | Custom `BaseMetric` (heuristic scorer) | per-case | ≥ 0.55 | min 0.620 |
| Hallucination grounding (mean) | Custom | aggregate | ≥ 0.62 | mean 0.682 |
| Keyword coverage | Custom `BaseMetric` | per-case | ≥ 0.30 | min 0.333 |
| Keyword coverage (mean) | Custom | aggregate | ≥ 0.75 | mean 0.883 |
| Tool-selection accuracy (the mock's keyword table, not the planner) | Aggregate assertion | cases with an expected tool (15 of 20) | ≥ 0.75 | 0.800 (12/15) |

Floors are calibrated from a run of the deterministic `MockPipelineRunner` and set **below** that baseline so ordinary scoring noise doesn't trip the check. Raise them (never silently lower) once the check runs on the real pipeline.

### Live LLM-judge check (opt-in)

| Metric | Threshold |
|--------|-----------|
| `AnswerRelevancyMetric` | ≥ 0.5 |
| `FaithfulnessMetric` | ≥ 0.5 |

Runs only when `RUN_LIVE_EVALS=1` and a real `OPENAI_API_KEY` are present. In CI this is a separate `live-evals` job keyed on the `OPENAI_API_KEY` secret. It no-ops (exits 0) when the secret is absent, and no secret is configured, so the live LLM-judge tests have never run in CI. Even when enabled, it would score the mock's responses.

### Run locally

```bash
# Offline check (no API key needed): this is what CI runs by default
pytest tests/test_evals_deepeval.py -v -o addopts="" -p no:cacheprovider

# Live LLM-judge check (needs a real key; costs money)
RUN_LIVE_EVALS=1 OPENAI_API_KEY=sk-... \
  pytest tests/test_evals_deepeval.py -v -o addopts="" -k live
```

> The `-o addopts=""` override disables the repo-wide coverage/`--maxfail=1` addopts so the eval suite runs standalone. Expected offline result: **23 passed, 20 skipped** (the 20 skips are the API-key-gated live-judge cases).

---

## Cost Analysis

`scripts/cost_analysis.py` estimates conversation cost from simulated token counts (prompt 200 tokens + 40 per turn, 100 completion tokens per turn) and the prices in `configs/model_pricing.yaml`. One run is saved in `reports/cost_analysis_history.jsonl` (30/04/2026): a 10-turn conversation comes to about $0.0195 on gpt-4o and $0.0012 on gpt-4o-mini. Real per-conversation usage isn't measured yet.

---

## Limitations & Known Issues

- **Traces are short-lived.** LLM call traces are kept in memory only (last 100 calls). Per-turn metadata (intent, confidence, sources, tool calls) is saved for the Session Inspector, but it's cleared with the history every 12 messages. There's no integration with a trace store such as LangSmith or Langfuse.
- **No streaming endpoint.** There's an SSE client (`app/core/stream_client.py`) but no `/chat/stream` route.
- **No online learning.** The knowledge base is static. Guest corrections ("actually, the Mummy Resort pool closes at 8pm, not 10pm") aren't fed back into the retrieval index.
- **Heuristic detector has a known gap.** Tier 1 measures lexical grounding, not factual accuracy, so responses that reuse context vocabulary but state wrong facts score MEDIUM. Tier 2 NLI runs automatically in that case; how well it catches them isn't measured yet.
- **Guardrails are rule-based.** InputGuard uses 20 prompt-injection patterns and redacts PII with regexes, not an ML model. Sophisticated adversarial attacks could bypass it.
- **Summarisation is lossy.** History is cleared every 12 messages and carried forward only as a short summary, so early details (allergies, room preferences, accessibility needs) can be lost, especially with the regex fallback.
- **Eval harness tool-use pass rate is 0%.** All 6 tool-use cases fail the retrieval-relevance ≥ 0.3 rule, which applies to every category whenever contexts are returned (`scripts/eval_harness.py:325`) and which the mock's fixed contexts fail. Three also get the wrong tool from the mock: the BK-001 lookup gets `book_room`, the coffin-bed booking gets no tool, and one case expects a `cancel_booking` tool that doesn't exist. Its 80% tool-selection figure is the mock's keyword table, not the planner.
- **Single-instance SQLite by default.** It can't scale writes horizontally without switching to PostgreSQL.
- **Rate limiting is per tool only.** The per-tool limiter (50 calls/min, in memory) is shared by all users, so one heavy user can starve others. HTTP rate limiting (SlowAPI) is configured but not active.
