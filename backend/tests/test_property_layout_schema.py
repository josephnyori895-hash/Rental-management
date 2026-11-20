from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.properties.schemas import PropertyCreate, PropertyLayoutConfig


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



def test_property_layout_config_accepts_internal_rooms_and_shared_spaces():
    unit_id = uuid4()
    config = PropertyLayoutConfig.model_validate({
        "version": 1,
        "building_type": "house",
        "sections": [{
            "id": "main-house",
            "name": "Main house",
            "levels": [{
                "id": "ground",
                "label": "Ground floor",
                "order": 0,
                "spaces": [
                    {"id": "bedroom-1", "label": "Main bedroom", "kind": "bedroom", "rentable_unit_id": str(unit_id)},
                    {"id": "kitchen", "label": "Kitchen", "kind": "kitchen", "rentable_unit_id": str(unit_id)},
                    {"id": "shared-garden", "label": "Shared garden", "kind": "shared"},
                ],
            }],
            "faces": [],
        }],
        "placements": [],
    })

    spaces = config.sections[0].levels[0].spaces
    assert len(spaces) == 3
    assert spaces[0].rentable_unit_id == unit_id
    assert spaces[2].rentable_unit_id is None


def test_property_layout_config_rejects_duplicate_internal_space_ids():
    with pytest.raises(ValidationError, match="Internal space IDs must be unique"):
        PropertyLayoutConfig.model_validate({
            "version": 1,
            "sections": [{
                "id": "main",
                "name": "Main",
                "levels": [
                    {"id": "ground", "label": "Ground", "order": 0,
                     "spaces": [{"id": "room-1", "label": "Bedroom", "kind": "bedroom"}]},
                    {"id": "upper", "label": "Upper", "order": 1,
                     "spaces": [{"id": "room-1", "label": "Kitchen", "kind": "kitchen"}]},
                ],
                "faces": [],
            }],
            "placements": [],
        })



@pytest.mark.parametrize("property_type", ["mixed_use", "compound"])
def test_property_create_accepts_flexible_property_types(property_type):
    payload = PropertyCreate(name="Flexible site", property_type=property_type)
    assert payload.property_type == property_type


def test_property_layout_config_supports_many_sections_and_levels():
    sections = [
        {
            "id": f"block-{block_index}",
            "name": f"Block {block_index}",
            "levels": [
                {"id": f"level-{level_index}", "label": f"Level {level_index}", "order": level_index}
                for level_index in range(40)
            ],
            "faces": [],
        }
        for block_index in range(40)
    ]
    config = PropertyLayoutConfig.model_validate({"building_type": "compound", "sections": sections})
    assert len(config.sections) == 40
    assert sum(len(section.levels) for section in config.sections) == 1600



def test_property_layout_config_keeps_legacy_v1_geometry_optional():
    config = PropertyLayoutConfig.model_validate({
        "version": 1,
        "sections": [{
            "id": "legacy", "name": "Legacy block",
            "levels": [{"id": "ground", "label": "Ground", "order": 0,
                        "spaces": [{"id": "room", "label": "Room"}]}],
            "faces": [{"id": "front", "label": "Front", "orientation": "front"}],
        }],
        "placements": [{
            "unit_id": str(uuid4()), "section_id": "legacy", "level_id": "ground",
            "face_id": "front", "position": 0,
        }],
    })
    assert config.placements[0].x is None
    assert config.sections[0].levels[0].spaces[0].width is None


@pytest.mark.parametrize("geometry", [
    {"x": -1}, {"y": 1001}, {"width": 9}, {"height": 1001}, {"rotation": 181},
])
def test_property_layout_config_rejects_out_of_range_unit_geometry(geometry):
    with pytest.raises(ValidationError):
        PropertyLayoutConfig.model_validate({
            "version": 1,
            "sections": [{
                "id": "main", "name": "Main",
                "levels": [{"id": "ground", "label": "Ground", "order": 0}],
                "faces": [{"id": "front", "label": "Front", "orientation": "front"}],
            }],
            "placements": [{
                "unit_id": str(uuid4()), "section_id": "main", "level_id": "ground",
                "face_id": "front", "position": 0, **geometry,
            }],
        })



def test_property_layout_config_rejects_geometry_outside_schematic_bounds():
    with pytest.raises(ValidationError, match="extends beyond the layout width"):
        PropertyLayoutConfig.model_validate({
            "version": 1,
            "sections": [{
                "id": "main", "name": "Main",
                "levels": [{"id": "ground", "label": "Ground", "order": 0}],
                "faces": [{"id": "front", "label": "Front", "orientation": "front"}],
            }],
            "placements": [{
                "unit_id": str(uuid4()), "section_id": "main", "level_id": "ground",
                "face_id": "front", "position": 0, "x": 900, "width": 200,
            }],
        })


def test_property_layout_config_rejects_internal_space_outside_schematic_bounds():
    with pytest.raises(ValidationError, match="Internal space.*extends beyond"):
        PropertyLayoutConfig.model_validate({
            "version": 1,
            "sections": [{
                "id": "main", "name": "Main",
                "levels": [{"id": "ground", "label": "Ground", "order": 0,
                            "spaces": [{"id": "bedroom", "label": "Bedroom", "x": 900, "width": 200}]}],
                "faces": [],
            }],
        })
