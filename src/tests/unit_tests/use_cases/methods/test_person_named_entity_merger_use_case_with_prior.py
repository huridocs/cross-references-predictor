from unittest import TestCase
from cross_references_predictor.use_cases.reference_destination_entities_use_case import ReferenceDestinationUseCase
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType


class TestPersonReferenceMergerUseCaseWithPrior(TestCase):
    def test_merge_with_prior_references(self):
        prior = [
            Reference(
                type=ReferenceType.PERSON,
                text="John Doe",
                group_name="John Doe",
                relevance_percentage=100,
            )
        ]
        use_case = ReferenceDestinationUseCase(prior_references=prior)

        new_entity = [
            Reference(
                type=ReferenceType.PERSON,
                text="John Doe",
                normalized_text="john doe",
                relevance_percentage=50,
            )
        ]

        result = use_case.group(new_entity)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "John Doe")
