from pydantic import BaseModel

from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.drivers.rest.response_entities.bounding_box_response import BoundingBoxResponse
from cross_references_predictor.drivers.rest.response_entities.segment_response import SegmentResponse


class ReferenceResponse(BaseModel):
    group_name: str
    type: ReferenceType
    text: str
    character_start: int
    character_end: int
    relevance_percentage: int = 0
    segment: SegmentResponse
    text_positions: list[BoundingBoxResponse] = []
    source_id: str

    @staticmethod
    def from_reference(reference: Reference):
        return ReferenceResponse(
            group_name=reference.group_name,
            type=reference.type,
            text=reference.text,
            character_start=reference.character_start,
            character_end=reference.character_end,
            relevance_percentage=reference.relevance_percentage,
            segment=SegmentResponse.from_reference(reference),
            source_id=reference.segment.source_id,
            text_positions=[BoundingBoxResponse.from_rectangle(x) for x in reference.text_positions],
        )
