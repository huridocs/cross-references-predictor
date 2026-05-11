from pdf_features import Rectangle
from pydantic import BaseModel
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from typing import Optional
from cross_references_predictor.domain.segment import Segment


class ReferencePersistence(BaseModel):
    id: int | None = None
    group_name: str = ""
    type: ReferenceType
    text: str
    normalized_text: str = ""
    character_start: int = 0
    character_end: int = 0
    relevance_percentage: int = 0
    segment_text: Optional[str] = None
    segment_page_number: Optional[int] = None
    segment_segment_number: Optional[int] = None
    segment_type: str = "Text"
    segment_source_id: Optional[str] = None
    segment_bounding_box_left: Optional[int] = None
    segment_bounding_box_top: Optional[int] = None
    segment_bounding_box_width: Optional[int] = None
    segment_bounding_box_height: Optional[int] = None
    appearance_count: int = 0
    percentage_to_segment_text: int = 0
    first_type_appearance: bool = False
    last_type_appearance: bool = False

    def to_reference(self) -> Reference:
        segment = Segment(
            text=self.segment_text if self.segment_text else "",
            page_number=self.segment_page_number if self.segment_segment_number else 0,
            segment_number=self.segment_segment_number if self.segment_segment_number else 0,
            type=self.segment_type,
            source_id=self.segment_source_id if self.segment_source_id else "",
            bounding_box=Rectangle.from_width_height(
                left=self.segment_bounding_box_left if self.segment_bounding_box_left else 0,
                top=self.segment_bounding_box_top if self.segment_bounding_box_top else 0,
                width=self.segment_bounding_box_width if self.segment_bounding_box_width else 0,
                height=self.segment_bounding_box_height if self.segment_bounding_box_height else 0,
            ),
        )

        return Reference(
            id=self.id,
            type=ReferenceType(self.type),
            text=self.text,
            normalized_text=self.normalized_text,
            character_start=self.character_start,
            character_end=self.character_end,
            destination=self.group_name,
            segment=segment,
            appearance_count=self.appearance_count,
            percentage_to_segment_text=self.percentage_to_segment_text,
            first_type_appearance=self.first_type_appearance,
            last_type_appearance=self.last_type_appearance,
            relevance_percentage=self.relevance_percentage,
        )

    @staticmethod
    def from_row(row, columns: list[str]):
        col_map = {name: idx for idx, name in enumerate(columns)}
        return ReferencePersistence(
            id=row[col_map["id"]],
            type=ReferenceType(row[col_map["type"]]),
            text=row[col_map["text"]],
            normalized_text=row[col_map["normalized_text"]],
            character_start=row[col_map["character_start"]],
            character_end=row[col_map["character_end"]],
            group_name=row[col_map["group_id"]],
            segment_text=row[col_map.get("segment_text")],
            segment_page_number=row[col_map.get("segment_page_number")],
            segment_segment_number=row[col_map.get("segment_segment_number")],
            segment_type=row[col_map.get("segment_type")],
            segment_source_id=row[col_map.get("segment_source_id")],
            segment_bounding_box_left=row[col_map.get("segment_bounding_box_left")],
            segment_bounding_box_top=row[col_map.get("segment_bounding_box_top")],
            segment_bounding_box_width=row[col_map.get("segment_bounding_box_width")],
            segment_bounding_box_height=row[col_map.get("segment_bounding_box_height")],
            appearance_count=row[col_map["appearance_count"]],
            percentage_to_segment_text=row[col_map["percentage_to_segment_text"]],
            first_type_appearance=bool(row[col_map["first_type_appearance"]]),
            last_type_appearance=bool(row[col_map["last_type_appearance"]]),
            relevance_percentage=row[col_map["relevance_percentage"]],
        )

    @staticmethod
    def from_reference(reference: Reference) -> "ReferencePersistence":
        segment = reference.segment
        return ReferencePersistence(
            id=reference.id,
            type=reference.type,
            text=reference.text,
            normalized_text=reference.normalized_text,
            character_start=reference.character_start,
            character_end=reference.character_end,
            group_name=reference.destination,
            segment_text=segment.text if segment else None,
            segment_page_number=segment.page_number if segment else None,
            segment_segment_number=segment.segment_number if segment else None,
            segment_type=segment.type if segment else "Text",
            segment_source_id=segment.source_id if segment else None,
            segment_bounding_box_left=segment.bounding_box.left if segment and segment.bounding_box else None,
            segment_bounding_box_top=segment.bounding_box.top if segment and segment.bounding_box else None,
            segment_bounding_box_width=segment.bounding_box.width if segment and segment.bounding_box else None,
            segment_bounding_box_height=segment.bounding_box.height if segment and segment.bounding_box else None,
            appearance_count=reference.appearance_count,
            percentage_to_segment_text=reference.percentage_to_segment_text,
            first_type_appearance=reference.first_type_appearance,
            last_type_appearance=reference.last_type_appearance,
            relevance_percentage=reference.relevance_percentage,
        )
