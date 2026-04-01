#!/usr/bin/env python3
"""
RAG Benchmark: Custom AdvancedRAG vs LangChain RAG
===================================================

Ingests the same knowledge base into both systems, runs identical queries,
and compares latency and result quality. Logs to MLflow if available.

Usage:
    python scripts/benchmark_rag.py
"""

import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.records_room.advanced_rag import AdvancedRAG
from app.records_room.langchain_rag import LangChainRAG
from app.cctv.mlflow_tracking import MLflowTracker


BENCHMARK_QUERIES = [
    "What amenities does Vampire Manor offer?",
    "Tell me about the Werewolf Lodge pool",
    "Does Castle Frankenstein have room service?",
    "What is the check-in time at Zombie B&B?",
    "Are there spa services at the Mummy Resort?",
]


def benchmark_rag(rag, name: str, queries: list[str]) -> dict:
    """Run queries against a RAG system and return metrics."""
    latencies = []
    result_counts = []
    top_scores = []

    for query in queries:
        start = time.perf_counter()
        results = rag.search(query, k=5)
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

        result_list = results.get("results", [])
        result_counts.append(len(result_list))
        if result_list:
            top_scores.append(result_list[0].get("score", 0.0))

    return {
        "name": name,
        "avg_latency_ms": sum(latencies) / len(latencies),
        "max_latency_ms": max(latencies),
        "min_latency_ms": min(latencies),
        "avg_results": sum(result_counts) / len(result_counts),
        "avg_top_score": sum(top_scores) / len(top_scores) if top_scores else 0.0,
    }


def print_comparison(custom: dict, langchain: dict):
    """Print a comparison table."""
    print("\n" + "=" * 70)
    print("RAG BENCHMARK COMPARISON")
    print("=" * 70)
    print(f"{'Metric':<30} {'Custom AdvancedRAG':>18} {'LangChain RAG':>18}")
    print("-" * 70)

    metrics = [
        ("Avg Latency (ms)", "avg_latency_ms"),
        ("Max Latency (ms)", "max_latency_ms"),
        ("Min Latency (ms)", "min_latency_ms"),
        ("Avg Results Returned", "avg_results"),
        ("Avg Top Score", "avg_top_score"),
    ]

    for label, key in metrics:
        c_val = custom[key]
        l_val = langchain[key]
        print(f"{label:<30} {c_val:>18.2f} {l_val:>18.2f}")

    print("=" * 70)

    # Determine winner
    if custom["avg_latency_ms"] < langchain["avg_latency_ms"]:
        print("Winner (latency): Custom AdvancedRAG")
    else:
        print("Winner (latency): LangChain RAG")

    print()


def main():
    mlflow_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow_enabled = os.environ.get("MLFLOW_ENABLED", "false").lower() == "true"

    tracker = MLflowTracker(
        tracking_uri=mlflow_uri,
        experiment_name="rag-benchmark",
        enabled=mlflow_enabled,
    )

    # Use temporary directories for clean comparison
    custom_dir = tempfile.mkdtemp(prefix="rag_custom_")
    langchain_dir = tempfile.mkdtemp(prefix="rag_langchain_")

    print("Initializing RAG systems...")
    custom_rag = AdvancedRAG(custom_dir, "benchmark_custom")
    langchain_rag = LangChainRAG(langchain_dir, "benchmark_langchain")

    # Ingest knowledge
    knowledge_path = os.path.join(os.getcwd(), "data", "knowledge")
    if os.path.exists(knowledge_path):
        print(f"Ingesting from {knowledge_path}...")
        custom_rag.ingest_folder(knowledge_path)
        langchain_rag.ingest_folder(knowledge_path)
    else:
        # Use sample data for testing
        sample_texts = [
            "Vampire Manor offers eternal night ambiance with gothic towers, "
            "a moonlit infinity pool, and candlelit dining.",
            "The Werewolf Lodge features a heated outdoor pool surrounded by ancient oaks, "
            "moonlight yoga sessions, and a full-service spa.",
            "Castle Frankenstein provides high voltage luxury with 24-hour room service, "
            "an electrifying laboratory tour, and Tesla coil light shows.",
            "Zombie Bed & Breakfast has flexible check-in starting at 2 PM, "
            "complimentary brain-shaped pastries, and shambling garden walks.",
            "The Mummy Resort & Tomb-Service offers ancient Egyptian spa treatments, "
            "gold-leaf wrapping therapy, and sarcophagus meditation rooms.",
        ]
        print("Using sample data (no knowledge folder found)...")
        custom_rag.ingest_texts(sample_texts, source="benchmark")
        langchain_rag.ingest_texts(sample_texts, source="benchmark")

    print(f"\nRunning {len(BENCHMARK_QUERIES)} benchmark queries...")

    custom_metrics = benchmark_rag(custom_rag, "Custom AdvancedRAG", BENCHMARK_QUERIES)
    langchain_metrics = benchmark_rag(langchain_rag, "LangChain RAG", BENCHMARK_QUERIES)

    print_comparison(custom_metrics, langchain_metrics)

    # Log to MLflow
    tracker.log_benchmark_results(
        "custom_advanced_rag",
        {k: v for k, v in custom_metrics.items() if isinstance(v, (int, float))},
        params={"rag_type": "custom_advanced"},
    )
    tracker.log_benchmark_results(
        "langchain_rag",
        {k: v for k, v in langchain_metrics.items() if isinstance(v, (int, float))},
        params={"rag_type": "langchain"},
    )

    print("Benchmark complete!")
    if mlflow_enabled:
        print(f"View results at: {mlflow_uri}")


if __name__ == "__main__":
    main()
