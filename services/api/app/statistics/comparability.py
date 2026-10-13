from .cutoffs import Cutoff
from .admissions import AdmissionObservation


def result(status, reason):
    return {"status": status, "reason": reason, "definition_only": True,
            "current_authority_established": False, "qualification_modified": False}


def compare_statistics(left, right):
    if type(left) not in (Cutoff, AdmissionObservation) or type(right) not in (Cutoff, AdmissionObservation):
        return result("unknown", "unsupported_definition")
    left, right = type(left).model_validate(left), type(right).model_validate(right)
    if type(left) is not type(right):
        return result("not_comparable", "different_observation_family")
    if left.is_synthetic != right.is_synthetic:
        return result("not_comparable", "different_data_mode")
    if type(left) is AdmissionObservation:
        # Unresolved annual codes and unspecified single-subject definitions are not joinable.
        return result("unknown", "mapping_or_subject_definition_unreviewed")
    if any(value is None for value in (left.value, right.value, left.max_score, right.max_score,
                                      left.bonus_definition, right.bonus_definition, left.scope.reform_ref, right.scope.reform_ref)) or "other" in (left.line_kind, right.line_kind):
        return result("unknown", "missing_definition")
    if (left.scope, left.line_kind, left.unit, left.max_score, left.bonus_definition) != (right.scope, right.line_kind, right.unit, right.max_score, right.bonus_definition):
        return result("not_comparable", "different_exam_or_line_definition")
    if left.original_label != right.original_label:
        return result("limited", "original_labels_need_review")
    return result("comparable", "same_reported_definition")
