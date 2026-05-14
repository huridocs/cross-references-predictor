from unittest import TestCase
from unittest.mock import MagicMock, patch

from cross_references_predictor.domain.destination_detection import DestinationDetection
from cross_references_predictor.domain.destination_info import DestinationInfo
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.domain.segment import Segment
from pdf_features import Rectangle

from cross_references_predictor.use_cases.generate_detection_scripts_use_case import (
    GenerateDestinationDetectionsUseCase,
    SENTENCE_SPLIT_PATTERN,
)


class TestGenerateDestinationDetectionsUseCase(TestCase):
    def setUp(self):
        self.mock_llm_service = MagicMock()
        self.mock_repository = MagicMock()

        self.use_case = GenerateDestinationDetectionsUseCase(
            llm_service=self.mock_llm_service,
            repository=self.mock_repository,
        )

    def _create_segment(self, text: str, pdf_name: str = "doc.pdf") -> Segment:
        return Segment(
            text=text,
            page_number=1,
            segment_number=1,
            type="Text",
            pdf_name=pdf_name,
            bounding_box=Rectangle.from_width_height(0, 0, 100, 50),
        )

    def _create_reference(
        self,
        ref_id: int,
        text: str,
        destination: str,
        segment: Segment = None,
    ) -> Reference:
        return Reference(
            id=ref_id,
            type=ReferenceType.REFERENCE,
            text=text,
            normalized_text=text,
            destination=destination,
            segment=segment,
        )

    def test_execute_returns_empty_when_no_references(self):
        self.mock_repository.get_references_by_type.return_value = []

        result = self.use_case.execute()

        self.assertEqual(result, [])
        self.mock_repository.get_references_by_type.assert_called_once_with(ReferenceType.REFERENCE)

    def test_execute_groups_references_by_destination(self):
        segment1 = self._create_segment("Reference to Section 1 in this document", "doc1.pdf")

        ref1 = self._create_reference(1, "Section 1", "Section 1", segment1)
        ref2 = self._create_reference(2, "Sec. 1", "Section 1", segment1)

        all_refs = [ref1, ref2]
        self.mock_repository.get_references_by_type.return_value = all_refs

        self.mock_llm_service.query.return_value = "(?P<reference>Section\\s+1)"

        result = self.use_case.execute()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].destination.name, "Section 1")
        self.mock_repository.save_detection_script.assert_called_once()

    def test_execute_creates_separate_scripts_for_different_destinations(self):
        segment1 = self._create_segment("Reference to Doc A here", "doc1.pdf")
        segment2 = self._create_segment("Reference to Doc B here", "doc2.pdf")

        ref1 = self._create_reference(1, "Doc A", "Doc A", segment1)
        ref2 = self._create_reference(2, "Doc B", "Doc B", segment2)

        self.mock_repository.get_references_by_type.return_value = [ref1, ref2]
        self.mock_llm_service.query.side_effect = [
            "(?P<reference>Doc\\s+A)",
            "def is_reference(match_text, sentence_text, paragraph_text):\n    return True",
            "(?P<reference>Doc\\s+B)",
            "def is_reference(match_text, sentence_text, paragraph_text):\n    return True",
        ]

        result = self.use_case.execute()

        self.assertEqual(len(result), 2)
        destination_names = [r.destination.name for r in result]
        self.assertIn("Doc A", destination_names)
        self.assertIn("Doc B", destination_names)

    def test_split_into_sentences(self):
        text = "This is sentence one. And this is sentence two! What about this?"
        sentences = GenerateDestinationDetectionsUseCase._split_into_sentences(text)

        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0], "This is sentence one.")
        self.assertEqual(sentences[1], "And this is sentence two!")
        self.assertEqual(sentences[2], "What about this?")

    def test_group_references_by_destination_uses_segment_info(self):
        segment = Segment(
            text="Section about topic A",
            page_number=1,
            segment_number=1,
            type="Title",
            pdf_name="document.pdf",
        )

        ref1 = self._create_reference(1, "Topic A", "Topic A", segment)
        ref2 = self._create_reference(2, "topic a", "Topic A", segment)

        groups = self.use_case._group_references_by_destination([ref1, ref2])

        self.assertEqual(len(groups), 1)
        grouped_dest = list(groups.keys())[0]
        self.assertEqual(grouped_dest.name, "Topic A")
        self.assertIsNone(grouped_dest.segment_text)
        self.assertIsNone(grouped_dest.segment_pdf_name)

    def test_group_references_by_destination_without_segment(self):
        ref1 = self._create_reference(1, "Some Reference", "Some Reference", None)

        groups = self.use_case._group_references_by_destination([ref1])

        self.assertEqual(len(groups), 1)
        grouped_dest = list(groups.keys())[0]
        self.assertEqual(grouped_dest.name, "Some Reference")
        self.assertIsNone(grouped_dest.segment_text)
        self.assertIsNone(grouped_dest.segment_pdf_name)

    def test_get_reference_texts(self):
        ref1 = self._create_reference(1, "Original Text", "Some Destination", None)
        ref2 = self._create_reference(2, "Original Text", "Some Destination", None)
        ref3 = self._create_reference(3, "Different Text", "Some Destination", None)

        texts = self.use_case._get_reference_texts([ref1, ref2, ref3])

        self.assertEqual(len(texts), 2)
        self.assertIn("Original Text", texts)
        self.assertIn("Different Text", texts)

    def test_get_positive_samples(self):
        segment = self._create_segment("This contains the reference to Section 1 here.")
        ref = self._create_reference(1, "Section 1", "Section 1", segment)

        samples = self.use_case._get_positive_samples([ref], r"(?P<reference>Section\s+1)")

        self.assertGreater(len(samples), 0)
        for sample in samples:
            self.assertIn("Section 1", sample["text"])

    def test_get_negative_samples_excludes_target_refs(self):
        segment1 = self._create_segment("Reference to Section 1 in doc")
        segment2 = self._create_segment("Reference to Section 2 in doc")

        target_ref = self._create_reference(1, "Section 1", "Section 1", segment1)
        other_ref = self._create_reference(2, "Section 2", "Section 2", segment2)

        all_refs = [target_ref, other_ref]

        samples = self.use_case._get_negative_samples([target_ref], all_refs, r"(?P<reference>Section\s+1)")

        for sample in samples:
            self.assertNotIn("Section 1", sample["sentence"])

    def test_generate_regex_calls_llm_with_correct_prompt(self):
        segment = self._create_segment("Example paragraph mentioning Section 1", "doc.pdf")
        ref = self._create_reference(1, "Section 1", "Section 1", segment)

        destination_info = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Section 1",
            segment_text="Example paragraph mentioning Section 1",
            segment_pdf_name="doc.pdf",
        )

        expected_regex = "(?P<reference>Section\\s+1)"
        self.mock_llm_service.query.return_value = expected_regex

        regex = self.use_case._generate_regex(
            destination_info,
            ["Section 1"],
            ["Example paragraph mentioning Section 1"],
        )

        self.mock_llm_service.query.assert_called_once()
        call_args = self.mock_llm_service.query.call_args[0][0]
        self.assertIn("Destination Document: Section 1", call_args)
        self.assertIn("Section 1", call_args)

    def test_generate_disambiguation_script_calls_llm(self):
        destination_info = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Section 1",
            segment_text="Target section text",
            segment_pdf_name="doc.pdf",
        )

        self.mock_llm_service.query.return_value = """def is_reference(match_text: str, sentence_text: str, paragraph_text: str) -> bool:
    return True"""

        positive_samples = [
            {"text": "Section 1", "sentence": "...Section 1...", "paragraph_text": "...Section 1..."},
        ]
        negative_samples = [
            {
                "text": "Section 2",
                "sentence": "...Section 2...",
                "destination_entity_title": "Section 2",
                "paragraph_text": "...Section 2...",
            },
        ]

        script = self.use_case._generate_disambiguation_script(
            destination_info,
            "(?P<reference>Section 1)",
            positive_samples,
            negative_samples,
        )

        self.mock_llm_service.query.assert_called_once()
        call_args = self.mock_llm_service.query.call_args[0][0]
        self.assertIn("Section 1", call_args)

    def test_destination_info_equality(self):
        dest1 = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
            segment_text="Text A",
            segment_pdf_name="doc.pdf",
        )
        dest2 = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
            segment_text="Text A",
            segment_pdf_name="doc.pdf",
        )
        dest3 = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Different",
            segment_text="Text A",
            segment_pdf_name="doc.pdf",
        )

        self.assertEqual(dest1, dest2)
        self.assertNotEqual(dest1, dest3)

    def test_destination_info_get_destination_id(self):
        dest = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Test",
            segment_text="Text A",
            segment_pdf_name="doc.pdf",
        )

        dest_id = dest.get_destination_id()

        self.assertIn("REFERENCE", dest_id)
        self.assertIn("Test", dest_id)
        self.assertIn("Text A", dest_id)
        self.assertIn("doc.pdf", dest_id)

    def test_detection_script_from_destination_and_refs(self):
        segment = self._create_segment("Test paragraph", "test.pdf")
        ref = self._create_reference(1, "Reference Text", "Reference Text", segment)

        destination = DestinationInfo(
            type=ReferenceType.REFERENCE,
            name="Reference Text",
            segment_text="Test paragraph",
            segment_pdf_name="test.pdf",
        )

        script = DestinationDetection.from_destination_and_refs(
            destination=destination,
            refs=[ref],
            regex="(?P<reference>Reference\\s+Text)",
            script="def is_reference(...): ...",
        )

        self.assertEqual(script.destination.name, "Reference Text")
        self.assertEqual(script.reference_ids, [1])
        self.assertEqual(script.regex, "(?P<reference>Reference\\s+Text)")
        self.assertEqual(script.script, "def is_reference(...): ...")

    def test_regex_prompt_includes_all_required_sections(self):
        from cross_references_predictor.use_cases.generate_detection_scripts_use_case import REGEX_PROMPT

        self.assertIn("Destination Document:", REGEX_PROMPT)
        self.assertIn("Target Section/Text:", REGEX_PROMPT)
        self.assertIn("Specific Reference Strings to Match:", REGEX_PROMPT)
        self.assertIn("Examples of paragraphs that contain references", REGEX_PROMPT)
        self.assertIn("Core Matching Strategy", REGEX_PROMPT)
        self.assertIn("Human Error", REGEX_PROMPT)
        self.assertIn("Pattern Mechanics", REGEX_PROMPT)
        self.assertIn("Syntax & Grouping", REGEX_PROMPT)
        self.assertIn("Strict Output Format", REGEX_PROMPT)

    def test_train_prompt_includes_all_required_sections(self):
        from cross_references_predictor.use_cases.generate_detection_scripts_use_case import TRAIN_PROMPT

        self.assertIn("TARGET_METADATA", TRAIN_PROMPT)
        self.assertIn("GROUND TRUTH DATA", TRAIN_PROMPT)
        self.assertIn("Positive Samples", TRAIN_PROMPT)
        self.assertIn("NEGATIVE SAMPLES", TRAIN_PROMPT)
        self.assertIn("LOGIC REQUIREMENTS", TRAIN_PROMPT)
        self.assertIn("INPUT/OUTPUT SCHEMA", TRAIN_PROMPT)

    def test_sentence_split_pattern(self):
        test_text = "First sentence. Second sentence! Third sentence?"
        sentences = SENTENCE_SPLIT_PATTERN.split(test_text)

        self.assertEqual(len(sentences), 3)

    def test_get_paragraph_examples_limits_to_five(self):
        segment1 = self._create_segment("Example 1 text")
        segment2 = self._create_segment("Example 2 text")
        segment3 = self._create_segment("Example 3 text")
        segment4 = self._create_segment("Example 4 text")
        segment5 = self._create_segment("Example 5 text")
        segment6 = self._create_segment("Example 6 text")

        refs = [
            self._create_reference(i, f"Ref {i}", "Dest", segment)
            for i, segment in enumerate([segment1, segment2, segment3, segment4, segment5, segment6])
        ]

        examples = self.use_case._get_paragraph_examples(refs)

        self.assertLessEqual(len(examples), 5)
