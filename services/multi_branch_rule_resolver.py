"""Pure resolver for multi-branch rule precedence and raw scenario values."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math

import pandas as pd

from domain.multi_branch_contracts import (
    BranchException,
    EffectiveChange,
    EffectiveChangeSource,
    MultiBranchScenarioV1,
    PercentageDirection,
    PercentageRule,
    PrimaryBranchOverride,
)
from engine.indicator_registry import INDICATOR_REGISTRY, validate_indicator_value
from engine.ranking_engine import BRANCH_ID


class MultiBranchRuleValidationError(ValueError):
    def __init__(self, issues: Iterable[str]) -> None:
        self.issues = tuple(issues)
        super().__init__(self.issues[0] if self.issues else "Invalid multi-branch scenario")


@dataclass(frozen=True)
class ResolvedMultiBranchScenario:
    scenario_data: pd.DataFrame
    manifest: tuple[EffectiveChange, ...]


class MultiBranchRuleResolver:
    """Resolve primary explicit > branch exception > general > baseline."""

    @classmethod
    def resolve(
        cls, scenario: MultiBranchScenarioV1, eligible_baseline: pd.DataFrame
    ) -> ResolvedMultiBranchScenario:
        issues = cls._validate_definition(scenario, eligible_baseline)
        if issues:
            raise MultiBranchRuleValidationError(issues)

        general = {rule.indicator_key: rule for rule in scenario.general_rules}
        exceptions = {
            (exception.branch_code, rule.indicator_key): rule
            for exception in scenario.branch_exceptions
            for rule in exception.indicator_rules
        }
        explicit = {
            override.indicator_key: override
            for override in scenario.primary_branch_overrides
        }
        scenario_data = eligible_baseline.copy(deep=True)
        scenario_data[BRANCH_ID] = scenario_data[BRANCH_ID].astype(str)
        manifest: list[EffectiveChange] = []

        for row_index, row in scenario_data.iterrows():
            branch_code = str(row[BRANCH_ID])
            for indicator_key in INDICATOR_REGISTRY:
                baseline = float(row[indicator_key])
                override = explicit.get(indicator_key) if branch_code == scenario.primary_branch_code else None
                exception = exceptions.get((branch_code, indicator_key))
                rule = exception or general.get(indicator_key)
                if override is not None:
                    value = float(override.resolved_raw_value)
                    source = EffectiveChangeSource.PRIMARY_EXPLICIT
                    effective_percentage = cls._derived_percentage(baseline, value)
                elif rule is not None:
                    value = cls._apply_percentage(baseline, rule)
                    source = (
                        EffectiveChangeSource.BRANCH_EXCEPTION
                        if exception is not None
                        else EffectiveChangeSource.GENERAL_RULE
                    )
                    effective_percentage = cls._signed_percentage(rule)
                else:
                    value = baseline
                    source = EffectiveChangeSource.UNCHANGED
                    effective_percentage = None
                validation_code = validate_indicator_value(indicator_key, value)
                if validation_code is not None or not math.isfinite(value):
                    raise MultiBranchRuleValidationError(
                        [f"{branch_code}:{indicator_key}:{validation_code or 'NON_FINITE_VALUE'}"]
                    )
                scenario_data.at[row_index, indicator_key] = value
                manifest.append(
                    EffectiveChange(
                        branch_code=branch_code,
                        indicator_key=indicator_key,
                        baseline_value=baseline,
                        scenario_value=value,
                        effective_source=source,
                        effective_percentage=effective_percentage,
                        explicit_input_mode=override.input_mode if override else None,
                        explicit_input_value=override.input_value if override else None,
                    )
                )
        return ResolvedMultiBranchScenario(scenario_data, tuple(manifest))

    @staticmethod
    def _apply_percentage(baseline: float, rule: PercentageRule) -> float:
        factor = 1.0 + rule.percentage / 100.0
        if rule.direction is PercentageDirection.DECREASE:
            factor = 1.0 - rule.percentage / 100.0
        return baseline * factor

    @staticmethod
    def _signed_percentage(rule: PercentageRule) -> float:
        return rule.percentage if rule.direction is PercentageDirection.INCREASE else -rule.percentage

    @staticmethod
    def _derived_percentage(baseline: float, value: float) -> float | None:
        return None if baseline == 0 else ((value - baseline) / baseline) * 100.0

    @classmethod
    def _validate_definition(
        cls, scenario: MultiBranchScenarioV1, baseline: pd.DataFrame
    ) -> list[str]:
        issues: list[str] = []
        required = {BRANCH_ID, *INDICATOR_REGISTRY}
        missing = required - set(baseline.columns)
        if missing:
            issues.append(f"MISSING_COLUMNS:{','.join(sorted(missing))}")
            return issues
        branch_codes = baseline[BRANCH_ID].astype(str)
        if branch_codes.duplicated().any():
            issues.append("DUPLICATE_ELIGIBLE_BRANCH")
        known = set(branch_codes)
        if scenario.primary_branch_code not in known:
            issues.append("UNKNOWN_PRIMARY_BRANCH")
        if scenario.population_definition.expected_branch_count is not None and len(baseline) != scenario.population_definition.expected_branch_count:
            issues.append("POPULATION_COUNT_MISMATCH")
        cls._validate_rules(scenario.general_rules, "GENERAL", issues)
        seen_branches: set[str] = set()
        for exception in scenario.branch_exceptions:
            if exception.branch_code in seen_branches:
                issues.append(f"DUPLICATE_EXCEPTION_BRANCH:{exception.branch_code}")
            seen_branches.add(exception.branch_code)
            if exception.branch_code not in known:
                issues.append(f"UNKNOWN_EXCEPTION_BRANCH:{exception.branch_code}")
            cls._validate_rules(exception.indicator_rules, f"EXCEPTION:{exception.branch_code}", issues)
        seen_overrides: set[str] = set()
        for override in scenario.primary_branch_overrides:
            if override.indicator_key not in INDICATOR_REGISTRY:
                issues.append(f"UNKNOWN_OVERRIDE_INDICATOR:{override.indicator_key}")
            if override.indicator_key in seen_overrides:
                issues.append(f"DUPLICATE_PRIMARY_OVERRIDE:{override.indicator_key}")
            seen_overrides.add(override.indicator_key)
            if not cls._finite(override.input_value) or not cls._finite(override.resolved_raw_value):
                issues.append(f"INVALID_PRIMARY_OVERRIDE:{override.indicator_key}")
        for branch_code, row in baseline.assign(**{BRANCH_ID: branch_codes}).set_index(BRANCH_ID).iterrows():
            for indicator_key in INDICATOR_REGISTRY:
                if not cls._finite(row[indicator_key]):
                    issues.append(f"INVALID_BASELINE:{branch_code}:{indicator_key}")
        return issues

    @classmethod
    def _validate_rules(cls, rules: Iterable[PercentageRule], scope: str, issues: list[str]) -> None:
        seen: set[str] = set()
        for rule in rules:
            if rule.indicator_key not in INDICATOR_REGISTRY:
                issues.append(f"UNKNOWN_INDICATOR:{scope}:{rule.indicator_key}")
            if rule.indicator_key in seen:
                issues.append(f"DUPLICATE_RULE:{scope}:{rule.indicator_key}")
            seen.add(rule.indicator_key)
            if not cls._finite(rule.percentage) or rule.percentage < 0:
                issues.append(f"INVALID_PERCENTAGE:{scope}:{rule.indicator_key}")

    @staticmethod
    def _finite(value: object) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False
