from pdf_features import Rectangle
from pydantic import BaseModel


class Segment(BaseModel):
    id: int | None = None
    text: str
    page_number: int
    segment_number: int
    type: str = "Text"
    pdf_name: str = ""
    bounding_box: Rectangle = Rectangle.from_width_height(left=0, top=0, width=0, height=0)
    page_width: int = 0
    page_height: int = 0

    @staticmethod
    def from_segment_box(segment_box_dict: dict, pdf_name: str, segment_number: int):
        return Segment(
            text=segment_box_dict["text"],
            page_number=segment_box_dict["page_number"],
            type=segment_box_dict.get("type", "Text"),
            segment_number=segment_number,
            pdf_name=pdf_name,
            bounding_box=Rectangle.from_width_height(
                left=int(segment_box_dict["left"]),
                top=int(segment_box_dict["top"]),
                width=int(segment_box_dict["width"]),
                height=int(segment_box_dict["height"]),
            ),
            page_width=segment_box_dict.get("page_width", 0),
            page_height=segment_box_dict.get("page_height", 0),
        )

    @staticmethod
    def from_text(text: str, pdf_name: str = None):
        return Segment(
            text=text,
            page_number=0,
            segment_number=0,
            type="Text",
            pdf_name=pdf_name if pdf_name else "default",
            bounding_box=Rectangle.from_width_height(left=0, top=0, width=0, height=0),
        )
