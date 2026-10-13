"""Actual private ASGI and PostgreSQL assessment transactions, synthetic only."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from services.api.app.api.assessments import create_assessments_v2_app
from services.api.app.assessments.models import EligibilityAssessment
from services.api.app.auth.router import SESSION_COOKIE
from services.api.app.profiles.schemas import AppendInput
from services.api.app.rules.schemas import AssessmentPolicy, ReplayRequest
from services.api.app.rules.service import EligibilityService


pytestmark = pytest.mark.postgres


def denied(operation, status):
    with pytest.raises(ValueError) as caught:
        operation()
    assert caught.value.status_code == status
    return caught.value


def records(engine):
    with Session(engine) as session:
        return session.scalars(select(EligibilityAssessment)).all()


def headers(client, actor):
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE, actor.cookie.get_secret_value())
    csrf = client.get('/auth/csrf')
    assert csrf.status_code == 200
    return {'Origin': 'https://app.test.invalid', 'X-CSRF-Token': csrf.json()['data']['csrf_token']}


def safe(response, status):
    assert response.status_code == status
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['referrer-policy'] == 'no-referrer'
    envelope = response.json()
    identifier = envelope['meta']['request_id'] if status == 200 else envelope['error']['request_id']
    assert identifier == response.headers['x-request-id']
    return envelope['data'] if status == 200 else envelope['error']


def test_actual_published_binding_is_persisted_and_replays_minimal_original_context(assessment_case_factory, pg_engine):
    case = assessment_case_factory()
    result = case.service.evaluate(case.principal, case.request)
    assert result.eligibility.status == 'eligible' and result.eligibility.evaluation.truth == 'true'
    assert result.current_validity == 'current' and result.binding_mode == 'test_fixture'
    assert case.release.ruleset_version is None
    saved = case.service.get_assessment(case.principal, result.assessment_id)
    replay = case.service.replay(case.principal, result.assessment_id, ReplayRequest(confirmed=True))
    assert saved.eligibility == replay.eligibility == result.eligibility
    assert saved.result_sha256 == replay.result_sha256 == result.result_sha256 and replay.replayed
    rows = records(pg_engine)
    assert len(rows) == 1 and rows[0].audit_event_id
    context = rows[0].replay_snapshot['context']
    assert len(context['fields']) == 1 and context['fields'][0]['field']['key'] == 'gaokao_total'
    serialized = json.dumps(rows[0].payload)
    for excluded in ('owner_user_id', 'file_id', 'storage_path', 'entry_url', 'quote', 'weekly_hours'):
        assert '"'+excluded+'"' not in serialized


@pytest.mark.parametrize('binding', [False, True])
def test_facts_only_or_wrong_scope_does_not_create_formal_rules(assessment_case_factory, binding):
    case = assessment_case_factory(binding=binding)
    request = case.request
    if binding:
        request = request.model_copy(update={'channel': None})
    result = case.service.evaluate(case.principal, request)
    assert result.eligibility.status == 'unknown' and result.eligibility.evaluation is None
    assert result.ruleset_version is None and result.binding_mode == 'unavailable'
    assert result.eligibility.reason in {'RULESET_UNAVAILABLE', 'SCOPE_UNAVAILABLE'}
    forged = AssessmentPolicy(enabled=True).model_copy(update={'real_assessments_ready':True})
    denied(lambda: EligibilityService(case.profiles, case.releases, case.service.store,
        forged), 503)


def test_false_rule_and_missing_achieved_never_consume_prediction(assessment_case_factory):
    rule = {'op':'gte','field':{'name':'assessment','key':'gaokao_total','basis':'achieved'},
        'value':{'kind':'decimal','value':'700','unit':'points','scale':'750'}}
    case = assessment_case_factory(expression=rule)
    result = case.service.evaluate(case.principal, case.request)
    assert result.eligibility.status == 'ineligible'
    payload = case.profile.profile.model_dump(mode='json')
    payload['assessments']['gaokao_total']['achieved'] = {'status':'pending','value':None,'scale':None,'unit':None}
    updated = case.profiles.append_version(case.principal, case.profile.profile_id,
        AppendInput(profile=payload, confirmed=True, expected_current_version=1)).version
    request = case.request.model_copy(update={'profile_version_id':updated.version_id})
    unknown = case.service.evaluate(case.principal, request)
    assert unknown.eligibility.status == 'unknown' and unknown.eligibility.obligations == ()


def test_explicit_policy_descriptor_and_date_evidence_are_required_for_conditional(assessment_case_factory):
    rule = {'op':'gte','field':{'name':'assessment','key':'math','basis':'achieved'},
        'value':{'kind':'decimal','value':'600','unit':'points','scale':'750'}}
    case = assessment_case_factory(expression=rule, deferral=True)
    result = case.service.evaluate(case.principal, case.request)
    assert result.eligibility.status == 'conditional'
    assert tuple(item.assessment_key for item in result.eligibility.obligations) == ('math',)
    replay = case.service.replay(case.principal, result.assessment_id, ReplayRequest(confirmed=True))
    assert replay.eligibility == result.eligibility


def test_profile_append_preserves_history_but_requires_current_version_for_new_check(assessment_case_factory, pg_engine):
    case = assessment_case_factory()
    first = case.service.evaluate(case.principal, case.request)
    payload = case.profile.profile.model_dump(mode='json')
    payload['assessments']['gaokao_total']['achieved']['value'] = '0'
    updated = case.profiles.append_version(case.principal, case.profile.profile_id,
        AppendInput(profile=payload, confirmed=True, expected_current_version=1)).version
    saved = case.service.get_assessment(case.principal, first.assessment_id)
    assert saved.eligibility.status == 'eligible' and saved.current_validity == 'needs_review'
    replay = case.service.replay(case.principal, first.assessment_id, ReplayRequest(confirmed=True))
    assert replay.result_sha256 == first.result_sha256 and replay.current_validity == 'needs_review'
    denied(lambda: case.service.evaluate(case.principal, case.request), 409)
    assert len(records(pg_engine)) == 1
    latest = case.service.evaluate(case.principal, case.request.model_copy(update={'profile_version_id':updated.version_id}))
    assert latest.eligibility.status == 'ineligible' and latest.current_validity == 'current'


def test_new_http_requires_current_cookie_csrf_explicit_body_and_exact_owner(assessment_case_factory, actor_factory, pg_engine):
    case = assessment_case_factory()
    app = create_assessments_v2_app(case.service.auth_service.runtime_settings,
        identity_service=case.service.auth_service, profile_service=case.profiles, assessment_service=case.service)
    with TestClient(app, base_url='https://app.test.invalid') as client:
        request_headers = headers(client, case.owner)
        safe(client.get('/eligibility/context'), 200)
        payload = case.request.model_dump(mode='json')
        safe(client.post('/eligibility/evaluations', json=payload), 403)
        safe(client.post('/eligibility/evaluations', json={**payload,'owner_user_id':str(case.principal.user_id)}, headers=request_headers), 422)
        safe(client.post('/eligibility/evaluations', json={**payload,'confirmed':1}, headers=request_headers), 422)
        first = safe(client.post('/eligibility/evaluations', json=payload, headers=request_headers), 200)
        identifier = first['assessment_id']
        assert client.get('/eligibility/evaluations/'+identifier).json()['meta']['profile_version_id'] == str(case.profile.version_id)
        safe(client.post('/eligibility/evaluations/'+identifier+'/replay', headers=request_headers), 422)
        replay = safe(client.post('/eligibility/evaluations/'+identifier+'/replay', json={'confirmed':True}, headers=request_headers), 200)
        assert replay['replayed'] and replay['result_sha256'] == first['result_sha256']
        outsider = actor_factory()
        headers(client, outsider)
        safe(client.get('/eligibility/evaluations/'+identifier), 403)
        client.cookies.clear()
        safe(client.get('/eligibility/evaluations/'+identifier), 401)
    assert len(records(pg_engine)) == 1


def test_routed_mapper_is_rejected_before_foreign_connection_and_caller_tx_aborts(assessment_case_factory, pg_engine):
    case = assessment_case_factory()
    foreign = create_engine(pg_engine.url, hide_parameters=True)
    connected = []
    def refused(*args):
        connected.append(True)
        raise AssertionError('Foreign connection must not occur')
    event.listen(foreign, 'do_connect', refused)
    try:
        with Session(pg_engine, binds={EligibilityAssessment:foreign}) as session:
            session.begin()
            denied(lambda: case.service.evaluate(case.principal, case.request, session=session), 503)
            assert not session.in_transaction() and connected == []
            session.commit()
        assert records(pg_engine) == []
        with Session(pg_engine) as session:
            session.begin()
            case.service.evaluate(case.principal, case.request, session=session)
            denied(lambda: case.service.replay(case.principal, uuid4(), {'confirmed':1}, session=session), 422)
            assert not session.in_transaction()
            session.commit()
        assert records(pg_engine) == []
    finally:
        foreign.dispose()
