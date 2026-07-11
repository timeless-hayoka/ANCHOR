from __future__ import annotations

import json
from pathlib import Path

import pytest

from trinity_lead_state_machine import LEAD_STATES, LeadRecord, validate_lead

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "trinity_schemas" / "trinity_lead_state_machine.schema.json"
EXAMPLE_PATH = ROOT / "examples" / "trinity_lead_state_machine.example.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_schema_file_is_valid_json_with_expected_top_level_shape():
    schema = _load_schema()
    assert schema["title"] == "Trinity Lead State Machine"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "state" in schema["properties"]
    assert "events" in schema["properties"]


def test_schema_required_fields_match_lead_record_serialization():
    schema = _load_schema()
    record = LeadRecord(lead_id="lead_x", target="target-x", title="Title x")
    serialized_keys = set(record.to_dict().keys())
    assert set(schema["required"]) == serialized_keys


def test_schema_state_enum_matches_lead_states():
    schema = _load_schema()
    assert set(schema["$defs"]["state"]["enum"]) == set(LEAD_STATES)


def test_schema_event_required_fields_match_event_serialization():
    schema = _load_schema()
    event_schema = schema["$defs"]["event"]
    assert set(event_schema["required"]) == {
        "event_id",
        "lead_id",
        "from_state",
        "to_state",
        "actor",
        "reason",
        "evidence_refs",
        "created_at",
    }


def test_schema_event_from_state_allows_null():
    schema = _load_schema()
    from_state_schema = schema["$defs"]["event"]["properties"]["from_state"]
    types = [option.get("type") for option in from_state_schema["anyOf"]]
    assert "null" in types


def test_example_file_matches_expected_lead_id_and_state():
    example = _load_example()
    assert example["lead_id"] == "lead_001"
    assert example["state"] == "report_ready"
    assert example["schema_version"] == "1.0"


def test_example_file_contains_only_schema_declared_properties():
    schema = _load_schema()
    example = _load_example()
    allowed_keys = set(schema["properties"].keys())
    assert set(example.keys()) <= allowed_keys


def test_example_file_events_are_internally_consistent_chain():
    example = _load_example()
    events = example["events"]
    assert events[0]["from_state"] is None
    for previous, current in zip(events, events[1:]):
        assert previous["to_state"] == current["from_state"]
    assert events[-1]["to_state"] == example["state"]


def test_example_file_validates_against_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load_schema()
    example = _load_example()
    jsonschema.validate(instance=example, schema=schema)


def test_example_file_missing_required_field_fails_json_schema_validation():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load_schema()
    example = _load_example()
    del example["impact_boundary"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=example, schema=schema)


def test_example_file_is_accepted_by_lead_record_and_validate_lead():
    example = _load_example()
    record = LeadRecord.from_dict(example)
    assert validate_lead(record) == []