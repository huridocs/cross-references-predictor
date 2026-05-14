from abc import abstractmethod, ABC

from cross_references_predictor.domain.consolidated_destination import ConsolidatedDestination
from cross_references_predictor.domain.destination_detection import DestinationDetection
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.segment import Segment


class ReferencesStoreRepository(ABC):

    @abstractmethod
    def get_references(self) -> list[Reference]:
        pass

    @abstractmethod
    def get_references_by_type(self, reference_type: str) -> list[Reference]:
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
    def get_consolidated_destinations(self) -> list[ConsolidatedDestination]:
        pass

    @abstractmethod
    def save_consolidated_destinations(self, destinations: list[ConsolidatedDestination]) -> bool:
        pass

    @abstractmethod
    def reset_consolidated_destinations(self) -> bool:
        pass

    @abstractmethod
    def get_all_destinations(self) -> list[ConsolidatedDestination]:
        pass

    @abstractmethod
    def save_reference_occurrences(self, references: list[Reference]) -> bool:
        pass

    @abstractmethod
    def save_detection_script(self, script: DestinationDetection) -> bool:
        pass

    @abstractmethod
    def get_detection_scripts(self) -> list[DestinationDetection]:
        pass

    @abstractmethod
    def get_detection_script_by_destination_id(self, destination_id: str) -> DestinationDetection | None:
        pass

    @abstractmethod
    def delete_detection_script(self, destination_id: str) -> bool:
        pass

    @abstractmethod
    def save_negative_samples(self, destination_id: str, segments: list[Segment]) -> bool:
        pass

    @abstractmethod
    def get_negative_samples(self, destination_id: str) -> list[Segment]:
        pass
