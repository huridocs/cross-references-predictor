from typing import Optional
from dateparser.search import search_dates
from dateparser_data.settings import default_parsers
from pdf_features.Rectangle import Rectangle
from pdf_features.PdfWord import PdfWord
from pdf_token_type_labels import TokenType
from pydantic import BaseModel
from unidecode import unidecode
import dateparser
import logging

from cross_references_predictor.configuration import TITLES_TYPES, SEPARATOR
from cross_references_predictor.domain.reference_type import ReferenceType
import country_converter as coco
from cross_references_predictor.domain.segment import Segment

logging.getLogger("country_converter").setLevel(logging.ERROR)


class Reference(BaseModel):
    type: ReferenceType
    text: str
    normalized_text: str = ""
    character_start: int = 0
    character_end: int = 0
    destination: str = ""
    segment_type: TokenType = TokenType.TEXT
    appearance_count: int = 0
    percentage_to_segment_text: int = 0
    first_type_appearance: bool = False
    last_type_appearance: bool = False
    segment: Optional[Segment] = None
    text_positions: list[Rectangle] = []
    relevance_percentage: int = 0

    @staticmethod
    def from_segment(reference: "Reference", segment: Segment, destination: str = "") -> "Reference":
        reference.segment = segment
        if not reference.destination:
            reference.destination = destination
        return reference

    @staticmethod
    def normalize_text(text: str) -> str:
        normalized_text = text.lower().strip()
        normalized_text = normalized_text.replace(",", " ")
        normalized_text = normalized_text.replace(".", " ")
        normalized_text = " ".join(sorted(normalized_text.split()))
        return unidecode(normalized_text)

    @staticmethod
    def normalize_reference(text: str) -> str:
        return text.split(SEPARATOR)[0].strip()

    def normalize_location(self, text):
        iso_3 = coco.convert(names=[text], to="ISO3")
        return iso_3 if iso_3 != "not found" else self.normalize_text(text)

    def normalize_date(self, text, language: str = "en"):
        if self.normalized_text:
            return self.normalized_text

        parsers = [parser for parser in default_parsers if parser != "relative-time"]
        settings = {"STRICT_PARSING": True, "PARSERS": parsers}
        return (
            dateparser.parse(text, languages=[language]).strftime("%Y-%m-%d")
            if search_dates(self.text, languages=[language], settings=settings)
            else self.text
        )

    def get_with_normalize_entity_text(self, language: str = "en"):
        if self.type == ReferenceType.REFERENCE:
            return self

        normalization_functions = {
            ReferenceType.PERSON: self.normalize_text,
            ReferenceType.ORGANIZATION: self.normalize_text,
            ReferenceType.LOCATION: self.normalize_location,
            ReferenceType.DATE: lambda x: self.normalize_date(x, language),
            ReferenceType.LAW: self.normalize_text,
            ReferenceType.DOCUMENT_CODE: lambda x: x.strip(),
        }

        self.normalized_text = normalization_functions[self.type](self.text)
        return self

    def set_relevance_score(self, references: list["Reference"]):
        self.set_score_parameters(references)

        if self.type == ReferenceType.REFERENCE:
            self.relevance_percentage = 100 if str(self.segment_type).lower() in TITLES_TYPES else 0
            return self

        if not self.segment or not self.segment.text:
            return self

        self.relevance_percentage = int(10 * self.percentage_to_segment_text / 100)
        if self.first_type_appearance:
            self.relevance_percentage += 15
        if self.last_type_appearance:
            self.relevance_percentage += 15
        if str(self.segment_type).lower() in TITLES_TYPES:
            self.relevance_percentage += 60
        if str(self.segment_type).lower() == "page header":
            self.relevance_percentage += 30
        if str(self.segment_type).lower() in "text":
            self.relevance_percentage += 15

        return self

    def set_score_parameters(self, references):
        self.appearance_count = sum(1 for ne in references if ne.type == self.type and ne.text == self.text)
        if self.segment and hasattr(self.segment, "text") and self.segment.text:
            self.percentage_to_segment_text = int(100 * len(self.text) / len(self.segment.text))
        else:
            self.percentage_to_segment_text = 0
        same_type_entities = [ne for ne in references if ne.type == self.type]
        if same_type_entities:
            self.first_type_appearance = same_type_entities[0].text == self.text
            self.last_type_appearance = same_type_entities[-1].text == self.text
        else:
            self.first_type_appearance = False
            self.last_type_appearance = False

    def add_positions_from_pdf_words(self, pdf_words: list[PdfWord]) -> "Reference":
        if not self.segment or not self.segment.bounding_box:
            return self

        bounding_boxes = []
        for position in pdf_words:
            bounding_boxes.append(position.bounding_box)

        self.text_positions = bounding_boxes
        return self

    def has_iso_code(self):
        if self.type != ReferenceType.LOCATION:
            return True

        iso_3 = coco.convert(names=[self.text], to="ISO3")
        return iso_3 != "not found"
