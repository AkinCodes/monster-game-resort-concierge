# Study Notes — retrieval_ground_truth.json

## What is this file?

It's the **answer key** for measuring how good your RAG retrieval is.

When `evals/eval_retrieval.py` runs, it takes each query (e.g., "What are the check-in times?"), sends it through your retrieval pipeline (BM25 + dense + reranker), and checks: **did the retrieved chunks contain these specific snippets?**

## The three fields

- **query** = the test question
- **relevant_snippets** = the phrases that SHOULD appear in the retrieved results
- **source_files** = which knowledge base files contain the answer

## Why it matters

Without this file, you can report "retrieval works" but you can't report "retrieval finds the right answer 75% of the time." It's the difference between **"I built it"** and **"I measured it."** That's exactly what the external reviewer said was missing.

## Metrics it enables

- **MRR** (Mean Reciprocal Rank) — where does the first relevant result appear?
- **Precision@K** — how many of the top K results were relevant?
- **Recall@K** — of all relevant docs, how many did we find?

## The 13 queries

| ID | Query | Type | Files |
|----|-------|------|-------|
| 1 | Check-in/checkout times | Factoid | checkin_checkout.txt, policies.txt |
| 2 | Pet policy | Factoid | policies.txt |
| 3 | Vampire Manor rooms | Factoid | amenities.txt |
| 4 | WiFi password | Factoid | faq.txt, policies.txt |
| 5 | Werewolf spa services | Factoid | amenities.txt |
| 6 | Halloween event | Factoid | seasonal_events.txt |
| 7 | Cancellation policy | Factoid | policies.txt |
| 8 | Castle Frankenstein dining | Factoid | amenities.txt |
| 9 | Zombie B&B booking (non-zombie) | Intent | faq.txt |
| 10 | Mummy Resort spa | Factoid (untested property) | amenities.txt |
| 11 | Romantic Valentine's property | **Multi-hop reasoning** | seasonal_events.txt + amenities.txt |
| 12 | Cryptocurrency payment | Factoid (untested topic) | policies.txt |
| 13 | Halloween booking timeline | Cross-file | faq.txt + seasonal_events.txt |

## How the matching works

`eval_retrieval.py` uses **case-insensitive substring matching**. For each query, it retrieves top-K chunks from the pipeline, then checks if any retrieved chunk contains each snippet as a substring. A snippet "matches" if it appears anywhere inside any retrieved chunk.

## How to run

```bash
# Live mode (uses actual RAG pipeline)
python evals/eval_retrieval.py --live

# Compare against last run
python evals/eval_retrieval.py --compare-last
```
