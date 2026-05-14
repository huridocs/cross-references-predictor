from pydantic import BaseModel


class SaveReferencesRequest(BaseModel):
    namespace: str
    language: str = "en"
    references: list
