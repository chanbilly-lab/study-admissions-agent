"""Prove the contract checker detects semantic drift, including absent/null fields."""

from copy import deepcopy

import pytest

from scripts.verify_contract import Contract, ContractMismatch, assert_schema_matches


DECLARATIONS = """
export type Status = 'eligible' | 'ineligible' | 'conditional' | 'unknown';
export interface Score { value: number; scale: number; kind: 'achieved' | 'predicted' }
export interface Profile { scores: Record<string, Score>; province: string | null; status: Status }
export interface Meta { demo_mode: true; profile_version: number | null }
export interface Envelope<T> { data: T; meta: Meta }
"""


@pytest.fixture
def contract():
    return Contract(DECLARATIONS)


@pytest.fixture
def profile_schema():
    return {
        "type": "object",
        "required": ["scores", "province", "status"],
        "properties": {
            "scores": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["value", "scale", "kind"],
                    "properties": {
                        "value": {"type": "number"},
                        "scale": {"type": "integer", "minimum": 1},
                        "kind": {"type": "string", "enum": ["achieved", "predicted"]},
                    },
                },
            },
            "province": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "status": {"type": "string", "enum": ["eligible", "ineligible", "conditional", "unknown"]},
        },
    }


def test_integer_constraints_and_reordered_fields_are_wire_compatible(contract, profile_schema):
    assert_schema_matches(contract, "Profile", profile_schema, {})
    profile_schema["required"].reverse()
    profile_schema["properties"]["status"]["enum"].reverse()
    assert_schema_matches(contract, "Profile", profile_schema, {})


@pytest.mark.parametrize("mutation", ["optional", "non_nullable", "string_score", "missing_unknown", "extra_field"])
def test_contract_drift_is_rejected(contract, profile_schema, mutation):
    changed = deepcopy(profile_schema)
    if mutation == "optional":
        changed["required"].remove("province")
    elif mutation == "non_nullable":
        changed["properties"]["province"] = {"type": "string"}
    elif mutation == "string_score":
        changed["properties"]["scores"]["additionalProperties"]["properties"]["value"] = {"type": "string"}
    elif mutation == "missing_unknown":
        changed["properties"]["status"]["enum"].remove("unknown")
    elif mutation == "extra_field":
        changed["properties"]["admission_probability"] = {"type": "number"}
    with pytest.raises(ContractMismatch):
        assert_schema_matches(contract, "Profile", changed, {})


def test_generic_envelope_checks_actual_serialization(contract):
    payload = {
        "data": [{"scores": {"english": {"value": 120, "scale": 150, "kind": "achieved"}}, "province": None, "status": "unknown"}],
        "meta": {"demo_mode": True, "profile_version": None},
    }
    contract.assert_payload("Envelope<Profile[]>", payload)
    payload["data"][0]["scores"]["english"]["value"] = True
    with pytest.raises(ContractMismatch, match="expected number"):
        contract.assert_payload("Envelope<Profile[]>", payload)


def test_nullable_field_is_required_in_actual_json(contract):
    with pytest.raises(ContractMismatch, match="missing fields"):
        contract.assert_payload("Meta", {"demo_mode": True})


def test_demo_mode_cannot_be_silently_false(contract):
    with pytest.raises(ContractMismatch, match="literal True"):
        contract.assert_payload("Meta", {"demo_mode": False, "profile_version": None})


def test_inherited_fields_and_optional_fields_are_distinct():
    contract = Contract("export interface Base { id: string } export interface Child extends Base { label?: string; pending: string | null }")
    contract.assert_payload("Child", {"id": "DEMO_child", "pending": None})
    with pytest.raises(ContractMismatch, match="missing fields"):
        contract.assert_payload("Child", {"pending": None})


def test_unsupported_types_fail_instead_of_reducing_contract_coverage():
    with pytest.raises(ValueError, match="Unsupported TypeScript syntax"):
        Contract("export type Unverified = { [K in keyof Profile]: Profile[K] };")
