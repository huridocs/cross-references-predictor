from pydantic import BaseModel
from typing import Optional
from cross_references_predictor.domain.reference_type import ReferenceType


class DestinationInfo(BaseModel):
    type: ReferenceType
    name: str
    segment_text: Optional[str] = None
    segment_pdf_name: Optional[str] = None

    def __hash__(self):
        return hash((self.type, self.name, self.segment_text, self.segment_pdf_name))

    def __eq__(self, other):
        if not isinstance(other, DestinationInfo):
            return False
        return (
            self.type == other.type
            and self.name == other.name
            and self.segment_text == other.segment_text
            and self.segment_pdf_name == other.segment_pdf_name
        )

    def get_destination_id(self) -> str:
        parts = [str(self.type), self.name]
        if self.segment_text:
            parts.append(self.segment_text)
        if self.segment_pdf_name:
            parts.append(self.segment_pdf_name)
        return " ||| ".join(parts)
