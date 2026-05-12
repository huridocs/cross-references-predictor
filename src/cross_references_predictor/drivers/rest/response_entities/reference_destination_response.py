from pydantic import BaseModel

from cross_references_predictor.domain.reference_destination import ReferenceDestination
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.drivers.rest.response_entities.reference_text_response import ReferenceTextResponse
from cross_references_predictor.drivers.rest.response_entities.reference_response import ReferenceResponse


class ReferenceDestinationResponse(BaseModel):
    name: str
    type: ReferenceType
    destination_id: str = ""
    references: list[ReferenceTextResponse] = []
    top_relevance_entity: ReferenceResponse

    @staticmethod
    def from_destination(
        references: list[ReferenceResponse], reference: ReferenceResponse, group: ReferenceDestination
    ) -> "ReferenceDestinationResponse":
        entity_text = ReferenceTextResponse.from_entity(references, reference)
        if group.top_relevance_entity and group.top_relevance_entity.relevance_percentage > reference.relevance_percentage:
            top_relevance_entity = ReferenceResponse.from_reference(group.top_relevance_entity)
        else:
            top_relevance_entity = reference

        return ReferenceDestinationResponse(
            name=reference.destination,
            type=reference.type,
            destination_id=group.destination_id,
            references=[entity_text],
            top_relevance_entity=top_relevance_entity,
        )
