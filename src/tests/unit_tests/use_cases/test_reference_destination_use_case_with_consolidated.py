from unittest import TestCase
from cross_references_predictor.use_cases.reference_destination_entities_use_case import ReferenceDestinationUseCase
from cross_references_predictor.domain.consolidated_destination import ConsolidatedDestination
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType


class TestReferenceDestinationUseCaseWithConsolidated(TestCase):
    def test_consolidated_destination_used_as_prior(self):
        consolidated = [
            ConsolidatedDestination(
                name="Maria P. Doo",
                type=ReferenceType.PERSON,
                alternative_names=["Maria P. D."],
            )
        ]
        use_case = ReferenceDestinationUseCase(consolidated_destinations=consolidated)

        new_entity = [Reference(type=ReferenceType.PERSON, text="Maria P. D.", normalized_text="maria p d")]

        result = use_case.group(new_entity)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Maria P. Doo")
        self.assertEqual(len(result[0].references), 1)

    def test_consolidated_destination_name_grows_longer(self):
        consolidated = [
            ConsolidatedDestination(
                name="Maria P. D.",
                type=ReferenceType.PERSON,
            )
        ]
        use_case = ReferenceDestinationUseCase(consolidated_destinations=consolidated)

        new_entity = [Reference(type=ReferenceType.PERSON, text="Maria P. Doo", normalized_text="maria p doo")]

        result = use_case.group(new_entity)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Maria P. Doo")

    def test_consolidated_destination_from_reference_does_not_change_name(self):
        consolidated = [
            ConsolidatedDestination(
                name="John D.",
                type=ReferenceType.PERSON,
                is_from_reference=True,
            )
        ]
        use_case = ReferenceDestinationUseCase(consolidated_destinations=consolidated)

        new_entity = [Reference(type=ReferenceType.PERSON, text="John Doe", normalized_text="john doe")]

        result = use_case.group(new_entity)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "John D.")

    def test_prior_reference_and_consolidated_destination_both_used(self):
        prior = [
            Reference(
                type=ReferenceType.PERSON,
                text="Jane Smith",
                destination="Jane Smith",
                relevance_percentage=100,
            )
        ]
        consolidated = [
            ConsolidatedDestination(
                name="John Doe",
                type=ReferenceType.PERSON,
            )
        ]
        use_case = ReferenceDestinationUseCase(prior_references=prior, consolidated_destinations=consolidated)

        new_entities = [
            Reference(type=ReferenceType.PERSON, text="Jane Smith", normalized_text="jane smith"),
            Reference(type=ReferenceType.PERSON, text="John D.", normalized_text="john d"),
        ]

        result = use_case.group(new_entities)

        self.assertEqual(len(result), 2)
        names = [r.name for r in result]
        self.assertIn("Jane Smith", names)
        self.assertIn("John Doe", names)

    def test_new_destination_uses_longest_name(self):
        use_case = ReferenceDestinationUseCase()

        new_entities = [
            Reference(type=ReferenceType.PERSON, text="Maria P. D.", normalized_text="maria p d"),
            Reference(type=ReferenceType.PERSON, text="Maria P. Doo", normalized_text="maria p doo"),
        ]

        result = use_case.group(new_entities)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Maria P. Doo")
