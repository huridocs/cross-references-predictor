from pydantic import BaseModel

from cross_references_predictor.domain.reference_destination import ReferenceDestination
from cross_references_predictor.drivers.rest.response_entities.reference_text_response import ReferenceTextResponse
from cross_references_predictor.drivers.rest.response_entities.reference_response import ReferenceResponse


class CrossReferencesResponse(BaseModel):
    references: list
    destinations: list

    @staticmethod
    def from_destinations(destinations: list[ReferenceDestination]) -> "CrossReferencesResponse":
        all_references = []
        destinations_list = []

        for group in destinations:
            references_list = [ReferenceResponse.from_reference(ref) for ref in group.references]
            all_references.extend(references_list)

            entity_texts = [
                ReferenceTextResponse.from_entity(references_list, ReferenceResponse.from_reference(ref))
                for ref in group.references
            ]

            destinations_list.append(
                {
                    "name": group.name,
                    "type": str(group.type),
                    "source_id": group.source_id,
                    "references": entity_texts,
                    "top_relevance_entity": (
                        ReferenceResponse.from_reference(group.top_relevance_entity).model_dump()
                        if group.top_relevance_entity
                        else None
                    ),
                }
            )

        return CrossReferencesResponse(
            references=[ref.model_dump() for ref in all_references],
            destinations=destinations_list,
        )
