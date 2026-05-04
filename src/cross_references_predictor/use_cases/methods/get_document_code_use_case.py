import re
from typing import List

from cross_references_predictor.use_cases.methods.base import ReferenceExtractionMethod
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType

UN_CODE_REGEX = r"^(A|S|E|T|ST)/([A-Z]+\.\d+|[A-Z]{2,}|\d{1,4})(/([A-Z]+\.\d+|[A-Z]{2,}|\d{1,4}))*(/(Rev|Add|Corr)\.\d+)*$"


class GetDocumentCodeUseCase(ReferenceExtractionMethod):
    def __init__(self):
        self.pattern = re.compile(UN_CODE_REGEX)

    def get_references(self, text: str) -> List[Reference]:
        references: List[Reference] = []
        codes = self.find_un_codes(text)

        for code in codes:
            start_index = text.upper().find(code)
            if start_index == -1:
                continue

            end_index = start_index + len(code)

            reference = Reference(
                type=ReferenceType.DOCUMENT_CODE,
                text=text[start_index:end_index],
                character_start=start_index,
                character_end=end_index,
            )

            try:
                reference = reference.get_with_normalize_entity_text()
                references.append(reference)
            except Exception:
                pass

        references = self.remove_overlapping_references(references)
        return references

    def find_un_codes(self, text: str) -> List[str]:
        words = re.split(r"\s+|,|\(|\)|\[|\]", text)

        found_codes = []
        for word in words:
            clean_word = word.strip(";:.").upper()

            if self.pattern.fullmatch(clean_word):
                found_codes.append(clean_word)

        return found_codes
