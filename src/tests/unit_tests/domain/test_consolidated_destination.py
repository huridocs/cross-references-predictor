from unittest import TestCase
from cross_references_predictor.domain.consolidated_destination import ConsolidatedDestination
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType


class TestConsolidatedDestination(TestCase):
    def test_add_alternative_name(self):
        dest = ConsolidatedDestination(name="Maria P. Doo", type=ReferenceType.PERSON)
        dest.add_alternative_name("Maria P. D.")
        self.assertIn("Maria P. D.", dest.alternative_names)

    def test_add_alternative_name_does_not_duplicate(self):
        dest = ConsolidatedDestination(name="Maria P. Doo", type=ReferenceType.PERSON)
        dest.add_alternative_name("Maria P. Doo")
        self.assertEqual(len(dest.alternative_names), 0)

    def test_update_name_longer(self):
        dest = ConsolidatedDestination(name="Maria P. D.", type=ReferenceType.PERSON)
        dest.update_name("Maria P. Doo")
        self.assertEqual(dest.name, "Maria P. Doo")
        self.assertIn("Maria P. D.", dest.alternative_names)

    def test_update_name_does_not_change_when_shorter(self):
        dest = ConsolidatedDestination(name="Maria P. Doo", type=ReferenceType.PERSON)
        dest.update_name("Maria P. D.")
        self.assertEqual(dest.name, "Maria P. Doo")
        self.assertIn("Maria P. D.", dest.alternative_names)

    def test_belongs_to_reference_matches_similar_name(self):
        dest = ConsolidatedDestination(
            name="Maria P. Doo",
            type=ReferenceType.PERSON,
            alternative_names=["Maria P. D."],
        )
        ref = Reference(type=ReferenceType.PERSON, text="Maria P. D.")
        self.assertTrue(dest.belongs_to_reference(ref))

    def test_belongs_to_reference_does_not_match_different_type(self):
        dest = ConsolidatedDestination(name="Maria P. Doo", type=ReferenceType.PERSON)
        ref = Reference(type=ReferenceType.ORGANIZATION, text="Maria P. Doo")
        self.assertFalse(dest.belongs_to_reference(ref))

    def test_merge_with_other_longer_name(self):
        dest1 = ConsolidatedDestination(name="Maria P. D.", type=ReferenceType.PERSON)
        dest2 = ConsolidatedDestination(name="Maria P. Doo", type=ReferenceType.PERSON)
        dest1.merge_with(dest2)
        self.assertEqual(dest1.name, "Maria P. Doo")
        self.assertIn("Maria P. D.", dest1.alternative_names)
