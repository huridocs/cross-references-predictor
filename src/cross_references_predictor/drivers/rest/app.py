import sys
import tempfile
import uuid
from pathlib import Path
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from starlette.responses import FileResponse

from cross_references_predictor.adapters.pdf_layout_analysis_repository import PDFLayoutAnalysisRepository
from cross_references_predictor.adapters.pdf_visualization_repository import PDFVisualizationRepository
from cross_references_predictor.adapters.postgres_entities_store_repository import PostgresReferencesStoreRepository

from cross_references_predictor.domain.segment import Segment
from cross_references_predictor.drivers.rest.catch_exceptions import catch_exceptions
from cross_references_predictor.drivers.rest.response_entities.cross_references_response import CrossReferencesResponse

from cross_references_predictor.use_cases.get_geolocation_use_case import GetGeolocationUseCase
from cross_references_predictor.use_cases.get_words_positions_use_case import GetWordsPositionsUseCase
from cross_references_predictor.use_cases.reference_destination_entities_use_case import ReferenceDestinationUseCase
from cross_references_predictor.use_cases.get_references_use_case import GetReferencesUseCase
from cross_references_predictor.use_cases.visualize_entities_use_case import VisualizeEntitiesUseCase
import logging

logging.basicConfig(level=logging.INFO)

try:
    import torch

    logging.info(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        logging.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
except ImportError:
    logging.info("PyTorch not installed")

app = FastAPI()


def pdf_content_to_pdf_path(file_content, file_name: str = None) -> Path:
    file_name = file_name if file_name else str(uuid.uuid1()) + ".pdf"
    pdf_path = Path(tempfile.gettempdir()) / file_name
    pdf_path.write_bytes(file_content)
    return pdf_path


@app.get("/")
async def info():
    return sys.version


@app.post("/")
@catch_exceptions
async def get_cross_references(
    namespace: str = Form(None),
    identifier: str = Form(None),
    text: str = Form(None),
    file: UploadFile = File(None),
    fast: bool = Form(False),
    language: str = Form("en"),
):
    pdf_path = None
    if file:
        pdf_path = pdf_content_to_pdf_path(await file.read(), file.filename)
        segments = PDFLayoutAnalysisRepository().get_segments(pdf_path, fast)
    else:
        segments = [Segment.from_text(text=text if text else "", source_id=identifier)]

    references_from_db = PostgresReferencesStoreRepository(namespace, language).get_references() if namespace else list()

    get_references_use_case = GetReferencesUseCase(language)
    references = get_references_use_case.get_references_from_segments(segments)

    if file and pdf_path:
        references = GetWordsPositionsUseCase(PDFLayoutAnalysisRepository(), pdf_path).add_positions(references)

    reference_destinations = ReferenceDestinationUseCase(references_from_db, language).group(references)

    if namespace:
        repository = PostgresReferencesStoreRepository(namespace, language)
        repository.save_references(references)
        if identifier:
            repository.save_identifier(identifier)

    return CrossReferencesResponse.from_destinations(reference_destinations)


@app.get("/identifiers")
@catch_exceptions
async def get_identifiers(namespace: str = "default_namespace", language: str = "en"):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    return store_repository.get_identifiers()


@app.get("/segments")
@catch_exceptions
async def get_segments(identifier: str, namespace: str = "default_namespace", language: str = "en"):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    return [
        segment.to_dict() if hasattr(segment, "to_dict") else segment.__dict__
        for segment in store_repository.get_segments(identifier)
    ]


@app.post("/save_text")
@catch_exceptions
async def save_text(
    namespace: str = Form(None),
    identifier: str = Form(None),
    text: str = Form(None),
    file: UploadFile = File(None),
    fast: bool = Form(False),
    language: str = Form("en"),
):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    if store_repository.is_processed(identifier):
        return "Already processed"

    if file:
        pdf_path = pdf_content_to_pdf_path(await file.read(), file.filename)
        segments = PDFLayoutAnalysisRepository().get_segments(pdf_path, fast)
    else:
        segments = [Segment.from_text(text=text if text else "", source_id=identifier)]

    store_repository.save_segments(segments)
    return "Texts saved"


@app.post("/delete_namespace")
@catch_exceptions
async def delete_namespace(namespace: str = Form(None), language: str = Form("en")):
    PostgresReferencesStoreRepository(namespace, language).delete_database()
    return "Deleted"


@app.post("/is_processed")
@catch_exceptions
async def is_processed(namespace: str = Form(None), identifier: str = Form(None), language: str = Form("en")):
    if not namespace or not identifier:
        return False

    exists = PostgresReferencesStoreRepository(namespace, language).is_processed(identifier)
    return exists


@app.post("/visualize")
@catch_exceptions
async def visualize(file: UploadFile = File(...), fast: bool = Form(False), language: str = Form("en")):
    pdf_path = pdf_content_to_pdf_path(await file.read(), file.filename)
    segments = PDFLayoutAnalysisRepository().get_segments(pdf_path, fast)

    get_references_use_case = GetReferencesUseCase(language)
    references = get_references_use_case.get_references_from_segments(segments)
    references = GetWordsPositionsUseCase(PDFLayoutAnalysisRepository(), pdf_path).add_positions(references)

    annotated_pdf_path = VisualizeEntitiesUseCase(PDFVisualizationRepository()).create_annotated_pdf(pdf_path, references)

    return FileResponse(path=annotated_pdf_path, media_type="application/pdf", filename=f"annotated_{file.filename}")


@app.post("/geolocation")
@catch_exceptions
async def geolocation(location: str = Form(...)):
    return GetGeolocationUseCase().get_coordinates(location)


@app.post("/create_reference")
@catch_exceptions
async def create_reference(
    namespace: str = Form(...),
    segment_id: int = Form(None),
    reference_text: str = Form(...),
    to_text: str = Form(...),
    language: str = Form("en"),
):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    success = store_repository.save_reference(segment_id, reference_text, to_text)
    if success:
        return {"status": "success", "message": "Reference created successfully"}
    else:
        return {"status": "error", "message": "Failed to create reference"}


@app.get("/references")
@catch_exceptions
async def get_references(namespace: str = "default_namespace", language: str = "en"):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    return store_repository.get_all_references()


@app.get("/references/{reference_id}")
@catch_exceptions
async def get_reference(reference_id: int, namespace: str = "default_namespace", language: str = "en"):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    reference = store_repository.get_reference_by_id(reference_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="Reference not found")
    return reference


@app.patch("/references/{reference_id}")
@catch_exceptions
async def update_reference(
    reference_id: int,
    namespace: str = Form(...),
    language: str = Form("en"),
    text: str = Form(None),
    destination_name: str = Form(None),
):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    updates = {}
    if text is not None:
        updates["text"] = text
    if destination_name is not None:
        updates["destination_name"] = destination_name

    if not updates:
        return {"status": "error", "message": "No updates provided"}

    success = store_repository.update_reference(reference_id, updates)
    if success:
        return {"status": "success", "message": "Reference updated successfully"}
    else:
        return {"status": "error", "message": "Failed to update reference"}, 400


@app.post("/delete_reference")
@catch_exceptions
async def delete_reference(namespace: str = Form(...), reference_id: int = Form(...), language: str = "en"):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    success = store_repository.delete_reference(reference_id)
    if success:
        return {"status": "success", "message": "Reference deleted successfully"}
    else:
        return {"status": "error", "message": "Failed to delete reference"}
