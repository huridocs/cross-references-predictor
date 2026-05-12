from pydantic import BaseModel
from typing import Optional
from cross_references_predictor.domain.destination_info import DestinationInfo


class DestinationDetection(BaseModel):
    destination_id: str
    destination: DestinationInfo
    reference_ids: list[int]
    regex: str
    script: str
    created_at: Optional[str] = None

    @staticmethod
    def from_destination_and_refs(
        destination: DestinationInfo,
        refs: list,
        regex: str,
        script: str,
    ) -> "DestinationDetection":
        reference_ids = [ref.id for ref in refs if ref.id is not None]
        return DestinationDetection(
            destination_id=destination.get_destination_id(),
            destination=destination,
            reference_ids=reference_ids,
            regex=regex,
            script=script,
        )
