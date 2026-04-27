# Evaluation & Ablation Studies

Quantitative evaluation of the Monster Game Resort Concierge across retrieval quality, conversation memory, hallucination detection, and cost.

---

## Retrieval Quality (Ground Truth Evaluation)

13 queries evaluated against a ground truth answer key (`evals/retrieval_ground_truth.json`). Each query is sent through the retrieval pipeline and checked: did the retrieved chunks contain the expected snippets?

**Live mode (real AdvancedRAG pipeline — BM25 + dense + cross-encoder reranker):**

| Metric | Score |
|--------|-------|
| MRR | 0.756 |
| Recall@3 | 76.9% |
| Recall@10 | 78.5% |
| Precision@3 | 46.2% |

11 of 13 queries find the correct answer in position 1 or 2. Two queries fail completely (Werewolf spa, Frankenstein dining) — both are amenity lookups where the chunker splits the relevant section across chunk boundaries. Fix path: parent-document retrieval or overlapping chunk windows.

```bash
# Run against live RAG pipeline
python evals/eval_retrieval.py --live

# Run against mock corpus (fast, reproducible, no ML deps)
python evals/eval_retrieval.py

# Compare against previous run
python evals/eval_retrieval.py --compare-last
```

---

## Retrieval Ablation

How much does each retrieval stage contribute? Isolating BM25, dense vectors, fusion, and reranking.

| Config | MRR@5 | Precision@5 | Latency (ms) |
|--------|-------|-------------|---------------|
| BM25-only | 0.42 | 0.15 | 0.1 |
| Dense-only (ChromaDB) | 0.75 | 0.30 | 9.0 |
| Hybrid (BM25 + Dense + RRF) | 0.58 | 0.30 | 10.2 |
| Hybrid + Cross-Encoder Reranker | 0.67 | 0.33 | 1,087 |

> Run `python scripts/ablation_retrieval.py` to reproduce.

**Key finding:** Dense-only achieves the best MRR (0.75) on this small corpus. The cross-encoder reranker adds ~1s latency for marginal precision gain (+0.03). On a larger, noisier corpus the reranker's benefit would be more pronounced.

---

## Conversation Memory

Results from context management experiments (`scripts/test_context_management.py`).

### Token Scaling

Prompt tokens scale approximately **12.5x** from turn 0 to turn 20. At turn 0 the prompt is ~95 tokens; by turn 20 it is ~1,190 tokens. This is the primary driver of per-conversation cost growth.

### Window Size vs. Information Retention

| Window Strategy | Retains Dietary Restrictions (msg 1)? | Retains Room Preference (msg 3)? | Retains Name (msg 0)? |
|-----------------|---------------------------------------|----------------------------------|-----------------------|
| Last 2 messages | No | Yes | No |
| Last 5 messages | Depends on turn | Yes | Depends on turn |
| Full history (10 messages) | Yes | Yes | Yes |

**Key finding:** A sliding window of 2 loses dietary restrictions mentioned early in the conversation. This is a real failure mode for a concierge that takes food orders. The auto-summarization approach (below) is the mitigation.

### Auto-Summarization

- **Trigger:** Fires at 12 messages in a conversation.
- **Mechanism:** LLM-based summarization of the oldest messages into a rolling summary. Falls back to regex extraction if the LLM call fails.
- **Trade-off:** Summarization compresses detail. A guest who mentioned a shellfish allergy in message 2 may lose that detail if the summary is lossy. The threshold of 12 balances token cost against information loss.

---

## Hallucination Detection

Every response is scored by three signals, weighted and combined into a confidence score.

### Signal Weights

| Signal | Weight | Method |
|--------|--------|--------|
| Semantic similarity | 50% | Cosine similarity between response and retrieved context using `all-MiniLM-L6-v2` |
| Token overlap | 30% | Token-level intersection ratio (response tokens vs. context tokens) |
| Source attribution | 20% | Sentence-level grounding check: what fraction of response sentences have >= 30% overlap with a source chunk |

### Confidence Thresholds

| Level | Threshold | Interpretation |
|-------|-----------|----------------|
| HIGH | >= 0.7 | Response is well-grounded in retrieved context |
| MEDIUM | >= 0.4 | Partially grounded; some claims may not be in the knowledge base |
| LOW | < 0.4 | Significant portions of the response are not supported by retrieved context |

### Where It Fails

- **Paraphrased facts:** If the LLM rephrases a fact heavily, token overlap drops even though the information is correct. Semantic similarity partially compensates but not fully.
- **Multi-hop reasoning:** If the answer requires combining facts from two different chunks, no single chunk scores high on attribution, pulling the score down.
- **Chitchat responses:** Greetings and small talk have no corresponding knowledge base content, so they always score LOW. The system does not distinguish "no context needed" from "hallucinating."

---

## Cost Analysis

Estimated cost per 10-turn conversation by model, assuming average token usage observed in testing.

| Model | Est. Input Tokens (10 turns) | Est. Output Tokens (10 turns) | Est. Cost (USD) |
|-------|------------------------------|-------------------------------|-----------------|
| gpt-4o-mini | Pending | Pending | Pending |
| gpt-4o | Pending | Pending | Pending |
| gpt-4-turbo | Pending | Pending | Pending |
| claude-sonnet-4 | Pending | Pending | Pending |
| claude-3-haiku | Pending | Pending | Pending |
| llama3 (local) | Pending | Pending | $0.00 |

> Token counts depend on conversation complexity, number of tool calls, and whether summarization triggers. The estimates above use averages from the eval harness runs.

---

## Limitations & Known Issues

- **In-memory traces only.** Hallucination scores and retrieval metadata are returned in the API response but not persisted to a database or logging backend. There is no way to retroactively audit past responses.
- **No persistent tracing.** No integration with LangSmith, Langfuse, or any trace store. Debugging a bad response from yesterday means re-running the query.
- **Streaming is incomplete.** The `/chat/stream` endpoint exists but hallucination detection runs after full generation, so confidence scores are only available at the end of the stream, not incrementally.
- **No online learning.** The knowledge base is static. Guest corrections ("actually, the Mummy Resort pool closes at 8pm, not 10pm") are not fed back into the retrieval index.
- **Hallucination detector is heuristic.** Token overlap + semantic similarity is not a trained classifier. It works well for high-confidence and low-confidence cases but is unreliable in the 0.4-0.7 range where it matters most.
- **Guardrails are rule-based.** InputGuard detects 13 injection patterns and redacts PII, but it's regex-based, not ML-based. Sophisticated adversarial attacks could bypass it.
- **Summarization is lossy.** The auto-summarization at 12 messages compresses context, which means specific details from early in a conversation (allergies, room preferences, accessibility needs) can be lost.
- **Eval harness tool-use pass rate is 0%.** Tool selection accuracy is 80%, but end-to-end tool execution in the eval harness fails consistently due to mock/integration boundary issues. This needs investigation.
- **Single-instance SQLite by default.** Cannot horizontally scale writes without switching to PostgreSQL.
- **Rate limiting is global, not per-user.** All clients share the same quota, so one heavy user can starve others.
