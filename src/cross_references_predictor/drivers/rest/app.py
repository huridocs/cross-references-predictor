import json
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from starlette.responses import FileResponse

from cross_references_predictor.adapters.ollama_llm_repository import OllamaLLMRepository
from cross_references_predictor.adapters.pdf_layout_analysis_repository import PDFLayoutAnalysisRepository
from cross_references_predictor.configuration import DEFAULT_LLM_MODEL
from cross_references_predictor.adapters.pdf_visualization_repository import PDFVisualizationRepository
from cross_references_predictor.adapters.postgres_entities_store_repository import PostgresReferencesStoreRepository
from cross_references_predictor.adapters.model_loader_repository import ConcreteModelLoader

from cross_references_predictor.domain.consolidated_destination import ConsolidatedDestination
from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_type import ReferenceType
from cross_references_predictor.domain.segment import Segment
from cross_references_predictor.drivers.rest.catch_exceptions import catch_exceptions
from cross_references_predictor.drivers.rest.models.cross_references_response import CrossReferencesResponse
from cross_references_predictor.drivers.rest.models.save_destinations_request import DestinationSeed, SaveDestinationsRequest
from cross_references_predictor.drivers.rest.models.save_reference_occurrences_request import SaveReferenceOccurrencesRequest
from cross_references_predictor.drivers.rest.models.save_negative_samples_request import SaveNegativeSamplesRequest

from cross_references_predictor.use_cases.generate_detection_scripts_use_case import GenerateDestinationDetectionsUseCase
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

_tasks: dict[str, dict] = {}


def pdf_content_to_pdf_path(file_content, file_name: str = None) -> Path:
    file_name = file_name if file_name else str(uuid.uuid1()) + ".pdf"
    pdf_path = Path(tempfile.gettempdir()) / file_name
    pdf_path.write_bytes(file_content)
    return pdf_path


@app.get("/")
async def info():
    return sys.version


@app.get("/health/llm")
@catch_exceptions
async def health_llm():
    try:
        llm = OllamaLLMRepository(model=DEFAULT_LLM_MODEL)
        response = llm.query("Respond with only the word OK")
        if response.strip() != "OK":
            return {"status": "error", "model": DEFAULT_LLM_MODEL, "error": f"Unexpected response: {response}"}
        return {"status": "ok", "model": DEFAULT_LLM_MODEL}
    except Exception as e:
        return {"status": "error", "model": DEFAULT_LLM_MODEL, "error": str(e)}


@app.post("/")
@catch_exceptions
async def get_cross_references(
    namespace: str = Form(None),
    identifier: str = Form(None),
    text: str = Form(None),
    file: UploadFile = File(None),
    fast: bool = Form(False),
    language: str = Form("en"),
    segments: str = Form(None),
):
    pdf_path = None
    if file:
        pdf_path = pdf_content_to_pdf_path(await file.read(), file.filename)
        segments = PDFLayoutAnalysisRepository().get_segments(pdf_path, fast)
    elif segments:
        segments_data = json.loads(segments)
        segments = [Segment(**seg) for seg in segments_data]
    else:
        segments = [Segment.from_text(text=text if text else "", pdf_name=identifier)]

    store_repository = PostgresReferencesStoreRepository(namespace, language) if namespace else None
    references_from_db = store_repository.get_references() if store_repository else list()
    consolidated_destinations = store_repository.get_consolidated_destinations() if store_repository else list()

    model_loader = ConcreteModelLoader()
    get_references_use_case = GetReferencesUseCase(
        language,
        model_loader=model_loader,
        references_repository=store_repository,
    )
    references = get_references_use_case.get_references_from_segments(segments)

    if file and pdf_path:
        references = GetWordsPositionsUseCase(PDFLayoutAnalysisRepository(), pdf_path).add_positions(references)

    reference_destinations = ReferenceDestinationUseCase(references_from_db, language, consolidated_destinations).group(
        references
    )

    return CrossReferencesResponse.from_destinations(reference_destinations)


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

    if file:
        pdf_path = pdf_content_to_pdf_path(await file.read(), file.filename)
        segments = PDFLayoutAnalysisRepository().get_segments(pdf_path, fast)
    else:
        segments = [Segment.from_text(text=text if text else "", pdf_name=identifier)]

    store_repository.save_segments(segments)
    return "Texts saved"


@app.post("/delete_namespace")
@catch_exceptions
async def delete_namespace(namespace: str = Form(None), language: str = Form("en")):
    PostgresReferencesStoreRepository(namespace, language).delete_database()
    return "Deleted"


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


@app.post("/destinations")
@catch_exceptions
async def save_destinations(request: SaveDestinationsRequest):
    store_repository = PostgresReferencesStoreRepository(request.namespace, request.language)
    destinations = [
        ConsolidatedDestination(
            name=seed.name,
            type=seed.type,
            alternative_names=seed.alternative_names,
            external_id=seed.external_id,
        )
        for seed in request.destinations
    ]
    success = store_repository.save_consolidated_destinations(destinations)
    if success:
        return {"status": "success", "message": f"Saved {len(destinations)} destinations"}
    else:
        return {"status": "error", "message": "Failed to save destinations"}, 400


@app.get("/destinations")
@catch_exceptions
async def get_destinations(namespace: str = "default_namespace", language: str = "en"):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    destinations = store_repository.get_all_destinations()
    return [
        {
            "name": dest.name,
            "type": str(dest.type),
            "external_id": dest.external_id,
            "alternative_names": dest.alternative_names,
        }
        for dest in destinations
    ]


@app.put("/destinations/{name}")
@catch_exceptions
async def update_destination(
    name: str, destination: DestinationSeed, namespace: str = "default_namespace", language: str = "en"
):
    store_repository = PostgresReferencesStoreRepository(namespace, language)

    updated = ConsolidatedDestination(
        name=destination.name,
        type=destination.type,
        alternative_names=destination.alternative_names,
        external_id=destination.external_id,
    )

    success = store_repository.update_consolidated_destination(name, updated)

    if success:
        return {"status": "success", "message": f"Destination '{name}' updated"}
    else:
        return {"status": "error", "message": f"Destination '{name}' not found"}, 404


@app.post("/reference_occurrences")
@catch_exceptions
async def save_reference_occurrences(request: SaveReferenceOccurrencesRequest):
    references = []
    for occ in request.occurrences:
        segment = Segment(
            text=occ.segment_text or "",
            page_number=occ.page or 0,
            segment_number=0,
            type="Text",
            pdf_name=occ.pdf_name or "",
        )
        references.append(
            Reference(
                type=ReferenceType.REFERENCE,
                text=occ.text,
                destination=occ.destination,
                segment=segment,
                character_start=occ.character_start or 0,
                character_end=occ.character_end or 0,
            )
        )

    store_repository = PostgresReferencesStoreRepository(request.namespace, request.language)
    success = store_repository.save_reference_occurrences(references)

    if success:
        return {"status": "success", "message": f"Saved {len(references)} reference occurrences"}
    else:
        return {"status": "error", "message": "Failed to save reference occurrences"}, 400


@app.post("/negative_samples")
@catch_exceptions
async def save_negative_samples(request: SaveNegativeSamplesRequest):
    segments = [
        Segment(
            text=seg.text,
            page_number=seg.page or 0,
            segment_number=0,
            type="Text",
            pdf_name=seg.pdf_name or "",
        )
        for seg in request.segments
    ]

    store_repository = PostgresReferencesStoreRepository(request.namespace, request.language)
    success = store_repository.save_negative_samples(request.destination, segments)

    if success:
        return {"status": "success", "message": f"Saved {len(segments)} negative samples"}
    else:
        return {"status": "error", "message": "Failed to save negative samples"}, 400


@app.post("/reset_destinations")
@catch_exceptions
async def reset_destinations(namespace: str = Form(...), language: str = Form("en")):
    store_repository = PostgresReferencesStoreRepository(namespace, language)
    success = store_repository.reset_consolidated_destinations()
    if success:
        return {"status": "success", "message": "Consolidated destinations reset successfully"}
    else:
        return {"status": "error", "message": "Failed to reset consolidated destinations"}, 400


@app.post("/generate_detection_scripts")
@catch_exceptions
async def generate_detection_scripts(
    namespace: str = Form(...),
    language: str = Form("en"),
):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "pending",
        "result": None,
        "error": None,
    }

    def _run():
        _tasks[task_id]["status"] = "running"
        try:
            llm_service = OllamaLLMRepository()
            repository = PostgresReferencesStoreRepository(namespace, language)
            use_case = GenerateDestinationDetectionsUseCase(
                llm_service=llm_service,
                repository=repository,
            )
            scripts = use_case.execute()
            _tasks[task_id]["result"] = {
                "scripts_generated": len(scripts),
            }
            _tasks[task_id]["status"] = "completed"
        except Exception as e:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"task_id": task_id}


@app.get("/tasks/{task_id}")
@catch_exceptions
async def get_task_status(task_id: str):
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": task["status"],
        "result": task["result"],
        "error": task["error"],
    }
