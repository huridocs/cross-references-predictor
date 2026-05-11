import requests
from unittest import TestCase


class TestReferencesCrud(TestCase):
    service_url = "http://localhost:5070"
    namespace = "test_references_crud_namespace"
    identifier = "test_crud_identifier"

    def setUp(self):
        requests.post(f"{self.service_url}/delete_namespace", data={"namespace": self.namespace})

    def tearDown(self):
        requests.post(f"{self.service_url}/delete_namespace", data={"namespace": self.namespace})

    def _create_cross_reference(self, text: str, destination: str) -> dict:
        return {
            "type": "REFERENCE",
            "text": text,
            "destination": destination,
        }

    def test_save_references_without_id(self):
        references = [
            self._create_cross_reference("John Doe", "Section 1"),
            self._create_cross_reference("Paris", "Section 2"),
        ]

        result = requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        self.assertEqual(200, result.status_code)
        self.assertEqual("success", result.json()["status"])
        self.assertEqual("2", result.json()["message"].split()[1])

    def test_save_references_with_id(self):
        references = [
            {"id": 100, **self._create_cross_reference("John Doe", "Section 1")},
            {"id": 101, **self._create_cross_reference("Paris", "Section 2")},
        ]

        result = requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        self.assertEqual(200, result.status_code)
        self.assertEqual("success", result.json()["status"])

    def test_update_reference_by_id(self):
        references = [self._create_cross_reference("John Doe", "Section 1")]

        save_result = requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )
        self.assertEqual(200, save_result.status_code)

        all_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})
        self.assertTrue(len(all_refs.json()) > 0)

        ref_id = all_refs.json()[0]["references"][0]["id"]

        update_result = requests.patch(
            f"{self.service_url}/references/{ref_id}",
            data={"namespace": self.namespace, "text": "Jane Doe", "destination_name": "Jane Destination"},
        )

        self.assertEqual(200, update_result.status_code)
        self.assertEqual("success", update_result.json()["status"])

    def test_update_reference_with_only_text(self):
        references = [self._create_cross_reference("John Doe", "Section 1")]

        requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        all_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})
        ref_id = all_refs.json()[0]["references"][0]["id"]

        update_result = requests.patch(
            f"{self.service_url}/references/{ref_id}", data={"namespace": self.namespace, "text": "Jane Smith"}
        )

        self.assertEqual(200, update_result.status_code)

    def test_update_reference_with_only_destination(self):
        references = [self._create_cross_reference("John Doe", "Section 1")]

        requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        all_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})
        ref_id = all_refs.json()[0]["references"][0]["id"]

        update_result = requests.patch(
            f"{self.service_url}/references/{ref_id}",
            data={"namespace": self.namespace, "destination_name": "New Destination"},
        )

        self.assertEqual(200, update_result.status_code)

    def test_update_reference_no_changes(self):
        references = [self._create_cross_reference("John Doe", "Section 1")]

        requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        all_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})
        ref_id = all_refs.json()[0]["references"][0]["id"]

        update_result = requests.patch(f"{self.service_url}/references/{ref_id}", data={"namespace": self.namespace})

        self.assertEqual(200, update_result.status_code)
        self.assertEqual("error", update_result.json()["status"])

    def test_get_reference_by_id(self):
        references = [self._create_cross_reference("John Doe", "Section 1")]

        requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        all_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})
        ref_id = all_refs.json()[0]["references"][0]["id"]

        get_result = requests.get(f"{self.service_url}/references/{ref_id}", params={"namespace": self.namespace})

        self.assertEqual(200, get_result.status_code)
        self.assertEqual(ref_id, get_result.json()["id"])
        self.assertEqual("John Doe", get_result.json()["text"])
        self.assertEqual("REFERENCE", get_result.json()["type"])

    def test_get_reference_by_id_not_found(self):
        result = requests.get(f"{self.service_url}/references/99999", params={"namespace": self.namespace})

        self.assertEqual(404, result.status_code)

    def test_delete_reference(self):
        references = [self._create_cross_reference("John Doe", "Section 1")]

        requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        all_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})
        ref_id = all_refs.json()[0]["references"][0]["id"]

        delete_result = requests.post(
            f"{self.service_url}/delete_reference", data={"namespace": self.namespace, "reference_id": ref_id}
        )

        self.assertEqual(200, delete_result.status_code)
        self.assertEqual("success", delete_result.json()["status"])

        get_result = requests.get(f"{self.service_url}/references/{ref_id}", params={"namespace": self.namespace})
        self.assertEqual(404, get_result.status_code)

    def test_delete_reference_not_found(self):
        delete_result = requests.post(
            f"{self.service_url}/delete_reference", data={"namespace": self.namespace, "reference_id": 99999}
        )

        self.assertEqual(200, delete_result.status_code)

    def test_get_all_references(self):
        references = [
            self._create_cross_reference("John Doe", "Section 1"),
            self._create_cross_reference("Paris", "Section 2"),
            self._create_cross_reference("2024-01-01", "Section 3"),
        ]

        requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        all_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})

        self.assertEqual(200, all_refs.status_code)
        self.assertIsInstance(all_refs.json(), list)

        destinations = all_refs.json()
        self.assertGreaterEqual(len(destinations), 1)

        first_dest = destinations[0]
        self.assertIn("references", first_dest)
        self.assertIsInstance(first_dest["references"], list)

    def test_save_and_update_with_id_preserves_existing(self):
        references = [self._create_cross_reference("John Doe", "Section 1")]

        requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        all_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})
        original_ref_id = all_refs.json()[0]["references"][0]["id"]

        requests.post(
            f"{self.service_url}/save_references",
            json={"namespace": self.namespace, "identifier": self.identifier, "references": references},
        )

        updated_refs = requests.get(f"{self.service_url}/references", params={"namespace": self.namespace})
        updated_ref_id = updated_refs.json()[0]["references"][0]["id"]

        self.assertEqual(original_ref_id, updated_ref_id)
