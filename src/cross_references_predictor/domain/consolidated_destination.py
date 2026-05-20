from pydantic import BaseModel

from cross_references_predictor.domain.reference import Reference
from cross_references_predictor.domain.reference_destination import ReferenceDestination
from cross_references_predictor.domain.reference_type import ReferenceType


class ConsolidatedDestination(BaseModel):
    name: str
    type: ReferenceType
    alternative_names: list[str] = []
    external_id: str | None = None

    def add_alternative_name(self, name: str):
        if name != self.name and name not in self.alternative_names:
            self.alternative_names.append(name)

    def update_name(self, new_name: str):
        if len(new_name) > len(self.name):
            old_name = self.name
            self.name = new_name
            self.add_alternative_name(old_name)
        elif new_name != self.name:
            self.add_alternative_name(new_name)

    def belongs_to_reference(self, reference: Reference) -> bool:
        temp = ReferenceDestination(type=self.type, name=self.name)
        for name in [self.name] + self.alternative_names:
            temp.references.append(Reference(type=self.type, text=name, normalized_text=Reference.normalize_text(name)))
        return temp.belongs_to_destination(reference)

    def matches(self, other: "ConsolidatedDestination") -> bool:
        temp = ReferenceDestination(type=self.type, name=self.name)
        for name in [self.name] + self.alternative_names:
            temp.references.append(Reference(type=self.type, text=name, normalized_text=Reference.normalize_text(name)))
        for name in [other.name] + other.alternative_names:
            ref = Reference(type=other.type, text=name, normalized_text=Reference.normalize_text(name))
            if temp.belongs_to_destination(ref):
                return True
        return False

    def merge_with(self, other: "ConsolidatedDestination"):
        if other.name != self.name:
            old_name = self.name
            self.name = other.name
            self.add_alternative_name(old_name)

        for alt in other.alternative_names:
            self.add_alternative_name(alt)
