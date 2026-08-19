import io
import logging
from dataclasses import dataclass

from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass
class PdfExtraction:
    """Result of extracting text from a PDF."""
    text: str
    page_count: int
    file_name: str
    file_size: int


def extract_text_from_pdf(
    file_content: bytes,
    file_name: str,
) -> PdfExtraction:
    """
    Extract text from a PDF file using pypdf.

    Extracts text page-by-page with layout mode for better structure
    preservation. Each page is separated by a double newline.

    Args:
        file_content: Raw bytes of the PDF file.
        file_name: Original file name for metadata.

    Returns:
        PdfExtraction with extracted text and metadata.

    Raises:
        ValueError: If the PDF cannot be read or contains no extractable text.
    """
    try:
        reader = PdfReader(io.BytesIO(file_content))
    except Exception as e:
        raise ValueError(f"Failed to read PDF file '{file_name}': {e}")

    if len(reader.pages) == 0:
        raise ValueError(f"PDF file '{file_name}' has no pages.")

    page_texts = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
            if text.strip():
                page_texts.append(text.strip())
        except Exception as e:
            logger.warning(
                f"Failed to extract text from page {i + 1} of '{file_name}': {e}"
            )
            continue

    full_text = "\n\n".join(page_texts)

    if not full_text.strip():
        raise ValueError(
            f"PDF file '{file_name}' contains no extractable text. "
            f"It may be a scanned/image-only PDF. OCR is not supported yet."
        )

    logger.info(
        f"Extracted {len(full_text)} characters from {len(reader.pages)} pages "
        f"of '{file_name}'."
    )

    return PdfExtraction(
        text=full_text,
        page_count=len(reader.pages),
        file_name=file_name,
        file_size=len(file_content),
    )
