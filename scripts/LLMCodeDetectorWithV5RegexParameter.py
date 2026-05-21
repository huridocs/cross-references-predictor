import json
import re
from pathlib import Path

import ollama

from ml_train_set.domain.ReferenceData import ReferenceData
from ml_train_set.domain.Prediction import Prediction
from ml_train_set.methods.BaseParagraphReferenceDetector import BaseParagraphReferenceDetector

REGEX_FILE_PATH = Path(__file__).parent.parent / "results" / "v5_generate_regexes.json"
CODE_PATH = Path(__file__).parent.parent / "results" / Path(__file__).stem

LLM_MODEL = "gemma4:31b-cloud"

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

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


class LLMCodeDetectorWithV5RegexParameter(BaseParagraphReferenceDetector):
    def __init__(self, name: str = ""):
        super().__init__(name)
        self.regexes: dict = {}
        self.destination_id: str = ""

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

    @staticmethod
    def _validate_code(code: str, train_data: list[ReferenceData], regex_pattern: str) -> bool:
        try:
            namespace = {}
            exec(code, namespace)
            is_reference = namespace.get("is_reference")

            if not is_reference or not callable(is_reference):
                return False

            compiled = re.compile(regex_pattern)
            true_count = 0
            for sample in train_data:
                match = compiled.search(sample.paragraph_text)
                if not match:
                    continue
                sentence = LLMCodeDetectorWithV5RegexParameter._find_sentence_with_match(
                    sample.paragraph_text, match.start(), match.end()
                )
                match_text = match.group("reference")
                context_before, context_after = LLMCodeDetectorWithV5RegexParameter._get_context_strings(
                    sample.paragraph_text, match.start(), match.end()
                )
                try:
                    result = is_reference(match_text, sentence, sample.paragraph_text, context_before, context_after)
                    if result:
                        true_count += 1
                except Exception:
                    return False

            return true_count > 0
        except Exception:
            return False

    def _load_regexes(self) -> dict:
        if not self.regexes:
            with open(REGEX_FILE_PATH) as f:
                self.regexes = json.load(f)
        return self.regexes

    def train(self, train_data: list[ReferenceData], negative_samples: list[ReferenceData]) -> None:
        self.reset()
        self.destination_id = train_data[0].destination_id

        CODE_PATH.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w\-]", "_", train_data[0].destination_id)
        code_file = CODE_PATH / f"{safe_name}.py"

        if code_file.exists():
            return

        regexes = self._load_regexes()
        regex_pattern = regexes[self.destination_id]["regex_pattern"]
        compiled = re.compile(regex_pattern)

        positive_with_sentences: list[dict] = []
        for s in train_data[:10]:
            match = compiled.search(s.paragraph_text)
            if match:
                sentence = self._find_sentence_with_match(s.paragraph_text, match.start(), match.end())
                context_before, context_after = self._get_context_strings(s.paragraph_text, match.start(), match.end())
            else:
                sentence = s.paragraph_text
                context_before = ""
                context_after = ""
            positive_with_sentences.append(
                {"text": s.text, "sentence": sentence, "context_before": context_before, "context_after": context_after}
            )

        false_positive_samples: list[ReferenceData] = []
        for neg in negative_samples:
            m = compiled.search(neg.paragraph_text)
            if m:
                copy_negative = neg.model_copy()
                copy_negative.text = m.group("reference")
                false_positive_samples.append(copy_negative)

        if not false_positive_samples:
            false_positive_samples = negative_samples[:5]

        negative_with_sentences: list[dict] = []
        for s in false_positive_samples[:10]:
            match = compiled.search(s.paragraph_text)
            if match:
                sentence = self._find_sentence_with_match(s.paragraph_text, match.start(), match.end())
                context_before, context_after = self._get_context_strings(s.paragraph_text, match.start(), match.end())
            else:
                sentence = s.paragraph_text
                context_before = ""
                context_after = ""
            negative_with_sentences.append(
                {
                    "text": s.text,
                    "sentence": sentence,
                    "destination_entity_title": s.destination_entity_title,
                    "context_before": context_before,
                    "context_after": context_after,
                }
            )

        positive_samples_str = "\n".join(
            [
                f'- {{"text": "{d["text"]}", "sentence": "{d["sentence"]}", "context_before": "{d["context_before"]}", "context_after": "{d["context_after"]}"}}'
                for d in positive_with_sentences
            ]
        )
        negative_samples_str = "\n".join(
            [
                f'- {{"text": "{d["text"]}", "sentence": "{d["sentence"]}", "destination_entity_title": "{d["destination_entity_title"]}", "context_before": "{d["context_before"]}", "context_after": "{d["context_after"]}"}}'
                for d in negative_with_sentences
            ]
        )

        prompt = TRAIN_PROMPT.format(
            destination_title=train_data[0].destination_entity_title,
            destination_text=train_data[0].destination_text,
            regex_from_destination_id=regex_pattern,
            positive_samples=positive_samples_str,
            negative_samples=negative_samples_str,
        )

        max_retries = 3
        for attempt in range(max_retries):
            response = ollama.chat(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )

            code = response.message.content.strip()
            if code.startswith("```"):
                code = code.split("\n", 1)[1]
            if code.endswith("```"):
                code = code.rsplit("```", 1)[0]

            if self._validate_code(code, train_data, regex_pattern):
                code_file.write_text(code)
                return

        code_file.write_text(code)

    def reset(self) -> None:
        self.destination_id: str = ""

    def predict(self, paragraph_text: str) -> Prediction:
        regexes = self._load_regexes()
        regex_pattern = regexes[self.destination_id]["regex_pattern"]
        match = re.search(regex_pattern, paragraph_text)

        if not match:
            return Prediction(text="", destination_id="")

        match_text = match.group("reference")
        match_start = match.start()
        match_end = match.end()
        sentence = self._find_sentence_with_match(paragraph_text, match_start, match_end)
        context_before, context_after = self._get_context_strings(paragraph_text, match_start, match_end)
        safe_name = re.sub(r"[^\w\-]", "_", self.destination_id)
        code_file = CODE_PATH / f"{safe_name}.py"

        if code_file.exists():
            namespace = {}
            exec(code_file.read_text(), namespace)
            is_reference = namespace.get("is_reference")
            if is_reference and is_reference(match_text, sentence, paragraph_text, context_before, context_after):
                return Prediction(text=match_text, destination_id=self.destination_id)
        else:
            return Prediction(text=match_text, destination_id=self.destination_id)

        return Prediction(text="", destination_id="")
