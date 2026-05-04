from unittest import TestCase
from cross_references_predictor.use_cases.methods.get_gli_ner_entities_use_case import GetGLiNEREntitiesUseCase
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType


class TestGetGLiNEREntitiesUseCase(TestCase):
    def setUp(self):
        self.use_case = GetGLiNEREntitiesUseCase(language="en")

    def test_create_use_case(self):
        self.assertEqual(self.use_case.language, "en")
        self.assertEqual(self.use_case.WINDOW_SIZE, 20)
        self.assertEqual(self.use_case.SLIDE_SIZE, 10)

    def test_remove_uncompleted_dates_filters_short_dates(self):
        references = [
            Reference(type=ReferenceType.DATE, text="12 January 2024", character_start=0, character_end=16),
            Reference(type=ReferenceType.DATE, text="Jan 2024", character_start=0, character_end=10),
        ]

        result = GetGLiNEREntitiesUseCase.remove_uncompleted_dates(references)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "12 January 2024")

    def test_remove_uncompleted_dates_keeps_long_dates(self):
        references = [
            Reference(type=ReferenceType.DATE, text="12 January 2024", character_start=0, character_end=16),
            Reference(type=ReferenceType.DATE, text="1 January 2024", character_start=0, character_end=15),
        ]

        result = GetGLiNEREntitiesUseCase.remove_uncompleted_dates(references)

        self.assertEqual(len(result), 2)

    def test_convert_to_named_entity_type(self):
        window_references = [{"text": "12 January 2024", "start": 0, "end": 16}]

        result = self.use_case.convert_to_named_entity_type(window_references)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].type, ReferenceType.DATE)
        self.assertEqual(result[0].text, "12 January 2024")

    def test_convert_to_named_entity_handles_invalid_data(self):
        window_references = []

        result = self.use_case.convert_to_named_entity_type(window_references)

        self.assertEqual(len(result), 0)
