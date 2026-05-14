import json
import re
import time
from pathlib import Path
from ollama import chat

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:31b-cloud"


def load_data(file_path: Path) -> list[dict]:
    with open(file_path, "r") as f:
        file_data = json.load(f)

    references = []
    for item in file_data:
        paragraph_text = item["paragraph_text"]
        for ref in item["references"]:
            ref["paragraph_text"] = paragraph_text
            references.append(ref)
    return references


def call_ollama(prompt: str, think: bool = False) -> str:
    messages = [
        {
            "role": "user",
            "content": prompt,
        },
    ]
    response = chat(MODEL, messages=messages, think=think)
    return response["message"]["content"].strip()


PROMPT_TEMPLATE = """
Objective: Create a Python-compatible regular expression to identify specific cross-document references within a large corpus.

Target Metadata:

    Destination Document: {DESTINATION_TITLE}

    Target Section/Text: {DESTINATION_TEXT}

Specific Reference Strings to Match:
The regex must specifically capture the following variations that point to the target:
{REFERENCE_LIST}

Examples of paragraphs that contain references to the target:

{PARAGRAPH_EXAMPLES}
{FAILING_REGEX_SECTION}
Requirements:

    1. Core Matching Strategy (Prioritize Recall)

    Target the Essence: Extract only the core, identifying elements of the reference text.

    Maximize Recall: Optimize for high recall over strict precision. You must match any reasonable variation of the target, including alternative spellings, plurals, and partial text (so long as the partial text unambiguously identifies the destination).

    2. Human Error & Future-Proofing
    
        Anticipate Typos & Variations: Humans make mistakes and change formatting. Use optional characters (?), character classes ([...]), or alternations (|) to account for common typos, phonetic spellings, or double-letter errors.
    
        Abbreviations & Equivalents: Account for common abbreviations (e.g., matching both "St" and "Street", or "N" and "North").
    
        Omissions & Reordering: If the reference text contains multiple words, make non-essential connecting words optional so the regex still matches if a human drops a word.
    
    3. Pattern Mechanics (Flexibility & Precision)
    
        Whitespace & Punctuation: Account for variable formatting by replacing standard spaces with \s+ to handle multiple spaces, tabs, or newlines. Allow for optional punctuation (like stray commas or periods) between words.
    
        Word Boundaries (\b): Apply \b to isolate short strings or numbers (e.g., ensuring "5" does not match "50" or "April 5"). Exception: Do NOT use word boundaries next to non-word characters (like parentheses or punctuation).
    
    4. Syntax & Grouping
    
        Compatibility: The generated regex MUST be 100% compatible with Python's standard re module.
    
        Internal Grouping: Use non-capturing groups (?:...) for any internal alternations or variations.
    
        Final Capture: Wrap the entire matching pattern within a single named capturing group called "reference": (?P<reference>...)
    
    5. Strict Output Format
    
        OUTPUT ONLY THE RAW REGEX STRING.
    
        DO NOT include markdown formatting, code blocks (no backticks), quotes, or any explanatory text.
"""


def generate_regex_for_destination(
    destination_title: str,
    destination_text: str,
    reference_texts: list[str],
    paragraph_examples: list[str] | None = None,
    think: bool = False,
    failing_regex: str | None = None,
) -> str:
    reference_list = "\n".join(f"- {ref}" for ref in reference_texts)
    examples_str = ""
    if paragraph_examples:
        for i, ex in enumerate(paragraph_examples[:2], 1):
            examples_str += f"\n\nExample {i}:\n{ex[:500]}"

    failing_regex_section = ""
    if failing_regex:
        failing_regex_section = f"\n\nPreviously Generated Regex (FAILED):\n\nThe following regex was generated but did not match all reference strings:\n{failing_regex}\n\nPlease generate a different regex that matches ALL reference strings listed above."

    prompt = PROMPT_TEMPLATE.format(
        DESTINATION_TITLE=destination_title,
        DESTINATION_TEXT=destination_text[:500],
        REFERENCE_LIST=reference_list,
        PARAGRAPH_EXAMPLES=examples_str.strip() or "No examples available.",
        FAILING_REGEX_SECTION=failing_regex_section,
    )
    return call_ollama(prompt, think=think)


def check_regex_against_references(regex_pattern: str, reference_texts: list[str]) -> list[dict]:
    return [
        {"text": ref, "matched": bool(re.search(regex_pattern, ref, re.IGNORECASE | re.DOTALL))} for ref in reference_texts
    ]


def all_references_matched(test_matches: list[dict]) -> bool:
    return all(m["matched"] for m in test_matches)


def build_result(
    dest_title: str,
    dest_text: str,
    reference_texts: list[str],
    regex_pattern: str,
    test_matches: list[dict],
) -> dict:
    return {
        "destination_title": dest_title,
        "destination_text": dest_text,
        "reference_texts": reference_texts,
        "regex_pattern": regex_pattern,
        "test_matches": test_matches,
    }


def build_error_result(
    dest_title: str,
    dest_text: str,
    reference_texts: list[str],
    error: str,
    error_think: str | None = None,
) -> dict:
    result = {
        "destination_title": dest_title,
        "destination_text": dest_text,
        "reference_texts": reference_texts,
        "error": error,
    }
    if error_think:
        result["error_think"] = error_think
    return result


def _generate_regex_with_think(
    dest_title: str,
    dest_text: str,
    reference_texts: list[str],
    paragraph_examples: list[str] | None = None,
    initial_error: str | None = None,
    failing_regex: str | None = None,
) -> dict:
    try:
        regex_pattern = generate_regex_for_destination(
            dest_title, dest_text, reference_texts, paragraph_examples, think=True, failing_regex=failing_regex
        )
        print(f"  Generated regex (think): {regex_pattern}")
        test_matches = check_regex_against_references(regex_pattern, reference_texts)
        print(f"  Test matches (think): {test_matches}")
        return build_result(dest_title, dest_text, reference_texts, regex_pattern, test_matches)
    except Exception as e:
        print(f"  ERROR (think): {e}")
        return build_error_result(
            dest_title, dest_text, reference_texts, initial_error or str(e), str(e) if initial_error else None
        )


def generate_regex_with_retry(
    dest_title: str,
    dest_text: str,
    reference_texts: list[str],
    paragraph_examples: list[str] | None = None,
) -> dict:
    try:
        regex_pattern = generate_regex_for_destination(dest_title, dest_text, reference_texts, paragraph_examples)
        print(f"  Generated regex: {regex_pattern}")
    except Exception as e:
        print(f"  ERROR: {e}, retrying with think=True...")
        return _generate_regex_with_think(dest_title, dest_text, reference_texts, paragraph_examples, initial_error=str(e))

    try:
        test_matches = check_regex_against_references(regex_pattern, reference_texts)
        print(f"  Test matches: {test_matches}")
    except re.error as e:
        print(f"  ERROR: Invalid regex ({e}), retrying with think=True...")
        return _generate_regex_with_think(
            dest_title, dest_text, reference_texts, paragraph_examples, failing_regex=regex_pattern
        )

    if all_references_matched(test_matches):
        return build_result(dest_title, dest_text, reference_texts, regex_pattern, test_matches)

    print("  Not all references matched, retrying with think=True...")
    return _generate_regex_with_think(
        dest_title, dest_text, reference_texts, paragraph_examples, failing_regex=regex_pattern
    )


def group_samples_by_destination(data: list[dict]) -> tuple[dict[str, list], dict[str, str], dict[str, str]]:
    samples_by_destination_id: dict[str, list] = {}
    destination_titles: dict[str, str] = {}
    destination_texts: dict[str, str] = {}

    for sample in data:
        samples_by_destination_id.setdefault(sample["destination_id"], []).append(sample)
        destination_titles[sample["destination_id"]] = sample["destination_entity_title"]
        if sample.get("destination_text"):
            destination_texts[sample["destination_id"]] = sample["destination_text"]

    return samples_by_destination_id, destination_titles, destination_texts


def generate_regexes_for(destination_id: str | None = None):
    train_path = Path(__file__).parent / "labeled_data" / "train.json"
    data = load_data(train_path)

    samples_by_destination_id, destination_titles, destination_texts = group_samples_by_destination(data)

    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    total = len(samples_by_destination_id)

    for idx, (each_destination_id, samples) in enumerate(samples_by_destination_id.items(), 1):
        if destination_id and destination_id != each_destination_id:
            continue
        print(f"[{idx}/{total}] Processing destination: {each_destination_id}")
        print(f"  Samples: {len(samples)}")

        reference_texts = list({s["text"].strip() for s in samples})
        paragraph_examples = list({s["paragraph_text"].strip() for s in samples if s.get("paragraph_text")})
        dest_title = destination_titles[each_destination_id]
        dest_text = destination_texts.get(each_destination_id, "")

        print(f"  Title: {dest_title}")
        print(f"  References: {reference_texts}")

        results[each_destination_id] = generate_regex_with_retry(dest_title, dest_text, reference_texts, paragraph_examples)

        if idx < total:
            time.sleep(1)

    if not destination_id:
        output_file = output_dir / f"{Path(__file__).stem}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    # destination_id = "human_rights_council_resolution_5/1_3_710"
    destination_id = None
    generate_regexes_for(destination_id=destination_id)
