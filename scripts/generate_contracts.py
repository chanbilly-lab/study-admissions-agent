"""Generate the deliberately bounded v2 wire contract without network or a DB.

The supported JSON Schema subset is explicit. Constraints remain in OpenAPI;
TypeScript represents wire shape, requiredness, nullability and literal values.
An unsupported structure is an error, never an implicit `any`.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "packages" / "contracts" / "v2"
RIGHTS_OPERATIONS = {("/privacy/rights/context", "get"), ("/privacy/exports", "post"), ("/privacy/exports/{request_id}", "get"), ("/privacy/exports/{request_id}/content", "get"), ("/privacy/deletions", "post"), ("/privacy/deletions/{request_id}", "get")}
QA_OPERATIONS = {("/qa/context", "get"), ("/qa/answers", "post")}
PUBLIC_PARENT_OPERATIONS = {("/config", "get"), ("/offerings", "get"), ("/evidence/{evidence_id}", "get")}
PROFILES_OPERATIONS = {
    ("/profiles/context", "get"), ("/profiles", "get"), ("/profiles", "post"),
    ("/profiles/{profile_id}", "get"),
    ("/profiles/{profile_id}/versions/{version_id}", "get"),
    ("/profiles/{profile_id}/versions", "post"),
}
ASSESSMENTS_OPERATIONS = {
    ("/eligibility/context", "get"), ("/eligibility/evaluations", "post"),
    ("/eligibility/evaluations/{assessment_id}", "get"),
    ("/eligibility/evaluations/{assessment_id}/replay", "post"),
}
PLANS_OPERATIONS = {
    ("/plans/context", "get"), ("/plans", "get"), ("/plans", "post"),
    ("/plans/{plan_id}", "get"),
    ("/plans/{plan_id}/versions/{state_version}", "get"),
    ("/plans/{plan_id}/workspace", "post"), ("/plans/{plan_id}/confirm", "post"),
    ("/plans/{plan_id}/tasks/{task_key}/complete", "post"),
}
REVISIONS_OPERATIONS = {
    ("/plan-revisions/context", "get"), ("/plan-revisions/history/{plan_id}", "get"),
    ("/plan-revisions", "post"), ("/plan-revisions/{revision_id}", "get"),
    ("/plan-revisions/{revision_id}/decision", "post"),
}
NOTIFICATIONS_OPERATIONS = {
    ("/notifications/context", "get"), ("/notifications/preferences", "get"),
    ("/notifications/preferences", "post"), ("/notifications", "get"),
    ("/notifications/{notification_id}/read", "post"),
}
PROFILES_PARENT_OPERATIONS = {
    ("/config", "get"), ("/offerings", "get"),
    ("/auth/login", "get"), ("/auth/callback", "get"), ("/auth/session", "get"),
    ("/auth/csrf", "get"), ("/auth/logout", "post"),
    ("/privacy/notices/current", "get"), ("/me/admission", "get"),
    ("/me/age-declarations", "post"), ("/me/consents", "post"),
    ("/me/consents/{consent_id}", "delete"), ("/sharing/policy", "get"),
    ("/access-grants", "get"), ("/access-grants", "post"),
    ("/access-grants/{grant_id}", "delete"), ("/access-grants/{grant_id}/accept", "post"),
}
IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
ANNOTATIONS = {"title", "description", "default", "examples", "example", "deprecated", "readOnly", "writeOnly"}
FACETS = {
    "string": {"minLength", "maxLength", "pattern", "format"},
    "number": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "format"},
    "integer": {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "format"},
    "boolean": set(),
    "null": set(),
    "array": {"minItems", "maxItems", "uniqueItems"},
    "object": {"minProperties", "maxProperties"},
}


class UnsupportedSchema(ValueError):
    """A schema cannot be represented by the explicitly supported wire subset."""


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _literal(value: Any, context: str) -> str:
    if value is None or isinstance(value, (str, bool)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return json.dumps(value, allow_nan=False)
    raise UnsupportedSchema(f"{context}: only primitive literal values are supported")


class TypeScriptGenerator:
    def __init__(self, document: dict[str, Any], *, allow_identity_redirects: bool = False,
                 allow_public_catalog: bool = False, allow_admin: bool = False, allow_admin_review: bool = False,
                 allow_profiles: bool = False, allow_assessments: bool = False, allow_plans: bool = False,
                 allow_revisions: bool = False, allow_notifications: bool = False, allow_qa: bool = False, allow_rights: bool = False):
        self.document = document
        self.allow_identity_redirects = allow_identity_redirects
        self.allow_public_catalog = allow_public_catalog
        self.allow_admin = allow_admin
        self.allow_admin_review = allow_admin_review
        self.allow_profiles = allow_profiles
        self.allow_assessments = allow_assessments
        self.allow_plans = allow_plans
        self.allow_revisions = allow_revisions
        self.allow_notifications = allow_notifications
        self.allow_qa = allow_qa
        self.allow_rights = allow_rights
        if allow_rights and not allow_notifications:
            raise UnsupportedSchema("rights requires its independent notifications-backed profile")
        if allow_qa and not allow_public_catalog:
            raise UnsupportedSchema("qa requires its explicit public-catalog-backed profile")
        if allow_notifications and not allow_revisions:
            raise UnsupportedSchema("notifications requires its independent revisions-backed profile")
        if allow_revisions and not allow_plans:
            raise UnsupportedSchema("revisions requires its independent plans-backed profile")
        if allow_plans and not allow_assessments:
            raise UnsupportedSchema("plans requires its independent assessments-backed profile")
        if allow_assessments and not allow_profiles:
            raise UnsupportedSchema("assessments requires its independent profiles-backed profile")
        if allow_profiles and (not allow_identity_redirects or allow_public_catalog or allow_admin or allow_admin_review):
            raise UnsupportedSchema("profiles requires its independent identity-backed profile")
        if allow_admin_review and not allow_admin:
            raise UnsupportedSchema("admin_review requires the explicit admin-backed profile")
        if allow_admin and (not allow_identity_redirects or allow_public_catalog):
            raise UnsupportedSchema("admin requires its explicit identity-backed profile")
        if allow_identity_redirects and allow_public_catalog:
            raise UnsupportedSchema("application contract profiles must be selected independently")
        components = document.get("components", {}).get("schemas", {})
        if not isinstance(components, dict):
            raise UnsupportedSchema("components.schemas must be an object")
        self.components = components
        self.declarations: dict[str, str] = {}
        self.reserved = set(components)
        for name in self.components:
            self._identifier(name, "component name")

    @staticmethod
    def _identifier(value: str, context: str) -> str:
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise UnsupportedSchema(f"{context}: unsupported TypeScript identifier {value!r}")
        return value

    @staticmethod
    def _check_keys(schema: dict[str, Any], allowed: set[str], context: str) -> None:
        unknown = set(schema) - ANNOTATIONS - allowed
        if unknown:
            raise UnsupportedSchema(f"{context}: unsupported schema keywords {', '.join(sorted(unknown))}")

    def _reference(self, reference: Any, context: str) -> str:
        prefix = "#/components/schemas/"
        if not isinstance(reference, str) or not reference.startswith(prefix):
            raise UnsupportedSchema(f"{context}: only local component schema references are supported")
        name = reference[len(prefix):]
        if name not in self.components:
            raise UnsupportedSchema(f"{context}: unknown schema reference {reference!r}")
        return self._identifier(name, context)

    def _unique_name(self, context: str) -> str:
        base = re.sub(r"[^A-Za-z0-9_$]", "_", context)
        if not IDENTIFIER.fullmatch(base):
            base = "Schema_" + base
        candidate, suffix = base, 2
        while candidate in self.reserved:
            candidate = f"{base}_{suffix}"
            suffix += 1
        self.reserved.add(candidate)
        return candidate

    def _object_fields(self, schema: dict[str, Any], context: str) -> list[str]:
        self._check_keys(schema, {"type", "properties", "required", "additionalProperties"} | FACETS["object"], context)
        if schema.get("additionalProperties") is not False:
            raise UnsupportedSchema(f"{context}: object must explicitly set additionalProperties=false")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if (not isinstance(properties, dict) or any(not isinstance(key, str) for key in properties)
                or not isinstance(required, list) or any(not isinstance(key, str) for key in required)):
            raise UnsupportedSchema(f"{context}: malformed properties or required fields")
        if len(set(required)) != len(required) or set(required) - set(properties):
            raise UnsupportedSchema(f"{context}: required fields must be unique declared properties")
        fields = []
        for name, field in sorted(properties.items()):
            if not isinstance(name, str):
                raise UnsupportedSchema(f"{context}: property name must be a string")
            property_name = name if IDENTIFIER.fullmatch(name) else json.dumps(name, ensure_ascii=False)
            optional = "" if name in required else "?"
            fields.append(f"  {property_name}{optional}: {self.render_schema(field, context + '__' + name)};")
        return fields

    def _declare(self, name: str, schema: dict[str, Any]) -> None:
        if isinstance(schema, dict) and schema.get("type") == "object" and not any(key in schema for key in ("enum", "const", "nullable")):
            fields = self._object_fields(schema, name)
            self.declarations[name] = "export interface " + name + " {\n" + "\n".join(fields) + "\n}"
        else:
            self.declarations[name] = f"export type {name} = {self.render_schema(schema, name)};"

    def render_schema(self, schema: Any, context: str) -> str:
        if not isinstance(schema, dict):
            raise UnsupportedSchema(f"{context}: schema must be an object, boolean schemas are unsupported")
        if "$ref" in schema:
            self._check_keys(schema, {"$ref"}, context)
            return self._reference(schema["$ref"], context)
        if "nullable" in schema:
            if schema["nullable"] is not True:
                raise UnsupportedSchema(f"{context}: nullable must be true when present")
            nonnullable = {key: value for key, value in schema.items() if key != "nullable"}
            return self._union([self.render_schema(nonnullable, context + "__Value"), "null"])
        if "anyOf" in schema:
            self._check_keys(schema, {"anyOf"}, context)
            branches = schema["anyOf"]
            if not isinstance(branches, list) or not branches:
                raise UnsupportedSchema(f"{context}: anyOf must contain at least one schema")
            return self._union([self.render_schema(branch, f"{context}__Option{index}") for index, branch in enumerate(branches)])
        kind = schema.get("type")
        if kind is not None and not isinstance(kind, (str, list)):
            raise UnsupportedSchema(f"{context}: schema type must be a string or a list of strings")
        if isinstance(kind, list):
            if not kind or any(not isinstance(item, str) for item in kind) or len(set(kind)) != len(kind):
                raise UnsupportedSchema(f"{context}: malformed type union")
            return self._union([self.render_schema({**schema, "type": item}, context + "__" + item) for item in sorted(kind)])
        if "const" in schema or "enum" in schema:
            if "const" in schema and "enum" in schema:
                raise UnsupportedSchema(f"{context}: combined const and enum are unsupported")
            facets = FACETS.get(kind, set()) if isinstance(kind, str) else set()
            self._check_keys(schema, {"type", "const", "enum"} | facets, context)
            values = [schema["const"]] if "const" in schema else schema["enum"]
            if not isinstance(values, list) or not values:
                raise UnsupportedSchema(f"{context}: enum must be a nonempty array")
            literals = []
            for value in values:
                literal = _literal(value, context)
                if kind is not None and not self._literal_matches(kind, value):
                    raise UnsupportedSchema(f"{context}: literal disagrees with schema type {kind!r}")
                literals.append(literal)
            return self._union(literals)
        if kind not in FACETS:
            raise UnsupportedSchema(f"{context}: unsupported or missing schema type {kind!r}")
        if kind == "object":
            name = self._unique_name(context)
            self._declare(name, schema)
            return name
        if kind == "array":
            self._check_keys(schema, {"type", "items"} | FACETS[kind], context)
            if "items" not in schema:
                raise UnsupportedSchema(f"{context}: array must declare its item schema")
            item = self.render_schema(schema["items"], context + "__Item")
            if " | " in item:
                name = self._unique_name(context + "__ItemType")
                self.declarations[name] = f"export type {name} = {item};"
                item = name
            return item + "[]"
        self._check_keys(schema, {"type"} | FACETS[kind], context)
        return "number" if kind == "integer" else kind

    @staticmethod
    def _literal_matches(kind: str, value: Any) -> bool:
        return {
            "null": value is None,
            "string": isinstance(value, str),
            "boolean": isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        }.get(kind, False)

    @staticmethod
    def _union(expressions: list[str]) -> str:
        return " | ".join(sorted(set(expressions)))

    def _operations(self) -> None:
        if self.allow_qa:
            paths = self.document.get("paths", {})
            if (not isinstance(paths, dict) or any(not isinstance(item, dict) for item in paths.values())
                    or {(path, method) for path, item in paths.items() for method in item} != PUBLIC_PARENT_OPERATIONS | QA_OPERATIONS):
                raise UnsupportedSchema("qa supports exactly its two selected and three public parent operations")
        if self.allow_profiles:
            paths = self.document.get("paths", {})
            if not isinstance(paths, dict) or any(not isinstance(item, dict) for item in paths.values()):
                raise UnsupportedSchema("profiles paths must be inline objects")
            actual = {(path, method) for path, item in paths.items() for method in item}
            expected = PROFILES_OPERATIONS | PROFILES_PARENT_OPERATIONS
            if self.allow_assessments:
                expected |= ASSESSMENTS_OPERATIONS
            if self.allow_plans:
                expected |= PLANS_OPERATIONS
            if self.allow_revisions:
                expected |= REVISIONS_OPERATIONS
            if self.allow_notifications:
                expected |= NOTIFICATIONS_OPERATIONS
            if self.allow_rights:
                expected |= RIGHTS_OPERATIONS
            if actual != expected:
                raise UnsupportedSchema("profiles supports exactly its selected and identity parent operations")
        for path, path_item in sorted(self.document.get("paths", {}).items()):
            if not isinstance(path_item, dict):
                raise UnsupportedSchema(f"{path}: path item must be an object")
            for method, operation in sorted(path_item.items()):
                if method not in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}:
                    raise UnsupportedSchema(f"{path}: unsupported path item {method!r}")
                if not isinstance(operation, dict):
                    raise UnsupportedSchema(f"{method} {path}: operation must be an object")
                if self.allow_profiles and (path, method) in PROFILES_OPERATIONS and method == "post" and "requestBody" not in operation:
                    raise UnsupportedSchema("profiles writes require an explicit body")
                if self.allow_assessments and (path, method) in ASSESSMENTS_OPERATIONS and method == "post" and "requestBody" not in operation:
                    raise UnsupportedSchema("assessment writes require an explicit body")
                if self.allow_plans and (path, method) in PLANS_OPERATIONS and method == "post" and "requestBody" not in operation:
                    raise UnsupportedSchema("plan writes require an explicit body")
                if self.allow_revisions and (path, method) in REVISIONS_OPERATIONS and method == "post" and "requestBody" not in operation:
                    raise UnsupportedSchema("revision writes require an explicit body")
                if self.allow_notifications and (path, method) in NOTIFICATIONS_OPERATIONS and method == "post" and "requestBody" not in operation:
                    raise UnsupportedSchema("notification writes require an explicit body")
                if self.allow_rights and (path, method) in RIGHTS_OPERATIONS and method == "post" and "requestBody" not in operation:
                    raise UnsupportedSchema("rights writes require an explicit body")
                if self.allow_admin_review and path.startswith("/admin/"):
                    selected = {
                        ("/admin/context", "get"), ("/admin/sources", "post"),
                        ("/admin/sources/{source_id}", "get"), ("/admin/sources/{source_id}", "put"),
                        ("/admin/source-files", "post"), ("/admin/imports", "post"),
                        ("/admin/imports/{import_id}", "get"), ("/admin/review-context", "get"),
                        ("/admin/imports/{import_id}/rows", "get"),
                        ("/admin/evidence/documents", "post"), ("/admin/evidence/versions", "post"),
                        ("/admin/evidence/snippets", "post"), ("/admin/facts", "post"),
                        ("/admin/review-candidates", "get"), ("/admin/review-candidates/{fact_id}", "get"),
                        ("/admin/review-decisions", "post"), ("/admin/releases/precheck", "post"),
                        ("/admin/releases", "post"), ("/admin/releases/current", "get"),
                        ("/admin/releases/{release_id}", "get"),
                        ("/admin/releases/{release_id}/withdraw", "post"),
                    }
                    if (path, method) not in selected:
                        raise UnsupportedSchema("admin_review supports only its explicit operations")
                    if method in {"post", "put"} and "requestBody" not in operation:
                        raise UnsupportedSchema("admin_review writes require an explicit body")
                if self.allow_qa and (path, method) == ("/qa/answers", "post") and "requestBody" not in operation:
                    raise UnsupportedSchema("qa answer requires its explicit body")
                operation_id = self._identifier(operation.get("operationId"), f"{method} {path} operationId")
                prefix = operation_id[0].upper() + operation_id[1:]
                query_name = prefix + "Query"
                if query_name in self.reserved:
                    raise UnsupportedSchema(f"{path}: generated operation type collides with {query_name}")
                self.reserved.add(query_name)
                if "requestBody" in operation:
                    identity_bodies = {
                        ("/me/age-declarations", "post"), ("/me/consents", "post"),
                        ("/access-grants", "post"), ("/access-grants/{grant_id}/accept", "post"),
                    }
                    admin_bodies = {
                        ("/admin/sources", "post"), ("/admin/sources/{source_id}", "put"),
                        ("/admin/source-files", "post"), ("/admin/imports", "post"),
                    }
                    review_bodies = {
                        ("/admin/evidence/documents", "post"), ("/admin/evidence/versions", "post"),
                        ("/admin/evidence/snippets", "post"), ("/admin/facts", "post"),
                        ("/admin/review-decisions", "post"), ("/admin/releases/precheck", "post"),
                        ("/admin/releases", "post"), ("/admin/releases/{release_id}/withdraw", "post"),
                    }
                    profile_bodies = {("/profiles", "post"), ("/profiles/{profile_id}/versions", "post")}
                    if not ((self.allow_identity_redirects and (path, method) in identity_bodies)
                            or (self.allow_admin and (path, method) in admin_bodies)
                            or (self.allow_admin_review and (path, method) in review_bodies)
                            or (self.allow_profiles and (path, method) in profile_bodies)
                            or (self.allow_assessments and (path, method) in ASSESSMENTS_OPERATIONS and method == "post")
                            or (self.allow_plans and (path, method) in PLANS_OPERATIONS and method == "post")
                            or (self.allow_revisions and (path, method) in REVISIONS_OPERATIONS and method == "post")
                            or (self.allow_notifications and (path, method) in NOTIFICATIONS_OPERATIONS and method == "post")
                            or (self.allow_qa and (path, method) == ("/qa/answers", "post"))
                            or (self.allow_rights and (path, method) in RIGHTS_OPERATIONS and method == "post")):
                        raise UnsupportedSchema(f"{path}: request bodies need an explicit generator implementation")
                    body = operation["requestBody"]
                    if (not isinstance(body, dict) or set(body) - {"content", "required", "description"}
                            or body.get("required") is not True
                            or not isinstance(body.get("content"), dict)
                            or set(body["content"]) != {"application/json"}):
                        raise UnsupportedSchema(f"{path}: only required inline JSON request bodies are supported")
                    media = body["content"]["application/json"]
                    if not isinstance(media, dict) or set(media) != {"schema"}:
                        raise UnsupportedSchema(f"{path}: JSON request body must contain exactly one schema")
                    body_name = prefix + "RequestBody"
                    if body_name in self.reserved:
                        raise UnsupportedSchema(f"{path}: generated operation type collides with {body_name}")
                    self.reserved.add(body_name)
                    self._declare(body_name, media["schema"])
                parameters = operation.get("parameters", [])
                if not isinstance(parameters, list):
                    raise UnsupportedSchema(f"{path}: operation parameters must be an array")
                fields = {}
                required = []
                path_fields = {}
                header_fields = {}
                identity_path_parameter = {
                    ("/me/consents/{consent_id}", "delete"): "consent_id",
                    ("/access-grants/{grant_id}", "delete"): "grant_id",
                    ("/access-grants/{grant_id}/accept", "post"): "grant_id",
                }.get((path, method))
                public_path_parameter = "evidence_id" if (path, method) == ("/evidence/{evidence_id}", "get") else None
                if self.allow_public_catalog and (path, method) not in (PUBLIC_PARENT_OPERATIONS | (QA_OPERATIONS if self.allow_qa else set())):
                    raise UnsupportedSchema("public profile supports only its explicitly selected operations")
                path_parameter = identity_path_parameter if self.allow_identity_redirects else public_path_parameter if self.allow_public_catalog else None
                if self.allow_admin:
                    path_parameter = {
                        ("/admin/sources/{source_id}", "get"): "source_id",
                        ("/admin/sources/{source_id}", "put"): "source_id",
                        ("/admin/imports/{import_id}", "get"): "import_id",
                    }.get((path, method), path_parameter)
                if self.allow_admin_review:
                    path_parameter = {
                        ("/admin/imports/{import_id}/rows", "get"): "import_id",
                        ("/admin/review-candidates/{fact_id}", "get"): "fact_id",
                        ("/admin/releases/{release_id}", "get"): "release_id",
                        ("/admin/releases/{release_id}/withdraw", "post"): "release_id",
                    }.get((path, method), path_parameter)
                required_path_parameters = {path_parameter} if path_parameter is not None else set()
                if self.allow_profiles:
                    required_path_parameters |= {
                        ("/profiles/{profile_id}", "get"): {"profile_id"},
                        ("/profiles/{profile_id}/versions/{version_id}", "get"): {"profile_id", "version_id"},
                        ("/profiles/{profile_id}/versions", "post"): {"profile_id"},
                    }.get((path, method), set())
                if self.allow_assessments and path.startswith("/eligibility/evaluations/{assessment_id}"):
                    required_path_parameters |= {"assessment_id"}
                if self.allow_revisions and (path, method) in REVISIONS_OPERATIONS:
                    if "{plan_id}" in path:
                        required_path_parameters |= {"plan_id"}
                    if "{revision_id}" in path:
                        required_path_parameters |= {"revision_id"}
                if self.allow_notifications and (path, method) in NOTIFICATIONS_OPERATIONS and "{notification_id}" in path:
                    required_path_parameters |= {"notification_id"}
                if self.allow_rights and (path, method) in RIGHTS_OPERATIONS and "{request_id}" in path:
                    required_path_parameters |= {"request_id"}
                plan_parameters = {}
                if self.allow_plans and (path, method) in PLANS_OPERATIONS and "{plan_id}" in path:
                    plan_parameters["plan_id"] = {"type": "string", "format": "uuid"}
                    if "{state_version}" in path:
                        plan_parameters["state_version"] = {"type": "integer", "minimum": 1, "maximum": 2147483647}
                    if "{task_key}" in path:
                        plan_parameters["task_key"] = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
                    required_path_parameters |= set(plan_parameters)
                idempotent_operation = (self.allow_admin and (path, method) == ("/admin/imports", "post")) or (
                    self.allow_admin_review and (path, method) == ("/admin/releases", "post")) or (
                    self.allow_profiles and (path, method) == ("/profiles", "post")) or (
                    self.allow_plans and (path, method) == ("/plans/{plan_id}/confirm", "post"))
                for parameter in parameters:
                    if (idempotent_operation
                            and isinstance(parameter, dict) and parameter.get("in") == "header"
                            and parameter.get("name") == "Idempotency-Key"
                            and parameter.get("required") is True and "$ref" not in parameter
                            and "Idempotency-Key" not in header_fields
                            and parameter.get("schema") == {"type": "string", "minLength": 1,
                                "maxLength": 128, "pattern": "^[A-Za-z0-9._:-]{1,128}$"}):
                        header_fields["Idempotency-Key"] = parameter["schema"]
                        continue
                    if (isinstance(parameter, dict) and parameter.get("in") == "path"
                            and parameter.get("name") in plan_parameters and parameter.get("required") is True
                            and "$ref" not in parameter and parameter["name"] not in path_fields
                            and parameter.get("schema") == plan_parameters[parameter["name"]]):
                        path_fields[parameter["name"]] = parameter["schema"]
                        continue
                    if (required_path_parameters
                            and isinstance(parameter, dict) and parameter.get("in") == "path"
                            and parameter.get("name") in required_path_parameters and parameter.get("required") is True
                            and parameter.get("name") not in plan_parameters
                            and "$ref" not in parameter and parameter["name"] not in path_fields
                            and isinstance(parameter.get("schema"), dict)
                            and parameter["schema"].get("type") == "string"
                            and parameter.get("schema", {}).get("format") == "uuid"):
                        path_fields[parameter["name"]] = parameter["schema"]
                        continue
                    if not isinstance(parameter, dict) or parameter.get("in") != "query" or "$ref" in parameter:
                        raise UnsupportedSchema(f"{path}: only inline query parameters are supported")
                    name = parameter.get("name")
                    if not isinstance(name, str) or name in fields:
                        raise UnsupportedSchema(f"{path}: query parameter names must be unique strings")
                    if self.allow_rights and (path, method) in RIGHTS_OPERATIONS:
                        raise UnsupportedSchema("rights operations do not accept query parameters")
                    if self.allow_qa and (path, method) in QA_OPERATIONS:
                        raise UnsupportedSchema("qa operations do not accept query parameters")
                    if self.allow_profiles and (path, method) in PROFILES_OPERATIONS:
                        if (path, method) != ("/profiles", "get") or name not in {"limit", "cursor"}:
                            raise UnsupportedSchema("profiles supports only its bounded list query")
                    if self.allow_assessments and (path, method) in ASSESSMENTS_OPERATIONS:
                        raise UnsupportedSchema("assessment operations do not accept query parameters")
                    if self.allow_revisions and (path, method) in REVISIONS_OPERATIONS:
                        raise UnsupportedSchema("revision operations do not accept query parameters")
                    if self.allow_plans and (path, method) in PLANS_OPERATIONS:
                        if (path, method) != ("/plans", "get") or name not in {"limit", "cursor"}:
                            raise UnsupportedSchema("plans supports only its bounded list query")
                        expected_query = {"limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 20},
                                          "cursor": {"type": "string", "minLength": 1, "maxLength": 1024}}
                        if parameter.get("required") is not False or parameter.get("schema") != expected_query[name]:
                            raise UnsupportedSchema("plans list query must keep its explicit bounds")
                    if self.allow_notifications and (path, method) in NOTIFICATIONS_OPERATIONS:
                        if (path, method) != ("/notifications", "get") or name not in {"limit", "cursor"}:
                            raise UnsupportedSchema("notifications supports only its bounded list query")
                        expected_notification_query = {"limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 20},
                                                       "cursor": {"type": "string", "minLength": 1, "maxLength": 1024}}
                        if parameter.get("required") is not False or parameter.get("schema") != expected_notification_query[name]:
                            raise UnsupportedSchema("notifications list query must keep its explicit bounds")
                    fields[name] = parameter.get("schema")
                    if parameter.get("required", False):
                        required.append(name)
                if required_path_parameters != set(path_fields):
                    raise UnsupportedSchema(f"{path}: the required UUID path parameters are missing")
                if idempotent_operation and not header_fields:
                    raise UnsupportedSchema("selected write requires its bounded idempotency header")
                if header_fields:
                    header_name = prefix + "Headers"
                    if header_name in self.reserved:
                        raise UnsupportedSchema(f"{path}: generated header type collision")
                    self.reserved.add(header_name)
                    self._declare(header_name, {"type": "object", "additionalProperties": False,
                        "properties": header_fields, "required": list(header_fields)})
                self._declare(query_name, {"type": "object", "additionalProperties": False, "properties": fields, "required": required})
                if path_fields:
                    path_name = prefix + "Path"
                    if path_name in self.reserved:
                        raise UnsupportedSchema(f"{path}: generated operation type collides with {path_name}")
                    self.reserved.add(path_name)
                    self._declare(path_name, {"type": "object", "additionalProperties": False,
                                             "properties": path_fields, "required": list(path_fields)})
                responses = operation.get("responses", {})
                if not isinstance(responses, dict) or not responses:
                    raise UnsupportedSchema(f"{path}: operation must document its responses")
                for status, response in sorted(responses.items()):
                    if not isinstance(status, str) or not re.fullmatch(r"[1-5][0-9]{2}|default", status):
                        raise UnsupportedSchema(f"{path}: unsupported response status {status!r}")
                    if not isinstance(response, dict):
                        raise UnsupportedSchema(f"{path} {status}: response must be an object")
                    content = response.get("content", {})
                    if self.allow_identity_redirects and isinstance(content, dict) and not content and (path, method, status) in {
                        ("/auth/login", "get", "302"), ("/auth/callback", "get", "303"),
                    }:
                        name = prefix + "Response" + status
                        if name in self.reserved:
                            raise UnsupportedSchema(f"{path}: generated operation type collides with {name}")
                        headers = response.get("headers", {})
                        if not isinstance(headers, dict) or set(headers) != {"Location", "Set-Cookie", "X-Request-ID"}:
                            raise UnsupportedSchema(f"{path}: identity redirect requires explicit bounded headers")
                        fields = {}
                        for key, header in headers.items():
                            if not isinstance(header, dict) or header.get("schema", {}).get("type") != "string":
                                raise UnsupportedSchema(f"{path}: redirect headers must be inline strings")
                            fields[key] = header["schema"]
                        self.reserved.add(name)
                        self.declarations[name] = f"export type {name} = undefined;"
                        header_name = name + "Headers"
                        if header_name in self.reserved:
                            raise UnsupportedSchema(f"{path}: generated operation type collides with {header_name}")
                        self.reserved.add(header_name)
                        self._declare(header_name, {"type": "object", "additionalProperties": False,
                                                   "properties": fields, "required": list(fields)})
                        continue
                    if not isinstance(content, dict) or set(content) != {"application/json"}:
                        raise UnsupportedSchema(f"{path} {status}: only explicitly described JSON responses are supported")
                    media = content["application/json"]
                    if not isinstance(media, dict):
                        raise UnsupportedSchema(f"{path} {status}: response media must be an object")
                    schema = media.get("schema")
                    name = prefix + "Response" + ("Default" if status == "default" else status)
                    if name in self.reserved:
                        raise UnsupportedSchema(f"{path}: generated operation type collides with {name}")
                    self.reserved.add(name)
                    self._declare(name, schema)

    def generate(self) -> str:
        for name, schema in sorted(self.components.items()):
            self._declare(name, schema)
        self._operations()
        header = "// Generated offline from create_v2_app().openapi() by scripts/generate_contracts.py.\n// Do not edit. JSON Schema validation constraints remain in openapi.json.\n\n"
        if self.allow_identity_redirects:
            header = header.replace("create_v2_app()", "create_identity_v2_app()")
        if self.allow_public_catalog:
            header = header.replace("create_v2_app()", "create_public_catalog_v2_app()")
        if self.allow_qa:
            header = header.replace("create_public_catalog_v2_app()", "create_qa_v2_app()")
        if self.allow_admin:
            header = header.replace("create_identity_v2_app()", "create_admin_v2_app()")
        if self.allow_admin_review:
            header = header.replace("create_admin_v2_app()", "create_admin_review_v2_app()")
        if self.allow_profiles:
            header = header.replace("create_identity_v2_app()", "create_profiles_v2_app()")
        if self.allow_assessments:
            header = header.replace("create_profiles_v2_app()", "create_assessments_v2_app()")
        if self.allow_plans:
            header = header.replace("create_assessments_v2_app()", "create_plans_v2_app()")
        if self.allow_revisions:
            header = header.replace("create_plans_v2_app()", "create_revisions_v2_app()")
        if self.allow_notifications:
            header = header.replace("create_revisions_v2_app()", "create_notifications_v2_app()")
        if self.allow_rights:
            header = header.replace("create_notifications_v2_app()", "create_rights_v2_app()")
        return header + "\n\n".join(self.declarations[name] for name in sorted(self.declarations)) + "\n"


def generate_types(document: dict[str, Any], *, allow_identity_redirects: bool = False,
                   allow_public_catalog: bool = False, allow_admin: bool = False, allow_admin_review: bool = False,
                   allow_profiles: bool = False, allow_assessments: bool = False, allow_plans: bool = False,
                   allow_revisions: bool = False, allow_notifications: bool = False, allow_qa: bool = False, allow_rights: bool = False) -> str:
    return TypeScriptGenerator(document, allow_identity_redirects=allow_identity_redirects,
                               allow_public_catalog=allow_public_catalog, allow_admin=allow_admin,
                               allow_admin_review=allow_admin_review, allow_profiles=allow_profiles, allow_assessments=allow_assessments,
                               allow_plans=allow_plans, allow_revisions=allow_revisions, allow_notifications=allow_notifications, allow_qa=allow_qa, allow_rights=allow_rights).generate()


def load_openapi(profile: str = "foundation") -> dict[str, Any]:
    # Import only the independent v2 factory, never the M0 app or persistence.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from services.api.app.api.v2 import create_v2_app
    from services.api.app.settings import V2RuntimeSettings

    # A build artifact describes the protocol, not the server doing the build.
    # Explicit values override even invalid V2_/legacy process configuration;
    # _env_file=None prevents M0's local .env from entering this export.
    if profile not in {"foundation", "identity", "public_catalog", "admin", "admin_review", "profiles", "assessments", "plans", "revisions", "notifications", "qa", "rights"}:
        raise UnsupportedSchema("unsupported application contract profile")
    settings = V2RuntimeSettings(
        app_environment="development", data_mode="demo" if profile == "foundation" else "verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None,
    )
    expected_paths = {"/config", "/offerings"}
    if profile in {"identity", "admin", "admin_review", "profiles", "assessments", "plans", "revisions", "notifications", "rights"}:
        from services.api.app.api.identity import create_identity_v2_app
        if profile == "rights":
            from services.api.app.api.rights import create_rights_v2_app
            document = create_rights_v2_app(settings).openapi()
            expected_paths |= {path for path, _ in PROFILES_OPERATIONS | ASSESSMENTS_OPERATIONS | PLANS_OPERATIONS | REVISIONS_OPERATIONS | NOTIFICATIONS_OPERATIONS | RIGHTS_OPERATIONS}
        elif profile == "notifications":
            from services.api.app.api.notifications import create_notifications_v2_app
            document = create_notifications_v2_app(settings).openapi()
            expected_paths |= {path for path, _ in PROFILES_OPERATIONS | ASSESSMENTS_OPERATIONS | PLANS_OPERATIONS | REVISIONS_OPERATIONS | NOTIFICATIONS_OPERATIONS}
        elif profile == "revisions":
            from services.api.app.api.revisions import create_revisions_v2_app
            document = create_revisions_v2_app(settings).openapi()
            expected_paths |= {path for path, _ in PROFILES_OPERATIONS | ASSESSMENTS_OPERATIONS | PLANS_OPERATIONS | REVISIONS_OPERATIONS}
        elif profile == "plans":
            from services.api.app.api.plans import create_plans_v2_app
            document = create_plans_v2_app(settings).openapi()
            expected_paths |= {path for path, _ in PROFILES_OPERATIONS | ASSESSMENTS_OPERATIONS | PLANS_OPERATIONS}
        elif profile == "assessments":
            from services.api.app.api.assessments import create_assessments_v2_app
            document = create_assessments_v2_app(settings).openapi()
            expected_paths |= {path for path, _ in PROFILES_OPERATIONS | ASSESSMENTS_OPERATIONS}
        elif profile == "profiles":
            from services.api.app.api.profiles import create_profiles_v2_app
            document = create_profiles_v2_app(settings).openapi()
            expected_paths |= {path for path, _ in PROFILES_OPERATIONS}
        elif profile in {"admin", "admin_review"}:
            from services.api.app.api.admin import create_admin_v2_app
            if profile == "admin_review":
                from services.api.app.api.admin_review import create_admin_review_v2_app
                document = create_admin_review_v2_app(settings).openapi()
                expected_paths |= {"/admin/review-context", "/admin/imports/{import_id}/rows",
                    "/admin/evidence/documents", "/admin/evidence/versions", "/admin/evidence/snippets",
                    "/admin/facts", "/admin/review-candidates", "/admin/review-candidates/{fact_id}",
                    "/admin/review-decisions", "/admin/releases/precheck", "/admin/releases",
                    "/admin/releases/current", "/admin/releases/{release_id}",
                    "/admin/releases/{release_id}/withdraw"}
            else:
                document = create_admin_v2_app(settings).openapi()
            expected_paths |= {"/admin/context", "/admin/sources", "/admin/sources/{source_id}",
                               "/admin/source-files", "/admin/imports", "/admin/imports/{import_id}"}
        else:
            document = create_identity_v2_app(settings).openapi()
        expected_paths |= {"/auth/login", "/auth/callback", "/auth/session", "/auth/csrf", "/auth/logout"}
        expected_paths |= {"/privacy/notices/current", "/me/admission", "/me/age-declarations",
                           "/me/consents", "/me/consents/{consent_id}"}
        expected_paths |= {"/sharing/policy", "/access-grants", "/access-grants/{grant_id}",
                           "/access-grants/{grant_id}/accept"}
    elif profile == "qa":
        from services.api.app.api.qa import create_qa_v2_app
        document = create_qa_v2_app(settings).openapi()
        expected_paths |= {"/evidence/{evidence_id}"} | {path for path, _ in QA_OPERATIONS}
    elif profile == "public_catalog":
        from services.api.app.api.public_catalog import create_public_catalog_v2_app
        document = create_public_catalog_v2_app(settings).openapi()
        expected_paths |= {"/evidence/{evidence_id}"}
    else:
        document = create_v2_app(settings).openapi()
    if document.get("servers") != [{"url": "/v2"}] or set(document.get("paths", {})) != expected_paths:
        raise UnsupportedSchema("v2 factory must export server /v2 and exactly the selected profile paths")
    return document


def generate_artifacts(document: dict[str, Any], *, allow_identity_redirects: bool = False,
                       allow_public_catalog: bool = False, allow_admin: bool = False, allow_admin_review: bool = False,
                       allow_profiles: bool = False, allow_assessments: bool = False, allow_plans: bool = False,
                       allow_revisions: bool = False, allow_notifications: bool = False, allow_qa: bool = False, allow_rights: bool = False) -> dict[str, str]:
    # Complete validation before either output is written.
    return {"openapi.json": canonical_json(document),
            "generated.ts": generate_types(document, allow_identity_redirects=allow_identity_redirects,
                                           allow_public_catalog=allow_public_catalog, allow_admin=allow_admin,
                                           allow_admin_review=allow_admin_review, allow_profiles=allow_profiles, allow_assessments=allow_assessments,
                                           allow_plans=allow_plans, allow_revisions=allow_revisions, allow_notifications=allow_notifications, allow_qa=allow_qa, allow_rights=allow_rights)}


def write_or_check(artifacts: dict[str, str], output_dir: Path, *, check: bool) -> list[str]:
    drift = []
    for filename, expected in artifacts.items():
        path = output_dir / filename
        if check:
            if not path.is_file() or path.read_bytes() != expected.encode("utf-8"):
                drift.append(filename)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected.encode("utf-8"))
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare existing artifacts without writing")
    parser.add_argument("--profile", choices=["foundation", "identity", "public_catalog", "admin", "admin_review", "profiles", "assessments", "plans", "revisions", "notifications", "qa", "rights"], default="foundation")
    args = parser.parse_args(argv)
    try:
        if args.profile == "rights":
            artifacts = generate_artifacts(load_openapi("rights"), allow_identity_redirects=True, allow_profiles=True, allow_assessments=True, allow_plans=True, allow_revisions=True, allow_notifications=True, allow_rights=True)
        elif args.profile == "qa":
            artifacts = generate_artifacts(load_openapi("qa"), allow_public_catalog=True, allow_qa=True)
        elif args.profile == "notifications":
            artifacts = generate_artifacts(load_openapi("notifications"), allow_identity_redirects=True,
                allow_profiles=True, allow_assessments=True, allow_plans=True, allow_revisions=True, allow_notifications=True)
        elif args.profile == "revisions":
            artifacts = generate_artifacts(load_openapi("revisions"), allow_identity_redirects=True,
                allow_profiles=True, allow_assessments=True, allow_plans=True, allow_revisions=True)
        elif args.profile == "plans":
            artifacts = generate_artifacts(load_openapi("plans"), allow_identity_redirects=True,
                allow_profiles=True, allow_assessments=True, allow_plans=True)
        elif args.profile == "assessments":
            artifacts = generate_artifacts(load_openapi("assessments"), allow_identity_redirects=True,
                allow_profiles=True, allow_assessments=True)
        elif args.profile == "profiles":
            artifacts = generate_artifacts(load_openapi("profiles"), allow_identity_redirects=True, allow_profiles=True)
        elif args.profile == "admin_review":
            artifacts = generate_artifacts(load_openapi("admin_review"), allow_identity_redirects=True,
                                           allow_admin=True, allow_admin_review=True)
        elif args.profile == "admin":
            artifacts = generate_artifacts(load_openapi("admin"), allow_identity_redirects=True, allow_admin=True)
        elif args.profile == "identity":
            artifacts = generate_artifacts(load_openapi("identity"), allow_identity_redirects=True)
        elif args.profile == "public_catalog":
            artifacts = generate_artifacts(load_openapi("public_catalog"), allow_public_catalog=True)
        else:
            # Preserve the zero-argument foundation API and its existing callers.
            artifacts = generate_artifacts(load_openapi())
        output = OUTPUT_DIR if args.profile == "foundation" else OUTPUT_DIR / args.profile
        drift = write_or_check(artifacts, output, check=args.check)
    except (UnsupportedSchema, ValueError) as exc:
        print(f"v2 contract generation failed: {exc}", file=sys.stderr)
        return 1
    if drift:
        print("v2 contract drift: " + ", ".join(drift), file=sys.stderr)
        return 1
    print("v2 contract artifacts match" if args.check else "v2 contract artifacts generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
