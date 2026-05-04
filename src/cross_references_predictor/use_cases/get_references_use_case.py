from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.segment import Segment
from cross_references_predictor.use_cases.methods.base import ReferenceExtractionMethod


class GetReferencesUseCase:
    def __init__(self, language: str = "en", methods: list[ReferenceExtractionMethod] = None):
        self.language = language
        if methods:
            self.methods = methods
        else:
            from cross_references_predictor.use_cases.methods.get_document_code_use_case import GetDocumentCodeUseCase
            from cross_references_predictor.use_cases.methods.get_flair_entities_use_case import GetFlairEntitiesUseCase
            from cross_references_predictor.use_cases.methods.get_gli_ner_entities_use_case import GetGLiNEREntitiesUseCase

            self.methods: list[ReferenceExtractionMethod] = [
                GetGLiNEREntitiesUseCase(language),
                GetFlairEntitiesUseCase(),
                GetDocumentCodeUseCase(),
            ]

    def execute(self, text: str) -> list[Reference]:
        return self.get_references_from_text(text)

    def get_references_from_text(self, text: str) -> list[Reference]:
        entities = []
        for method in self.methods:
            entities.extend(method.get_references(text))
        return sorted(entities, key=lambda x: x.character_start)

    def get_references_from_segments(self, segments: list[Segment]) -> list[Reference]:
        entities: list[Reference] = []
        for segment in segments:
            references: list[Reference] = self.get_references_from_text(segment.text)
            pdf_references = [Reference.from_segment(ref, segment) for ref in references]
            entities.extend(pdf_references)
        return entities
