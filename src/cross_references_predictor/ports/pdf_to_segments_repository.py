from abc import ABC, abstractmethod
from pathlib import Path

from pdf_features.PdfWord import PdfWord

from cross_references_predictor.domain.segment import Segment


class PDFToSegmentsRepository(ABC):

    @staticmethod
    @abstractmethod
    def get_segments(pdf_path: Path, fast: bool) -> list[Segment]:
        pass

    @staticmethod
    @abstractmethod
    def get_word_positions(pdf_path: Path) -> list[PdfWord]:
        pass
