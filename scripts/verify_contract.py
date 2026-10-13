"""Offline semantic checks for the small, deliberately explicit M0 wire contract.

This is a parser for the supported TypeScript declaration subset, not a string
search. Unsupported syntax fails loudly so expanding the contract requires an
explicit verifier update. OpenAPI constraints such as minimum/format may be
stricter than TypeScript; required fields, nullability, literal values, and
wire types must agree. Integer schemas are compatible with TS's number type.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "packages" / "contracts" / "index.ts"


class ContractMismatch(AssertionError):
    """The declarations, published schema, or actual JSON disagree."""


@dataclass(frozen=True)
class TypeExpression:
    kind: str
    value: Any = None
    arguments: tuple["TypeExpression", ...] = ()


@dataclass(frozen=True)
class Interface:
    parameters: tuple[str, ...]
    bases: tuple[TypeExpression, ...]
    fields: dict[str, TypeExpression]
    optional: frozenset[str]


TOKEN = re.compile(
    r"\s+|//[^\n]*|/\*[\s\S]*?\*/|'(?:\\.|[^'\\])*'|"
    r'"(?:\\.|[^"\\])*"|[A-Za-z_$][\w$]*|[{}<>\[\]():;,|?=]'
)


class Contract:
    def __init__(self, source: str):
        self.tokens: list[str] = []
        position = 0
        for match in TOKEN.finditer(source):
            if match.start() != position:
                raise ValueError(f"Unsupported TypeScript syntax at offset {position}")
            token = match.group()
            position = match.end()
            if not token.isspace() and not token.startswith(("//", "/*")):
                self.tokens.append(token)
        if position != len(source):
            raise ValueError(f"Unsupported TypeScript syntax at offset {position}")
        self.position = 0
        self.interfaces: dict[str, Interface] = {}
        self.aliases: dict[str, TypeExpression] = {}
        while self.position < len(self.tokens):
            self.expect("export")
            declaration = self.take()
            name = self.take()
            if declaration == "type":
                self.expect("=")
                self.aliases[name] = self.expression()
                self.accept(";")
            elif declaration == "interface":
                parameters: list[str] = []
                if self.accept("<"):
                    parameters.append(self.take())
                    while self.accept(","):
                        parameters.append(self.take())
                    self.expect(">")
                bases: list[TypeExpression] = []
                if self.accept("extends"):
                    bases.append(self.primary())
                    while self.accept(","):
                        bases.append(self.primary())
                self.expect("{")
                fields: dict[str, TypeExpression] = {}
                optional: set[str] = set()
                while not self.accept("}"):
                    field = self.take()
                    if field in fields:
                        raise ValueError(f"Duplicate {name}.{field}")
                    if self.accept("?"):
                        optional.add(field)
                    self.expect(":")
                    fields[field] = self.expression()
                    if not self.accept(";"):
                        self.accept(",")
                self.accept(";")
                self.interfaces[name] = Interface(
                    tuple(parameters), tuple(bases), fields, frozenset(optional)
                )
            else:
                raise ValueError(f"Unsupported TypeScript syntax: declaration {declaration!r}")

    def take(self) -> str:
        if self.position >= len(self.tokens):
            raise ValueError("Unsupported TypeScript syntax: unexpected end of declaration")
        result = self.tokens[self.position]
        self.position += 1
        return result

    def accept(self, token: str) -> bool:
        if self.position < len(self.tokens) and self.tokens[self.position] == token:
            self.position += 1
            return True
        return False

    def expect(self, token: str) -> None:
        actual = self.take()
        if actual != token:
            raise ValueError(f"Unsupported TypeScript syntax: expected {token!r}, got {actual!r}")

    def primary(self) -> TypeExpression:
        token = self.take()
        if token[0] in "'\"":
            # M0 literals contain no escape sequences; reject them explicitly.
            if "\\" in token:
                raise ValueError("Unsupported TypeScript syntax: escaped literal declarations")
            result = TypeExpression("literal", token[1:-1])
        elif token in {"true", "false"}:
            result = TypeExpression("literal", token == "true")
        elif token in {"string", "number", "boolean", "null"}:
            result = TypeExpression(token)
        else:
            arguments: list[TypeExpression] = []
            if self.accept("<"):
                arguments.append(self.expression())
                while self.accept(","):
                    arguments.append(self.expression())
                self.expect(">")
            result = TypeExpression("reference", token, tuple(arguments))
        while self.accept("["):
            self.expect("]")
            result = TypeExpression("array", arguments=(result,))
        return result

    def expression(self) -> TypeExpression:
        branches = [self.primary()]
        while self.accept("|"):
            branches.append(self.primary())
        if len(branches) == 1:
            return branches[0]
        return TypeExpression("union", arguments=tuple(branches))

    def parse_type(self, declaration: str) -> TypeExpression:
        parser = Contract(f"export type Value = {declaration};")
        return parser.aliases["Value"]

    def fields(
        self, expression: TypeExpression, bindings: dict[str, TypeExpression]
    ) -> tuple[dict[str, tuple[TypeExpression, dict[str, TypeExpression]]], set[str]]:
        interface = self.interfaces[expression.value]
        if len(expression.arguments) != len(interface.parameters):
            raise ContractMismatch(f"Missing generic arguments for {expression.value}")
        local = dict(bindings)
        local.update(zip(interface.parameters, expression.arguments))
        fields: dict[str, tuple[TypeExpression, dict[str, TypeExpression]]] = {}
        required: set[str] = set()
        for base in interface.bases:
            inherited, inherited_required = self.fields(base, local)
            fields.update(inherited)
            required.update(inherited_required)
        fields.update({name: (value, local) for name, value in interface.fields.items()})
        required.update(set(interface.fields) - set(interface.optional))
        return fields, required

    def signature(
        self, expression: TypeExpression, bindings: dict[str, TypeExpression] | None = None
    ) -> tuple:
        bindings = bindings or {}
        kind = expression.kind
        if kind == "literal":
            return ("literal", type(expression.value).__name__, expression.value)
        if kind == "array":
            return ("array", self.signature(expression.arguments[0], bindings))
        if kind == "union":
            return union(self.signature(item, bindings) for item in expression.arguments)
        if kind != "reference":
            return (kind,)
        name = expression.value
        if name in bindings:
            return self.signature(bindings[name], bindings)
        if name in self.aliases:
            return self.signature(self.aliases[name], bindings)
        if name == "Record":
            if len(expression.arguments) != 2 or expression.arguments[0].kind != "string":
                raise ValueError("Unsupported TypeScript syntax: only Record<string, T> is supported")
            return ("record", self.signature(expression.arguments[1], bindings))
        if name not in self.interfaces:
            raise ValueError(f"Unsupported TypeScript syntax: unknown type {name}")
        fields, required = self.fields(expression, bindings)
        return (
            "object",
            tuple(sorted((key, self.signature(value, context)) for key, (value, context) in fields.items())),
            tuple(sorted(required)),
        )

    def assert_payload(self, declaration: str, payload: Any) -> None:
        validate_value(self.signature(self.parse_type(declaration)), payload, declaration)


def union(branches) -> tuple:
    flattened: set[tuple] = set()
    for branch in branches:
        if branch[0] == "union":
            flattened.update(branch[1])
        else:
            flattened.add(branch)
    if len(flattened) == 1:
        return next(iter(flattened))
    return ("union", tuple(sorted(flattened, key=repr)))


def resolve_schema(schema: dict, openapi: dict) -> dict:
    if "$ref" in schema:
        reference = schema["$ref"]
        if not reference.startswith("#/components/schemas/"):
            raise ContractMismatch(f"Unsupported OpenAPI reference {reference}")
        referenced = openapi["components"]["schemas"][reference.rsplit("/", 1)[-1]]
        return resolve_schema({**referenced, **{k: v for k, v in schema.items() if k != "$ref"}}, openapi)
    if "allOf" in schema:
        combined: dict = {}
        for branch in schema["allOf"]:
            branch = resolve_schema(branch, openapi)
            combined["properties"] = {**combined.get("properties", {}), **branch.get("properties", {})}
            combined["required"] = sorted(set(combined.get("required", [])) | set(branch.get("required", [])))
            combined.update({k: v for k, v in branch.items() if k not in {"properties", "required"}})
        combined.update({k: v for k, v in schema.items() if k != "allOf"})
        return combined
    return schema


def schema_signature(schema: dict, openapi: dict) -> tuple:
    schema = resolve_schema(schema, openapi)
    if "anyOf" in schema or "oneOf" in schema:
        result = union(schema_signature(branch, openapi) for branch in schema.get("anyOf", schema.get("oneOf")))
    elif "const" in schema:
        value = schema["const"]
        result = ("literal", type(value).__name__, value)
    elif "enum" in schema:
        result = union(("literal", type(value).__name__, value) for value in schema["enum"])
    elif isinstance(schema.get("type"), list):
        result = union(schema_signature({**schema, "type": kind}, openapi) for kind in schema["type"])
    elif schema.get("type") == "object" or "properties" in schema:
        if "properties" in schema:
            result = (
                "object",
                tuple(sorted((key, schema_signature(value, openapi)) for key, value in schema["properties"].items())),
                tuple(sorted(schema.get("required", []))),
            )
        elif isinstance(schema.get("additionalProperties"), dict):
            result = ("record", schema_signature(schema["additionalProperties"], openapi))
        else:
            raise ContractMismatch(f"Untyped JSON object in OpenAPI: {schema}")
    elif schema.get("type") == "array":
        result = ("array", schema_signature(schema["items"], openapi))
    elif schema.get("type") in {"string", "number", "integer", "boolean", "null"}:
        result = ("number" if schema["type"] == "integer" else schema["type"],)
    else:
        raise ContractMismatch(f"Unsupported or unconstrained OpenAPI schema: {schema}")
    return union((result, ("null",))) if schema.get("nullable") else result


def validate_value(signature: tuple, value: Any, path: str) -> None:
    kind = signature[0]
    if kind == "union":
        for branch in signature[1]:
            try:
                validate_value(branch, value, path)
                return
            except ContractMismatch:
                pass
        raise ContractMismatch(f"{path}: {value!r} matches no declared union member")
    if kind == "literal":
        if type(value).__name__ != signature[1] or value != signature[2]:
            raise ContractMismatch(f"{path}: expected literal {signature[2]!r}, got {value!r}")
    elif kind == "object":
        if not isinstance(value, dict):
            raise ContractMismatch(f"{path}: expected an object")
        fields = dict(signature[1])
        missing = set(signature[2]) - set(value)
        extra = set(value) - set(fields)
        if missing or extra:
            raise ContractMismatch(f"{path}: missing fields {sorted(missing)}, unexpected fields {sorted(extra)}")
        for field, item in value.items():
            validate_value(fields[field], item, f"{path}.{field}")
    elif kind == "record":
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise ContractMismatch(f"{path}: expected a string-keyed record")
        for key, item in value.items():
            validate_value(signature[1], item, f"{path}[{key!r}]")
    elif kind == "array":
        if not isinstance(value, list):
            raise ContractMismatch(f"{path}: expected an array")
        for index, item in enumerate(value):
            validate_value(signature[1], item, f"{path}[{index}]")
    else:
        valid = {
            "string": isinstance(value, str),
            "number": type(value) in {int, float},
            "boolean": type(value) is bool,
            "null": value is None,
        }.get(kind, False)
        if not valid:
            raise ContractMismatch(f"{path}: expected {kind}, got {type(value).__name__}")


def load_contract(path: Path = CONTRACT_PATH) -> Contract:
    return Contract(path.read_text(encoding="utf-8"))


def assert_schema_matches(contract: Contract, declaration: str, schema: dict, openapi: dict) -> None:
    expected = contract.signature(contract.parse_type(declaration))
    actual = schema_signature(schema, openapi)
    if expected != actual:
        raise ContractMismatch(
            f"{declaration}: TypeScript/OpenAPI semantic mismatch\n"
            f"TypeScript: {expected!r}\nOpenAPI: {actual!r}"
        )


def assert_openapi_contract(contract: Contract, openapi: dict) -> None:
    schemas = openapi.get("components", {}).get("schemas", {})
    # Keep the mapping explicit: a renamed Python class does not rename the wire contract.
    mapping = {
        "Score": "Score", "ProfileInput": "ProfileInput", "Profile": "Profile",
        "Deferral": "Deferral", "Rule": "Rule", "Evidence": "Evidence",
        "Offering": "Offering", "RuleResult": "RuleResult", "Eligibility": "Eligibility",
        "DraftTask": "DraftTask", "PlanDraft": "PlanDraft", "Meta": "Meta",
        "RuntimeConfig": "RuntimeConfig",
    }
    failures: list[str] = []
    for declaration, schema_name in mapping.items():
        if schema_name not in schemas:
            failures.append(f"Missing OpenAPI component for {declaration} ({schema_name})")
            continue
        try:
            assert_schema_matches(contract, declaration, schemas[schema_name], openapi)
        except ContractMismatch as error:
            failures.append(str(error))
    if failures:
        raise ContractMismatch("\n\n".join(failures))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openapi", type=Path, help="Read an exported OpenAPI JSON without starting the API")
    arguments = parser.parse_args()
    if arguments.openapi:
        openapi = json.loads(arguments.openapi.read_text(encoding="utf-8"))
    else:
        import sys

        sys.path.insert(0, str(ROOT))
        from services.api.app.main import create_app
        from services.api.app.settings import Settings

        app = create_app(Settings(database_url="sqlite+pysqlite:///:memory:", sqlite_test_mode=True))
        openapi = app.openapi()
    assert_openapi_contract(load_contract(), openapi)
    print("PASS: TypeScript and OpenAPI M0 contracts agree (required/null/literals/types/arrays/records).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
