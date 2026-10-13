"""Concrete bounded identity search through frozen T20 publication proofs."""

import base64
from hashlib import sha256
import json
import re
from uuid import UUID

from sqlalchemy import func, select

from ..admissions_catalog.models import (AdmissionOffering, CatalogDataset, CatalogInstitution, CatalogProgram)
from ..api.v2.schemas import PageInfo
from ..public_catalog.reader import CatalogReader
from ..public_catalog.schemas import PublicCatalogError
from ..releases.models import CatalogRelease, CatalogReleaseMember, CatalogReleaseState
from .schemas import (DirectoryData, DirectoryQuery, IdentityProof, InstitutionOption,
                      ProgramDirectoryQuery, ProgramOption, disabled_data, filters_for)


def _fingerprint(resource, query):
    value = {"resource": resource, "filters": filters_for(query), "limit": query.limit}
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _cursor(resource, query, watermark, identifier):
    body = {"v": 1, "q": _fingerprint(resource, query), "w": watermark, "i": str(identifier)}
    return base64.urlsafe_b64encode(json.dumps(body, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("ascii")).decode("ascii").rstrip("=")


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _decode(resource, query):
    if query.cursor is None:
        return None
    try:
        token = query.cursor
        if type(token) is not str or not 1 <= len(token) <= 512 or re.fullmatch(r"[A-Za-z0-9_-]+", token) is None:
            raise ValueError()
        raw = base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True)
        if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != token:
            raise ValueError()
        body = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if (type(body) is not dict or set(body) != {"v", "q", "w", "i"}
                or type(body["v"]) is not int or body["v"] != 1
                or body["q"] != _fingerprint(resource, query)
                or type(body["w"]) is not int or not 0 <= body["w"] <= 9007199254740991
                or type(body["i"]) is not str):
            raise ValueError()
        identifier = UUID(body["i"])
        if str(identifier) != body["i"]:
            raise ValueError()
        return body["w"], identifier
    except Exception:
        raise PublicCatalogError(422) from None


class PublishedDirectoryReader:
    def __init__(self, catalog: CatalogReader):
        if type(catalog) is not CatalogReader:
            raise PublicCatalogError()
        self.catalog = catalog
        self._initial_catalog = catalog
        self._validate()

    def _validate(self):
        if self.catalog is not self._initial_catalog or type(self.catalog) is not CatalogReader:
            raise PublicCatalogError()
        runtime, policy = self.catalog._validate()
        if runtime.data_mode != "verified" or runtime.model_mode != "disabled" or policy.allow_test_fixture_read:
            raise PublicCatalogError()
        return runtime, policy

    def validate_runtime(self, runtime):
        current, _ = self._validate()
        if (current.app_environment, current.data_mode, current.model_mode) != (
                runtime.app_environment, runtime.data_mode, runtime.model_mode):
            raise PublicCatalogError()

    def _statement(self, resource, query, now, after=None):
        identity = CatalogProgram.id if resource == "programs" else CatalogInstitution.id
        name = CatalogProgram.name if resource == "programs" else CatalogInstitution.name
        statement = select(identity.label("identity_id"), name.label("identity_name"),
            CatalogInstitution.country.label("identity_country"), CatalogInstitution.id.label("institution_id"),
            CatalogProgram.id.label("program_id"), CatalogRelease.id.label("release_id"),
            CatalogRelease.dataset_id.label("dataset_id"), CatalogRelease.entry_year.label("entry_year"),
            CatalogReleaseMember.offering_id.label("offering_id"), CatalogReleaseMember.offering_version.label("offering_version")
        ).select_from(CatalogRelease).join(CatalogReleaseState, CatalogReleaseState.release_id == CatalogRelease.id
        ).join(CatalogReleaseMember, CatalogReleaseMember.release_id == CatalogRelease.id
        ).join(AdmissionOffering, AdmissionOffering.id == CatalogReleaseMember.offering_id
        ).join(CatalogProgram, CatalogProgram.id == AdmissionOffering.program_id
        ).join(CatalogInstitution, CatalogInstitution.id == CatalogProgram.institution_id
        ).join(CatalogDataset, CatalogDataset.id == CatalogRelease.dataset_id).where(
            CatalogReleaseState.status == "published", CatalogRelease.kind == "formal",
            CatalogRelease.is_synthetic.is_(False), CatalogRelease.valid_from <= now, CatalogRelease.valid_until > now,
            CatalogDataset.data_mode == "verified", CatalogDataset.is_synthetic.is_(False),
            AdmissionOffering.is_synthetic.is_(False), CatalogProgram.is_synthetic.is_(False),
            CatalogInstitution.is_synthetic.is_(False), CatalogProgram.study_level == "undergraduate",
            AdmissionOffering.dataset_id == CatalogRelease.dataset_id,
            CatalogProgram.dataset_id == CatalogRelease.dataset_id, CatalogInstitution.dataset_id == CatalogRelease.dataset_id,
        )
        if query.q:
            # Bound parameter and literal substring; %/_ never become wildcard operators.
            statement = statement.where(func.strpos(func.lower(name), func.lower(query.q)) > 0)
        if query.country is not None:
            statement = statement.where(CatalogInstitution.country == query.country)
        if resource == "programs":
            statement = statement.where(CatalogInstitution.id == query.institution_id)
        if after is not None:
            statement = statement.where(identity > after)
        return statement.distinct(identity).order_by(identity, CatalogRelease.id,
            CatalogReleaseMember.offering_id, CatalogReleaseMember.offering_version)

    def search(self, resource, query):
        try:
            if resource == "institutions":
                current = DirectoryQuery.model_validate(query.model_dump())
            elif resource == "programs":
                current = ProgramDirectoryQuery.model_validate(query.model_dump())
            else:
                raise PublicCatalogError(422)
            cursor = _decode(resource, current)
            _, policy = self._validate()
            if not policy.enabled or not policy.real_catalog_ready:
                if cursor is not None:
                    raise PublicCatalogError(422)
                return disabled_data(resource, current)
            catalog = self.catalog
            with catalog._transaction() as session:
                watermark = catalog._watermark(session)
                if cursor is not None and cursor[0] != watermark:
                    raise PublicCatalogError(409)
                hints = session.execute(self._statement(resource, current, catalog._now(),
                    cursor[1] if cursor is not None else None).limit(current.limit + 1)).all()
                # Lock datasets before releases/members, matching the original writer order.
                for dataset_id in sorted({hint.dataset_id for hint in hints}, key=str):
                    catalog.store.dataset(session, dataset_id)
                items, all_proofs, releases, cached = [], [], [], {}
                for hint in hints[:current.limit]:
                    if hint.release_id not in cached:
                        cached[hint.release_id] = catalog._release(session, hint.release_id)
                        root, state, _, proofs = cached[hint.release_id]
                        releases.append((root, state))
                        all_proofs.extend(proofs)
                    root, _, released, proofs = cached[hint.release_id]
                    selected = tuple(proof for proof in proofs if (proof.member.offering_id, proof.member.offering_version) ==
                                     (hint.offering_id, hint.offering_version))
                    if not selected or root.is_synthetic or root.kind != "formal" or root.entry_year != hint.entry_year:
                        raise PublicCatalogError(409)
                    for proof in selected:
                        identity = proof.program if resource == "programs" else proof.institution
                        if (identity.id != hint.identity_id or identity.name != hint.identity_name
                                or proof.institution.country != hint.identity_country
                                or proof.institution.id != hint.institution_id or proof.program.id != hint.program_id
                                or proof.program.institution_id != hint.institution_id
                                or proof.institution.is_synthetic or proof.program.is_synthetic
                                or proof.program.study_level != "undergraduate"
                                or proof.evidence.scope.entry_year != hint.entry_year
                                or proof.evidence.scope.country != hint.identity_country
                                or proof.evidence.scope.institution_id != hint.institution_id
                                or proof.evidence.scope.program_id != hint.program_id
                                or root.dataset_id != hint.dataset_id
                                or current.q and current.q.lower() not in identity.name.lower()
                                or current.country is not None and proof.institution.country != current.country
                                or resource == "programs" and proof.program.institution_id != current.institution_id):
                            raise PublicCatalogError(409)
                    identity_proof = IdentityProof(release_id=root.id, offering_id=hint.offering_id,
                        offering_version=hint.offering_version, identity_evidence_entry_year=root.entry_year,
                        requirements_version=released.requirements_version)
                    first = selected[0]
                    identity = first.program if resource == "programs" else first.institution
                    fields = {"id": identity.id, "name": identity.name, "country": first.institution.country,
                              "is_synthetic": False, "outcome_subject_ref": str(identity.id), "proof": identity_proof}
                    if resource == "programs":
                        items.append(ProgramOption(**fields, institution_id=first.program.institution_id))
                    else:
                        items.append(InstitutionOption(**fields))
                has_more = len(hints) > current.limit
                next_cursor = _cursor(resource, current, watermark, items[-1].id) if has_more else None
                result = DirectoryData(resource=resource, filters=filters_for(current), items=tuple(items),
                    page=PageInfo(limit=current.limit, next_cursor=next_cursor, has_more=has_more), directory_available=True,
                    missing_reason=None if items else "no_published_matches", catalog_watermark=watermark)
                if catalog._watermark(session) != watermark:
                    raise PublicCatalogError(409)
                self._validate()
                catalog.proof.final_deadlines(all_proofs, releases, catalog._now())
            return result
        except PublicCatalogError as error:
            if error.status_code == 404:
                # A previously selected published hint disappeared while obtaining
                # its locks/proofs; refresh the search rather than exposing an ID.
                raise PublicCatalogError(409) from None
            raise
        except Exception:
            raise PublicCatalogError() from None
