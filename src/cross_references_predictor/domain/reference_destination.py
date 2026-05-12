from pydantic import BaseModel
from cross_references_predictor.domain.reference_type import ReferenceType
from rapidfuzz import fuzz

from cross_references_predictor.domain.reference import Reference
import re

from cross_references_predictor.domain.segment import Segment


class ReferenceDestination(BaseModel):
    type: ReferenceType
    name: str
    destination_id: str = ""
    segment: Segment | None = None
    references: list[Reference] = list()
    known_forms: list[str] = []
    is_name_fixed: bool = False
    top_relevance_entity: Reference | None = None

    def is_same_type(self, reference: Reference) -> bool:
        return self.type == reference.type

    def is_exact_match(self, reference: Reference) -> bool:
        return self.name == reference.normalized_text

    def is_similar_entity(self, reference: Reference) -> bool:
        normalized_entity = reference.get_with_normalize_entity_text()
        entity_normalized_text = normalized_entity.normalized_text

        all_normalized_texts = [x.normalized_text for x in self.references]
        for known_form in self.known_forms:
            all_normalized_texts.append(Reference.normalize_text(known_form))

        for each_normalized_text in all_normalized_texts:
            if self.type in [ReferenceType.LOCATION, ReferenceType.PERSON, ReferenceType.ORGANIZATION]:
                if entity_normalized_text in each_normalized_text or each_normalized_text in entity_normalized_text:
                    return True
            if self.equal_but_less_words(entity_normalized_text, each_normalized_text):
                return True
            if self.similar_text(each_normalized_text, entity_normalized_text):
                return True
            if self.is_abbreviation(each_normalized_text, entity_normalized_text):
                return True
        return False

    @staticmethod
    def equal_but_less_words(text: str, other_text: str) -> bool:
        if len(text) < 4 or len(other_text) < 4:
            return False

        text_words = text.split()
        other_text_words = other_text.split()

        words_in_both = [x for x in text_words if x in other_text_words]

        if len(words_in_both) < 2:
            return False

        shorter_name_words = text_words if len(text_words) < len(other_text_words) else other_text_words
        longer_name_words = other_text_words if shorter_name_words == text_words else text_words

        for word in shorter_name_words:
            if word not in longer_name_words:
                return False

        return True

    @staticmethod
    def is_abbreviation(text: str, other_text: str) -> bool:
        if len(text) < 4 or len(other_text) < 4:
            return False

        text_words = text.split()
        other_text_words = other_text.split()

        text_one_letter_words = [x for x in text_words if len(x) == 1]
        other_text_one_letter_words = [x for x in other_text_words if len(x) == 1]

        if not text_one_letter_words and not other_text_one_letter_words:
            return False

        text_first_letters = "".join([x[0] for x in text_words])
        other_text_first_letters = "".join([x[0] for x in other_text_words])

        if text_first_letters != other_text_first_letters:
            return False

        for text_word, other_text_word in zip(text_words, other_text_words):
            if len(text_word) == 1 or len(other_text_word) == 1:
                continue

            if text_word != other_text_word:
                return False

        return True

    @staticmethod
    def similar_text(text: str, other_text: str):
        if abs(len(text) - len(other_text)) > 1:
            return False

        length = max(len(text), len(other_text))
        threshold = 100 * (length - 1) / length if length > 10 else 100
        return fuzz.ratio(text, other_text) >= threshold

    def belongs_to_destination(self, reference: Reference) -> bool:
        if self.type != reference.type:
            return False
        if self.type in [ReferenceType.PERSON, ReferenceType.LOCATION, ReferenceType.ORGANIZATION]:
            return self.is_similar_entity(reference)
        return self.is_exact_match(reference)

    def is_same_destination(self, other: "ReferenceDestination") -> bool:
        if self.type != other.type:
            return False

        for entity in other.references:
            if self.belongs_to_destination(entity):
                return True

        return False

    def add_reference(self, reference: Reference):
        if self.type == ReferenceType.DATE and reference.normalized_text:
            self.name = reference.normalized_text
            self.references.append(reference.get_with_normalize_entity_text())
            return

        if len(reference.text) > len(self.name):
            self.name = reference.text

        self.references.append(reference.get_with_normalize_entity_text())

    def get_references_in_text(self, text: str) -> list[tuple[int, int]]:
        if self.type != ReferenceType.REFERENCE:
            return []

        original_name = self.name.strip()
        stripped_text = text.strip()

        if not original_name or not stripped_text:
            return []

        search_patterns = set()
        search_patterns.add(original_name)

        if ": " in original_name:
            parts = original_name.split(": ", 1)
            if len(parts) == 2:
                part_before_colon = parts[0].strip()
                part_after_colon = parts[1].strip()
                if part_before_colon:
                    search_patterns.add(part_before_colon)
                if part_after_colon:
                    search_patterns.add(part_after_colon)

        # Handle titles with a numbered/lettered prefix ending in a dot,
        # e.g., "4. Results Interpretation" -> adds "Results Interpretation"
        # The prefix part is like "1.", "A.1.", "IV.", etc.
        # Regex: ^ (?:non-capturing-prefix-ending-with-dot) \\s+ (capturing-title-part) $
        dot_prefix_match = re.match(r"^(?:[A-Za-z0-9]+(?:[\.\-][A-ZaZ0-9]+)*[\.\-\,;])\s+(.+)$", original_name)
        if dot_prefix_match:
            title_part = dot_prefix_match.group(1).strip()
            if title_part:
                search_patterns.add(title_part)

        matches = []

        for pattern_text in search_patterns:
            if not pattern_text:
                continue

            escaped_pattern = re.escape(pattern_text)
            # Regex explanation:
            # (?<![\w.])   : Negative lookbehind - asserts that the match is not preceded by a word character or a dot.
            # (?:\"|\')?  : Optional non-capturing group for a double or single quote.
            # escaped_pattern : The actual pattern text, with regex special characters escaped.
            # (?:\"|\')?  : Optional non-capturing group for a double or single quote.
            # (?![\w.])    : Negative lookahead - asserts that the match is not followed by a word character or a dot.
            regex_str = r"(?<![\w.])(?:\"|\')?" + escaped_pattern + r"(?:\"|\')?(?![\w.])"

            try:
                for match in re.finditer(regex_str, text):  # Use original text for spans
                    matches.append(match.span())
            except re.error:
                # Should not happen with proper escaping and non-empty patterns
                pass

        if not matches:
            return []

        # Deduplicate and sort matches by their start position
        unique_matches = sorted(list(set(matches)), key=lambda m: m[0])

        return unique_matches

    @staticmethod
    def references_to_destinations(named_entities: list[Reference]) -> list["ReferenceDestination"]:
        if not named_entities:
            return []

        groups = []
        for entity in named_entities:
            if not groups or not groups[-1].is_same_destination(entity):
                new_group = ReferenceDestination(type=entity.type, name=entity.normalized_text)
                new_group.add_reference(entity)
                groups.append(new_group)
            else:
                groups[-1].add_reference(entity)

        return groups
