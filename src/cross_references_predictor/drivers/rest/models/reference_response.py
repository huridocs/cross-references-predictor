from pydantic import BaseModel

from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.drivers.rest.models.bounding_box_response import BoundingBoxResponse
from cross_references_predictor.drivers.rest.models.segment_response import SegmentResponse


class ReferenceResponse(BaseModel):
    destination: str
    type: ReferenceType
    text: str
    character_start: int
    character_end: int
    relevance_percentage: int = 0
    segment: SegmentResponse
    text_positions: list[BoundingBoxResponse] = []
    pdf_name: str

    @staticmethod
    def from_reference(reference: Reference):
        return ReferenceResponse(
            destination=reference.destination,
            type=reference.type,
            text=reference.text,
            character_start=reference.character_start,
            character_end=reference.character_end,
            relevance_percentage=reference.relevance_percentage,
            segment=SegmentResponse.from_reference(reference),
            pdf_name=reference.segment.pdf_name if reference.segment else "",
            text_positions=[BoundingBoxResponse.from_rectangle(x) for x in reference.text_positions],
        )
