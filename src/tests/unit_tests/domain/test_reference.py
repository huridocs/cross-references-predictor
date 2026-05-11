from unittest import TestCase
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.domain.segment import Segment
from pdf_features import Rectangle


class TestReference(TestCase):
    def test_create_reference(self):
        reference = Reference(
            type=ReferenceType.DOCUMENT_CODE,
            text="A/79/150",
            character_start=0,
            character_end=8,
        )

        self.assertEqual(reference.type, ReferenceType.DOCUMENT_CODE)
        self.assertEqual(reference.text, "A/79/150")
        self.assertEqual(reference.character_start, 0)
        self.assertEqual(reference.character_end, 8)

    def test_normalize_text(self):
        reference = Reference(
            type=ReferenceType.PERSON,
            text="John Doe",
        )

        normalized = reference.normalize_text("John Doe")

        self.assertEqual("doe john", normalized)

    def test_normalize_text_removes_punctuation(self):
        reference = Reference(
            type=ReferenceType.PERSON,
            text="John, Doe",
        )

        normalized = reference.normalize_text("John, Doe")

        self.assertEqual("doe john", normalized)

    def test_from_segment(self):
        segment = Segment(
            text="Test segment",
            page_number=1,
            segment_number=1,
            type="Text",
            source_id="test.pdf",
        )
        reference = Reference(
            type=ReferenceType.REFERENCE,
            text="Section 1",
        )

        result = Reference.from_segment(reference, segment, "Section 1")

        self.assertEqual(result.segment, segment)
        self.assertEqual(result.destination, "Section 1")

    def test_has_iso_code_true_for_valid_location(self):
        reference = Reference(
            type=ReferenceType.LOCATION,
            text="USA",
        )

        result = reference.has_iso_code()

        self.assertTrue(result)

    def test_has_iso_code_false_for_invalid_location(self):
        reference = Reference(
            type=ReferenceType.LOCATION,
            text="Nonexistentland",
        )

        result = reference.has_iso_code()

        self.assertFalse(result)


class TestReferenceIntegration(TestCase):
    def test_reference_with_segment(self):
        segment = Segment(
            text="Test segment text",
            page_number=1,
            segment_number=1,
            type="Text",
            source_id="test.pdf",
            bounding_box=Rectangle.from_width_height(left=0, top=0, width=100, height=50),
            page_width=612,
            page_height=792,
        )
        reference = Reference(
            type=ReferenceType.DOCUMENT_CODE,
            text="A/79/150",
            character_start=0,
            character_end=8,
            segment=segment,
        )

        self.assertEqual(reference.segment, segment)
        self.assertEqual(reference.segment.page_number, 1)

    def test_set_relevance_score(self):
        references = [
            Reference(type=ReferenceType.DOCUMENT_CODE, text="A/79/150", character_start=0, character_end=8),
            Reference(type=ReferenceType.DOCUMENT_CODE, text="A/79/150", character_start=0, character_end=8),
        ]

        reference = Reference(
            type=ReferenceType.DOCUMENT_CODE,
            text="A/79/150",
            character_start=0,
            character_end=8,
        )
        result = reference.set_relevance_score(references)

        self.assertEqual(result.appearance_count, 2)
        self.assertTrue(result.first_type_appearance)
        self.assertTrue(result.last_type_appearance)
