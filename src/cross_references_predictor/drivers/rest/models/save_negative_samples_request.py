from pydantic import BaseModel


class NegativeSampleSegment(BaseModel):
    text: str
    pdf_name: str = ""
    page: int | None = None


class SaveNegativeSamplesRequest(BaseModel):
    namespace: str
    language: str = "en"
    destination_id: str
    segments: list[NegativeSampleSegment]
