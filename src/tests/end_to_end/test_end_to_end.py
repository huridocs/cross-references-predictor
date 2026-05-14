import json
from pathlib import Path
from unittest import TestCase
import requests

from cross_references_predictor.configuration import ROOT_PATH, SRC_PATH


class TestEndToEnd(TestCase):
    service_url = "http://localhost:5070"

    @staticmethod
    def similar_value(value: int):
        return [value - 1, value, value + 1]

    def test_empty_query(self):
        result = requests.post(self.service_url)

        self.assertEqual(200, result.status_code)
        self.assertEqual([], result.json()["references"])
        self.assertEqual([], result.json()["destinations"])

    def test_empty_text_query(self):
        data = {"text": ""}
        result = requests.post(self.service_url, data=data)

        self.assertEqual(200, result.status_code)
        self.assertEqual([], result.json()["references"])
        self.assertEqual([], result.json()["destinations"])

    def test_wrong_pdf(self):
        pdf_path = Path(SRC_PATH) / "tests" / "end_to_end" / "test_pdfs" / "not_a_pdf.pdf"

        with open(pdf_path, "rb") as pdf_file:
            files = {"file": pdf_file}
            result = requests.post(self.service_url, files=files)

        self.assertEqual(400, result.status_code)
        self.assertEqual("Unprocessable text or PDF file", result.json()["detail"])

    def test_text_extraction(self):
        text = (
            "The International Space Station past above Tokyo on 12 June 2025. "
            "Maria Rodriguez was in the Senate when Resolution No. 122 passed on twelve of June 2025."
        )
        data = {"text": text}
        result = requests.post(self.service_url, data=data)

        response_data = result.json()
        references = response_data["references"]
        destinations = response_data["destinations"]

        self.assertEqual(200, result.status_code)
        self.assertEqual(6, len(references))

        expected_references = [
            {"text": "Tokyo", "type": "LOCATION", "destination": "Tokyo", "character_start": 43, "character_end": 48},
            {
                "text": "12 June 2025",
                "type": "DATE",
                "destination": "2025-06-12",
                "character_start": 52,
                "character_end": 64,
            },
            {
                "text": "twelve of June 2025",
                "type": "DATE",
                "destination": "2025-06-12",
                "character_start": 134,
                "character_end": 153,
            },
            {
                "text": "Maria Rodriguez",
                "type": "PERSON",
                "destination": "Maria Rodriguez",
                "character_start": 66,
                "character_end": 81,
            },
            {"text": "Senate", "type": "ORGANIZATION", "destination": "Senate", "character_start": 93, "character_end": 99},
            {
                "text": "Resolution No. 122",
                "type": "LAW",
                "destination": "Resolution No. 122",
                "character_start": 105,
                "character_end": 123,
            },
        ]

        for i, expected in enumerate(expected_references):
            reference = references[i]
            self.assertIn("text", reference)
            self.assertIn("type", reference)
            self.assertIn("destination", reference)
            self.assertIn("segment", reference)
            self.assertIn("relevance_percentage", reference)
            self.assertIn("pdf_name", reference)
            self.assertIn("page_number", reference["segment"])
            self.assertIn("segment_number", reference["segment"])
            self.assertIn("character_start", reference["segment"])
            self.assertIn("character_end", reference["segment"])
            self.assertEqual(expected["text"], reference["text"])
            self.assertEqual(expected["type"], reference["type"])
            self.assertEqual(expected["destination"], reference["destination"])
            self.assertEqual(expected["character_start"], reference["character_start"])
            self.assertEqual(expected["character_end"], reference["character_end"])

        self.assertEqual(5, len(destinations))

        expected_destinations = [
            {"name": "Tokyo", "type": "LOCATION"},
            {"name": "2025-06-12", "type": "DATE"},
            {"name": "Maria Rodriguez", "type": "PERSON"},
            {"name": "Senate", "type": "ORGANIZATION"},
            {"name": "Resolution No. 122", "type": "LAW"},
        ]

        for i, expected_dest in enumerate(expected_destinations):
            dest = destinations[i]
            self.assertIn("name", dest)
            self.assertIn("type", dest)
            self.assertIn("references", dest)
            self.assertIn("top_relevance_entity", dest)
            self.assertIsInstance(dest["references"], list)
            self.assertEqual(expected_dest["name"], dest["name"])
            self.assertEqual(expected_dest["type"], dest["type"])

    def test_text_extraction_for_dates(self):
        text = "Today is 13th of January 2024. One month later it will be 13th of February. "
        text += "My birthday this year is January 13th of 2024."
        data = {"text": text}
        result = requests.post(f"{self.service_url}", data=data)

        self.assertEqual(200, result.status_code)

        references = result.json()["references"]
        destinations = result.json()["destinations"]

        self.assertEqual(3, len(references))

        expected_references = [
            {"text": "13th of January 2024", "type": "DATE", "destination": "2024-01-13"},
            {"text": "January 13th of 2024", "type": "DATE", "destination": "2024-01-13"},
            {"text": "13th of February", "type": "DATE", "destination": "13th of February"},
        ]

        for i, expected_ref in enumerate(expected_references):
            reference = references[i]
            self.assertEqual(expected_ref["text"], reference["text"])
            self.assertEqual(expected_ref["type"], reference["type"])
            self.assertEqual(expected_ref["destination"], reference["destination"])

        self.assertEqual(2, len(destinations))

        expected_destinations = [
            {"name": "2024-01-13", "type": "DATE"},
            {"name": "13th of February", "type": "DATE"},
        ]

        for i, expected_dest in enumerate(expected_destinations):
            dest = destinations[i]
            self.assertEqual(expected_dest["name"], dest["name"])
            self.assertEqual(expected_dest["type"], dest["type"])
            self.assertIn("top_relevance_entity", dest)

    def test_pdf_extraction(self):
        pdf_path: Path = Path(SRC_PATH, "tests", "end_to_end", "test_pdfs", "test_document.pdf")
        with open(pdf_path, "rb") as pdf_file:
            files = {"file": pdf_file}
            result = requests.post(self.service_url, files=files)

        self.assertEqual(200, result.status_code)

        references = result.json()["references"]
        destinations = result.json()["destinations"]

        expected_references = json.loads((SRC_PATH / "tests" / "end_to_end" / "expected_references.json").read_text())
        expected_destinations = json.loads((SRC_PATH / "tests" / "end_to_end" / "expected_destinations.json").read_text())

        self.assertIsInstance(references, list)
        self.assertEqual(len(references), len(expected_references))
        self.assertIsInstance(destinations, list)
        self.assertEqual(len(destinations), len(expected_destinations))

        # Assert all expected reference fields and values
        for i, expected in enumerate(expected_references):
            reference = references[i]
            self.assertEqual(expected["text"], reference["text"])
            self.assertEqual(expected["type"], reference["type"])
            self.assertEqual(expected["destination"], reference["destination"])
            self.assertIn("segment", reference)
            segment = reference["segment"]
            self.assertEqual(expected["segment"]["text"], segment["text"])
            self.assertEqual(expected["segment"]["page_number"], segment["page_number"])
            self.assertEqual(expected["segment"]["segment_number"], segment["segment_number"])
            self.assertEqual(expected["segment"]["character_start"], segment["character_start"])
            self.assertEqual(expected["segment"]["character_end"], segment["character_end"])
            self.assertIn("bounding_box", segment)
            for box_field in ["left", "top", "width", "height"]:
                self.assertEqual(expected["segment"]["bounding_box"][box_field], segment["bounding_box"][box_field])

        # Assert all expected destination fields and values
        for i, expected in enumerate(expected_destinations):
            dest = destinations[i]
            self.assertEqual(expected["name"], dest["name"])
            self.assertEqual(expected["type"], dest["type"])
            self.assertIn("references", dest)
            self.assertEqual(len(dest["references"]), len(expected["references"]))
            for j, expected_entity in enumerate(expected["references"]):
                entity_text = dest["references"][j]
                self.assertEqual(expected_entity["index"], entity_text["index"])
                self.assertEqual(expected_entity["text"], entity_text["text"])
            self.assertIn("top_relevance_entity", dest)
            if "entities_ids" in expected:
                self.assertIn("entities_ids", dest)
                self.assertEqual(expected["entities_ids"], dest["entities_ids"])
            if "entities_text" in expected:
                self.assertIn("entities_text", dest)
                self.assertEqual(expected["entities_text"], dest["entities_text"])

    def test_extraction_does_not_save_to_database(self):
        namespace = "test_no_save_namespace"
        identifier = "test_identifier_no_save"
        text = "Document with Tokyo and Maria Rodriguez"

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

        data = {"text": text, "namespace": namespace, "identifier": identifier}
        result = requests.post(self.service_url, data=data)
        self.assertEqual(200, result.status_code)
        self.assertIn("references", result.json())
        self.assertIn("destinations", result.json())

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

    def test_new_destinations_with_prior_references(self):
        namespace = "test_new_destinations_namespace"
        identifier_1 = "test_identifier_prior_1"
        identifier_2 = "test_identifier_prior_2"

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

        text_1 = "Document about Tokyo and Maria Rodriguez"
        requests.post(
            self.service_url + "/save_text", data={"text": text_1, "namespace": namespace, "identifier": identifier_1}
        )

        text_2 = "Document about Paris and John Smith"
        data = {"text": text_2, "namespace": namespace, "identifier": identifier_2}
        result = requests.post(self.service_url, data=data)
        self.assertEqual(200, result.status_code)

        destinations = result.json()["destinations"]
        destination_names = [d["name"] for d in destinations]

        self.assertIn("Paris", destination_names)
        self.assertIn("John Smith", destination_names)
        self.assertNotIn("Tokyo", destination_names)
        self.assertNotIn("Maria Rodriguez", destination_names)

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

    def test_destination_consolidation_across_extractions(self):
        namespace = "test_consolidation_namespace"

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

        text_1 = "Document about Maria P. Doo"
        data = {"text": text_1, "namespace": namespace, "identifier": "doc1"}
        result = requests.post(self.service_url, data=data)
        self.assertEqual(200, result.status_code)

        destinations = result.json()["destinations"]
        destination_names = [d["name"] for d in destinations]
        self.assertIn("Maria P. Doo", destination_names)

        text_2 = "Document about Maria P. D."
        data = {"text": text_2, "namespace": namespace, "identifier": "doc2"}
        result = requests.post(self.service_url, data=data)
        self.assertEqual(200, result.status_code)

        destinations = result.json()["destinations"]
        destination_names = [d["name"] for d in destinations]
        self.assertIn("Maria P. Doo", destination_names)

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

    def test_saved_reference_destination_name_preserved(self):
        namespace = "test_reference_destination_namespace"

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

        destinations = [
            {"name": "John D.", "type": "PERSON"},
        ]
        result = requests.post(
            f"{self.service_url}/destinations",
            json={"namespace": namespace, "destinations": destinations},
        )
        self.assertEqual(200, result.status_code)

        text = "Document about John Doe"
        data = {"text": text, "namespace": namespace, "identifier": "doc2"}
        result = requests.post(self.service_url, data=data)
        self.assertEqual(200, result.status_code)

        destinations = result.json()["destinations"]
        destination_names = [d["name"] for d in destinations]
        self.assertIn("John D.", destination_names)

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

    def test_reset_destinations(self):
        namespace = "test_reset_destinations_namespace"

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})

        text = "Document about Maria P. Doo"
        data = {"text": text, "namespace": namespace, "identifier": "doc1"}
        result = requests.post(self.service_url, data=data)
        self.assertEqual(200, result.status_code)

        reset_result = requests.post(f"{self.service_url}/reset_destinations", data={"namespace": namespace})
        self.assertEqual(200, reset_result.status_code)
        self.assertEqual("success", reset_result.json()["status"])

        text_2 = "Document about Maria P. D."
        data = {"text": text_2, "namespace": namespace, "identifier": "doc2"}
        result = requests.post(self.service_url, data=data)
        self.assertEqual(200, result.status_code)

        destinations = result.json()["destinations"]
        destination_names = [d["name"] for d in destinations]
        self.assertIn("Maria P. D", destination_names)

        requests.post(self.service_url + "/delete_namespace", data={"namespace": namespace})
