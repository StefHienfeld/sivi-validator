"""
PDF processor for extracting and chunking text from PDF documents.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default chunk settings
DEFAULT_CHUNK_SIZE = 1000  # characters
DEFAULT_CHUNK_OVERLAP = 200  # characters


class PDFProcessor:
    """Processor for extracting text from PDF documents."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        """
        Initialize the PDF processor.

        Args:
            chunk_size: Target size for text chunks in characters.
            chunk_overlap: Overlap between consecutive chunks.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process(self, pdf_path: Path) -> list[dict]:
        """
        Process a PDF file and return document chunks.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of document dictionaries with 'id', 'content', and 'metadata'.
        """
        if not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            return []

        logger.info(f"Processing PDF: {pdf_path.name}")

        # Extract text using PyMuPDF (faster) with pdfplumber fallback for tables
        pages = self._extract_pages(pdf_path)

        if not pages:
            logger.warning(f"No text extracted from: {pdf_path}")
            return []

        # Chunk the text with section awareness
        chunks = self._chunk_pages(pages, pdf_path.name)

        logger.info(f"Created {len(chunks)} chunks from {pdf_path.name}")
        return chunks

    def _extract_pages(self, pdf_path: Path) -> list[dict]:
        """
        Extract text from each page of the PDF.

        Returns list of dicts with 'page', 'text', and 'section'.
        """
        pages = []

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(pdf_path))

            for page_num, page in enumerate(doc, 1):
                text = page.get_text("text")

                # Clean up the text
                text = self._clean_text(text)

                if text.strip():
                    # Try to detect section headers
                    section = self._detect_section(text)

                    pages.append({
                        "page": page_num,
                        "text": text,
                        "section": section,
                    })

            doc.close()

        except ImportError:
            logger.warning("PyMuPDF not available, trying pdfplumber")
            pages = self._extract_with_pdfplumber(pdf_path)
        except Exception as e:
            logger.error(f"Error extracting PDF with PyMuPDF: {e}")
            # Try pdfplumber as fallback
            pages = self._extract_with_pdfplumber(pdf_path)

        return pages

    def _extract_with_pdfplumber(self, pdf_path: Path) -> list[dict]:
        """Extract text using pdfplumber (better for tables)."""
        pages = []

        try:
            import pdfplumber

            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""

                    # Also extract tables
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            table_text = self._format_table(table)
                            if table_text:
                                text += "\n\n" + table_text

                    text = self._clean_text(text)

                    if text.strip():
                        section = self._detect_section(text)
                        pages.append({
                            "page": page_num,
                            "text": text,
                            "section": section,
                        })

        except ImportError:
            logger.error("Neither PyMuPDF nor pdfplumber available")
        except Exception as e:
            logger.error(f"Error extracting PDF with pdfplumber: {e}")

        return pages

    def _format_table(self, table: list) -> str:
        """Format a table as text."""
        if not table:
            return ""

        rows = []
        for row in table:
            if row:
                # Filter out None values and join
                cells = [str(cell) if cell else "" for cell in row]
                rows.append(" | ".join(cells))

        return "\n".join(rows)

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        # Remove page numbers and headers/footers (common patterns)
        text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^Pagina \d+ van \d+\s*$", "", text, flags=re.MULTILINE)

        return text.strip()

    def _detect_section(self, text: str) -> Optional[str]:
        """
        Try to detect section header from text.

        Returns section identifier if found.
        """
        # Look for common section patterns
        patterns = [
            r"^(\d+\.[\d\.]*)\s+(.+?)(?:\n|$)",  # "1.2.3 Title"
            r"^(Hoofdstuk\s+\d+)[\s:]+(.+?)(?:\n|$)",  # "Hoofdstuk 1: Title"
            r"^(Sectie\s+[\d\.]+)[\s:]+(.+?)(?:\n|$)",  # "Sectie 1.2: Title"
            r"^(Bijlage\s+\w+)[\s:]+(.+?)(?:\n|$)",  # "Bijlage A: Title"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                return f"{match.group(1)} {match.group(2)[:50]}"

        return None

    def _chunk_pages(self, pages: list[dict], filename: str) -> list[dict]:
        """
        Chunk pages into smaller documents while preserving context.

        Uses sentence-aware chunking with section tracking.
        """
        chunks = []
        current_section = None

        for page_data in pages:
            page_num = page_data["page"]
            text = page_data["text"]
            section = page_data.get("section") or current_section

            if section:
                current_section = section

            # Split into paragraphs first
            paragraphs = text.split("\n\n")

            current_chunk = ""
            chunk_start_page = page_num

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Check if adding this paragraph exceeds chunk size
                if len(current_chunk) + len(para) + 2 > self.chunk_size:
                    # Save current chunk if it has content
                    if current_chunk.strip():
                        chunk = self._create_chunk(
                            content=current_chunk,
                            filename=filename,
                            page=chunk_start_page,
                            section=current_section,
                        )
                        chunks.append(chunk)

                    # Start new chunk with overlap
                    if len(current_chunk) > self.chunk_overlap:
                        # Take last part of previous chunk for overlap
                        overlap_text = current_chunk[-self.chunk_overlap :]
                        # Find sentence boundary for cleaner overlap
                        sentence_end = overlap_text.find(". ")
                        if sentence_end > 0:
                            overlap_text = overlap_text[sentence_end + 2 :]
                        current_chunk = overlap_text + "\n\n" + para
                    else:
                        current_chunk = para

                    chunk_start_page = page_num
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para

            # Don't forget the last chunk on this page
            # It will be continued on next page or saved at the end

        # Save final chunk
        if current_chunk.strip():
            chunk = self._create_chunk(
                content=current_chunk,
                filename=filename,
                page=chunk_start_page,
                section=current_section,
            )
            chunks.append(chunk)

        return chunks

    def _create_chunk(
        self,
        content: str,
        filename: str,
        page: int,
        section: Optional[str],
    ) -> dict:
        """Create a document chunk with metadata."""
        # Generate unique ID based on content
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        doc_id = f"pdf_{filename}_{page}_{content_hash}"

        return {
            "id": doc_id,
            "content": content,
            "metadata": {
                "source_type": "pdf",
                "source_file": filename,
                "title": filename.replace(".pdf", "").replace("-", " ").replace("_", " "),
                "page": page,
                "section": section,
            },
        }

    def process_directory(self, directory: Path) -> list[dict]:
        """
        Process all PDF files in a directory.

        Args:
            directory: Path to directory containing PDFs.

        Returns:
            Combined list of document chunks from all PDFs.
        """
        all_chunks = []

        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            return all_chunks

        pdf_files = list(directory.glob("*.pdf")) + list(directory.glob("*.PDF"))
        logger.info(f"Found {len(pdf_files)} PDF files in {directory}")

        for pdf_path in pdf_files:
            chunks = self.process(pdf_path)
            all_chunks.extend(chunks)

        return all_chunks
