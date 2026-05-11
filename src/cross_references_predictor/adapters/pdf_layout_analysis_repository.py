import requests
from fastapi import HTTPException
from pathlib import Path

from pdf_features.PdfWord import PdfWord

from cross_references_predictor.configuration import PDF_ANALYSIS_SERVICE_URL
from cross_references_predictor.domain.segment import Segment
from cross_references_predictor.ports.pdf_to_segments_repository import PDFToSegmentsRepository

PDF_HEADER = b"%PDF-"


def _is_pdf(pdf_path: Path) -> bool:
    try:
        with open(pdf_path, "rb") as f:
            return f.read(5).startswith(PDF_HEADER)
    except Exception:
        return False


class PDFLayoutAnalysisRepository(PDFToSegmentsRepository):
    @staticmethod
    def get_segments(pdf_path: Path, fast: bool = False, url: str = "") -> list[Segment]:
        if not _is_pdf(pdf_path):
            raise HTTPException(status_code=400, detail="Unprocessable text or PDF file")

        with open(pdf_path, "rb") as pdf_file:
            files = {"file": pdf_file}
            data = {"fast": fast}
            pdf_document_url = url if url else PDF_ANALYSIS_SERVICE_URL
            response = requests.post(pdf_document_url, files=files, data=data)
            response.raise_for_status()
            segment_boxes = response.json()
            return [
                Segment.from_segment_box(segment_box, pdf_path.name, index + 1)
                for index, segment_box in enumerate(segment_boxes)
            ]

    @staticmethod
    def get_word_positions(pdf_path: Path) -> list[PdfWord]:
        if not _is_pdf(pdf_path):
            raise HTTPException(status_code=400, detail="Unprocessable text or PDF file")

        with open(pdf_path, "rb") as pdf_file:
            files = {"file": pdf_file}
            response = requests.post(PDF_ANALYSIS_SERVICE_URL + "/word_positions", files=files)
            response.raise_for_status()
            pdf_words = response.json()
            return [PdfWord(**segment_box) for segment_box in pdf_words]


if __name__ == "__main__":
    pdf_path = Path(__file__).parent.parent.parent / "tests" / "end_to_end" / "test_pdfs" / "test_document.pdf"
    repository = PDFLayoutAnalysisRepository()
    segments = repository.get_segments(pdf_path, False, "http://localhost:5060")
    print(segments)
