#!/usr/bin/env python3
"""
RAG Experiment Runner
=====================

Runs RAG evaluation experiments with different configurations
and logs results to MLflow for comparison.

Usage:
    python scripts/run_rag_experiment.py
"""

import os
import sys
import time
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.advanced_rag import AdvancedRAG
from app.monitoring.mlflow_tracking import MLflowTracker


BENCHMARK_QUERIES = [
    "What amenities does Vampire Manor offer?",
    "Tell me about the Werewolf Lodge pool",
    "Does Castle Frankenstein have room service?",
    "What is the check-in time at Zombie B&B?",
    "Are there spa services at the Mummy Resort?",
    "What dining options are available at Ghostly B&B?",
    "Is there a gym at Vampire Manor?",
    "What is the cancellation policy?",
]


def run_experiment(
    rag: AdvancedRAG,
    tracker: MLflowTracker,
    queries: list[str],
    config_name: str,
    bm25_weight: float = 0.4,
    use_reranker: bool = True,
):
    """Run a set of queries and log results."""
    print(f"\n{'='*60}")
    print(f"Experiment: {config_name}")
    print(f"BM25 weight: {bm25_weight}, Reranker: {use_reranker}")
    print(f"{'='*60}")

    total_latency = 0
    total_results = 0

    for query in queries:
        start = time.perf_counter()
        results = rag.search(
            query, k=5, bm25_weight=bm25_weight, use_reranker=use_reranker
        )
        latency_ms = (time.perf_counter() - start) * 1000
        total_latency += latency_ms

        result_list = results.get("results", [])
        total_results += len(result_list)
        top_score = result_list[0]["score"] if result_list else 0.0

        print(f"  Query: {query[:50]}... | {len(result_list)} results | "
              f"top_score={top_score:.3f} | {latency_ms:.1f}ms")

        tracker.log_rag_evaluation(
            query=query,
            results=result_list,
            latency_ms=latency_ms,
            rag_type=config_name,
            extra_params={"bm25_weight": str(bm25_weight), "use_reranker": str(use_reranker)},
        )

    avg_latency = total_latency / len(queries)
    avg_results = total_results / len(queries)

    tracker.log_benchmark_results(
        benchmark_name=config_name,
        metrics={"avg_latency_ms": avg_latency, "avg_results": avg_results},
        params={"bm25_weight": str(bm25_weight), "use_reranker": str(use_reranker)},
    )

    print(f"\n  Average latency: {avg_latency:.1f}ms")
    print(f"  Average results: {avg_results:.1f}")


def main():
    persist_dir = os.environ.get("RAG_PERSIST_DIR", "./.rag_store")
    collection = os.environ.get("RAG_COLLECTION", "monster_resort_knowledge")
    mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow_enabled = os.environ.get("MLFLOW_ENABLED", "true").lower() == "true"

    tracker = MLflowTracker(
        tracking_uri=mlflow_uri,
        experiment_name="rag-experiments",
        enabled=mlflow_enabled,
    )

    rag = AdvancedRAG(persist_dir, collection)

    # Ingest knowledge if available
    knowledge_path = Path.cwd() / "data" / "knowledge"
    if knowledge_path.exists():
        print(f"Ingesting knowledge from {knowledge_path}...")
        rag.ingest_folder(str(knowledge_path))

    # Experiment 1: Hybrid with reranker (default)
    run_experiment(rag, tracker, BENCHMARK_QUERIES, "hybrid_reranked", bm25_weight=0.4, use_reranker=True)

    # Experiment 2: Dense-only with reranker
    run_experiment(rag, tracker, BENCHMARK_QUERIES, "dense_reranked", bm25_weight=0.0, use_reranker=True)

    # Experiment 3: BM25-heavy with reranker
    run_experiment(rag, tracker, BENCHMARK_QUERIES, "bm25_heavy_reranked", bm25_weight=0.7, use_reranker=True)

    # Experiment 4: Hybrid without reranker
    run_experiment(rag, tracker, BENCHMARK_QUERIES, "hybrid_no_reranker", bm25_weight=0.4, use_reranker=False)

    print("\nAll experiments complete!")
    if mlflow_enabled:
        print(f"View results at: {mlflow_uri}")


if __name__ == "__main__":
    main()
