from pydantic import BaseModel

from cross_references_predictor.domain.reference_type import ReferenceType


class DestinationSeed(BaseModel):
    name: str
    type: ReferenceType
    external_id: str | None = None
    alternative_names: list[str] = []


class SaveDestinationsRequest(BaseModel):
    namespace: str
    language: str = "en"
    destinations: list[DestinationSeed]
