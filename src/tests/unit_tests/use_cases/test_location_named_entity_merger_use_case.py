from unittest import TestCase
from cross_references_predictor.use_cases.reference_destination_entities_use_case import ReferenceDestinationUseCase
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType


class TestLocationReferenceMergerUseCase(TestCase):
    def setUp(self):
        self.use_case = ReferenceDestinationUseCase()

    def test_merge_locations_by_iso_code(self):
        location_entities = [
            Reference(type=ReferenceType.LOCATION, text="Turkey", relevance_percentage=80),
            Reference(type=ReferenceType.LOCATION, text="TUR", relevance_percentage=80),
            Reference(type=ReferenceType.LOCATION, text="ESP", relevance_percentage=80),
            Reference(type=ReferenceType.LOCATION, text="Spain", relevance_percentage=80),
        ]

        locations_grouped = self.use_case.group(location_entities)

        self.assertGreaterEqual(len(locations_grouped), 1)

    def test_merge_cities_with_similar_names(self):
        location_entities = [
            Reference(type=ReferenceType.LOCATION, text="Paris", relevance_percentage=80),
            Reference(type=ReferenceType.LOCATION, text="PARIS", relevance_percentage=80),
            Reference(type=ReferenceType.LOCATION, text="New York", relevance_percentage=80),
        ]

        locations_grouped = self.use_case.group(location_entities)

        self.assertGreaterEqual(len(locations_grouped), 1)

    def test_group_entities_with_same_text(self):
        location_entities = [
            Reference(type=ReferenceType.LOCATION, text="Madrid", relevance_percentage=50),
            Reference(type=ReferenceType.LOCATION, text="Madrid", relevance_percentage=80),
        ]

        locations_grouped = self.use_case.group(location_entities)

        self.assertEqual(len(locations_grouped), 1)
        self.assertEqual(locations_grouped[0].name, "Madrid")


class TestReferenceDestinationUseCaseEmpty(TestCase):
    def test_group_empty_returns_empty(self):
        use_case = ReferenceDestinationUseCase()
        result = use_case.group([])

        self.assertEqual(result, [])

    def test_group_single_entity(self):
        use_case = ReferenceDestinationUseCase()
        entities = [
            Reference(type=ReferenceType.DOCUMENT_CODE, text="A/79/150", character_start=0, character_end=8),
        ]

        result = use_case.group(entities)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "A/79/150")


class TestReferenceDestinationUseCaseWithPrior(TestCase):
    def test_group_with_prior_references(self):
        prior = [
            Reference(
                type=ReferenceType.REFERENCE,
                text="Section 1",
                destination="Section 1",
                relevance_percentage=100,
            )
        ]
        use_case = ReferenceDestinationUseCase(prior_references=prior)

        new_entity = [
            Reference(
                type=ReferenceType.REFERENCE,
                text="Section 1",
                normalized_text="Section 1",
                relevance_percentage=0,
            )
        ]

        result = use_case.group(new_entity)

        self.assertEqual(len(result), 0)
