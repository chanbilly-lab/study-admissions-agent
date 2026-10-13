"""Pure bounded import; no persistence, DB or publication authority."""
from dataclasses import dataclass
from hashlib import sha256
import json
from decimal import Decimal, DecimalException
from typing import Annotated, Literal
from pydantic import AfterValidator, Field, field_validator, model_validator
from ..admissions_catalog.schemas import CatalogModel, Identifier, _namespace

Year = Annotated[int, Field(strict=True, ge=1, le=9999)]
def _text(value):
    if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Nonblank plain text required")
    return value


Text = Annotated[str, Field(strict=True, min_length=1, max_length=500), AfterValidator(_text)]
Value = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=4, allow_inf_nan=False)]


class CandidateError(ValueError):
    def __init__(self):
        super().__init__("CANDIDATE_BATCH_REJECTED")


class Candidate(CatalogModel):
    record_id: Identifier
    is_synthetic: bool = Field(strict=True)
    source_ref: Identifier | None = None
    source_sha256: str | None = Field(default=None, strict=True, pattern=r"^[0-9a-f]{64}$")
    original_label: Text
    review_status: Literal["pending"] = "pending"
    published: Literal[False] = False

    @field_validator("published", mode="before")
    @classmethod
    def explicit_false(cls, value):
        if value is not False:
            raise ValueError("Candidates cannot be published")
        return value

    @model_validator(mode="after")
    def namespace(self):
        _namespace(self.record_id, self.is_synthetic)
        return self


@dataclass(frozen=True)
class CandidateBatch:
    sha256: str
    records: tuple[Candidate, ...]
    persisted: bool = False
    publishable: bool = False


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CandidateError()
        result[key] = value
    return result


def load_candidates(payload: bytes, model: type[Candidate]) -> CandidateBatch:
    try:
        if type(payload) is not bytes or not 1 <= len(payload) <= 1024 * 1024 or not issubclass(model, Candidate):
            raise CandidateError()
        # Reuse T15 lexical bounds, not its offering/fact parser or persistence.
        from ..ingestion.structured import _lexical_bounds
        text = payload.decode("utf-8")
        _lexical_bounds(text)
        data = json.loads(text, object_pairs_hook=_pairs, parse_float=Decimal,
                          parse_constant=lambda _: (_ for _ in ()).throw(CandidateError()))
        if type(data) is not dict or set(data) != {"schema_version", "records"} or data["schema_version"] != "candidate.1":
            raise CandidateError()
        if type(data["records"]) is not list or not 1 <= len(data["records"]) <= 200:
            raise CandidateError()
        rows = tuple(model.model_validate(row) for row in data["records"])
        if len({row.record_id for row in rows}) != len(rows):
            raise CandidateError()
        canonical = json.dumps([row.model_dump(mode="json") for row in sorted(rows, key=lambda row: row.record_id)],
                               ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        return CandidateBatch(sha256(canonical).hexdigest(), rows)
    except (ValueError, TypeError, UnicodeError, RecursionError, AttributeError, DecimalException):
        raise CandidateError() from None
