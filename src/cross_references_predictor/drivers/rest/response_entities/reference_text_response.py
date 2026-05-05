from pydantic import BaseModel

from cross_references_predictor.drivers.rest.response_entities.reference_response import ReferenceResponse


class ReferenceTextResponse(BaseModel):
    index: int
    text: str

    @staticmethod
    def from_entity(entities: list[ReferenceResponse], entity: ReferenceResponse) -> "ReferenceTextResponse":
        index = entities.index(entity)
        return ReferenceTextResponse(index=index, text=entity.text)
