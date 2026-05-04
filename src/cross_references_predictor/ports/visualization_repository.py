from abc import ABC, abstractmethod
from pathlib import Path

from cross_references_predictor.domain.reference import Reference


class VisualizationRepository(ABC):
    @abstractmethod
    def create_pdf_with_annotations(self, pdf_path: Path, references: list[Reference]) -> Path:
        pass
