from unittest import TestCase
from unittest.mock import MagicMock, patch
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.domain.segment import Segment
from pdf_features import Rectangle


class TestReferencePersistence(TestCase):

    def test_to_reference_includes_id(self):
        from cross_references_predictor.adapters.reference_persistence import ReferencePersistence

        persistence = ReferencePersistence(
            id=42,
            type=ReferenceType.PERSON,
            text="John Doe",
        )

        reference = persistence.to_reference()

        self.assertEqual(42, reference.id)

    def test_to_reference_without_id(self):
        from cross_references_predictor.adapters.reference_persistence import ReferencePersistence

        persistence = ReferencePersistence(
            type=ReferenceType.PERSON,
            text="John Doe",
        )

        reference = persistence.to_reference()

        self.assertIsNone(reference.id)

    def test_from_reference_includes_id(self):
        from cross_references_predictor.adapters.reference_persistence import ReferencePersistence

        reference = Reference(
            id=99,
            type=ReferenceType.LOCATION,
            text="Paris",
        )

        persistence = ReferencePersistence.from_reference(reference)

        self.assertEqual(99, persistence.id)

    def test_from_reference_without_id(self):
        from cross_references_predictor.adapters.reference_persistence import ReferencePersistence

        reference = Reference(
            type=ReferenceType.LOCATION,
            text="Paris",
        )

        persistence = ReferencePersistence.from_reference(reference)

        self.assertIsNone(persistence.id)

    def test_from_row_with_id_column(self):
        from cross_references_predictor.adapters.reference_persistence import ReferencePersistence

        columns = ["id", "type", "text", "normalized_text", "character_start", "character_end"]
        row = [10, "PERSON", "Jane Doe", "jane doe", 0, 8]

        persistence = ReferencePersistence.from_row(row, columns)

        self.assertEqual(10, persistence.id)
        self.assertEqual(ReferenceType.PERSON, persistence.type)
        self.assertEqual("Jane Doe", persistence.text)


class TestEntityPersistence(TestCase):

    def test_to_reference_includes_id(self):
        from cross_references_predictor.adapters.entity_persistence import EntityPersistence

        persistence = EntityPersistence(
            id=42,
            type=ReferenceType.PERSON,
            text="John Doe",
        )

        reference = persistence.to_reference()

        self.assertEqual(42, reference.id)

    def test_to_reference_without_id(self):
        from cross_references_predictor.adapters.entity_persistence import EntityPersistence

        persistence = EntityPersistence(
            type=ReferenceType.PERSON,
            text="John Doe",
        )

        reference = persistence.to_reference()

        self.assertIsNone(reference.id)


class TestPostgresReferencesStoreRepositorySaveReferences(TestCase):

    @patch("cross_references_predictor.adapters.postgres_entities_store_repository.psycopg2")
    def test_save_references_with_id_updates_existing(self, mock_psycopg2):
        from cross_references_predictor.adapters.postgres_entities_store_repository import PostgresReferencesStoreRepository

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = (mock_connection, mock_cursor)
        mock_cursor.fetchone.return_value = (1,)

        repository = PostgresReferencesStoreRepository("test_ns", "en")

        segment = Segment(
            text="Test segment",
            source_id="test_source",
            page_number=1,
            segment_number=1,
            type="Text",
            bounding_box=Rectangle.from_width_height(0, 0, 100, 50),
        )

        references = [
            Reference(
                id=42,
                type=ReferenceType.PERSON,
                text="John Doe",
                segment=segment,
            ),
        ]

        with patch.object(repository, "exists_schema", return_value=True):
            repository.save_references(references)

        cursor_calls = mock_cursor.execute.call_args_list
        update_call_found = any("UPDATE" in str(call) for call in cursor_calls)

        self.assertTrue(update_call_found, "UPDATE statement should be called for references with id")


class TestPostgresReferencesStoreRepositoryGetReferences(TestCase):

    @patch("cross_references_predictor.adapters.postgres_entities_store_repository.psycopg2")
    def test_get_references_returns_with_ids(self, mock_psycopg2):
        from cross_references_predictor.adapters.postgres_entities_store_repository import PostgresReferencesStoreRepository

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_psycopg2.connect.return_value = (mock_connection, mock_cursor)
        mock_cursor.fetchone.return_value = True
        mock_cursor.fetchall.return_value = [
            (
                1,
                "PERSON",
                "John Doe",
                "john doe",
                0,
                8,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                0,
                0,
                False,
                False,
                50,
            )
        ]
        mock_cursor.description = [
            ("id",),
            ("type",),
            ("text",),
            ("normalized_text",),
            ("character_start",),
            ("character_end",),
            ("group_id",),
            ("segment_id",),
            ("segment_text",),
            ("segment_page_number",),
            ("segment_segment_number",),
            ("segment_type",),
            ("segment_source_id",),
            ("segment_bounding_box_left",),
            ("segment_bounding_box_top",),
            ("segment_bounding_box_width",),
            ("segment_bounding_box_height",),
            ("page_width",),
            ("page_height",),
            ("appearance_count",),
            ("percentage_to_segment_text",),
            ("first_type_appearance",),
            ("last_type_appearance",),
            ("relevance_percentage",),
        ]

        repository = PostgresReferencesStoreRepository("test_ns", "en")

        with patch.object(repository, "exists_schema", return_value=True):
            references = repository.get_references()

        self.assertEqual(1, len(references))
        self.assertEqual(1, references[0].id)
        self.assertEqual("John Doe", references[0].text)
        self.assertEqual(ReferenceType.PERSON, references[0].type)
