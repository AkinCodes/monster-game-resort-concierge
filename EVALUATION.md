# Evaluation & Ablation Studies

Quantitative evaluation of the Monster Game Resort Concierge across retrieval quality, conversation memory, hallucination detection, and cost.

---

## Retrieval Ablation

How much does each retrieval stage contribute? The table below isolates the impact of BM25, dense vectors, fusion, and cross-encoder reranking on the 8-query evaluation set.

| Config | MRR@5 | Precision@5 | Latency (ms) |
|--------|-------|-------------|---------------|
| BM25-only | Pending | Pending | Pending |
| Dense-only (ChromaDB) | Pending | Pending | Pending |
| Hybrid (BM25 + Dense + RRF) | Pending | Pending | Pending |
| Hybrid + Cross-Encoder Reranker | Pending | Pending | Pending |

> Run `python scripts/ablation_retrieval.py` to reproduce.

**What to look for:** BM25-only should win on exact hotel name queries (e.g., "Vampire Manor amenities") but lose on semantic queries (e.g., "somewhere relaxing with a spa"). Dense-only should show the inverse. Hybrid + Reranker should dominate both, at the cost of ~50ms additional latency.

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
- **No prompt injection defense.** Input sanitization strips HTML/script tags, but adversarial prompt attacks (e.g., "ignore previous instructions and...") are not actively detected or blocked.
- **Summarization is lossy.** The auto-summarization at 12 messages compresses context, which means specific details from early in a conversation (allergies, room preferences, accessibility needs) can be lost.
- **Eval harness tool-use pass rate is 0%.** Tool selection accuracy is 80%, but end-to-end tool execution in the eval harness fails consistently due to mock/integration boundary issues. This needs investigation.
- **Single-instance SQLite by default.** Cannot horizontally scale writes without switching to PostgreSQL.
- **Rate limiting is global, not per-user.** All clients share the same quota, so one heavy user can starve others.
