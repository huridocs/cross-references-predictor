from unittest import TestCase
from cross_references_predictor.domain.segment import Segment
from pdf_features import Rectangle


class TestSegment(TestCase):
    def test_create_segment(self):
        segment = Segment(
            text="Test text",
            page_number=1,
            segment_number=1,
            type="Text",
            source_id="test.pdf",
            bounding_box=Rectangle.from_width_height(left=0, top=0, width=100, height=50),
        )

        self.assertEqual(segment.text, "Test text")
        self.assertEqual(segment.page_number, 1)
        self.assertEqual(segment.segment_number, 1)

    def test_from_segment_box(self):
        segment_box = {
            "text": "Test segment",
            "page_number": 1,
            "left": 0,
            "top": 0,
            "width": 100,
            "height": 50,
        }

        segment = Segment.from_segment_box(segment_box, "test.pdf", 1)

        self.assertEqual(segment.text, "Test segment")
        self.assertEqual(segment.page_number, 1)
        self.assertEqual(segment.segment_number, 1)
        self.assertEqual(segment.source_id, "test.pdf")

    def test_from_text(self):
        segment = Segment.from_text("Hello world", "doc.pdf")

        self.assertEqual(segment.text, "Hello world")
        self.assertEqual(segment.source_id, "doc.pdf")
        self.assertEqual(segment.page_number, 0)
        self.assertEqual(segment.segment_number, 0)

    def test_segment_with_bounding_box(self):
        bounding_box = Rectangle.from_width_height(left=10, top=20, width=100, height=50)
        segment = Segment(
            text="Test",
            page_number=1,
            segment_number=1,
            bounding_box=bounding_box,
        )

        self.assertEqual(segment.bounding_box.left, 10)
        self.assertEqual(segment.bounding_box.top, 20)
        self.assertEqual(segment.bounding_box.width, 100)
        self.assertEqual(segment.bounding_box.height, 50)
