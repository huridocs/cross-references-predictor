from unittest import TestCase
from cross_references_predictor.use_cases.reference_destination_entities_use_case import ReferenceDestinationUseCase
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType


class TestPersonReferenceMergerUseCase(TestCase):
    def setUp(self):
        self.use_case = ReferenceDestinationUseCase()

    def test_merge_same_person_names(self):
        name_entity_1 = Reference(type=ReferenceType.PERSON, text="John Doe", relevance_percentage=50)
        name_entity_2 = Reference(type=ReferenceType.PERSON, text="John Doe", relevance_percentage=50)
        name_entity_3 = Reference(type=ReferenceType.PERSON, text="Jane Smith", relevance_percentage=50)

        named_entities_grouped = self.use_case.group([name_entity_1, name_entity_2, name_entity_3])

        self.assertEqual(len(named_entities_grouped), 2)

    def test_merge_similar_person_names(self):
        name_entity_1 = Reference(type=ReferenceType.PERSON, text="John Doe", relevance_percentage=50)
        name_entity_2 = Reference(type=ReferenceType.PERSON, text="John Doe", relevance_percentage=80)

        named_entities_grouped = self.use_case.group([name_entity_1, name_entity_2])

        self.assertEqual(len(named_entities_grouped), 1)
        self.assertEqual(named_entities_grouped[0].name, "John Doe")

    def test_group_different_person_types(self):
        name_entity_1 = Reference(type=ReferenceType.PERSON, text="Alice", relevance_percentage=50)
        name_entity_2 = Reference(type=ReferenceType.ORGANIZATION, text="Alice Corp", relevance_percentage=50)

        named_entities_grouped = self.use_case.group([name_entity_1, name_entity_2])

        self.assertEqual(2, len(named_entities_grouped))

    def test_group_with_relevance_scores(self):
        name_entity_1 = Reference(type=ReferenceType.PERSON, text="John Doe", relevance_percentage=30)
        name_entity_2 = Reference(type=ReferenceType.PERSON, text="John Doe", relevance_percentage=80)

        named_entities_grouped = self.use_case.group([name_entity_1, name_entity_2])

        self.assertEqual(len(named_entities_grouped), 1)
        self.assertEqual(named_entities_grouped[0].top_relevance_entity.text, "John Doe")
        self.assertEqual(named_entities_grouped[0].top_relevance_entity.relevance_percentage, 80)
