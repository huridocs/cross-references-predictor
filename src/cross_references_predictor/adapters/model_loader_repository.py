from pathlib import Path

from cross_references_predictor.configuration import MODELS_PATH, PROCESS_REFERENCE_TYPES
from cross_references_predictor.ports.model_loader import ModelLoader


class ConcreteModelLoader(ModelLoader):
    FLAIR = "flair"
    GLINER = "gliner"

    _MODEL_TYPES = {
        FLAIR: {"PERSON", "ORGANIZATION", "LOCATION", "LAW"},
        GLINER: {"DATE"},
    }

    def __init__(self):
        self._models: dict[str, object] = {}
        self._enabled_types: set[str] = set(PROCESS_REFERENCE_TYPES)

    def has_model(self, name: str) -> bool:
        if name not in self._MODEL_TYPES:
            return False
        model_types = self._MODEL_TYPES[name]
        return not model_types.isdisjoint(self._enabled_types)

    def get_model(self, name: str):
        if not self.has_model(name):
            return None
        if name not in self._models:
            self._load_model(name)
        return self._models.get(name)

    def is_loaded(self, name: str) -> bool:
        return name in self._models

    def unload_model(self, name: str):
        self._models.pop(name, None)

    def _load_model(self, name: str):
        if name == self.FLAIR:
            from flair.nn import Classifier

            self._models[self.FLAIR] = Classifier.load(Path(MODELS_PATH, "flair", "pytorch_model.bin"))
        elif name == self.GLINER:
            from gliner import GLiNER

            gliner_path = Path(MODELS_PATH, "gliner")
            self._models[self.GLINER] = GLiNER.from_pretrained(gliner_path) if gliner_path.exists() else None
