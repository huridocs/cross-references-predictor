from pydantic import BaseModel


class ReferenceOccurrence(BaseModel):
    text: str
    destination: str
    pdf_name: str = ""
    page: int | None = None
    segment_text: str | None = None


class SaveReferenceOccurrencesRequest(BaseModel):
    namespace: str
    language: str = "en"
    occurrences: list[ReferenceOccurrence]
