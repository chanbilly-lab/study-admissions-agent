from .schemas import OutcomeMetric
from ..statistics.comparability import result


def compare_outcomes(left: OutcomeMetric, right: OutcomeMetric):
    left, right = OutcomeMetric.model_validate(left), OutcomeMetric.model_validate(right)
    if left.suppressed or right.suppressed or left.value is None or right.value is None:
        return result("unknown", "missing_or_suppressed_value")
    if (left.kind, left.unit, left.population.level, left.population.subject_ref) != (right.kind, right.unit, right.population.level, right.population.subject_ref):
        return result("not_comparable", "different_metric_or_population_level")
    critical = ("graduation_cohort", "degree", "study_mode", "observation_start", "observation_end", "method", "sample_definition", "denominator_definition")
    if any(getattr(item.population, key) is None for item in (left, right) for key in critical):
        return result("unknown", "missing_population_definition")
    if any(getattr(left.population, key) != getattr(right.population, key) for key in critical) or left.definition != right.definition:
        return result("not_comparable", "different_cohort_window_or_method")
    if left.kind == "salary":
        if any(item.currency is None or item.salary_period == "unknown" or item.tax_basis == "unknown" for item in (left, right)):
            return result("unknown", "missing_salary_definition")
        if (left.currency, left.salary_period, left.tax_basis) != (right.currency, right.salary_period, right.tax_basis):
            return result("not_comparable", "different_currency_period_or_tax")
    counts = ("sample_count", "response_count", "denominator")
    if any(getattr(item.population, key) is None for item in (left, right) for key in counts):
        return result("unknown", "missing_sample_or_denominator")
    if any(getattr(left.population, key) != getattr(right.population, key) for key in counts):
        return result("limited", "different_reported_samples")
    return result("comparable", "same_reported_population_definition")
