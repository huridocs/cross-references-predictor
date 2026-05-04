from abc import ABC, abstractmethod
from typing import List

from cross_references_predictor.domain.reference import Reference


class ReferenceExtractionMethod(ABC):
    @abstractmethod
    def get_references(self, text: str) -> List[Reference]:
        pass

    @staticmethod
    def remove_overlapping_references(references: List[Reference]) -> List[Reference]:
        sorted_references = sorted(references, key=lambda x: (x.character_start, -len(x.text)))
        result = []
        last_end = -1
        for entity in sorted_references:
            if entity.character_start >= last_end:
                result.append(entity)
                last_end = entity.character_end
        return result
