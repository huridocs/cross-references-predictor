import psycopg2
from cross_references_predictor.adapters.reference_persistence import ReferencePersistence
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.segment import Segment
from cross_references_predictor.ports.entities_store_repository import EntitiesStoreRepository
import os


class PostgresReferencesStoreRepository(EntitiesStoreRepository):
    def __init__(self, schema_name: str = "public", language: str = "en"):
        self.language = language
        self.schema_name = f"{schema_name}_{language}"
        self.host = os.environ.get("POSTGRES_HOST", "postgres")
        self.port = os.environ.get("POSTGRES_PORT", "5432")
        self.dbname = os.environ.get("POSTGRES_DB", "references_db")
        self.user = os.environ.get("POSTGRES_USER", "postgres")
        self.password = os.environ.get("POSTGRES_PASSWORD", "postgres")

    def get_connection(self):
        connection = psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
        )
        cursor = connection.cursor()
        return connection, cursor

    def exists_schema(self) -> bool:
        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                (self.schema_name,),
            )
            exists = cursor.fetchone() is not None
            connection.close()
            return exists
        except Exception:
            return False

    def create_database(self):
        connection, cursor = self.get_connection()

        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name}")

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.schema_name}.reference_destination (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.schema_name}.segments (
                id SERIAL PRIMARY KEY,
                text TEXT,
                page_number INTEGER,
                segment_number INTEGER,
                type TEXT,
                source_id TEXT,
                bounding_box_left INTEGER,
                bounding_box_top INTEGER,
                bounding_box_width INTEGER,
                bounding_box_height INTEGER,
                page_width INTEGER,
                page_height INTEGER
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.schema_name}.references (
                id SERIAL PRIMARY KEY,
                type TEXT NOT NULL,
                text TEXT,
                normalized_text TEXT,
                character_start INTEGER,
                character_end INTEGER,
                group_id INTEGER REFERENCES {self.schema_name}.reference_destination(id),
                segment_id INTEGER REFERENCES {self.schema_name}.segments(id),
                appearance_count INTEGER,
                percentage_to_segment_text INTEGER,
                first_type_appearance BOOLEAN,
                last_type_appearance BOOLEAN,
                relevance_percentage INTEGER
            )
        """)
        connection.commit()
        connection.close()

    def get_references(self) -> list[Reference]:
        if not self.exists_schema():
            return []

        self.create_database()
        connection, cursor = self.get_connection()

        cursor.execute(f"""
            SELECT r.id, r.type, r.text, r.normalized_text, r.character_start, r.character_end,
                   r.group_id, r.segment_id,
                   s.text AS segment_text, s.page_number AS segment_page_number,
                   s.segment_number AS segment_segment_number, s.type AS segment_type,
                   s.source_id AS segment_source_id,
                   s.bounding_box_left AS segment_bounding_box_left,
                   s.bounding_box_top AS segment_bounding_box_top,
                   s.bounding_box_width AS segment_bounding_box_width,
                   s.bounding_box_height AS segment_bounding_box_height,
                   s.page_width, s.page_height,
                   r.appearance_count, r.percentage_to_segment_text,
                   r.first_type_appearance, r.last_type_appearance,
                   r.relevance_percentage
            FROM {self.schema_name}.references r
            LEFT JOIN {self.schema_name}.segments s ON r.segment_id = s.id
        """)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        entities = [ReferencePersistence.from_row(row, columns).to_reference() for row in rows]

        connection.close()
        return entities

    def _get_or_create_destination_id(self, cursor, destination_name: str) -> int | None:
        if not destination_name:
            return None
        cursor.execute(
            f"SELECT id FROM {self.schema_name}.reference_destination WHERE name = %s",
            (destination_name,),
        )
        row = cursor.fetchone()
        if row is not None:
            return row[0]
        cursor.execute(
            f"INSERT INTO {self.schema_name}.reference_destination (name) VALUES (%s) RETURNING id",
            (destination_name,),
        )
        result = cursor.fetchone()
        return result[0] if result is not None else None

    def save_references(self, references: list[Reference]) -> bool:
        if not self.exists_schema():
            self.create_database()
        try:
            connection, cursor = self.get_connection()
            source_ids = set(entity.segment.source_id for entity in references if entity.segment is not None)
            if source_ids:
                format_strings = ",".join(["%s"] * len(source_ids))
                cursor.execute(
                    f"""DELETE FROM {self.schema_name}.references 
                    WHERE segment_id IN (SELECT id FROM {self.schema_name}.segments WHERE source_id IN ({format_strings}))""",
                    tuple(source_ids),
                )
                connection.commit()

            for entity in references:
                persistence = ReferencePersistence.from_reference(entity)
                group_id = self._get_or_create_destination_id(cursor, persistence.group_name)

                if entity.id is not None:
                    cursor.execute(
                        f"SELECT id FROM {self.schema_name}.references WHERE id = %s",
                        (entity.id,),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute(
                            f"""
                            UPDATE {self.schema_name}.references SET
                                type = %s, text = %s, normalized_text = %s, character_start = %s,
                                character_end = %s, appearance_count = %s, percentage_to_segment_text = %s,
                                first_type_appearance = %s, last_type_appearance = %s, relevance_percentage = %s,
                                group_id = %s
                            WHERE id = %s
                            """,
                            (
                                str(persistence.type),
                                persistence.text,
                                persistence.normalized_text,
                                persistence.character_start,
                                persistence.character_end,
                                persistence.appearance_count,
                                persistence.percentage_to_segment_text,
                                persistence.first_type_appearance,
                                persistence.last_type_appearance,
                                persistence.relevance_percentage,
                                group_id,
                                entity.id,
                            ),
                        )
                        continue

                segment_id = None
                if entity.segment and entity.segment.source_id:
                    cursor.execute(
                        f"SELECT id FROM {self.schema_name}.segments WHERE source_id = %s",
                        (entity.segment.source_id,),
                    )
                    seg_row = cursor.fetchone()
                    if seg_row:
                        segment_id = seg_row[0]

                cursor.execute(
                    f"""
                    INSERT INTO {self.schema_name}.references (
                        type, text, normalized_text, character_start, character_end, group_id,
                        segment_id,
                        appearance_count, percentage_to_segment_text, first_type_appearance, last_type_appearance, relevance_percentage
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(persistence.type),
                        persistence.text,
                        persistence.normalized_text,
                        persistence.character_start,
                        persistence.character_end,
                        group_id,
                        segment_id,
                        persistence.appearance_count,
                        persistence.percentage_to_segment_text,
                        persistence.first_type_appearance,
                        persistence.last_type_appearance,
                        persistence.relevance_percentage,
                    ),
                )
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error saving entities: {e}")
            return False

    def delete_database(self):
        try:
            connection, cursor = self.get_connection()
            cursor.execute(f"DROP SCHEMA IF EXISTS {self.schema_name} CASCADE")
            connection.commit()
            connection.close()
        except Exception as e:
            print(f"Error deleting database schema: {e}")

    def save_segments(self, segments: list[Segment]) -> bool:
        if not self.exists_schema():
            self.create_database()

        try:
            connection, cursor = self.get_connection()

            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.segments (
                    id SERIAL PRIMARY KEY,
                    text TEXT,
                    page_number INTEGER,
                    segment_number INTEGER,
                    type TEXT,
                    source_id TEXT,
                    bounding_box_left INTEGER,
                    bounding_box_top INTEGER,
                    bounding_box_width INTEGER,
                    bounding_box_height INTEGER,
                    page_width INTEGER,
                    page_height INTEGER
                )
            """)

            source_ids = set(seg.source_id for seg in segments)
            if source_ids:
                format_strings = ",".join(["%s"] * len(source_ids))
                cursor.execute(
                    f"DELETE FROM {self.schema_name}.segments WHERE source_id IN ({format_strings})",
                    tuple(source_ids),
                )

            for segment in segments:
                cursor.execute(
                    f"""
                    INSERT INTO {self.schema_name}.segments (
                        text, page_number, segment_number, type, source_id,
                        bounding_box_left, bounding_box_top, bounding_box_width, bounding_box_height,
                        page_width, page_height
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        segment.text,
                        segment.page_number,
                        segment.segment_number,
                        segment.type,
                        segment.source_id,
                        segment.bounding_box.left,
                        segment.bounding_box.top,
                        segment.bounding_box.width,
                        segment.bounding_box.height,
                        segment.page_width,
                        segment.page_height,
                    ),
                )

            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error saving segments: {e}")
            return False

    def get_segments(self, identifier: str) -> list[Segment]:
        if not self.exists_schema():
            return []

        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"SELECT * FROM {self.schema_name}.segments WHERE source_id = %s",
                (identifier,),
            )
            rows = cursor.fetchall()
            connection.close()

            segments = []
            for row in rows:
                from pdf_features import Rectangle

                segments.append(
                    Segment(
                        id=row[0],
                        text=row[1],
                        page_number=row[2],
                        segment_number=row[3],
                        type=row[4],
                        source_id=row[5],
                        bounding_box=Rectangle.from_width_height(left=row[6], top=row[7], width=row[8], height=row[9]),
                        page_width=row[10],
                        page_height=row[11],
                    )
                )
            return segments
        except Exception as e:
            print(f"Error getting segments: {e}")
            return []

    def get_all_references(self) -> list:
        if not self.exists_schema():
            return []

        try:
            connection, cursor = self.get_connection()
            cursor.execute(f"SELECT id, name FROM {self.schema_name}.reference_destination ORDER BY id")
            destinations = cursor.fetchall()

            groups = []
            from cross_references_predictor.domain.reference_destination import ReferenceDestination
            from cross_references_predictor.domain.reference import Reference
            from cross_references_predictor.domain.reference_type import ReferenceType
            from pdf_features import Rectangle
            from cross_references_predictor.domain.segment import Segment

            for dest_id, dest_name in destinations:
                destination = ReferenceDestination(
                    type=ReferenceType.REFERENCE,
                    name=dest_name,
                    segment=None,
                    references=[],
                )

                cursor.execute(
                    f"""
                    SELECT ne.id, ne.text, s.text, s.page_number, s.segment_number, s.type, s.source_id, s.bounding_box_left, s.bounding_box_top, s.bounding_box_width, s.bounding_box_height
                    FROM {self.schema_name}.references ne
                    LEFT JOIN {self.schema_name}.segments s ON ne.segment_id = s.id
                    WHERE ne.group_id = %s AND ne.type = 'REFERENCE'
                    ORDER BY ne.id
                    """,
                    (dest_id,),
                )

                refs = cursor.fetchall()
                for ref in refs:
                    ref_id, ref_text = ref[0], ref[1]
                    (
                        segment_text,
                        segment_page_number,
                        segment_segment_number,
                        segment_type,
                        segment_source_id,
                        segment_bounding_box_left,
                        segment_bounding_box_top,
                        segment_bounding_box_width,
                        segment_bounding_box_height,
                    ) = (
                        ref[2],
                        ref[3],
                        ref[4],
                        ref[5],
                        ref[6],
                        ref[7],
                        ref[8],
                        ref[9],
                        ref[10],
                    )

                    segment = None
                    if segment_text is not None or segment_source_id is not None:
                        segment = Segment(
                            text=segment_text if segment_text else "",
                            page_number=(segment_page_number if segment_page_number else 0),
                            segment_number=(segment_segment_number if segment_segment_number else 0),
                            type=segment_type if segment_type else "Text",
                            source_id=segment_source_id if segment_source_id else "",
                            bounding_box=Rectangle.from_width_height(
                                left=(segment_bounding_box_left if segment_bounding_box_left else 0),
                                top=(segment_bounding_box_top if segment_bounding_box_top else 0),
                                width=(segment_bounding_box_width if segment_bounding_box_width else 0),
                                height=(segment_bounding_box_height if segment_bounding_box_height else 0),
                            ),
                        )

                    entity = Reference(type=ReferenceType.REFERENCE, text=ref_text, segment=segment)
                    entity_dict = entity.model_dump()
                    entity_dict["id"] = ref_id
                    destination.references.append(entity_dict)

                groups.append(destination.model_dump())

            connection.close()
            return groups
        except Exception as e:
            print(f"Error getting references: {e}")
            return []

    def delete_reference(self, reference_id: int) -> bool:
        if not self.exists_schema():
            return False

        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"DELETE FROM {self.schema_name}.references WHERE id = %s AND type = 'REFERENCE'",
                (reference_id,),
            )
            cursor.execute(f"""
                DELETE FROM {self.schema_name}.reference_destination
                WHERE id NOT IN (SELECT DISTINCT group_id FROM {self.schema_name}.references WHERE type = 'REFERENCE' AND group_id IS NOT NULL)
            """)
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error deleting reference: {e}")
            return False

    def get_reference_by_id(self, reference_id: int) -> dict | None:
        self.create_database()
        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"""
                SELECT ne.id, ne.type, ne.text, ne.normalized_text, ne.character_start, ne.character_end,
                       ne.group_id, ne.segment_id, ne.appearance_count, ne.percentage_to_segment_text,
                       ne.first_type_appearance, ne.last_type_appearance, ne.relevance_percentage,
                       rd.name as destination_name,
                       s.id as segment_id_db, s.text as segment_text, s.page_number, s.segment_number,
                       s.type as segment_type, s.source_id, s.bounding_box_left, s.bounding_box_top,
                       s.bounding_box_width, s.bounding_box_height, s.page_width, s.page_height
                FROM {self.schema_name}.references ne
                LEFT JOIN {self.schema_name}.reference_destination rd ON ne.group_id = rd.id
                LEFT JOIN {self.schema_name}.segments s ON ne.segment_id = s.id
                WHERE ne.id = %s AND ne.type = 'REFERENCE'
                """,
                (reference_id,),
            )
            row = cursor.fetchone()
            connection.close()

            if row is None:
                return None

            from cross_references_predictor.domain.reference_type import ReferenceType
            from pdf_features import Rectangle
            from cross_references_predictor.domain.segment import Segment

            segment = None
            if row[14] is not None:
                segment = Segment(
                    id=row[14],
                    text=row[15] or "",
                    page_number=row[16] or 0,
                    segment_number=row[17] or 0,
                    type=row[18] or "Text",
                    source_id=row[19] or "",
                    bounding_box=Rectangle.from_width_height(
                        left=row[20] or 0,
                        top=row[21] or 0,
                        width=row[22] or 0,
                        height=row[23] or 0,
                    ),
                    page_width=row[24] or 0,
                    page_height=row[25] or 0,
                )

            return {
                "id": row[0],
                "type": row[1],
                "text": row[2],
                "normalized_text": row[3],
                "character_start": row[4],
                "character_end": row[5],
                "group_id": row[6],
                "segment_id": row[7],
                "appearance_count": row[8],
                "percentage_to_segment_text": row[9],
                "first_type_appearance": row[10],
                "last_type_appearance": row[11],
                "relevance_percentage": row[12],
                "destination_name": row[13],
                "segment": segment.to_dict() if segment else None,
            }
        except Exception as e:
            print(f"Error getting reference by id: {e}")
            return None

    def update_reference(self, reference_id: int, updates: dict) -> bool:
        if not self.exists_schema():
            return False

        try:
            connection, cursor = self.get_connection()

            destination_name = updates.get("destination_name")
            if destination_name is not None:
                cursor.execute(
                    f"SELECT id FROM {self.schema_name}.reference_destination WHERE name = %s",
                    (destination_name,),
                )
                row = cursor.fetchone()
                if row is not None:
                    group_id = row[0]
                else:
                    cursor.execute(
                        f"INSERT INTO {self.schema_name}.reference_destination (name) VALUES (%s) RETURNING id",
                        (destination_name,),
                    )
                    result = cursor.fetchone()
                    group_id = result[0] if result else None
            else:
                group_id = None

            reference_text = updates.get("text")
            if group_id is not None and reference_text is not None:
                cursor.execute(
                    f"""
                    UPDATE {self.schema_name}.references
                    SET text = %s, normalized_text = %s, group_id = %s
                    WHERE id = %s AND type = 'REFERENCE'
                    """,
                    (reference_text, reference_text, group_id, reference_id),
                )
            elif reference_text is not None:
                cursor.execute(
                    f"""
                    UPDATE {self.schema_name}.references
                    SET text = %s, normalized_text = %s
                    WHERE id = %s AND type = 'REFERENCE'
                    """,
                    (reference_text, reference_text, reference_id),
                )
            elif group_id is not None:
                cursor.execute(
                    f"UPDATE {self.schema_name}.references SET group_id = %s WHERE id = %s AND type = 'REFERENCE'",
                    (group_id, reference_id),
                )

            cursor.execute(f"""
                DELETE FROM {self.schema_name}.reference_destination
                WHERE id NOT IN (SELECT DISTINCT group_id FROM {self.schema_name}.references WHERE type = 'REFERENCE' AND group_id IS NOT NULL)
            """)

            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error updating reference: {e}")
            return False
