import ipaddress
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, field_validator
from ...admissions_catalog.schemas import CatalogModel, Identifier


class RegisteredEndpoint(CatalogModel):
    source_ref: Identifier
    fixed_url: str = Field(strict=True, min_length=10, max_length=2048)
    permission_status: Literal["pending"] = "pending"

    @field_validator("fixed_url")
    @classmethod
    def https_syntax_only(cls, value):
        if any(character.isspace() or ord(character) < 32 for character in value):
            raise ValueError("HTTPS endpoint syntax required")
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment:
            raise ValueError("Fixed HTTPS endpoint required")
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            if "." not in parsed.hostname or parsed.hostname.endswith((".local", ".localhost", ".internal")):
                raise ValueError("Public hostname syntax required")
        else:
            raise ValueError("Literal IP targets forbidden")
        return value


class ConnectorRequest(CatalogModel):
    source_ref: Identifier
    reference_year: int = Field(strict=True, ge=1, le=9999)
    # No request URL, cookies, authorization, destination path or transport options.


class ConnectorPolicy(CatalogModel):
    mode: Literal["disabled"] = "disabled"
    endpoints: tuple[RegisteredEndpoint, ...] = Field(default=(), max_length=10)


def plan_request(request: ConnectorRequest, policy: ConnectorPolicy = ConnectorPolicy()) -> dict:
    request, policy = ConnectorRequest.model_validate(request), ConnectorPolicy.model_validate(policy)
    refs = [endpoint.source_ref for endpoint in policy.endpoints]
    if len(refs) != len(set(refs)):
        raise ValueError("Duplicate registered source")
    return {"status": "disabled", "reason": "FETCH_NOT_IMPLEMENTED" if request.source_ref in refs else "SOURCE_NOT_REGISTERED",
            "network_requested": False, "live_available": False, "candidate_created": False,
            "permission_verified": False, "public_release_ready": False}
