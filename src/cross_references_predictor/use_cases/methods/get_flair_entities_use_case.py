from pathlib import Path
from flair.nn import Classifier
from cross_references_predictor.use_cases.methods.base import ReferenceExtractionMethod
from cross_references_predictor.configuration import MODELS_PATH
from cross_references_predictor.domain.reference import Reference
from flair.data import Sentence, Span
from cross_references_predictor.domain.reference_type import ReferenceType

flair_model = Classifier.load(Path(MODELS_PATH, "flair", "pytorch_model.bin"))


class GetFlairEntitiesUseCase(ReferenceExtractionMethod):

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
        sentence = Sentence(text)
        flair_model.predict(sentence)
        flair_raw_result: list[Span] = sentence.get_spans("ner")
        references = self.convert_to_named_entity_type(flair_raw_result)
        references = self.remove_overlapping_references(references)
        return references
