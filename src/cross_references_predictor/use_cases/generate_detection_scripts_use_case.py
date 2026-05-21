import re

from cross_references_predictor.domain.destination_detection import DestinationDetection
from cross_references_predictor.domain.destination_info import DestinationInfo
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.ports.llm_service import LLMService
from cross_references_predictor.ports.references_store_repository import ReferencesStoreRepository

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


REGEX_PROMPT = """Objective: Create a Python-compatible regular expression to identify specific cross-document references within a large corpus.

Target Metadata:

    Destination Document: {destination_name}

    Target Section/Text: {destination_text}

Specific Reference Strings to Match:
The regex must specifically capture the following variations that point to the target:
{reference_texts_list}

Examples of paragraphs that contain references to the target:

{paragraph_examples}
{failing_regex_section}
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


ENTITY_REGEX_PROMPT = """Objective: Create a Python-compatible regular expression to identify references to an entity document within a large corpus.

Target Entity: {destination_name}

Reference Strings to Match:
The regex must specifically capture the following reference variations that point to this entity:
{reference_texts_list}

Requirements:

    1. Core Matching Strategy (Prioritize Recall)

        Target the Essence: Extract only the core, identifying elements of the reference text.

        Maximize Recall: Optimize for high recall over strict precision. You must match any reasonable variation of the target, including alternative spellings, plurals, and partial text.

    2. Human Error & Future-Proofing

        Anticipate Typos & Variations: Humans make mistakes. Use optional characters (?), character classes ([...]), or alternations (|) to account for common typos and variations.

        Abbreviations & Equivalents: Account for common abbreviations (e.g., "St" and "Street", "N" and "North").

    3. Pattern Mechanics

        Whitespace & Punctuation: Use \\s+ to handle variable whitespace, tabs, or newlines. Allow optional punctuation between words.

        Word Boundaries (\\b): Apply \\b to isolate short strings or numbers.

    4. Syntax

        Compatibility: The generated regex MUST be 100% compatible with Python's standard re module.

        Internal Grouping: Use non-capturing groups (?:...) for any internal alternations.

        Final Capture: Wrap the entire pattern within a named capturing group "reference": (?P<reference>...)

    5. Strict Output

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

    Positive Samples (True Matches — each sample shows the sentence containing the match, plus the immediate text before and after the matched occurrence):
    {positive_samples}


[NEGATIVE SAMPLES]
    Negative Samples (Distractors to Avoid — each sample shows the sentence containing the match, plus the immediate text before and after the matched occurrence):
    {negative_samples}

[CRITICAL DISAMBIGUATION RULE]
The same reference text may appear multiple times in a single paragraph referring to DIFFERENT documents.
Example: "As mentioned in Article 1 of the Charter and Article 1 of the Protocol."
The first "Article 1" refers to the Charter; the second "Article 1" refers to the Protocol.
You MUST validate ONLY the specific occurrence provided by the context strings.
DO NOT use `re.search()`, `str.find()`, or any method that locates the first occurrence of `match_text` inside the paragraph.

[LOGIC REQUIREMENTS]
Your task is to create a function is_reference(match_text: str, sentence_text: str, paragraph_text: str, context_before: str, context_after: str) that returns a boolean.

    Primary Match: The `match_text` is the regex-matched text. `sentence_text` is the single sentence containing it. `paragraph_text` is the full paragraph.
    
    Contextual Anchoring: Analyze `context_before` (text immediately before this specific occurrence) and `context_after` (text immediately after this specific occurrence) for keywords that refer to {destination_title}.

    Negative filter: If the contextual anchoring is not working well, create a "Negative filter" using the negative samples.

[INPUT/OUTPUT SCHEMA]

    Input: match_text (str), sentence_text (str), paragraph_text (str), context_before (str), context_after (str).

    Output: True if the reference points to the target metadata, False otherwise.

Write a Python function with this EXACT signature:

def is_reference(match_text: str, sentence_text: str, paragraph_text: str, context_before: str, context_after: str) -> bool:
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
        groups: dict[str, list[Reference]] = {}

        for ref in references:
            name = ref.destination or ref.text
            groups.setdefault(name, []).append(ref)

        result: dict[DestinationInfo, list[Reference]] = {}
        for name, refs in groups.items():
            result[DestinationInfo(type=ReferenceType.REFERENCE, name=name)] = refs

        return result

    def _has_segment_text(self, refs: list[Reference]) -> bool:
        return any(ref.segment and ref.segment.text for ref in refs)

    def _generate_script_for_destination(
        self,
        destination_info: DestinationInfo,
        refs: list[Reference],
        all_references: list[Reference],
    ) -> DestinationDetection | None:
        if not refs:
            return None

        reference_texts = self._get_reference_texts(refs)
        has_segment = self._has_segment_text(refs)

        if has_segment:
            paragraph_examples = self._get_paragraph_examples(refs)
            regex = self._generate_regex_with_retry(destination_info, reference_texts, paragraph_examples)
            positive_samples = self._get_positive_samples(refs, regex)
            negative_samples = self._get_negative_samples(refs, all_references, regex)
            script = self._generate_disambiguation_script_with_retry(
                destination_info,
                regex,
                positive_samples,
                negative_samples,
            )
        else:
            regex = self._generate_regex_for_entity_reference(destination_info, reference_texts)
            script = ""

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

    def _generate_regex_with_retry(
        self,
        destination_info: DestinationInfo,
        reference_texts: list[str],
        paragraph_examples: list[str],
    ) -> str:
        regex = self._generate_regex(destination_info, reference_texts, paragraph_examples)
        if self._validate_regex(regex, reference_texts):
            return regex

        regex = self._generate_regex(
            destination_info,
            reference_texts,
            paragraph_examples,
            think=True,
            failing_regex=regex,
        )
        if self._validate_regex(regex, reference_texts):
            return regex

        return regex

    @staticmethod
    def _validate_regex(regex: str, reference_texts: list[str]) -> bool:
        try:
            compiled = re.compile(regex, re.IGNORECASE | re.DOTALL)
            return all(compiled.search(ref) for ref in reference_texts)
        except re.error:
            return False

    def _generate_regex(
        self,
        destination_info: DestinationInfo,
        reference_texts: list[str],
        paragraph_examples: list[str],
        think: bool = False,
        failing_regex: str | None = None,
    ) -> str:
        reference_texts_str = "\n".join([f"  - {text}" for text in reference_texts])
        examples_str = "\n\n".join([f"Example {i+1}:\n{exp[:500]}" for i, exp in enumerate(paragraph_examples[:2])])

        failing_regex_section = ""
        if failing_regex:
            failing_regex_section = (
                f"\n\nPreviously Generated Regex (FAILED):\n\n"
                f"The following regex was generated but did not match all reference strings:\n"
                f"{failing_regex}\n\n"
                f"Please generate a different regex that matches ALL reference strings listed above."
            )

        prompt = REGEX_PROMPT.format(
            destination_name=destination_info.name,
            destination_text=destination_info.name,
            reference_texts_list=reference_texts_str,
            paragraph_examples=examples_str or "No examples available.",
            failing_regex_section=failing_regex_section,
        )

        response = self.llm_service.query(prompt, think=think)
        regex = response.strip().strip("`").strip('"').strip("'")

        if not regex.startswith("(?P<reference>"):
            regex = f"(?P<reference>{regex})"

        return regex

    def _generate_regex_for_entity_reference(
        self,
        destination_info: DestinationInfo,
        reference_texts: list[str],
    ) -> str:
        reference_texts_str = "\n".join([f"  - {text}" for text in reference_texts])

        prompt = ENTITY_REGEX_PROMPT.format(
            destination_name=destination_info.name,
            reference_texts_list=reference_texts_str,
        )

        response = self.llm_service.query(prompt)
        regex = response.strip().strip("`").strip('"').strip("'")

        if not regex.startswith("(?P<reference>"):
            regex = f"(?P<reference>{regex})"

        return regex

    @staticmethod
    def _get_context_strings(text: str, match_start: int, match_end: int) -> tuple[str, str]:
        match_text = text[match_start:match_end]

        next_pos = text.find(match_text, match_end)
        prev_pos = text.rfind(match_text, 0, match_start)

        before_start = max(0, match_start - 100)
        if prev_pos != -1:
            before_start = max(before_start, prev_pos + len(match_text))

        after_end = min(len(text), match_end + 100)
        if next_pos != -1:
            after_end = min(after_end, next_pos)

        context_before = text[before_start:match_start]
        context_after = text[match_end:after_end]
        return context_before, context_after

    def _get_positive_samples(self, refs: list[Reference], regex: str) -> list[dict]:
        try:
            compiled = re.compile(regex)
        except re.error:
            compiled = None

        samples: list[dict] = []
        for ref in refs[:10]:
            paragraph_text = ref.segment.text if ref.segment else ""
            if compiled and ref.character_start > 0 and ref.character_end > ref.character_start:
                match_start = ref.character_start
                match_end = ref.character_end
                sentence = self._find_sentence_with_match(paragraph_text, match_start, match_end)
                context_before, context_after = self._get_context_strings(paragraph_text, match_start, match_end)
                samples.append(
                    {
                        "text": ref.text,
                        "sentence": sentence,
                        "paragraph_text": paragraph_text,
                        "context_before": context_before,
                        "context_after": context_after,
                    }
                )
                continue

            if compiled:
                match = compiled.search(paragraph_text)
                if match:
                    sentence = self._find_sentence_with_match(paragraph_text, match.start(), match.end())
                    context_before, context_after = self._get_context_strings(paragraph_text, match.start(), match.end())
                    samples.append(
                        {
                            "text": match.group("reference"),
                            "sentence": sentence,
                            "paragraph_text": paragraph_text,
                            "context_before": context_before,
                            "context_after": context_after,
                        }
                    )
                    continue

            sentence = paragraph_text
            samples.append(
                {
                    "text": ref.text,
                    "sentence": sentence,
                    "paragraph_text": paragraph_text,
                    "context_before": "",
                    "context_after": "",
                }
            )

        return samples

    def _get_negative_samples(
        self,
        target_refs: list[Reference],
        all_references: list[Reference],
        regex: str,
    ) -> list[dict]:
        target_ids = {ref.id for ref in target_refs if ref.id is not None}
        compiled = re.compile(regex)
        negative_samples: list[dict] = []

        # 1. Try explicit negative samples from repository
        destination_name = target_refs[0].destination or target_refs[0].text
        try:
            explicit_negative_segments = self.repository.get_negative_samples(destination_name)
            for segment in explicit_negative_segments:
                paragraph_text = segment.text
                if not paragraph_text:
                    continue
                m = compiled.search(paragraph_text)
                if m:
                    sentence = self._find_sentence_with_match(paragraph_text, m.start(), m.end())
                    context_before, context_after = self._get_context_strings(paragraph_text, m.start(), m.end())
                    negative_samples.append(
                        {
                            "text": m.group("reference"),
                            "sentence": sentence,
                            "destination_entity_title": "Unknown",
                            "paragraph_text": paragraph_text,
                            "context_before": context_before,
                            "context_after": context_after,
                        }
                    )
                if len(negative_samples) >= 10:
                    return negative_samples
        except Exception:
            pass

        # 2. Find false positives in other references' paragraphs
        target_texts = {ref.text for ref in target_refs}
        other_refs = [r for r in all_references if r.id not in target_ids]
        for ref in other_refs:
            paragraph_text = ref.segment.text if ref.segment else ""
            if not paragraph_text:
                continue

            if ref.text not in target_texts:
                continue

            if ref.character_start > 0 and ref.character_end > ref.character_start:
                m_start = ref.character_start
                m_end = ref.character_end
                sentence = self._find_sentence_with_match(paragraph_text, m_start, m_end)
                context_before, context_after = self._get_context_strings(paragraph_text, m_start, m_end)
                negative_samples.append(
                    {
                        "text": ref.text,
                        "sentence": sentence,
                        "destination_entity_title": ref.destination or ref.text,
                        "paragraph_text": paragraph_text,
                        "context_before": context_before,
                        "context_after": context_after,
                    }
                )
            else:
                m = compiled.search(paragraph_text)
                if m:
                    sentence = self._find_sentence_with_match(paragraph_text, m.start(), m.end())
                    context_before, context_after = self._get_context_strings(paragraph_text, m.start(), m.end())
                    negative_samples.append(
                        {
                            "text": m.group("reference"),
                            "sentence": sentence,
                            "destination_entity_title": ref.destination or ref.text,
                            "paragraph_text": paragraph_text,
                            "context_before": context_before,
                            "context_after": context_after,
                        }
                    )

            if len(negative_samples) >= 10:
                break

        # 3. Fallback: use other references' paragraphs with substring matches
        if not negative_samples:
            for ref in other_refs:
                paragraph_text = ref.segment.text if ref.segment else ""
                if not paragraph_text:
                    continue

                sentences = self._split_into_sentences(paragraph_text)
                for sentence in sentences:
                    has_match = False
                    for target_text in target_texts:
                        if target_text in sentence:
                            has_match = True
                            break

                    if has_match:
                        negative_samples.append(
                            {
                                "text": target_texts.pop() if target_texts else "",
                                "sentence": sentence,
                                "destination_entity_title": ref.destination or ref.text,
                                "paragraph_text": paragraph_text,
                                "context_before": "",
                                "context_after": "",
                            }
                        )
                        break

                if len(negative_samples) >= 5:
                    break

        return negative_samples[:10]

    def _generate_disambiguation_script_with_retry(
        self,
        destination_info: DestinationInfo,
        regex: str,
        positive_samples: list[dict],
        negative_samples: list[dict],
    ) -> str:
        script = self._generate_disambiguation_script(destination_info, regex, positive_samples, negative_samples)
        if self._validate_script(script, positive_samples, regex):
            return script

        for _ in range(2):
            script = self._generate_disambiguation_script(destination_info, regex, positive_samples, negative_samples)
            if self._validate_script(script, positive_samples, regex):
                return script

        return script

    @staticmethod
    def _validate_script(script: str, positive_samples: list[dict], regex: str) -> bool:
        try:
            namespace = {}
            exec(script, namespace)
            is_reference = namespace.get("is_reference")

            if not is_reference or not callable(is_reference):
                return False

            true_count = 0
            for sample in positive_samples:
                paragraph_text = sample.get("paragraph_text", "")
                if not paragraph_text:
                    continue

                match_text = sample.get("text", "")
                sentence = sample.get("sentence", "")
                context_before = sample.get("context_before", "")
                context_after = sample.get("context_after", "")
                try:
                    result = is_reference(match_text, sentence, paragraph_text, context_before, context_after)
                    if result:
                        true_count += 1
                except Exception:
                    return False

            return true_count > 0
        except Exception:
            return False

    def _generate_disambiguation_script(
        self,
        destination_info: DestinationInfo,
        regex: str,
        positive_samples: list[dict],
        negative_samples: list[dict],
    ) -> str:
        positive_samples_str = (
            "\n".join(
                [
                    f'- {{"text": "{s["text"]}", "sentence": "{s["sentence"]}", "context_before": "{s.get("context_before", "")}", "context_after": "{s.get("context_after", "")}"}}'
                    for s in positive_samples
                ]
            )
            or "    (none available)"
        )

        negative_samples_str = (
            "\n".join(
                [
                    f'- {{"text": "{s["text"]}", "sentence": "{s["sentence"]}", "destination_entity_title": "{s["destination_entity_title"]}", "context_before": "{s.get("context_before", "")}", "context_after": "{s.get("context_after", "")}"}}'
                    for s in negative_samples
                ]
            )
            or "    (none available)"
        )

        prompt = TRAIN_PROMPT.format(
            destination_title=destination_info.name,
            destination_text=destination_info.name,
            regex_from_destination_id=regex,
            positive_samples=positive_samples_str,
            negative_samples=negative_samples_str,
        )

        response = self.llm_service.query(prompt)
        script = response.strip().strip("`")

        return script

    @staticmethod
    def _find_sentence_with_match(text: str, match_start: int, match_end: int) -> str:
        sentences = SENTENCE_SPLIT_PATTERN.split(text)
        pos = 0
        for sentence in sentences:
            sentence_start = text.find(sentence, pos)
            sentence_end = sentence_start + len(sentence)
            if sentence_start <= match_start < sentence_end:
                return sentence.strip()
            pos = sentence_end
        return text

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        sentences = SENTENCE_SPLIT_PATTERN.split(text)
        return [s.strip() for s in sentences if s.strip()]
