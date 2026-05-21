import re

from cross_references_predictor.configuration import PROCESS_REFERENCE_TYPES
from cross_references_predictor.domain.destination_detection import DestinationDetection
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.domain.segment import Segment
from cross_references_predictor.ports.references_store_repository import ReferencesStoreRepository

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


class GetReferenceReferencesUseCase:
    def __init__(self, repository: ReferencesStoreRepository = None):
        self.repository = repository
        self.detection_scripts: list[DestinationDetection] = []
        self._load_detection_scripts()

    def _load_detection_scripts(self):
        if self.repository is not None:
            self.detection_scripts = self.repository.get_detection_scripts()

    def is_enabled(self) -> bool:
        return "REFERENCE" in PROCESS_REFERENCE_TYPES

    def execute(self, segments: list[Segment]) -> list[Reference]:
        if not self.is_enabled():
            return []
        return self.get_references_from_segments(segments)

    def get_references_from_segments(self, segments: list[Segment]) -> list[Reference]:
        all_references = []
        for segment in segments:
            references = self.get_references_from_text(segment.text, segment)
            all_references.extend(references)
        return all_references

    def get_references_from_text(self, text: str, segment: Segment = None) -> list[Reference]:
        references: list[Reference] = []
        for detection in self.detection_scripts:
            refs = self._detect_references(text, detection, segment)
            references.extend(refs)
        return self._deduplicate_references(references, text)

    def _deduplicate_references(self, references: list[Reference], text: str) -> list[Reference]:
        if not references:
            return references

        groups: dict[tuple[int, int], list[Reference]] = {}
        for ref in references:
            key = (ref.character_start, ref.character_end)
            if key not in groups:
                groups[key] = []
            groups[key].append(ref)

        result: list[Reference] = []
        for pos, refs in groups.items():
            if len(refs) == 1:
                result.extend(refs)
                continue

            _, context_after = self._get_context_strings(text, pos[0], pos[1])
            context_lower = context_after.lower()

            scored = []
            for ref in refs:
                dest_words = [w.strip(".,;:()[]{}") for w in ref.destination.lower().split() if len(w) > 2]
                if not dest_words:
                    scored.append((0, ref))
                    continue
                score = sum(1 for w in dest_words if w in context_lower)
                scored.append((score, ref))

            scored.sort(key=lambda x: x[0], reverse=True)
            result.append(scored[0][1])

        return sorted(result, key=lambda x: x.character_start)

    def _detect_references(self, text: str, detection: DestinationDetection, segment: Segment = None) -> list[Reference]:
        references = []
        try:
            compiled = re.compile(detection.regex, re.IGNORECASE | re.DOTALL)
        except re.error:
            return references

        for match in compiled.finditer(text):
            match_text = match.group("reference")
            match_start = match.start()
            match_end = match.end()
            sentence = self._find_sentence_with_match(text, match_start, match_end)
            context_before, context_after = self._get_context_strings(text, match_start, match_end)

            if self._is_true_reference(match_text, sentence, text, context_before, context_after, detection.script):
                reference = Reference(
                    type=ReferenceType.REFERENCE,
                    text=match_text,
                    destination=detection.destination.name,
                    character_start=match_start,
                    character_end=match_end,
                    segment=segment,
                )
                references.append(reference)

        return references

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
    def _is_true_reference(
        match_text: str, sentence_text: str, paragraph_text: str, context_before: str, context_after: str, script: str
    ) -> bool:
        if not script:
            return True

        try:
            namespace = {}
            exec(script, namespace)
            is_reference = namespace.get("is_reference")

            if not is_reference or not callable(is_reference):
                return True

            return is_reference(match_text, sentence_text, paragraph_text, context_before, context_after)
        except Exception:
            return True
