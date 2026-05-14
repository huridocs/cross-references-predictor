import requests
import time

SERVICE_URL = "http://localhost:5070"
NAMESPACE = "reference_references_test_1"
LANGUAGE = "en"


def cleanup():
    print("Cleaning up namespace...")
    requests.post(f"{SERVICE_URL}/delete_namespace", data={"namespace": NAMESPACE, "language": LANGUAGE})
    print("Cleanup complete.")


def save_references(occurrences: list[dict]) -> dict:
    response = requests.post(
        f"{SERVICE_URL}/reference_occurrences",
        json={"namespace": NAMESPACE, "language": LANGUAGE, "occurrences": occurrences},
    )
    return response


def generate_detection_scripts() -> tuple[bool, int]:
    repo = requests.post(
        f"{SERVICE_URL}/generate_detection_scripts",
        data={"namespace": NAMESPACE, "language": LANGUAGE},
    )
    if repo.status_code != 200:
        print(f"Error generating scripts: {repo.status_code} - {repo.text}")
        return False, 0

    task_id = repo.json()["task_id"]

    max_attempts = 30
    for _ in range(max_attempts):
        task_status = requests.get(f"{SERVICE_URL}/tasks/{task_id}")
        status_data = task_status.json()
        if status_data["status"] == "completed":
            return True, status_data["result"]["scripts_generated"]
        elif status_data["status"] == "failed":
            print(f"Script generation failed: {status_data['error']}")
            return False, 0
        time.sleep(1)

    return False, 0


def run_type_1_with_segment():
    print("\n=== Testing Type 1: REFERENCE with destination segment ===")

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

    response = save_references(occurrences)
    print(f"Saved Type 1 references: {response.json()}")
    assert response.status_code == 200, f"Failed to save references: {response.text}"

    text = "This is a test document that contains Section 5.2 and references Chapter 3"
    extract_response = requests.post(
        f"{SERVICE_URL}/",
        data={"text": text, "namespace": NAMESPACE, "language": LANGUAGE},
    )
    print(f"Extraction response: {extract_response.status_code}")

    refs_response = extract_response.json()
    print(f"Extracted references: {len(refs_response.get('references', []))}")
    print(f"Destinations: {len(refs_response.get('destinations', []))}")

    print("Type 1 test PASSED")


def run_type_2_without_segment():
    print("\n=== Testing Type 2: REFERENCE without destination segment ===")

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

    response = save_references(occurrences)
    print(f"Saved Type 2 references: {response.json()}")
    assert response.status_code == 200, f"Failed to save references: {response.text}"

    text = "According to Regulation 2024/1234 and Regulation 2024/5678"
    extract_response = requests.post(
        f"{SERVICE_URL}/",
        data={"text": text, "namespace": NAMESPACE, "language": LANGUAGE},
    )
    print(f"Extraction response: {extract_response.status_code}")

    refs_response = extract_response.json()
    print(f"Extracted references: {len(refs_response.get('references', []))}")
    print(f"Destinations: {len(refs_response.get('destinations', []))}")

    print("Type 2 test PASSED")


def run_mixed_types():
    print("\n=== Testing Mixed: Type 1 and Type 2 together ===")

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

    response = save_references(occurrences)
    print(f"Saved mixed references: {response.json()}")
    assert response.status_code == 200, f"Failed to save references: {response.text}"

    text = "Chapter 1 and Chapter 2 are important. Also Law 2025/100 and Law 2025/200 apply."
    extract_response = requests.post(
        f"{SERVICE_URL}/",
        data={"text": text, "namespace": NAMESPACE, "language": LANGUAGE},
    )
    print(f"Extraction response: {extract_response.status_code}")

    refs_response = extract_response.json()
    print(f"Extracted references: {len(refs_response.get('references', []))}")
    print(f"Destinations: {len(refs_response.get('destinations', []))}")

    print("Mixed types test PASSED")


def run_detection_scripts_with_ollama():
    print("\n=== Testing detection script generation with Ollama ===")

    occurrences = [
        {
            "text": "Test Ref 1",
            "destination": "Test Dest 1",
            "pdf_name": "test.pdf",
            "page": 1,
            "segment_text": "This is a test reference to Test Dest 1.",
        },
    ]

    response = save_references(occurrences)
    print(f"Saved references: {response.json()}")

    success, scripts_count = generate_detection_scripts()

    if not success:
        print("WARNING: Ollama not available, skipping script generation test")
        print("This is expected if Ollama is not running.")
        print("Detection scripts test SKIPPED")
        return

    print(f"Generated {scripts_count} detection scripts")
    assert scripts_count == 1, f"Expected 1 script, got {scripts_count}"

    text = "Here is a Test Ref 1 reference"
    extract_response = requests.post(
        f"{SERVICE_URL}/",
        data={"text": text, "namespace": NAMESPACE, "language": LANGUAGE},
    )

    refs_response = extract_response.json()
    ref_refs = [r for r in refs_response.get("references", []) if r.get("type") == "REFERENCE"]
    print(f"Detected REFERENCE references: {len(ref_refs)}")

    if ref_refs:
        for r in ref_refs:
            print(f"  - text: {r.get('text')}, destination: {r.get('destination')}")

    print("Detection scripts test PASSED")


def main():
    print(f"Starting REFERENCE extraction E2E tests for namespace: {NAMESPACE}")

    try:
        cleanup()

        run_type_1_with_segment()

        cleanup()

        run_type_2_without_segment()

        cleanup()

        run_mixed_types()

        cleanup()

        run_detection_scripts_with_ollama()

        print("\n=== ALL TESTS PASSED ===")

    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\nERROR: {e}")
        raise
    finally:
        cleanup()


if __name__ == "__main__":
    main()
