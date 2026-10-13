"""Independent deadline roles, source calendars, and exact boundary checks."""

from datetime import date, datetime, time, timedelta, timezone

import pytest

from test_t27_input import NOW, deadline, decide, values


@pytest.mark.parametrize("hour,status,reason", [(0, "allowed", "ALLOWED"),
    (1, "unknown", "DEADLINE_UNCERTAIN"), (25, "unknown", "DEADLINE_EXPIRED")])
def test_date_only_uses_source_calendar_even_when_utc_is_a_different_day(hour, status, reason):
    request, bundle, policy = values()
    # In Shanghai this is Oct 10 00:00, while the UTC calendar still says Oct 9.
    at = datetime(2026, 10, 9, 15, tzinfo=timezone.utc) + timedelta(hours=hour)
    bound = deadline("language_supplement", identifier=21, day=date(2026, 10, 10), calendar="Asia/Shanghai")
    result = decide(request.model_copy(update={"assessment_at": at}),
        bundle.model_copy(update={"supplement_deadline": bound,
            "application_deadline": deadline("application_deadline", day=date(2026, 10, 20))}), policy)
    assert result.deferral_status == status and result.reason == reason
    assert bound.date_event.local_time is None and bound.date_event.calculated_utc_instant is None
    assert bound.date_event.utc_instant is None


@pytest.mark.parametrize("offset,status,reason", [(-1, "allowed", "ALLOWED"),
    (0, "unknown", "DEADLINE_UNCERTAIN"), (1, "unknown", "DEADLINE_EXPIRED")])
def test_exact_deadline_equality_is_uncertain_without_an_inclusion_policy(offset, status, reason):
    request, bundle, policy = values()
    bound = deadline("language_supplement", identifier=21, day=NOW.date(), clock=time(12),
        precision="second", calendar="UTC", zone="UTC")
    result = decide(request.model_copy(update={"assessment_at": NOW + timedelta(seconds=offset)}),
        bundle.model_copy(update={"supplement_deadline": bound}), policy)
    assert result.deferral_status == status and result.reason == reason


def test_policy_expiry_has_a_different_explicit_half_open_boundary():
    request, bundle, policy = values()
    request = request.model_copy(update={"assessment_at": bundle.valid_until})
    result = decide(request, bundle, policy)
    assert result.deferral_status == "unknown" and result.reason == "POLICY_EXPIRED"


def test_future_supplement_cannot_rescue_a_past_application_deadline():
    request, bundle, policy = values()
    application = deadline("application_deadline", day=date(2026, 10, 1))
    result = decide(request, bundle.model_copy(update={"application_deadline": application}), policy)
    assert result.reason == "DEADLINE_EXPIRED"
    assert result.application_deadline_status == "expired"
    assert result.supplement_deadline_status == "before"


def test_enrollment_can_explicitly_declare_the_application_deadline_inapplicable():
    request, bundle, policy = values(stage="enrollment", application_required=False)
    result = decide(request, bundle, policy)
    assert result.deferral_status == "allowed"
    assert result.application_deadline_status == "not_applicable"
    assert result.application_deadline_event_id is None
    result = decide(request.model_copy(update={"stage": "application"}),
        bundle.model_copy(update={"stage": "application"}), policy)
    assert result.deferral_status == "unknown" and result.reason == "DEADLINE_MISSING"


@pytest.mark.parametrize("kind", ["equal_consideration", "materials_deadline", "offer_acceptance"])
def test_other_application_events_cannot_substitute_for_the_main_deadline(kind):
    request, bundle, policy = values()
    result = decide(request, bundle.model_copy(update={"application_deadline": deadline(kind)}), policy)
    assert result.deferral_status == "unknown" and result.reason == "DEADLINE_MISMATCH"


@pytest.mark.parametrize("calendar", [None, "Europe/Not_A_Zone"])
def test_missing_or_unknown_source_calendar_does_not_use_the_server_day(calendar):
    request, bundle, policy = values()
    bound = deadline("language_supplement", identifier=21, calendar=calendar)
    result = decide(request, bundle.model_copy(update={"supplement_deadline": bound}), policy)
    assert result.deferral_status == "unknown" and result.reason == "DEADLINE_UNCERTAIN"


@pytest.mark.parametrize("kind,expected", [("score_supplement", "allowed"), ("language_supplement", "unknown")])
def test_language_and_score_supplement_policies_are_not_interchangeable(kind, expected):
    request, bundle, policy = values(key="math")
    bound = deadline(kind, identifier=21)
    result = decide(request, bundle.model_copy(update={"supplement_deadline": bound}), policy)
    assert result.deferral_status == expected
