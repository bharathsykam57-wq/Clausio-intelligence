"""
ingest/run_ingest.py
Entry-point script. Run once on first setup.

USAGE:
  # Ingest public EU AI Act + RGPD documents (default)
  python -m ingest.run_ingest

  # Ingest a custom PDF
  python -m ingest.run_ingest --pdf path/to/your.pdf

  # Clear DB and re-ingest everything
  python -m ingest.run_ingest --clear
"""
import sys
import argparse
from pathlib import Path
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingest.loader import ingest_public_docs, load_pdf_from_path, chunk_documents
from ingest.embedder import embed_documents_batched
from ingest.vectorstore import init_db, insert_documents, get_document_count, clear_documents


def run(custom_pdf_path: str | None = None, clear: bool = False) -> None:
    logger.info("=== LexIA Ingestion Pipeline ===")

    init_db()

    if clear:
        logger.warning("Clearing existing documents...")
        clear_documents()

    if custom_pdf_path:
        logger.info(f"Loading custom PDF: {custom_pdf_path}")
        pages = load_pdf_from_path(custom_pdf_path)
        chunks = chunk_documents(pages)
    else:
        logger.info("Loading EU AI Act + RGPD (downloading PDFs...)")
        chunks = ingest_public_docs()

    if not chunks:
        logger.error("No documents loaded.")
        sys.exit(1)

    logger.info(f"Total chunks: {len(chunks)}")
    embedded = embed_documents_batched(chunks, batch_size=32)
    inserted = insert_documents(embedded)
    total = get_document_count()
    logger.success(f"=== Done: {inserted} new chunks, {total} total in DB ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=str, help="Path to custom PDF")
    parser.add_argument("--clear", action="store_true", help="Clear DB before ingesting")
    args = parser.parse_args()
    run(args.pdf, args.clear)
