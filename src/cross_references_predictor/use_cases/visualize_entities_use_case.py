from pathlib import Path

from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.ports.visualization_repository import VisualizationRepository


class VisualizeEntitiesUseCase:
    def __init__(self, visualization_repository: VisualizationRepository):
        self.visualization_repository = visualization_repository

    def create_annotated_pdf(self, pdf_path: Path, references: list[Reference]) -> Path:
        return self.visualization_repository.create_pdf_with_annotations(pdf_path, references)
