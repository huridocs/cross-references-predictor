from pydantic import BaseModel

from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.drivers.rest.response_entities.bounding_box_response import BoundingBoxResponse


class SegmentResponse(BaseModel):
    text: str
    page_number: int
    segment_number: int
    character_start: int
    character_end: int
    bounding_box: BoundingBoxResponse
    pdf_name: str = ""

    @staticmethod
    def from_reference(reference: Reference) -> "SegmentResponse":
        return SegmentResponse(
            text=reference.segment.text,
            page_number=reference.segment.page_number,
            segment_number=reference.segment.segment_number,
            character_start=reference.character_start,
            character_end=reference.character_end,
            bounding_box=BoundingBoxResponse.from_rectangle(reference.segment.bounding_box),
            pdf_name=reference.segment.pdf_name,
        )
