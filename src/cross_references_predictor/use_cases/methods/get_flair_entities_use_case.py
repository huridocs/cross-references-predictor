from flair.data import Sentence, Span
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.use_cases.methods.reference_extraction_method_base import ReferenceExtractionMethod


class GetFlairEntitiesUseCase(ReferenceExtractionMethod):

    def __init__(self, model):
        self._model = model

    @staticmethod
    def convert_to_named_entity_type(flair_raw_result: list[Span]) -> list[Reference]:
        result = []
        for entity in flair_raw_result:
            if entity.tag not in {"ORG", "PERSON", "LAW", "GPE"}:
                continue
            result.append(
                Reference(
                    type=ReferenceType.from_flair_type(entity.tag),
                    text=entity.text,
                    normalized_text=entity.text,
                    character_start=entity.start_position,
                    character_end=entity.end_position,
                )
            )
        return result

    @staticmethod
    def remove_no_iso_locations(references: list[Reference]) -> list[Reference]:
        filtered_references = []
        for entity in references:
            if entity.type == ReferenceType.LOCATION:
                if not entity.has_iso_code():
                    continue
            filtered_references.append(entity)
        return filtered_references

    def get_references(self, text: str) -> list[Reference]:
        if self._model is None:
            return []
        sentence = Sentence(text)
        self._model.predict(sentence)
        flair_raw_result: list[Span] = sentence.get_spans("ner")
        references = self.convert_to_named_entity_type(flair_raw_result)
        references = self.remove_overlapping_references(references)
        return references
