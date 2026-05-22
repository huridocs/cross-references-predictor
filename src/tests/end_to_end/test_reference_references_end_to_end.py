import os
import time
import unittest

import requests


class TestReferenceReferencesEndToEnd(unittest.TestCase):
    service_url = "http://localhost:5070"
    language = "en"

    def setUp(self):
        self.namespace = f"reference_references_test_{id(self)}"

    def tearDown(self):
        requests.post(f"{self.service_url}/delete_namespace", data={"namespace": self.namespace, "language": self.language})

    def _save_references(self, occurrences: list[dict]) -> requests.Response:
        return requests.post(
            f"{self.service_url}/reference_occurrences",
            json={"namespace": self.namespace, "language": self.language, "occurrences": occurrences},
        )

    def _generate_detection_scripts(self) -> tuple[bool, int, str]:
        repo = requests.post(
            f"{self.service_url}/generate_detection_scripts",
            data={"namespace": self.namespace, "language": self.language},
        )
        if repo.status_code != 200:
            return False, 0, f"HTTP {repo.status_code} - {repo.text}"

        task_id = repo.json()["task_id"]

        max_attempts = 600
        for attempt in range(max_attempts):
            status_data = requests.get(f"{self.service_url}/tasks/{task_id}").json()
            if status_data["status"] == "completed":
                return True, status_data["result"]["scripts_generated"], ""
            if status_data["status"] == "failed":
                return False, 0, status_data["error"]
            time.sleep(1)
        return False, 0, "Timed out waiting for script generation task to complete"

    @unittest.skip("Requires real Ollama API KEY")
    def test_type_1_with_segment(self):
        occurrences = [
            {
                "text": "Section 5.2",
                "destination": "Chapter 5 - Introduction",
                "pdf_name": "doc1.pdf",
                "page": 1,
                "segment_text": "This document references Section 5.2 in Chapter 5 - Introduction.",
            },
            {
                "text": "Chapter 3",
                "destination": "Chapter 3 - Background",
                "pdf_name": "doc1.pdf",
                "page": 2,
                "segment_text": "According to Chapter 3, the background is essential.",
            },
            {
                "text": "Section 5.2",
                "destination": "Chapter 5 - Introduction",
                "pdf_name": "doc2.pdf",
                "page": 1,
                "segment_text": "See Section 5.2 for more details.",
            },
        ]
        response = self._save_references(occurrences)
        self.assertEqual(200, response.status_code)

        text = "This is a test document that contains Section 5.2 and references Chapter 3"
        extract_response = requests.post(
            f"{self.service_url}/",
            data={"text": text, "namespace": self.namespace, "language": self.language},
        )
        self.assertEqual(200, extract_response.status_code)
        refs_response = extract_response.json()
        self.assertIn("references", refs_response)
        self.assertIn("destinations", refs_response)

    @unittest.skip("Requires real Ollama API KEY")
    def test_type_2_without_segment(self):
        occurrences = [
            {
                "text": "Regulation 2024/1234",
                "destination": "EU Regulation 2024/1234",
                "pdf_name": "doc3.pdf",
                "page": 1,
                "segment_text": None,
            },
            {
                "text": "EU Regulation 2024/1234",
                "destination": "EU Regulation 2024/1234",
                "pdf_name": "doc4.pdf",
                "page": 3,
                "segment_text": None,
            },
            {
                "text": "Regulation 2024/5678",
                "destination": "EU Regulation 2024/5678",
                "pdf_name": "doc3.pdf",
                "page": 2,
                "segment_text": None,
            },
        ]
        response = self._save_references(occurrences)
        self.assertEqual(200, response.status_code)

        text = "According to Regulation 2024/1234 and Regulation 2024/5678"
        extract_response = requests.post(
            f"{self.service_url}/",
            data={"text": text, "namespace": self.namespace, "language": self.language},
        )
        self.assertEqual(200, extract_response.status_code)
        refs_response = extract_response.json()
        self.assertIn("references", refs_response)
        self.assertIn("destinations", refs_response)

    @unittest.skip("Requires real Ollama API KEY")
    def test_mixed_types(self):
        occurrences = [
            {
                "text": "Chapter 1",
                "destination": "Chapter 1 - Overview",
                "pdf_name": "doc5.pdf",
                "page": 1,
                "segment_text": "Chapter 1 contains the overview.",
            },
            {
                "text": "Chapter 2",
                "destination": "Chapter 2 - Details",
                "pdf_name": "doc5.pdf",
                "page": 2,
                "segment_text": "Chapter 2 has the details.",
            },
            {
                "text": "Law 2025/100",
                "destination": "Law 2025/100",
                "pdf_name": "doc6.pdf",
                "page": 1,
                "segment_text": None,
            },
            {
                "text": "Law 2025/200",
                "destination": "Law 2025/200",
                "pdf_name": "doc6.pdf",
                "page": 2,
                "segment_text": None,
            },
        ]
        response = self._save_references(occurrences)
        self.assertEqual(200, response.status_code)

        text = "Chapter 1 and Chapter 2 are important. Also Law 2025/100 and Law 2025/200 apply."
        extract_response = requests.post(
            f"{self.service_url}/",
            data={"text": text, "namespace": self.namespace, "language": self.language},
        )
        self.assertEqual(200, extract_response.status_code)
        refs_response = extract_response.json()
        self.assertIn("references", refs_response)
        self.assertIn("destinations", refs_response)

    @unittest.skip("Requires real Ollama API KEY")
    def test_detection_scripts(self):
        occurrences = [
            {
                "text": "Test Ref 1",
                "destination": "Test Dest 1",
                "pdf_name": "test.pdf",
                "page": 1,
                "segment_text": "This is a test reference to Test Dest 1.",
            },
        ]
        response = self._save_references(occurrences)
        self.assertEqual(200, response.status_code)

        success, scripts_count, error_msg = self._generate_detection_scripts()
        self.assertTrue(success, error_msg)
        self.assertEqual(1, scripts_count)

        text = "Here is a Test Ref 1 reference"
        extract_response = requests.post(
            f"{self.service_url}/",
            data={"text": text, "namespace": self.namespace, "language": self.language},
        )
        self.assertEqual(200, extract_response.status_code)
        ref_refs = [r for r in extract_response.json().get("references", []) if r.get("type") == "REFERENCE"]
        self.assertGreater(len(ref_refs), 0)

    @unittest.skip("Requires real Ollama API KEY")
    def test_negative_samples(self):
        occurrences = [
            {
                "text": "Article 5",
                "destination": "Article 5 - Data Processing",
                "pdf_name": "regulation.pdf",
                "page": 3,
                "segment_text": "The processing of personal data shall comply with Article 5.",
            },
            {
                "text": "Article 5",
                "destination": "Article 5 - Data Processing",
                "pdf_name": "regulation.pdf",
                "page": 4,
                "segment_text": "Pursuant to Article 5, data must be processed lawfully.",
            },
            {
                "text": "Article 5a",
                "destination": "Article 5a - Special Categories",
                "pdf_name": "regulation.pdf",
                "page": 7,
                "segment_text": "Article 5a covers special categories of personal data.",
            },
        ]
        response = self._save_references(occurrences)
        self.assertEqual(200, response.status_code)

        negative_segments = [
            {
                "text": "Article 5a establishes additional requirements for special categories of data.",
                "pdf_name": "regulation.pdf",
                "page": 7,
            },
            {
                "text": "The provisions of Article 5a supplement the general rules in this Chapter.",
                "pdf_name": "regulation.pdf",
                "page": 8,
            },
        ]
        response = requests.post(
            f"{self.service_url}/negative_samples",
            json={
                "namespace": self.namespace,
                "language": self.language,
                "destination": "Article 5 - Data Processing",
                "segments": negative_segments,
            },
        )
        self.assertEqual(200, response.status_code)

        success, scripts_count, error_msg = self._generate_detection_scripts()
        self.assertTrue(success, error_msg)
        self.assertGreaterEqual(scripts_count, 1)

        text = "The general rules in Article 5 apply. Additionally, Article 5a covers special cases."
        extract_response = requests.post(
            f"{self.service_url}/",
            data={"text": text, "namespace": self.namespace, "language": self.language},
        )
        self.assertEqual(200, extract_response.status_code)
        ref_refs = [r for r in extract_response.json().get("references", []) if r.get("type") == "REFERENCE"]
        self.assertGreater(len(ref_refs), 0)

    @unittest.skip("Requires real Ollama API KEY")
    def test_same_text_different_destinations(self):
        segment_text = "As mentioned in Article 1 of the Charter and Article 1 of the Protocol."
        first_article_pos = segment_text.find("Article 1")
        second_article_pos = segment_text.find("Article 1", first_article_pos + 1)

        occurrences = [
            {
                "text": "Article 1",
                "destination": "Charter Article 1",
                "pdf_name": "same_doc.pdf",
                "page": 1,
                "segment_text": segment_text,
                "character_start": first_article_pos,
                "character_end": first_article_pos + len("Article 1"),
            },
            {
                "text": "Article 1",
                "destination": "Protocol Article 1",
                "pdf_name": "same_doc.pdf",
                "page": 1,
                "segment_text": segment_text,
                "character_start": second_article_pos,
                "character_end": second_article_pos + len("Article 1"),
            },
        ]
        response = self._save_references(occurrences)
        self.assertEqual(200, response.status_code)

        success, scripts_count, error_msg = self._generate_detection_scripts()
        self.assertTrue(success, error_msg)
        self.assertGreaterEqual(scripts_count, 2)

        extract_response = requests.post(
            f"{self.service_url}/",
            data={"text": segment_text, "namespace": self.namespace, "language": self.language},
        )
        self.assertEqual(200, extract_response.status_code)
        ref_refs = [r for r in extract_response.json().get("references", []) if r.get("type") == "REFERENCE"]
        self.assertEqual(2, len(ref_refs))
        starts = [r["character_start"] for r in ref_refs]
        self.assertEqual(2, len(set(starts)))
        destinations = {r["destination"] for r in ref_refs}
        self.assertIn("Charter Article 1", destinations)
        self.assertIn("Protocol Article 1", destinations)
