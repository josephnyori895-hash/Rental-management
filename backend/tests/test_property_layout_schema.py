from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.properties.schemas import PropertyLayoutConfig


def test_property_layout_config_accepts_multiple_faces_and_unit_placements():
    section_id = "east-wing"
    level_id = "level-1"
    face_id = "rear"
    unit_id = uuid4()
    config = PropertyLayoutConfig.model_validate({
        "version": 1,
        "building_type": "mixed_use",
        "sections": [{
            "id": section_id,
            "name": "East Wing",
            "kind": "wing",
            "levels": [{"id": level_id, "label": "First floor", "order": 1}],
            "faces": [
                {"id": face_id, "label": "Rear entrance", "orientation": "back"},
                {"id": "side", "label": "Side", "orientation": "right"},
            ],
        }],
        "placements": [{
            "unit_id": str(unit_id),
            "section_id": section_id,
            "level_id": level_id,
            "face_id": face_id,
            "position": 3,
        }],
    })

    assert config.placements[0].unit_id == unit_id
    assert config.sections[0].kind == "wing"


def test_property_layout_config_rejects_placement_to_unknown_face():
    with pytest.raises(ValidationError, match="Unknown face"):
        PropertyLayoutConfig.model_validate({
            "version": 1,
            "sections": [{
                "id": "main",
                "name": "Main block",
                "levels": [{"id": "ground", "label": "Ground floor", "order": 0}],
                "faces": [{"id": "front", "label": "Front", "orientation": "front"}],
            }],
            "placements": [{
                "unit_id": str(uuid4()),
                "section_id": "main",
                "level_id": "ground",
                "face_id": "rear",
                "position": 0,
            }],
        })


def test_property_layout_config_rejects_duplicate_unit_placements():
    unit_id = str(uuid4())
    with pytest.raises(ValidationError, match="only one layout placement"):
        PropertyLayoutConfig.model_validate({
            "version": 1,
            "sections": [{
                "id": "main",
                "name": "Main block",
                "levels": [{"id": "ground", "label": "Ground floor", "order": 0}],
                "faces": [{"id": "front", "label": "Front", "orientation": "front"}],
            }],
            "placements": [
                {"unit_id": unit_id, "section_id": "main", "level_id": "ground", "face_id": "front", "position": 0},
                {"unit_id": unit_id, "section_id": "main", "level_id": "ground", "face_id": "front", "position": 1},
            ],
        })
