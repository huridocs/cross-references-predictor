from unittest import TestCase

from cross_references_predictor.domain.destination_detection import DestinationDetection
from cross_references_predictor.domain.destination_info import DestinationInfo
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType


class TestDestinationInfo(TestCase):
    def test_get_destination_id_with_all_fields(self):
        dest = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test Section",
            segment_text="Full section text",
            segment_pdf_name="document.pdf",
        )

        dest_id = dest.get_destination_id()

        self.assertIn("REFERENCE", dest_id)
        self.assertIn("Test Section", dest_id)
        self.assertIn("Full section text", dest_id)
        self.assertIn("document.pdf", dest_id)

    def test_get_destination_id_without_optional_fields(self):
        dest = DestinationInfo(
            type=ReferenceType.PERSON,
            name="John Doe",
        )

        dest_id = dest.get_destination_id()

        self.assertIn("PERSON", dest_id)
        self.assertIn("John Doe", dest_id)

    def test_equality_same_fields(self):
        dest1 = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
            segment_text="Text",
            segment_pdf_name="doc.pdf",
        )
        dest2 = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
            segment_text="Text",
            segment_pdf_name="doc.pdf",
        )

        self.assertEqual(dest1, dest2)

    def test_equality_different_names(self):
        dest1 = DestinationInfo(type=ReferenceType.REFERENCE, name="Test A")
        dest2 = DestinationInfo(type=ReferenceType.REFERENCE, name="Test B")

        self.assertNotEqual(dest1, dest2)

    def test_equality_different_types(self):
        dest1 = DestinationInfo(type=ReferenceType.REFERENCE, name="Test")
        dest2 = DestinationInfo(type=ReferenceType.PERSON, name="Test")

        self.assertNotEqual(dest1, dest2)

    def test_equality_different_segments(self):
        dest1 = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
            segment_text="Text A",
        )
        dest2 = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
            segment_text="Text B",
        )

        self.assertNotEqual(dest1, dest2)


class TestDestinationDetection(TestCase):
    def test_from_destination_and_refs_collects_reference_ids(self):
        destination = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test Section",
        )

        refs = [
            Reference(id=1, type=ReferenceType.REFERENCE, text="Ref 1"),
            Reference(id=2, type=ReferenceType.REFERENCE, text="Ref 2"),
            Reference(id=None, type=ReferenceType.REFERENCE, text="Ref 3"),
        ]

        script = DestinationDetection.from_destination_and_refs(
            destination=destination,
            refs=refs,
            regex="(?P<reference>Test)",
            script="def is_reference(...): ...",
        )

        self.assertEqual(script.destination_id, destination.get_destination_id())
        self.assertEqual(script.destination, destination)
        self.assertEqual(script.reference_ids, [1, 2])
        self.assertEqual(script.regex, "(?P<reference>Test)")
        self.assertEqual(script.script, "def is_reference(...): ...")

    def test_detection_script_model_validation(self):
        destination = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
        )

        script = DestinationDetection(
            destination_id="REF|||Test|||Segment|||Doc",
            destination=destination,
            reference_ids=[1, 2, 3],
            regex="(?P<reference>Test)",
            script="code here",
        )

        self.assertEqual(script.destination_id, "REF|||Test|||Segment|||Doc")
        self.assertEqual(len(script.reference_ids), 3)

    def test_detection_script_with_created_at(self):
        destination = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
        )

        script = DestinationDetection(
            destination_id="REF|||Test",
            destination=destination,
            reference_ids=[1],
            regex="(?P<reference>)",
            script="pass",
            created_at="2024-01-01 12:00:00",
        )

        self.assertEqual(script.created_at, "2024-01-01 12:00:00")

    def test_detection_script_default_created_at_is_none(self):
        destination = DestinationInfo(type=ReferenceType.REFERENCE, name="Test")

        script = DestinationDetection(
            destination_id="REF|||Test",
            destination=destination,
            reference_ids=[],
            regex="",
            script="",
        )

        self.assertIsNone(script.created_at)
