"""
RENTAL OS — Property Schemas
"""

from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PropertyCreate(BaseModel):
    name: str
    address: str | None = None
    property_type: Literal[
        "hostel", "apartment", "building", "house", "commercial"
    ] = "hostel"
    description: str | None = None


class UnitCreate(BaseModel):
    unit_number: str
    unit_type: Literal[
        "room", "bedspace", "studio", "1_bedroom", "2_bedroom", "shop"
    ] = "room"
    monthly_rent: float
    deposit_amount: float = 0
    max_occupants: int = 1
    description: str | None = None


class PropertyOut(BaseModel):
    id: UUID
    name: str
    address: Optional[str] = None
    property_type: str
    description: Optional[str] = None
    manager_id: UUID | None = None
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
    rent_light: str = "vacant"  # vacant|unpaid|partial|paid|overpaid

    model_config = {"from_attributes": True}


class UnitOut(BaseModel):
    id: UUID
    unit_number: str
    unit_type: str
    status: str
    monthly_rent: float
    max_occupants: int

    model_config = {"from_attributes": True}


class LayoutSpace(BaseModel):
    """A non-rentable internal room or shared space inside a property level.

    rentable_unit_id links internal rooms to their containing rentable unit.
    A null value represents a shared/common area and never creates a lease.
    """
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    kind: Literal[
        "bedroom", "kitchen", "bathroom", "living_room", "dining_room",
        "balcony", "storage", "corridor", "office", "shop", "shared", "other",
    ] = "other"
    rentable_unit_id: UUID | None = None
    order: int = Field(default=0, ge=0, le=10000)


class LayoutLevel(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=100)
    order: int = Field(ge=0, le=100)
    spaces: list[LayoutSpace] = Field(default_factory=list, max_length=200)


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
        space_ids: list[str] = []
        for section in self.sections:
            level_ids = [level.id for level in section.levels]
            face_ids = [face.id for face in section.faces]
            if len(level_ids) != len(set(level_ids)) or len(face_ids) != len(set(face_ids)):
                raise ValueError("Level and face IDs must be unique within a section")
            for level in section.levels:
                space_ids.extend(space.id for space in level.spaces)
        if len(space_ids) != len(set(space_ids)):
            raise ValueError("Internal space IDs must be unique within a property")
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


class PropertyLayoutOut(BaseModel):
    property_id: UUID
    layout_config: PropertyLayoutConfig | None = None
