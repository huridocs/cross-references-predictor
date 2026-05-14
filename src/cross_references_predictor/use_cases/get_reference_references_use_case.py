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
        references = []
        for detection in self.detection_scripts:
            refs = self._detect_references(text, detection, segment)
            references.extend(refs)
        return sorted(references, key=lambda x: x.character_start)

    def _detect_references(self, text: str, detection: DestinationDetection, segment: Segment = None) -> list[Reference]:
        references = []
        try:
            compiled = re.compile(detection.regex, re.IGNORECASE | re.DOTALL)
        except re.error:
            return references

        for match in compiled.finditer(text):
            match_text = match.group("reference")
            sentence = self._find_sentence_with_match(text, match.start(), match.end())

            if self._is_true_reference(match_text, sentence, text, detection.script):
                reference = Reference(
                    type=ReferenceType.REFERENCE,
                    text=match_text,
                    destination=detection.destination.name,
                    character_start=match.start(),
                    character_end=match.end(),
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
    def _is_true_reference(match_text: str, sentence_text: str, paragraph_text: str, script: str) -> bool:
        if not script:
            return True

        try:
            namespace = {}
            exec(script, namespace)
            is_reference = namespace.get("is_reference")

            if not is_reference or not callable(is_reference):
                return True

            return is_reference(match_text, sentence_text, paragraph_text)
        except Exception:
            return True
