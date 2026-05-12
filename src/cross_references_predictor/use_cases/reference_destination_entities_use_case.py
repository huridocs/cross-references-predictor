from cross_references_predictor.domain.consolidated_destination import ConsolidatedDestination
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_destination import ReferenceDestination
from cross_references_predictor.domain.reference_type import ReferenceType


class ReferenceDestinationUseCase:
    def __init__(
        self,
        prior_references: list[Reference] = None,
        language: str = "en",
        consolidated_destinations: list[ConsolidatedDestination] = None,
    ):
        self.prior_references = prior_references if prior_references else []
        self.language = language
        self.consolidated_destinations = consolidated_destinations if consolidated_destinations else []
        self.prior_groups: dict[str, ReferenceDestination] = dict()
        self._initialize_prior_groups()
        self._initialize_consolidated_groups()
        self.groups: dict[str, ReferenceDestination] = dict()

    def _initialize_prior_groups(self):
        sorted_prior_entities = sorted(self.prior_references, key=lambda x: x.relevance_percentage, reverse=True)
        for prior_entity in sorted_prior_entities:
            prior_entity.is_from_current_extraction = False
            group_name = prior_entity.destination
            if group_name in self.prior_groups:
                self.prior_groups[group_name].references.append(prior_entity)
                continue

            group = ReferenceDestination(
                type=prior_entity.type,
                name=prior_entity.destination,
                references=[prior_entity],
                is_name_fixed=True,
                top_relevance_entity=prior_entity,
            )
            self.prior_groups[group_name] = group

    def _initialize_consolidated_groups(self):
        for consolidated in self.consolidated_destinations:
            if consolidated.name in self.prior_groups:
                self.prior_groups[consolidated.name].known_forms.extend([consolidated.name] + consolidated.alternative_names)
                if consolidated.is_from_reference:
                    self.prior_groups[consolidated.name].is_name_fixed = True
                continue

            group = ReferenceDestination(
                type=consolidated.type,
                name=consolidated.name,
                known_forms=[consolidated.name] + consolidated.alternative_names,
                is_name_fixed=consolidated.is_from_reference,
                top_relevance_entity=None,
            )
            self.prior_groups[consolidated.name] = group

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
        return self._get_new_destinations()

    def _get_new_destinations(self) -> list[ReferenceDestination]:
        for group in self.groups.values():
            group.references = [ref for ref in group.references if getattr(ref, "is_from_current_extraction", True)]
        return list(self.groups.values())

    @staticmethod
    def _calculate_relevance_scores(references: list[Reference]):
        for named_entity in references:
            named_entity.set_relevance_score(references)

    def _try_assign_to_prior_group(self, named_entity: Reference) -> bool:
        for prior_group_name, prior_group in list(self.prior_groups.items()):
            if prior_group.belongs_to_destination(named_entity):
                named_entity.destination = prior_group.name
                if not prior_group.is_name_fixed:
                    better_group_name = self._choose_better_group_name(
                        prior_group.name, named_entity.text, named_entity.type
                    )
                    if better_group_name != prior_group.name:
                        prior_group.name = better_group_name
                prior_group.references.append(named_entity)
                prior_group.top_relevance_entity = self._determine_top_relevance_entity(
                    prior_group.top_relevance_entity, named_entity
                )
                self.groups[prior_group.name] = prior_group
                del self.prior_groups[prior_group_name]
                return True
        return False

    def _try_assign_to_existing_group(self, named_entity: Reference) -> bool:
        for group in self.groups.values():
            if group.belongs_to_destination(named_entity):
                self._assign_to_existing_group(named_entity, group)
                return True
        return False

    def _assign_to_existing_group(self, named_entity: Reference, group: ReferenceDestination):
        if not group.is_name_fixed:
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
    def _determine_top_relevance_entity(current_top: Reference | None, candidate: Reference) -> Reference:
        if current_top is None:
            return candidate
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
