from typing import Optional
from cross_references_predictor.adapters.geolocation_repository import GeolocationRepository


class GetGeolocationUseCase:
    def __init__(self):
        self.geolocation_service = GeolocationRepository()

    def get_coordinates(self, location_name: str) -> Optional[tuple[float, float]]:
        return self.geolocation_service.get_coordinates(location_name)
