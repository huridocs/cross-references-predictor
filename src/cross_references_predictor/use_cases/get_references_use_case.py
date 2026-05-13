from cross_references_predictor.adapters.model_loader_repository import ConcreteModelLoader
from cross_references_predictor.configuration import PROCESS_REFERENCE_TYPES
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.segment import Segment
from cross_references_predictor.ports.model_loader import ModelLoader
from cross_references_predictor.use_cases.methods.get_document_code_use_case import GetDocumentCodeUseCase
from cross_references_predictor.use_cases.methods.get_flair_entities_use_case import GetFlairEntitiesUseCase
from cross_references_predictor.use_cases.methods.get_gli_ner_entities_use_case import GetGLiNEREntitiesUseCase
from cross_references_predictor.use_cases.methods.reference_extraction_method_base import ReferenceExtractionMethod


class GetReferencesUseCase:
    def __init__(
        self,
        language: str = "en",
        methods: list[ReferenceExtractionMethod] = None,
        model_loader: ModelLoader = None,
    ):
        self.language = language
        self.methods = methods if methods is not None else self._build_methods(language, model_loader)

    @staticmethod
    def _build_methods(language: str, model_loader: ModelLoader) -> list[ReferenceExtractionMethod]:
        methods: list[ReferenceExtractionMethod] = [GetDocumentCodeUseCase()]

        if model_loader is None:
            return methods

        flair_model = model_loader.get_model("flair")
        if flair_model is not None:
            methods.append(GetFlairEntitiesUseCase(flair_model))
        gliner_model = model_loader.get_model("gliner")
        if gliner_model is not None:
            methods.append(GetGLiNEREntitiesUseCase(gliner_model, language))

        return methods

    def execute(self, text: str) -> list[Reference]:
        return self.get_references_from_text(text)

    def get_references_from_text(self, text: str) -> list[Reference]:
        entities = []
        for method in self.methods:
            entities.extend(method.get_references(text))
        enabled = set(PROCESS_REFERENCE_TYPES)
        return sorted(
            [e for e in entities if e.type in enabled],
            key=lambda x: x.character_start,
        )

    def get_references_from_segments(self, segments: list[Segment]) -> list[Reference]:
        all_references = []
        for segment in segments:
            references = self.get_references_from_text(segment.text)
            pdf_references = [Reference.from_segment(ref, segment) for ref in references]
            all_references.extend(pdf_references)
        return all_references
