from pydantic import BaseModel


class ReferenceOccurrence(BaseModel):
    text: str
    destination: str
    pdf_name: str = ""
    page: int | None = None
    segment_text: str | None = None
    character_start: int | None = None
    character_end: int | None = None


class SaveReferenceOccurrencesRequest(BaseModel):
    namespace: str
    language: str = "en"
    occurrences: list[ReferenceOccurrence]
