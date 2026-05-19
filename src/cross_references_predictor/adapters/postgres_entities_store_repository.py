import json
import psycopg2
from cross_references_predictor.adapters.reference_persistence import ReferencePersistence
from cross_references_predictor.domain.consolidated_destination import ConsolidatedDestination
from cross_references_predictor.domain.destination_detection import DestinationDetection
from cross_references_predictor.domain.destination_info import DestinationInfo
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.domain.segment import Segment
from cross_references_predictor.ports.references_store_repository import ReferencesStoreRepository
import os


class PostgresReferencesStoreRepository(ReferencesStoreRepository):
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
                pdf_name TEXT,
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
                segment_text TEXT,
                appearance_count INTEGER,
                percentage_to_segment_text INTEGER,
                first_type_appearance BOOLEAN,
                last_type_appearance BOOLEAN,
                relevance_percentage INTEGER
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.schema_name}.consolidated_destinations (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                alternative_names TEXT DEFAULT '[]',
                is_from_reference BOOLEAN DEFAULT FALSE,
                external_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(f"""
            ALTER TABLE {self.schema_name}.consolidated_destinations
            DROP CONSTRAINT IF EXISTS consolidated_destinations_name_type_key
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.schema_name}.detection_scripts (
                id SERIAL PRIMARY KEY,
                destination_id TEXT UNIQUE NOT NULL,
                destination_type TEXT NOT NULL,
                destination_name TEXT NOT NULL,
                destination_segment_text TEXT,
                destination_segment_pdf_name TEXT,
                reference_ids TEXT DEFAULT '[]',
                regex TEXT NOT NULL,
                script TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.schema_name}.negative_samples (
                id SERIAL PRIMARY KEY,
                destination_id TEXT NOT NULL,
                segment_text TEXT NOT NULL,
                pdf_name TEXT,
                page_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                   rd.name AS group_name, r.segment_id,
                   COALESCE(r.segment_text, s.text) AS segment_text, s.page_number AS segment_page_number,
                   s.segment_number AS segment_segment_number, s.type AS segment_type,
                   s.pdf_name AS segment_pdf_name,
                   s.bounding_box_left AS segment_bounding_box_left,
                   s.bounding_box_top AS segment_bounding_box_top,
                   s.bounding_box_width AS segment_bounding_box_width,
                   s.bounding_box_height AS segment_bounding_box_height,
                   s.page_width, s.page_height,
                   r.appearance_count, r.percentage_to_segment_text,
                   r.first_type_appearance, r.last_type_appearance,
                   r.relevance_percentage
            FROM {self.schema_name}.references r
            LEFT JOIN {self.schema_name}.reference_destination rd ON r.group_id = rd.id
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
            pdf_names = set(entity.segment.pdf_name for entity in references if entity.segment is not None)
            if pdf_names:
                format_strings = ",".join(["%s"] * len(pdf_names))
                cursor.execute(
                    f"""DELETE FROM {self.schema_name}.references 
                    WHERE segment_id IN (SELECT id FROM {self.schema_name}.segments WHERE pdf_name IN ({format_strings}))""",
                    tuple(pdf_names),
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
                                group_id = %s, segment_text = %s
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
                                persistence.segment_text,
                                entity.id,
                            ),
                        )
                        continue

                segment_id = None
                if entity.segment and entity.segment.pdf_name:
                    cursor.execute(
                        f"SELECT id FROM {self.schema_name}.segments WHERE pdf_name = %s",
                        (entity.segment.pdf_name,),
                    )
                    seg_row = cursor.fetchone()
                    if seg_row:
                        segment_id = seg_row[0]

                cursor.execute(
                    f"""
                    INSERT INTO {self.schema_name}.references (
                        type, text, normalized_text, character_start, character_end, group_id,
                        segment_id, segment_text,
                        appearance_count, percentage_to_segment_text, first_type_appearance, last_type_appearance, relevance_percentage
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(persistence.type),
                        persistence.text,
                        persistence.normalized_text,
                        persistence.character_start,
                        persistence.character_end,
                        group_id,
                        segment_id,
                        persistence.segment_text,
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
                    pdf_name TEXT,
                    bounding_box_left INTEGER,
                    bounding_box_top INTEGER,
                    bounding_box_width INTEGER,
                    bounding_box_height INTEGER,
                    page_width INTEGER,
                    page_height INTEGER
                )
            """)

            pdf_names = set(seg.pdf_name for seg in segments)
            if pdf_names:
                format_strings = ",".join(["%s"] * len(pdf_names))
                cursor.execute(
                    f"DELETE FROM {self.schema_name}.segments WHERE pdf_name IN ({format_strings})",
                    tuple(pdf_names),
                )

            for segment in segments:
                cursor.execute(
                    f"""
                    INSERT INTO {self.schema_name}.segments (
                        text, page_number, segment_number, type, pdf_name,
                        bounding_box_left, bounding_box_top, bounding_box_width, bounding_box_height,
                        page_width, page_height
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        segment.text,
                        segment.page_number,
                        segment.segment_number,
                        segment.type,
                        segment.pdf_name,
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
                f"SELECT * FROM {self.schema_name}.segments WHERE pdf_name = %s",
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
                        pdf_name=row[5],
                        bounding_box=Rectangle.from_width_height(left=row[6], top=row[7], width=row[8], height=row[9]),
                        page_width=row[10],
                        page_height=row[11],
                    )
                )
            return segments
        except Exception as e:
            print(f"Error getting segments: {e}")
            return []

    def get_all_destinations(self) -> list[ConsolidatedDestination]:
        if not self.exists_schema():
            return []

        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"SELECT name, type, alternative_names, is_from_reference, external_id FROM {self.schema_name}.consolidated_destinations ORDER BY name"
            )
            rows = cursor.fetchall()
            connection.close()

            destinations = []
            for row in rows:
                alt_names = json.loads(row[2]) if row[2] else []
                destinations.append(
                    ConsolidatedDestination(
                        name=row[0],
                        type=ReferenceType(row[1]),
                        alternative_names=alt_names,
                        is_from_reference=bool(row[3]),
                        external_id=row[4],
                    )
                )
            return destinations
        except Exception as e:
            print(f"Error getting all destinations: {e}")
            return []

    def _get_or_create_segment_id(self, cursor, segment: Segment | None) -> int | None:
        if not segment:
            return None
        cursor.execute(
            f"""
            SELECT id FROM {self.schema_name}.segments
            WHERE pdf_name = %s AND text = %s AND page_number = %s AND segment_number = %s
            """,
            (segment.pdf_name, segment.text, segment.page_number, segment.segment_number),
        )
        row = cursor.fetchone()
        if row is not None:
            return row[0]
        cursor.execute(
            f"""
            INSERT INTO {self.schema_name}.segments (
                text, page_number, segment_number, type, pdf_name,
                bounding_box_left, bounding_box_top, bounding_box_width, bounding_box_height,
                page_width, page_height
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                segment.text,
                segment.page_number,
                segment.segment_number,
                segment.type,
                segment.pdf_name,
                segment.bounding_box.left if segment.bounding_box else 0,
                segment.bounding_box.top if segment.bounding_box else 0,
                segment.bounding_box.width if segment.bounding_box else 0,
                segment.bounding_box.height if segment.bounding_box else 0,
                segment.page_width,
                segment.page_height,
            ),
        )
        result = cursor.fetchone()
        return result[0] if result is not None else None

    def save_reference_occurrences(self, references: list[Reference]) -> bool:
        if not self.exists_schema():
            self.create_database()

        try:
            connection, cursor = self.get_connection()

            for entity in references:
                persistence = ReferencePersistence.from_reference(entity)
                group_id = self._get_or_create_destination_id(cursor, persistence.group_name)
                segment_id = self._get_or_create_segment_id(cursor, entity.segment)

                cursor.execute(
                    f"""
                    DELETE FROM {self.schema_name}.references
                    WHERE type = 'REFERENCE'
                      AND text = %s
                      AND group_id = %s
                    """,
                    (persistence.text, group_id),
                )

                cursor.execute(
                    f"""
                    INSERT INTO {self.schema_name}.references (
                        type, text, normalized_text, character_start, character_end, group_id,
                        segment_id, segment_text,
                        appearance_count, percentage_to_segment_text, first_type_appearance, last_type_appearance, relevance_percentage
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(persistence.type),
                        persistence.text,
                        persistence.normalized_text,
                        persistence.character_start,
                        persistence.character_end,
                        group_id,
                        segment_id,
                        persistence.segment_text,
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
            print(f"Error saving reference occurrences: {e}")
            return False

    def get_consolidated_destinations(self) -> list[ConsolidatedDestination]:
        if not self.exists_schema():
            return []

        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"SELECT name, type, alternative_names, is_from_reference, external_id FROM {self.schema_name}.consolidated_destinations"
            )
            rows = cursor.fetchall()
            connection.close()

            destinations = []
            for row in rows:
                alt_names = json.loads(row[2]) if row[2] else []
                destinations.append(
                    ConsolidatedDestination(
                        name=row[0],
                        type=ReferenceType(row[1]),
                        alternative_names=alt_names,
                        is_from_reference=bool(row[3]),
                        external_id=row[4],
                    )
                )

            # Deduplicate similar destinations
            deduplicated = []
            for dest in destinations:
                merged = False
                for existing in deduplicated:
                    if existing.type == dest.type and existing.matches(dest):
                        existing.merge_with(dest)
                        merged = True
                        break
                if not merged:
                    deduplicated.append(dest)

            return deduplicated
        except Exception as e:
            print(f"Error getting consolidated destinations: {e}")
            return []

    def save_consolidated_destinations(self, destinations: list[ConsolidatedDestination]) -> bool:
        if not self.exists_schema():
            self.create_database()

        try:
            connection, cursor = self.get_connection()

            cursor.execute(
                f"SELECT id, name, type, alternative_names, is_from_reference, external_id FROM {self.schema_name}.consolidated_destinations"
            )
            rows = cursor.fetchall()

            existing_list: list[dict] = []
            for row in rows:
                existing_list.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "type": ReferenceType(row[2]),
                        "alternative_names": json.loads(row[3]) if row[3] else [],
                        "is_from_reference": bool(row[4]),
                        "external_id": row[5],
                    }
                )

            matched_ids: set[int] = set()

            for dest in destinations:
                matched = False

                for existing in existing_list:
                    if existing["id"] in matched_ids:
                        continue

                    if existing["type"] != dest.type:
                        continue

                    existing_cd = ConsolidatedDestination(
                        name=existing["name"],
                        type=existing["type"],
                        alternative_names=existing["alternative_names"],
                        is_from_reference=existing["is_from_reference"],
                        external_id=existing["external_id"],
                    )

                    if existing_cd.matches(dest):
                        existing_cd.merge_with(dest)
                        if dest.is_from_reference and existing_cd.is_from_reference and dest.name != existing_cd.name:
                            old_name = existing_cd.name
                            existing_cd.name = dest.name
                            existing_cd.add_alternative_name(old_name)
                        merged_alt = [a for a in existing_cd.alternative_names if a != existing_cd.name]

                        cursor.execute(
                            f"""
                            UPDATE {self.schema_name}.consolidated_destinations
                            SET name = %s, alternative_names = %s, is_from_reference = %s, external_id = %s
                            WHERE id = %s
                            """,
                            (
                                existing_cd.name,
                                json.dumps(merged_alt),
                                existing_cd.is_from_reference,
                                existing_cd.external_id,
                                existing["id"],
                            ),
                        )

                        existing["name"] = existing_cd.name
                        existing["alternative_names"] = merged_alt
                        existing["is_from_reference"] = existing_cd.is_from_reference
                        existing["external_id"] = existing_cd.external_id
                        matched_ids.add(existing["id"])
                        matched = True
                        break

                if not matched:
                    alt_names_json = json.dumps(dest.alternative_names)
                    cursor.execute(
                        f"""
                        INSERT INTO {self.schema_name}.consolidated_destinations (name, type, alternative_names, is_from_reference, external_id)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (dest.name, str(dest.type), alt_names_json, dest.is_from_reference, dest.external_id),
                    )

            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error saving consolidated destinations: {e}")
            return False

    def update_consolidated_destination(self, current_name: str, updated: ConsolidatedDestination) -> bool:
        if not self.exists_schema():
            return False

        try:
            connection, cursor = self.get_connection()

            cursor.execute(
                f"SELECT id, name, type, alternative_names, is_from_reference, external_id FROM {self.schema_name}.consolidated_destinations WHERE name = %s",
                (current_name,),
            )
            row = cursor.fetchone()

            if not row:
                connection.close()
                return False

            existing_id = row[0]
            existing_alt = json.loads(row[3]) if row[3] else []
            existing_is_ref = bool(row[4])
            existing_ext_id = row[5]

            merged_alt = list(existing_alt)
            for alt in updated.alternative_names:
                if alt not in merged_alt and alt != updated.name:
                    merged_alt.append(alt)

            if current_name != updated.name and current_name not in merged_alt:
                merged_alt.append(current_name)

            is_ref = existing_is_ref or updated.is_from_reference
            ext_id = existing_ext_id or updated.external_id

            cursor.execute(
                f"""
                UPDATE {self.schema_name}.consolidated_destinations
                SET name = %s, type = %s, alternative_names = %s, is_from_reference = %s, external_id = %s
                WHERE id = %s
                """,
                (updated.name, str(updated.type), json.dumps(merged_alt), is_ref, ext_id, existing_id),
            )

            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error updating consolidated destination: {e}")
            return False

    def reset_consolidated_destinations(self) -> bool:
        if not self.exists_schema():
            return True

        try:
            connection, cursor = self.get_connection()
            cursor.execute(f"DELETE FROM {self.schema_name}.consolidated_destinations WHERE is_from_reference = FALSE")
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error resetting consolidated destinations: {e}")
            return False

    def get_references_by_type(self, reference_type: str) -> list[Reference]:
        if not self.exists_schema():
            return []

        self.create_database()
        try:
            connection, cursor = self.get_connection()

            cursor.execute(
                f"""
                SELECT r.id, r.type, r.text, r.normalized_text, r.character_start, r.character_end,
                       rd.name AS group_name, r.segment_id,
                       COALESCE(r.segment_text, s.text) AS segment_text, s.page_number AS segment_page_number,
                       s.segment_number AS segment_segment_number, s.type AS segment_type,
                       s.pdf_name AS segment_pdf_name,
                       s.bounding_box_left AS segment_bounding_box_left,
                       s.bounding_box_top AS segment_bounding_box_top,
                       s.bounding_box_width AS segment_bounding_box_width,
                       s.bounding_box_height AS segment_bounding_box_height,
                       s.page_width, s.page_height,
                       r.appearance_count, r.percentage_to_segment_text,
                       r.first_type_appearance, r.last_type_appearance,
                       r.relevance_percentage
                FROM {self.schema_name}.references r
                LEFT JOIN {self.schema_name}.reference_destination rd ON r.group_id = rd.id
                LEFT JOIN {self.schema_name}.segments s ON r.segment_id = s.id
                WHERE r.type = %s
            """,
                (reference_type,),
            )
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            entities = [ReferencePersistence.from_row(row, columns).to_reference() for row in rows]

            connection.close()
            return entities
        except Exception as e:
            print(f"Error getting references by type: {e}")
            return []

    def save_detection_script(self, script: DestinationDetection) -> bool:
        if not self.exists_schema():
            self.create_database()

        try:
            connection, cursor = self.get_connection()
            reference_ids_json = json.dumps(script.reference_ids)

            cursor.execute(
                f"""
                INSERT INTO {self.schema_name}.detection_scripts (
                    destination_id, destination_type, destination_name,
                    destination_segment_text, destination_segment_pdf_name,
                    reference_ids, regex, script
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (destination_id) DO UPDATE SET
                    destination_type = EXCLUDED.destination_type,
                    destination_name = EXCLUDED.destination_name,
                    destination_segment_text = EXCLUDED.destination_segment_text,
                    destination_segment_pdf_name = EXCLUDED.destination_segment_pdf_name,
                    reference_ids = EXCLUDED.reference_ids,
                    regex = EXCLUDED.regex,
                    script = EXCLUDED.script,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    script.destination_id,
                    str(script.destination.type),
                    script.destination.name,
                    script.destination.segment_text,
                    script.destination.segment_pdf_name,
                    reference_ids_json,
                    script.regex,
                    script.script,
                ),
            )
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error saving detection script: {e}")
            return False

    def get_detection_scripts(self) -> list[DestinationDetection]:
        if not self.exists_schema():
            return []

        self.create_database()
        try:
            connection, cursor = self.get_connection()
            cursor.execute(f"""
                SELECT destination_id, destination_type, destination_name,
                       destination_segment_text, destination_segment_pdf_name,
                       reference_ids, regex, script, created_at
                FROM {self.schema_name}.detection_scripts
            """)
            rows = cursor.fetchall()
            connection.close()

            scripts = []
            for row in rows:
                reference_ids = json.loads(row[5]) if row[5] else []
                destination = DestinationInfo(
                    type=ReferenceType(row[1]),
                    name=row[2],
                    segment_text=row[3],
                    segment_pdf_name=row[4],
                )
                scripts.append(
                    DestinationDetection(
                        destination_id=row[0],
                        destination=destination,
                        reference_ids=reference_ids,
                        regex=row[6],
                        script=row[7],
                        created_at=str(row[8]) if row[8] else None,
                    )
                )
            return scripts
        except Exception as e:
            print(f"Error getting detection scripts: {e}")
            return []

    def get_detection_script_by_destination_id(self, destination_id: str) -> DestinationDetection | None:
        if not self.exists_schema():
            return None

        self.create_database()
        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"""
                SELECT destination_id, destination_type, destination_name,
                       destination_segment_text, destination_segment_pdf_name,
                       reference_ids, regex, script, created_at
                FROM {self.schema_name}.detection_scripts
                WHERE destination_id = %s
            """,
                (destination_id,),
            )
            row = cursor.fetchone()
            connection.close()

            if row is None:
                return None

            reference_ids = json.loads(row[5]) if row[5] else []
            destination = DestinationInfo(
                type=ReferenceType(row[1]),
                name=row[2],
                segment_text=row[3],
                segment_pdf_name=row[4],
            )
            return DestinationDetection(
                destination_id=row[0],
                destination=destination,
                reference_ids=reference_ids,
                regex=row[6],
                script=row[7],
                created_at=str(row[8]) if row[8] else None,
            )
        except Exception as e:
            print(f"Error getting detection script by destination id: {e}")
            return None

    def delete_detection_script(self, destination_id: str) -> bool:
        if not self.exists_schema():
            return False

        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"DELETE FROM {self.schema_name}.detection_scripts WHERE destination_id = %s",
                (destination_id,),
            )
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error deleting detection script: {e}")
            return False

    def save_negative_samples(self, destination: str, segments: list[Segment]) -> bool:
        if not self.exists_schema():
            self.create_database()

        try:
            connection, cursor = self.get_connection()

            for segment in segments:
                cursor.execute(
                    f"""
                    INSERT INTO {self.schema_name}.negative_samples
                        (destination_id, segment_text, pdf_name, page_number)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (destination, segment.text, segment.pdf_name, segment.page_number),
                )

            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error saving negative samples: {e}")
            return False

    def get_negative_samples(self, destination: str) -> list[Segment]:
        if not self.exists_schema():
            return []

        try:
            connection, cursor = self.get_connection()
            cursor.execute(
                f"""
                SELECT segment_text, pdf_name, page_number
                FROM {self.schema_name}.negative_samples
                WHERE destination_id = %s
                """,
                (destination,),
            )
            rows = cursor.fetchall()
            connection.close()

            segments = []
            for row in rows:
                from pdf_features import Rectangle

                segments.append(
                    Segment(
                        text=row[0],
                        page_number=row[2] if row[2] is not None else 0,
                        segment_number=0,
                        type="Text",
                        pdf_name=row[1] if row[1] else "",
                        bounding_box=Rectangle.from_width_height(left=0, top=0, width=0, height=0),
                    )
                )
            return segments
        except Exception as e:
            print(f"Error getting negative samples: {e}")
            return []
