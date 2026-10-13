"""Opt-in QA may add only the two frozen anonymous operations."""

from copy import deepcopy
from pathlib import Path
import re

import pytest

from scripts import generate_contracts as generator

FLAGS = {"allow_public_catalog": True, "allow_qa": True}
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def document():
    return generator.load_openapi("qa")


def test_qa_inherits_exact_public_parent_and_has_typed_lf_artifacts(document):
    parent = generator.load_openapi("public_catalog")
    assert all(document["paths"][path] == value for path, value in parent["paths"].items())
    assert {(path, method) for path, item in document["paths"].items() for method in item} == generator.PUBLIC_PARENT_OPERATIONS | generator.QA_OPERATIONS
    artifacts = generator.generate_artifacts(document, **FLAGS)
    assert not generator.write_or_check(artifacts, ROOT / "packages/contracts/v2/qa", check=True)
    assert all("\r" not in value for value in artifacts.values())
    assert not re.search(r"\b(?:any|unknown)\s*(?:\[\]|;)", artifacts["generated.ts"])
    for operation in generator.QA_OPERATIONS:
        assert "security" not in document["paths"][operation[0]][operation[1]]


def test_input_reuses_closed_t38_scope_without_client_dataset_or_prompt(document):
    operation = document["paths"]["/qa/answers"]["post"]
    assert operation["requestBody"] == {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RetrievalRequest"}}}}
    model = document["components"]["schemas"]["RetrievalRequest"]
    assert model["additionalProperties"] is False and set(model["properties"]) == {"release_id", "offering_id", "offering_version", "entry_year", "scope", "intent", "keywords"}
    assert len(document["components"]["schemas"]["RequestScope"]["properties"]) == 20
    assert "dataset_id" not in document["components"]["schemas"]["RequestScope"]["properties"]
    answer = document["components"]["schemas"]["QAAnswerData"]
    assert not {"atoms", "claims", "question", "text"} & answer["properties"].keys()
    assert set(answer["required"]) == set(answer["properties"])


@pytest.mark.parametrize("mutation", ["missing", "extra", "method", "missingbody", "query", "header", "no_public_flag"])
def test_qa_generator_rejects_unregistered_operations_and_transport_expansion(document, mutation):
    value = deepcopy(document)
    operation = value["paths"]["/qa/answers"]["post"]
    if mutation == "missing":
        del value["paths"]["/qa/context"]
    elif mutation == "extra":
        value["paths"]["/qa/chat"] = {"post": deepcopy(operation)}
    elif mutation == "method":
        value["paths"]["/qa/answers"]["put"] = value["paths"]["/qa/answers"].pop("post")
    elif mutation == "missingbody":
        del operation["requestBody"]
    elif mutation in {"query", "header"}:
        operation["parameters"] = [{"name": "owner", "in": mutation, "schema": {"type": "string"}}]
    with pytest.raises(generator.UnsupportedSchema):
        generator.generate_artifacts(value, **(FLAGS if mutation != "no_public_flag" else {"allow_qa": True}))
