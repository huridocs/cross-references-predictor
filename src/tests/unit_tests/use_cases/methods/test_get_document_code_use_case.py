from unittest import TestCase
from cross_references_predictor.use_cases.methods.get_document_code_use_case import GetDocumentCodeUseCase
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType


class TestGetDocumentCodeUseCase(TestCase):
    def setUp(self):
        self.use_case = GetDocumentCodeUseCase()

    def test_extract_single_document_code(self):
        text = "The report ST/SG/2025/1 was discussed."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].type, ReferenceType.DOCUMENT_CODE)
        self.assertEqual(references[0].text, "ST/SG/2025/1")
        self.assertEqual(references[0].character_start, 11)
        self.assertEqual(references[0].character_end, 23)

    def test_extract_multiple_document_codes(self):
        text = "Documents A/79/150 and S/RES/2750 were referenced."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 2)
        self.assertEqual(references[0].text, "A/79/150")
        self.assertEqual(references[1].text, "S/RES/2750")

    def test_extract_document_code_with_revision(self):
        text = "See document A/C.3/79/L.5/Rev.1 for details."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].text, "A/C.3/79/L.5/Rev.1")

    def test_extract_document_code_with_corrigendum(self):
        text = "The corrected version E/2025/14/Corr.1 is available."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].text, "E/2025/14/Corr.1")

    def test_extract_document_code_with_addendum(self):
        text = "Please refer to A/79/100/Add.2 for additional information."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].text, "A/79/100/Add.2")

    def test_extract_trusteeship_council_code(self):
        text = "The Trusteeship Council document T/3200 was referenced."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].text, "T/3200")

    def test_extract_committee_code(self):
        text = "Committee draft resolution A/C.3/79/L.5 was introduced."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].text, "A/C.3/79/L.5")

    def test_ignore_non_matching_patterns(self):
        text = "This text contains A/B/C and 12345 which are not valid codes."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 0)

    def test_extract_multiple_codes_complex_text(self):
        text = """
        The Secretariat report (ST/SG/2025/1) was discussed during the 79th session
        of the General Assembly. The Committee introduced a draft resolution
        A/C.3/79/L.5 which was later revised as A/C.3/79/L.5/Rev.1. The Security
        Council also adopted resolution S/RES/2750, and the initial ECOSOC document
        E/2025/14 was subsequently corrected with E/2025/14/Corr.1. A related document
        from the Trusteeship Council, T/3200, was also referenced.
        """
        references = self.use_case.get_references(text)

        self.assertGreaterEqual(len(references), 6)
        codes = [entity.text for entity in references]
        self.assertIn("ST/SG/2025/1", codes)
        self.assertIn("A/C.3/79/L.5", codes)
        self.assertIn("A/C.3/79/L.5/Rev.1", codes)
        self.assertIn("S/RES/2750", codes)
        self.assertIn("E/2025/14", codes)
        self.assertIn("E/2025/14/Corr.1", codes)
        self.assertIn("T/3200", codes)

    def test_find_un_codes_basic(self):
        text = "See A/79/150 for more info."
        codes = self.use_case.find_un_codes(text)

        self.assertEqual(len(codes), 1)
        self.assertEqual(codes[0], "A/79/150")

    def test_find_un_codes_with_punctuation(self):
        text = "Documents (A/79/150) and [S/RES/2750] were cited."
        codes = self.use_case.find_un_codes(text)

        self.assertEqual(len(codes), 2)
        self.assertIn("A/79/150", codes)
        self.assertIn("S/RES/2750", codes)

    def test_find_un_codes_case_insensitive(self):
        text = "The document a/79/150 was reviewed."
        codes = self.use_case.find_un_codes(text)

        self.assertEqual(len(codes), 1)
        self.assertEqual(codes[0], "A/79/150")

    def test_remove_overlapping_references(self):
        references = [
            Reference(type=ReferenceType.DOCUMENT_CODE, character_start=0, character_end=10, text="A/79/150"),
            Reference(type=ReferenceType.DOCUMENT_CODE, character_start=5, character_end=15, text="79/150"),
            Reference(type=ReferenceType.DOCUMENT_CODE, character_start=20, character_end=30, text="S/RES/2750"),
        ]

        result = self.use_case.remove_overlapping_references(references)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].text, "A/79/150")
        self.assertEqual(result[1].text, "S/RES/2750")

    def test_extract_security_council_resolution(self):
        text = "Security Council Resolution S/RES/1234 was adopted."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].text, "S/RES/1234")

    def test_extract_general_assembly_plenary_meeting(self):
        text = "See the verbatim record A/79/PV.15 for the discussion."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 1)
        self.assertEqual(references[0].text, "A/79/PV.15")

    def test_empty_text(self):
        text = ""
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 0)

    def test_text_without_codes(self):
        text = "This is a regular text without any UN document codes."
        references = self.use_case.get_references(text)

        self.assertEqual(len(references), 0)
