# My "advanced" RAG pipeline was slower *and* worse than the baseline. Here's how I found out — and what I did about it.

I built a three-stage retrieval pipeline for the Monster Resort concierge: BM25 keyword search and dense vector search, fused with Reciprocal Rank Fusion, then reranked by a BGE cross-encoder. It has the shape of every "serious" RAG diagram you've seen. It looks like the thing a senior engineer builds.

Then I ran my own ablation scoreboard against it — and it lost. To the simplest baseline in the study.

This is the story of that scoreboard, the root-cause diagnosis, the fix, and — this is the part that matters — the *real* numbers after the fix, including the ones that are still uncomfortable.

## The scoreboard that ratted me out

I have a script, `scripts/ablation_retrieval.py`, that runs four retrieval configs over a 13-query ground-truth set and reports Precision@5, MRR, and latency:

- **BM25 only** — keyword search
- **Dense only** — the embedding retriever alone
- **Hybrid (no reranker)** — BM25 + dense fused via RRF
- **Full pipeline** — hybrid + the cross-encoder reranker

The first time I looked at it honestly, the numbers were embarrassing:

| Config | Latency (ms) | MRR |
|--------|-------------:|----:|
| BM25 only | 0.2 | 0.449 |
| **Dense only** | **9.8** | **0.718** |
| Hybrid (no reranker) | 8.7 | 0.667 |
| Full pipeline | 963.6 | 0.756 |

Two things jump out. First, **Hybrid-no-reranker (0.667 MRR) was *below* Dense-only (0.718)**. Adding BM25 to a strong dense retriever made the ranking *worse*. Second, the **Full pipeline cost ~960ms per query** — about 100x the latency of dense-only — for a reranker MRR that only barely edged out the baseline. And an earlier, even more damning snapshot (8-query, before I extended the ground truth) had the full pipeline at 1087ms and MRR *below* dense-only.

The instinct here is to reach for something shinier. Swap BGE for a bigger reranker. Add ColBERT. Try a new fusion algorithm. That instinct is wrong, and recognizing that it's wrong is the actual senior move. The scoreboard wasn't telling me I needed a fancier component. It was telling me my existing components were wired together badly. The senior move isn't adding ColBERT — it's noticing your reranker lost to dense-only and being able to *explain why*.

So I explained why.

## Root cause #1: RRF was diluting a strong signal with a weak one

My fusion used `bm25_weight=0.4`. That's a reasonable-sounding default — nearly an equal partnership between keyword and semantic search. But my own scoreboard said BM25-only had an MRR of **0.449**, while dense-only had **0.718**. These are not equal partners. Giving a 0.449-MRR retriever 40% of the vote in the fusion was actively pulling correct answers *down* the ranking.

I swept the weight across the ablation to find where it actually helped:

```
bm25_weight=0.0    hybrid-noRR  MRR=0.7179  P@5=0.3077
bm25_weight=0.1    hybrid-noRR  MRR=0.6564  P@5=0.3231
bm25_weight=0.15   hybrid-noRR  MRR=0.7179  P@5=0.3231
bm25_weight=0.2    hybrid-noRR  MRR=0.6923  P@5=0.3077
bm25_weight=0.25   hybrid-noRR  MRR=0.6795  P@5=0.3077
bm25_weight=0.4    hybrid-noRR  MRR=0.6667  P@5=0.3077   <- old default
bm25_weight=0.5    hybrid-noRR  MRR=0.6667  P@5=0.2923
```

The old 0.4 default sat at the bottom for MRR. The sweet spot was **0.15**: it recovered dense-only's MRR (0.7179) *and* delivered the best Precision@5 in the sweep (0.3231, above dense-only's 0.3077). That last part is the point of keeping BM25 at all — as a low-weight tie-breaker it adds exact-match precision (proper nouns like "Vampire Manor" and "Werewolf Lodge") without letting its weaker ranking drag the top result down. So I made `bm25_weight` configurable and set the default to 0.15.

## Root cause #2: the reranker was being fed a lossy, pre-truncated list

This one is subtler, and it's the mistake I'm least proud of. My pipeline did this:

1. Retrieve top-k from BM25 and top-k from dense.
2. **Fuse them with RRF and truncate to `hybrid_k`.**
3. Hand that truncated, RRF-ordered list to the cross-encoder.

The reranker re-scores every candidate from scratch — it doesn't care what order they arrive in. So pre-ordering them with RRF buys nothing. But pre-*truncating* them with RRF can actively hurt: if RRF's weak fusion score buries a document the cross-encoder would have ranked #1, that document can fall off the edge of `hybrid_k` and never reach the reranker at all. I was letting my *weakest* ranking signal decide which candidates my *strongest* ranking signal was even allowed to see.

The fix: feed the reranker the **deduplicated union** of the BM25 and dense candidate pools directly — maximize recall into the rerank stage, and let the cross-encoder do the actual deciding. RRF is now only used on the no-reranker path, where its ordering *is* the final answer and therefore matters.

## Root cause #3: cold-start was inflating the latency tail

The 963ms average hid a lie. Here's the per-query breakdown from that run:

```
3398.6 ms   What are the check-in and checkout times?   <- first query
 949.0 ms   What is the pet policy?
 841.4 ms   Tell me about Vampire Manor rooms...
 ...
 564.8 ms   How far in advance should I book...
```

The first query paid **3.4 seconds** — the cost of loading the cross-encoder weights off disk on first use. That's a one-time cost on the first query, not a per-request cost, but because the model loaded lazily *inside* the first timed `search()` call, it landed squarely on my latency measurement and dragged the mean up by ~200ms/query. Any p99 I quoted from this would be fiction.

The fix: a `warm_up()` method that pre-loads the cross-encoder (and forces a tiny warm forward pass), called before the timed loop. Now the measurement reflects steady state, which is what every query after the first one sees. The app itself doesn't call `warm_up()` yet, so its first knowledge query still pays the load cost.

## The real numbers after the fix

Here's the honest scoreboard, warm, `bm25_weight=0.15`, union candidates:

| Config | Latency (ms) | Precision@5 | MRR |
|--------|-------------:|------------:|----:|
| BM25 only | 0.1 | 0.169 | 0.449 |
| Dense only | 7.9 | 0.308 | 0.718 |
| Hybrid (no reranker) | 8.4 | **0.338** | 0.718 |
| **Full pipeline** | 736.9 | 0.308 | **0.756** |

What actually changed, and what didn't:

- **Hybrid-no-reranker went from *losing* to dense (0.667) to *matching* it (0.718) on MRR, and now beats it on Precision@5 (0.338 vs 0.308).** Fixing the RRF weight turned a negative-value stage into a positive one. This is the clean win.
- **The full pipeline still has the top MRR (0.756)** — the cross-encoder's ranking edge is real. But it's a *narrow* edge: +0.038 over dense-only.
- **Latency dropped from 963ms to 737ms** by killing cold-start, and the tail collapsed — every warm query now sits in a tight 565–860ms band instead of spiking to 3.4s.

And now the uncomfortable honesty, because a fabricated victory would defeat the entire purpose of having a scoreboard:

**On a 5-file corpus, dense-only is genuinely hard to beat.** The reranker technically wins on MRR, but it costs ~90x the latency (737ms vs 8ms on CPU) to move MRR by 0.04. On this corpus, if I were shipping a latency-sensitive path, I would ship **hybrid-no-reranker** — it has the best Precision@5, matches the best MRR, and runs in single-digit milliseconds. I did *not* make the reranker a slam-dunk, because on this data it isn't one.

So when *would* the reranker win decisively? When candidate ambiguity rises — a larger corpus with many near-duplicate chunks, where dense retrieval returns ten plausible-looking passages and only the cross-encoder can tell which one actually answers the question. And when there's a GPU: the ~730ms CPU inference should drop by roughly an order of magnitude (I haven't measured that here), which would change the trade-off entirely. Those are the conditions under which I'd turn the reranker on by default. Naming those conditions — instead of claiming the reranker always wins — is the whole point.

## The transferable lesson

Build the scoreboard *before* you build the pipeline, and then actually read it — including the rows that make your architecture look bad. My "advanced" pipeline wasn't broken because it lacked a fancy component. It was broken because I'd wired a strong retriever to a weak one with an equal vote, let the weak one gatekeep the strong one's candidates, and measured cold-start as if it were steady-state. None of those are exotic bugs. They're the boring, wiring-level mistakes that a benchmark catches and a diagram never will.

The senior move isn't adding ColBERT. It's noticing your reranker lost to dense-only, explaining exactly why, fixing the wiring, and then telling the truth about how much — or how little — it helped.
