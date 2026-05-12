from dataclasses import dataclass

from pdf_features import Rectangle

from cross_references_predictor.domain.segment import Segment


@dataclass
class PersistenceReferenceDestination:
    id: int
    title: str
    page_number: int
    segment_number: int
    destination_id: str
    left: int
    top: int
    width: int
    height: int

    @staticmethod
    def from_row(row):
        return PersistenceReferenceDestination(
            id=row[0],
            title=row[1],
            page_number=row[2],
            segment_number=row[3],
            destination_id=row[4],
            left=row[5],
            top=row[6],
            width=row[7],
            height=row[8],
        )

    def get_segment(self) -> Segment:
        bounding_box = Rectangle.from_width_height(left=self.left, top=self.top, width=self.width, height=self.height)
        return Segment(
            text=self.title,
            page_number=self.page_number,
            bounding_box=bounding_box,
            pdf_name=self.destination_id,
            segment_number=self.segment_number,
        )
