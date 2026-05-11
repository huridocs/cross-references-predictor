from pathlib import Path

from dateparser.search import search_dates
from gliner import GLiNER
from cross_references_predictor.use_cases.methods.reference_extraction_method_base import ReferenceExtractionMethod
from cross_references_predictor.configuration import MODELS_PATH
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType

gliner_path = Path(MODELS_PATH, "gliner")
classifier = GLiNER.from_pretrained(gliner_path) if gliner_path.exists() else None


class GetGLiNEREntitiesUseCase(ReferenceExtractionMethod):

    WINDOW_SIZE = 20
    SLIDE_SIZE = 10

    def __init__(self, language: str = "en"):
        self.language = language
        self.references: list[Reference] = list()

    def convert_to_named_entity_type(self, window_references: list[dict]):
        result = []
        for entity in window_references:
            named_entity = Reference(
                type=ReferenceType.DATE, text=entity["text"], character_start=entity["start"], character_end=entity["end"]
            )
            try:
                named_entity = named_entity.get_with_normalize_entity_text(self.language)
                result.append(named_entity)
            except Exception:
                pass
        return result

    def iterate_through_windows(self, words):
        last_slide_end_index = 0
        for i in range(0, len(words), self.SLIDE_SIZE):
            window_words = words[i : i + self.WINDOW_SIZE]
            window_text = " ".join(window_words)
            window_references = classifier.predict_entities(window_text, ["date"])
            window_references = self.convert_to_named_entity_type(window_references)

            for entity in window_references:
                entity.character_start += last_slide_end_index
                entity.character_end += last_slide_end_index

            slide_words = words[i : i + self.SLIDE_SIZE]
            slide_text = " ".join(slide_words)
            last_slide_end_index += len(slide_text) + 1

            for entity in window_references:
                if not any(e.text == entity.text and e.character_start == entity.character_start for e in self.references):
                    self.references.append(entity)

    @staticmethod
    def remove_uncompleted_dates(references):
        result = list()
        for entity in references:
            if len(entity.text.split()) < 3:
                continue
            result.append(entity)

        return result

    def get_references(self, text: str) -> list[Reference]:
        self.references: list[Reference] = list()
        words = text.split()
        self.iterate_through_windows(words)
        self.references = [e for e in self.references if search_dates(e.text, languages=[self.language])]
        self.references = self.remove_overlapping_references(self.references)
        self.references = self.remove_uncompleted_dates(self.references)
        return self.references
