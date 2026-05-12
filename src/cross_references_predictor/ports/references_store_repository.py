from abc import abstractmethod, ABC

from cross_references_predictor.domain.consolidated_destination import ConsolidatedDestination
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.segment import Segment


class ReferencesStoreRepository(ABC):

    @abstractmethod
    def get_references(self) -> list[Reference]:
        pass

    @abstractmethod
    def save_references(self, references: list[Reference]) -> bool:
        pass

    @abstractmethod
    def delete_database(self):
        pass

    @abstractmethod
    def save_segments(self, segments: list[Segment]) -> bool:
        pass

    @abstractmethod
    def get_segments(self, identifier: str) -> list[Segment]:
        pass

    @abstractmethod
    def get_reference_by_id(self, reference_id: int) -> dict | None:
        pass

    @abstractmethod
    def update_reference(self, reference_id: int, updates: dict) -> bool:
        pass

    @abstractmethod
    def delete_reference(self, reference_id: int) -> bool:
        pass

    @abstractmethod
    def get_consolidated_destinations(self) -> list[ConsolidatedDestination]:
        pass

    @abstractmethod
    def save_consolidated_destinations(self, destinations: list[ConsolidatedDestination]) -> bool:
        pass

    @abstractmethod
    def reset_consolidated_destinations(self) -> bool:
        pass
