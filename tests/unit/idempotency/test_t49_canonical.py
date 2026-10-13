"""Exact semantic distinctions and finite request-hash resource boundaries."""

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
import os
import subprocess
import sys
from uuid import uuid4

import pytest

from app.api.v2.idempotency_canonical import (
    CanonicalRequestError, MAX_CANONICAL_BYTES, MAX_SAFE_INTEGER, canonical_request_hash,
)


def test_hash_matches_fixed_utf8_encoding_and_does_not_mutate():
    request = {"DEMO_name": "合成学生", "items": [True, False, None, 3, -4, "a\nb"]}
    original = json.loads(json.dumps(request))
    expected = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert canonical_request_hash(request) == sha256(expected).hexdigest()
    assert request == original


def test_object_order_ignored_recursively_array_order_preserved():
    one = {"z": [{"b": 1, "a": 2}], "a": 0}
    two = {"a": 0, "z": [{"a": 2, "b": 1}]}
    assert canonical_request_hash(one) == canonical_request_hash(two)
    assert canonical_request_hash([1, 2]) != canonical_request_hash([2, 1])


def test_null_missing_boolean_integer_and_text_are_distinct():
    values = [{}, {"x": None}, {"x": False}, {"x": 0}, {"x": "0"}, {"x": []}]
    assert len({canonical_request_hash(value) for value in values}) == len(values)


def test_unicode_and_whitespace_are_preserved_without_normalization():
    values = [{"x": "é"}, {"x": "e\u0301"}, {"x": "é "}, {"x ": "é"}]
    assert len({canonical_request_hash(value) for value in values}) == len(values)
    assert canonical_request_hash({"x": "😀"}) == sha256('{"x":"😀"}'.encode()).hexdigest()


@pytest.mark.parametrize("value", [1.0, -0.0, float("nan"), float("inf"), Decimal("1"),
                                  uuid4(), date(2026, 10, 3), b"DEMO", (1,), {1}, object()])
def test_non_json_and_float_types_rejected_without_coercion(value):
    with pytest.raises(CanonicalRequestError) as caught:
        canonical_request_hash({"DEMO_input": value})
    assert str(caught.value) == "Request cannot be canonically hashed"


def test_roots_must_be_exact_objects_or_arrays():
    for root in (None, True, 0, "DEMO", 1.5):
        with pytest.raises(CanonicalRequestError):
            canonical_request_hash(root)


def test_subclasses_and_nonstring_object_keys_rejected():
    class DictSubclass(dict):
        pass
    class ListSubclass(list):
        pass
    class StringSubclass(str):
        pass
    class IntSubclass(int):
        pass
    for value in (DictSubclass(), ListSubclass(), {"x": StringSubclass("DEMO")},
                  {"x": IntSubclass(1)}, {StringSubclass("DEMO"): 1}, {1: "DEMO"}):
        with pytest.raises(CanonicalRequestError):
            canonical_request_hash(value)


def test_safe_integer_boundaries_and_large_integer_fail_without_stringification():
    assert canonical_request_hash([MAX_SAFE_INTEGER, -MAX_SAFE_INTEGER])
    for value in (MAX_SAFE_INTEGER + 1, -MAX_SAFE_INTEGER - 1, 10**20_000):
        with pytest.raises(CanonicalRequestError):
            canonical_request_hash([value])


def test_cycles_rejected_but_shared_acyclic_values_have_normal_tree_semantics():
    loop = []
    loop.append(loop)
    indirect = {}
    indirect["child"] = [indirect]
    for value in (loop, indirect):
        with pytest.raises(CanonicalRequestError):
            canonical_request_hash(value)
    shared = [1, 2]
    assert canonical_request_hash([shared, shared]) == canonical_request_hash([[1, 2], [1, 2]])


def test_depth_is_container_depth_and_rejects_before_python_recursion_limit():
    value = 0
    for _ in range(32):
        value = [value]
    assert canonical_request_hash(value)
    with pytest.raises(CanonicalRequestError):
        canonical_request_hash([value])


def test_node_limit_counts_object_keys_and_repeated_shared_values():
    assert canonical_request_hash([None] * 99_999)
    with pytest.raises(CanonicalRequestError):
        canonical_request_hash([None] * 100_000)
    with pytest.raises(CanonicalRequestError):
        canonical_request_hash({str(index): None for index in range(50_000)})
    shared = [None] * 999
    with pytest.raises(CanonicalRequestError):
        canonical_request_hash([shared] * 100)


def test_canonical_byte_limit_exact_boundary_and_escape_expansion():
    accepted = ["x" * (MAX_CANONICAL_BYTES - 4)]
    assert canonical_request_hash(accepted)
    with pytest.raises(CanonicalRequestError):
        canonical_request_hash([accepted[0] + "x"])
    with pytest.raises(CanonicalRequestError):
        canonical_request_hash(["\x00" * 180_000])
    with pytest.raises(CanonicalRequestError):
        canonical_request_hash(["😀" * 270_000])


def test_utf8_surrogate_keys_or_values_rejected_safely():
    for value in ({"x": "\ud800"}, {"\udfff": "DEMO"}):
        with pytest.raises(CanonicalRequestError) as caught:
            canonical_request_hash(value)
        assert "DEMO" not in str(caught.value)


def test_independent_hashing_does_not_load_db_auth_or_model_providers():
    program = '''
import sys
from app.api.v2.idempotency_canonical import canonical_request_hash
assert len(canonical_request_hash({"DEMO":True})) == 64
assert not any(name.startswith(("sqlalchemy", "app.auth", "app.privacy", "app.audit",
                               "app.idempotency", "app.providers", "app.main"))
               for name in sys.modules)
'''
    result = subprocess.run([sys.executable, "-B", "-c", program], capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": "services/api"})
    assert result.returncode == 0, result.stderr
