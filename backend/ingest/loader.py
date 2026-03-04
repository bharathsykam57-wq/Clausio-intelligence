"""
ingest/loader.py
Loads PDFs from disk or URL, splits into overlapping chunks.

HOW IT WORKS:
  1. Read PDF bytes page by page using PyPDF
  2. Split pages into overlapping chunks using RecursiveCharacterTextSplitter
  3. Return LangChain Document objects with metadata (title, page number, source)

WHY RecursiveCharacterTextSplitter?
  Legal docs have hierarchy: Chapter → Article → Paragraph
  This splitter tries \n\n first (paragraphs), then \n, then sentences.
  Respects natural boundaries before force-splitting mid-sentence.
"""
import io
from pathlib import Path
from typing import Union
import httpx
from pypdf import PdfReader
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from loguru import logger
from config import get_settings

settings = get_settings()

# Public domain EU regulatory documents
PUBLIC_DOCS = {
    "eu_ai_act": {
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689",
        "title": "EU Artificial Intelligence Act",
        "language": "en",
    },
    "rgpd_fr": {
        "url": "https://www.cnil.fr/sites/cnil/files/atoms/files/rgpd-texte-officiel-celex_02016r0679-20160504_fr.pdf",
        "title": "Règlement Général sur la Protection des Données",
        "language": "fr",
    },
}


def load_pdf_from_bytes(data: bytes, metadata: dict) -> list[Document]:
    """Parse raw PDF bytes → list of per-page Documents."""
    reader = PdfReader(io.BytesIO(data))
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            docs.append(Document(
                page_content=text,
                metadata={**metadata, "page": i + 1, "total_pages": len(reader.pages)},
            ))
    logger.info(f"Loaded {len(docs)} pages from '{metadata.get('title', 'unknown')}'")
    return docs


def load_pdf_from_path(path: Union[str, Path], metadata: dict | None = None) -> list[Document]:
    """Load a PDF from a local file path."""
    path = Path(path)
    metadata = metadata or {"source": path.stem, "title": path.stem}
    with open(path, "rb") as f:
        return load_pdf_from_bytes(f.read(), metadata)


def load_pdf_from_url(url: str, metadata: dict) -> list[Document]:
    """Download and load a PDF from URL."""
    logger.info(f"Downloading: {url}")
    resp = httpx.get(url, follow_redirects=True, timeout=60)
    resp.raise_for_status()
    return load_pdf_from_bytes(resp.content, metadata)


def chunk_documents(docs: list[Document]) -> list[Document]:
    """
    Split documents into overlapping chunks.
    chunk_size=512 tokens (~2048 chars) preserves one full legal article per chunk.
    chunk_overlap=64 tokens (~256 chars) prevents answers being cut at boundaries.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size * 4,
        chunk_overlap=settings.chunk_overlap * 4,
        separators=["\n\n", "\n", "(?<=\\. )", " ", ""],
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Split {len(docs)} pages → {len(chunks)} chunks")
    return chunks


def ingest_public_docs() -> list[Document]:
    """Download and chunk all public regulatory documents."""
    all_chunks = []
    for key, info in PUBLIC_DOCS.items():
        try:
            pages = load_pdf_from_url(info["url"], {
                "source": key, "title": info["title"],
                "language": info["language"], "url": info["url"],
            })
            chunks = chunk_documents(pages)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.error(f"Failed to load {key}: {e}")
    return all_chunks
