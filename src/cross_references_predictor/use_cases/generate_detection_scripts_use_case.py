import re

from cross_references_predictor.domain.destination_detection import DestinationDetection
from cross_references_predictor.domain.destination_info import DestinationInfo
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_destination import ReferenceDestination
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.ports.llm_service import LLMService
from cross_references_predictor.ports.references_store_repository import ReferencesStoreRepository

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


REGEX_PROMPT = """Objective: Create a Python-compatible regular expression to identify specific cross-document references within a large corpus.

Target Metadata:

    Destination Document: {destination_pdf_name}

    Target Section/Text: {destination_segment_text}

Specific Reference Strings to Match:
The regex must specifically capture the following variations that point to the target:
{reference_texts_list}

Examples of paragraphs that contain references to the target:

{paragraph_examples}
Requirements:

    1. Core Matching Strategy (Prioritize Recall)

    Target the Essence: Extract only the core, identifying elements of the reference text.

    Maximize Recall: Optimize for high recall over strict precision. You must match any reasonable variation of the target, including alternative spellings, plurals, and partial text (so long as the partial text unambiguously identifies the destination).

    2. Human Error & Future-Proofing
    
        Anticipate Typos & Variations: Humans make mistakes and change formatting. Use optional characters (?), character classes ([...]), or alternations (|) to account for common typos, phonetic spellings, or double-letter errors.
    
        Abbreviations & Equivalents: Account for common abbreviations (e.g., matching both "St" and "Street", or "N" and "North").
    
        Omissions & Reordering: If the reference text contains multiple words, make non-essential connecting words optional so the regex still matches if a human drops a word.
    
    3. Pattern Mechanics (Flexibility & Precision)
    
        Whitespace & Punctuation: Account for variable formatting by replacing standard spaces with \\s+ to handle multiple spaces, tabs, or newlines. Allow for optional punctuation (like stray commas or periods) between words.
    
        Word Boundaries (\b): Apply \b to isolate short strings or numbers (e.g., ensuring "5" does not match "50" or "April 5"). Exception: Do NOT use word boundaries next to non-word characters (like parentheses or punctuation).
    
    4. Syntax & Grouping
    
        Compatibility: The generated regex MUST be 100% compatible with Python's standard re module.
    
        Internal Grouping: Use non-capturing groups (?:...) for any internal alternations or variations.
    
        Final Capture: Wrap the entire matching pattern within a single named capturing group called "reference": (?P<reference>...)
    
    5. Strict Output Format
    
        OUTPUT ONLY THE RAW REGEX STRING.
    
        DO NOT include markdown formatting, code blocks (no backticks), quotes, or any explanatory text.
"""


TRAIN_PROMPT = """Role: Senior Legal Tech Developer & Python Expert.

Objective: Develop a robust Python validation function that distinguishes between True Matches (valid legal references) and False Positives (coincidental text matching the regex pattern below) within a given paragraph.

[TARGET_METADATA]

    Destination Document: {destination_title}

    Target Section/Text: {destination_text}
    
    Regex Pattern: {regex_from_destination_id}

[GROUND TRUTH DATA]

    Positive Samples (True Matches - each sample shows the sentence containing the match):
    {positive_samples}


[NEGATIVE SAMPLES]
    Negative Samples (Distractors to Avoid - each sample shows the sentence containing the match):
    {negative_samples}

[LOGIC REQUIREMENTS]
Your task is to create a function is_reference(match_text: str, sentence_text: str, paragraph_text: str) that returns a boolean. The input `match_text` is the regex-matched text found in the sentence. The `sentence_text` is a SINGLE SENTENCE extracted from a paragraph. The `paragraph_text` is the full paragraph for additional context.

    Primary Match: Use `re` to find `match_text` in `sentence_text`. Account for OCR errors, varying whitespace, and different dash/hyphen types.
    
    Contextual Anchoring: Analyze the sentence and surrounding context in the paragraph for keywords that refer to {destination_title}.

    Negative filter: If the contextual anchoring is not working well, create a "Negative filter" using the negative samples 

[INPUT/OUTPUT SCHEMA]

    Input: match_text (str), sentence_text (str), paragraph_text (str).

    Output: True if the reference points to the target metadata, False otherwise.

Write a Python function with this EXACT signature:

def is_reference(match_text: str, sentence_text: str, paragraph_text: str) -> bool:
    \"\"\"Return True if match_text in sentence_text is a true reference to {destination_title} - {destination_text}.\"\"\"

The function should analyze the context around the match within the sentence and paragraph to distinguish true references from false positives.

Return ONLY the Python function code, nothing else. No markdown, no explanation"""


class GenerateDestinationDetectionsUseCase:
    def __init__(
        self,
        llm_service: LLMService,
        repository: ReferencesStoreRepository,
    ):
        self.llm_service = llm_service
        self.repository = repository

    def execute(self) -> list[DestinationDetection]:
        references = self.repository.get_references_by_type(ReferenceType.REFERENCE)
        if not references:
            return []

        destination_groups = self._group_references_by_destination(references)
        scripts = []

        for destination_info, refs in destination_groups.items():
            script = self._generate_script_for_destination(destination_info, refs, references)
            if script:
                scripts.append(script)
                self.repository.save_detection_script(script)

        return scripts

    def _group_references_by_destination(
        self,
        references: list[Reference],
    ) -> dict[DestinationInfo, list[Reference]]:
        groups: dict[DestinationInfo, list[Reference]] = {}

        for ref in references:
            if not ref.segment:
                destination_info = DestinationInfo(type=ReferenceType.REFERENCE, name=ref.destination or ref.text)
            else:
                destination_info = DestinationInfo(
                    type=ReferenceType.REFERENCE,
                    name=ref.destination or ref.text,
                    segment_text=ref.segment.text if ref.segment else None,
                    segment_pdf_name=ref.segment.pdf_name if ref.segment else None,
                )

            if destination_info not in groups:
                groups[destination_info] = []
            groups[destination_info].append(ref)

        return groups

    def _generate_script_for_destination(
        self,
        destination_info: DestinationInfo,
        refs: list[Reference],
        all_references: list[Reference],
    ) -> DestinationDetection | None:
        if not refs:
            return None

        reference_texts = self._get_reference_texts(refs)
        paragraph_examples = self._get_paragraph_examples(refs)
        regex = self._generate_regex(destination_info, reference_texts, paragraph_examples)

        positive_samples = self._get_positive_samples(refs)
        negative_samples = self._get_negative_samples(refs, all_references)
        script = self._generate_disambiguation_script(
            destination_info,
            regex,
            positive_samples,
            negative_samples,
        )

        return DestinationDetection.from_destination_and_refs(
            destination=destination_info,
            refs=refs,
            regex=regex,
            script=script,
        )

    def _get_reference_texts(self, refs: list[Reference]) -> list[str]:
        texts = []
        for ref in refs:
            if ref.text and ref.text not in texts:
                texts.append(ref.text)
            if ref.normalized_text and ref.normalized_text not in texts:
                texts.append(ref.normalized_text)
        return texts

    def _get_paragraph_examples(self, refs: list[Reference]) -> list[str]:
        examples = []
        for ref in refs:
            if ref.segment and ref.segment.text and ref.segment.text not in examples:
                examples.append(ref.segment.text)
            if len(examples) >= 5:
                break
        return examples

    def _generate_regex(
        self,
        destination_info: DestinationInfo,
        reference_texts: list[str],
        paragraph_examples: list[str],
    ) -> str:
        reference_texts_str = "\n".join([f"  - {text}" for text in reference_texts])
        paragraph_examples_str = "\n\n".join([f"Example {i+1}:\n{exp}" for i, exp in enumerate(paragraph_examples)])

        prompt = REGEX_PROMPT.format(
            destination_pdf_name=destination_info.segment_pdf_name or "Unknown Document",
            destination_segment_text=destination_info.segment_text or destination_info.name,
            reference_texts_list=reference_texts_str,
            paragraph_examples=paragraph_examples_str,
        )

        response = self.llm_service.query(prompt)
        regex = response.strip().strip("`").strip('"').strip("'")

        if not regex.startswith("(?P<reference>"):
            regex = f"(?P<reference>{regex})"

        return regex

    def _get_positive_samples(self, refs: list[Reference]) -> list[str]:
        samples = []
        for ref in refs:
            segment_text = ref.segment.text if ref.segment else ""
            if segment_text and segment_text not in samples:
                sentences = self._split_into_sentences(segment_text)
                for sentence in sentences:
                    if ref.text in sentence:
                        samples.append(f"Match: '{ref.text}' | Sentence: '{sentence}'")
                        break
        return samples[:10]

    def _get_negative_samples(
        self,
        target_refs: list[Reference],
        all_references: list[Reference],
    ) -> list[str]:
        target_ids = {ref.id for ref in target_refs if ref.id is not None}
        target_texts = {ref.text for ref in target_refs}
        negative_samples = []

        other_refs = [r for r in all_references if r.id not in target_ids]

        for ref in other_refs:
            segment_text = ref.segment.text if ref.segment else ""
            if not segment_text:
                continue

            sentences = self._split_into_sentences(segment_text)
            for sentence in sentences:
                has_match = False
                for target_text in target_texts:
                    if target_text in sentence:
                        has_match = True
                        break

                if has_match:
                    sample = f"Sentence: '{sentence}'"
                    if sample not in negative_samples:
                        negative_samples.append(sample)
                        break

            if len(negative_samples) >= 10:
                break

        return negative_samples

    def _generate_disambiguation_script(
        self,
        destination_info: DestinationInfo,
        regex: str,
        positive_samples: list[str],
        negative_samples: list[str],
    ) -> str:
        positive_samples_str = "\n".join([f"    - {sample}" for sample in positive_samples]) or "    (none available)"
        negative_samples_str = "\n".join([f"    - {sample}" for sample in negative_samples]) or "    (none available)"

        prompt = TRAIN_PROMPT.format(
            destination_title=destination_info.name,
            destination_text=destination_info.segment_text or "Unknown Section",
            regex_from_destination_id=regex,
            positive_samples=positive_samples_str,
            negative_samples=negative_samples_str,
        )

        response = self.llm_service.query(prompt)
        script = response.strip().strip("`")

        return script

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        sentences = SENTENCE_SPLIT_PATTERN.split(text)
        return [s.strip() for s in sentences if s.strip()]
