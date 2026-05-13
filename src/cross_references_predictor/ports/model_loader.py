from abc import ABC, abstractmethod


class ModelLoader(ABC):
    @abstractmethod
    def has_model(self, name: str) -> bool:
        pass

    @abstractmethod
    def get_model(self, name: str):
        pass

    @abstractmethod
    def is_loaded(self, name: str) -> bool:
        pass

    @abstractmethod
    def unload_model(self, name: str):
        pass
