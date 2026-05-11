from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_destination import ReferenceDestination
from cross_references_predictor.domain.reference_type import ReferenceType


class ReferenceDestinationUseCase:
    def __init__(self, prior_references: list[Reference] = None, language: str = "en"):
        self.prior_references = prior_references if prior_references else []
        self.language = language
        self.prior_groups: dict[str, ReferenceDestination] = dict()
        self._initialize_prior_groups()
        self.groups: dict[str, ReferenceDestination] = dict()

    def _initialize_prior_groups(self):
        sorted_prior_entities = sorted(self.prior_references, key=lambda x: x.relevance_percentage, reverse=True)
        for prior_entity in sorted_prior_entities:
            group_name = prior_entity.destination
            if group_name in self.prior_groups:
                self.prior_groups[group_name].references.append(prior_entity)
                continue

            self.prior_groups[group_name] = ReferenceDestination(
                type=prior_entity.type,
                name=prior_entity.destination,
                references=[prior_entity],
                top_relevance_entity=prior_entity,
            )

    def group(self, references: list[Reference]) -> list[ReferenceDestination]:
        self._calculate_relevance_scores(references)

        for named_entity in references:
            normalized_entity = named_entity.get_with_normalize_entity_text(self.language)

            if self._try_assign_to_prior_group(normalized_entity):
                continue

            if self._try_assign_to_existing_group(normalized_entity):
                continue

            self._create_new_group_for_entity(normalized_entity)

        self._remove_empty_references_groups()
        return list(self.groups.values())

    @staticmethod
    def _calculate_relevance_scores(references: list[Reference]):
        for named_entity in references:
            named_entity.set_relevance_score(references)

    def _try_assign_to_prior_group(self, named_entity: Reference) -> bool:
        for prior_group in self.prior_groups.values():
            if prior_group.belongs_to_destination(named_entity):
                named_entity.destination = prior_group.name
                prior_group.references = [named_entity]
                prior_group.top_relevance_entity = self._determine_top_relevance_entity(
                    prior_group.top_relevance_entity, named_entity
                )
                del self.prior_groups[prior_group.name]
                self.groups[prior_group.name] = prior_group
                return True
        return False

    def _try_assign_to_existing_group(self, named_entity: Reference) -> bool:
        for group in self.groups.values():
            if group.belongs_to_destination(named_entity):
                self._assign_to_existing_group(named_entity, group)
                return True
        return False

    def _assign_to_existing_group(self, named_entity: Reference, group: ReferenceDestination):
        better_group_name = self._choose_better_group_name(group.name, named_entity.text, named_entity.type)
        if better_group_name != group.name:
            del self.groups[group.name]
            group.name = better_group_name
            self.groups[better_group_name] = group
            for entity in group.references:
                entity.destination = better_group_name

        named_entity.destination = group.name
        group.top_relevance_entity = self._determine_top_relevance_entity(group.top_relevance_entity, named_entity)
        group.references.append(named_entity)

    @staticmethod
    def _choose_better_group_name(current_name: str, candidate_name: str, entity_type: ReferenceType) -> str:
        if entity_type in [ReferenceType.LOCATION, ReferenceType.PERSON, ReferenceType.ORGANIZATION]:
            if len(candidate_name) > len(current_name):
                return candidate_name
            if "," in candidate_name and "," not in current_name:
                return candidate_name

        return current_name

    @staticmethod
    def _determine_top_relevance_entity(current_top: Reference, candidate: Reference) -> Reference:
        return current_top if current_top.relevance_percentage > candidate.relevance_percentage else candidate

    def _create_new_group_for_entity(self, named_entity: Reference):
        group_name = self._get_group_name_for_entity(named_entity)
        named_entity.destination = group_name

        self.groups[group_name] = ReferenceDestination(
            type=named_entity.type, name=group_name, references=[named_entity], top_relevance_entity=named_entity
        )

    @staticmethod
    def _get_group_name_for_entity(named_entity: Reference) -> str:
        if named_entity.type == ReferenceType.DATE and named_entity.normalized_text:
            return named_entity.normalized_text

        return named_entity.text

    def _remove_empty_references_groups(self):
        keys_to_remove = []
        for key, group in self.groups.items():
            if group.type != ReferenceType.REFERENCE:
                continue
            if len(group.references) != 1:
                continue
            if group.references[0].relevance_percentage != 100:
                continue
            keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.groups[key]
