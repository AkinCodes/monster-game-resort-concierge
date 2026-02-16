"""
Script to ingest knowledge files into the RAG system.
Run this manually or as part of a deployment pipeline.
"""

import argparse
import logging
from app.config import get_settings
from app.rag import VectorRAG


def main():
    parser = argparse.ArgumentParser(
        description="Ingest knowledge files into RAG store."
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="./data/knowledge",
        help="Folder containing knowledge files",
    )
    args = parser.parse_args()

    settings = get_settings()
    rag = VectorRAG(
        settings.rag_persist_dir,
        settings.rag_collection,
        embedding_model=getattr(settings, "embedding_model", "all-MiniLM-L6-v2"),
    )

    try:
        count = rag.ingest_folder(args.folder)
        print(f"Successfully ingested {count} documents from {args.folder}")
    except Exception as e:
        logging.error(f"Failed to ingest knowledge: {e}")
        exit(1)


if __name__ == "__main__":
    main()
