"""
Rental OS — Property Schemas
"""

from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PropertyOut(BaseModel):
    id: UUID
    name: str
    address: Optional[str] = None
    property_type: str
    description: Optional[str] = None
    layout_config: dict | None = None

    model_config = {"from_attributes": True}


class UnitRoomOut(BaseModel):
    id: str
    unit_number: str
    unit_type: str
    status: str
    monthly_rent: float
    max_occupants: int
    tenant_name: str | None = None
    tenant_phone: str | None = None
    tenant_id: str | None = None
    lease_start: str | None = None
    lease_end: str | None = None
    duration_months: int | None = None
    condition_notes: str | None = None
    invoice_status: str | None = None
    invoice_balance: float = 0.0
    total_paid: float = 0.0
    rent_light: str = "vacant"

    model_config = {"from_attributes": True}


class UnitOut(BaseModel):
    id: UUID
    unit_number: str
    unit_type: str
    status: str
    monthly_rent: float
    max_occupants: int

    model_config = {"from_attributes": True}


class LayoutLevel(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    order: int = Field(ge=0, le=100)


class LayoutFace(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    orientation: Literal["front", "back", "left", "right", "interior"]


class LayoutSection(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["block", "wing", "entrance", "standalone"] = "block"
    levels: list[LayoutLevel] = Field(default_factory=list, max_length=30)
    faces: list[LayoutFace] = Field(default_factory=list, max_length=10)


class UnitPlacement(BaseModel):
    unit_id: UUID
    section_id: str = Field(min_length=1, max_length=80)
    level_id: str = Field(min_length=1, max_length=80)
    face_id: str = Field(min_length=1, max_length=80)
    position: int = Field(ge=0, le=10000)


class PropertyLayoutConfig(BaseModel):
    version: Literal[1] = 1
    building_type: Literal["hostel", "apartment", "building", "house", "commercial", "mixed_use", "compound"] = "building"
    sections: list[LayoutSection] = Field(default_factory=list, max_length=30)
    placements: list[UnitPlacement] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def validate_references(self):
        section_ids = [section.id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("Section IDs must be unique")
        section_map = {section.id: section for section in self.sections}
        placement_ids = [placement.unit_id for placement in self.placements]
        if len(placement_ids) != len(set(placement_ids)):
            raise ValueError("Each unit may have only one layout placement")
        for section in self.sections:
            level_ids = [level.id for level in section.levels]
            face_ids = [face.id for face in section.faces]
            if len(level_ids) != len(set(level_ids)) or len(face_ids) != len(set(face_ids)):
                raise ValueError("Level and face IDs must be unique within a section")
        for placement in self.placements:
            section = section_map.get(placement.section_id)
            if section is None:
                raise ValueError(f"Unknown section: {placement.section_id}")
            if placement.level_id not in {level.id for level in section.levels}:
                raise ValueError(f"Unknown level {placement.level_id} in section {placement.section_id}")
            if placement.face_id not in {face.id for face in section.faces}:
                raise ValueError(f"Unknown face {placement.face_id} in section {placement.section_id}")
        return self


class PropertyLayoutUpdate(BaseModel):
    layout_config: PropertyLayoutConfig
