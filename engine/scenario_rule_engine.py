"""Pure bulk-rule and manual-override expansion with structured validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Iterable

import pandas as pd

from engine.indicator_registry import INDICATOR_REGISTRY, validate_indicator_value
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME
from engine.scenario_engine import ScenarioChange


class RuleOperation(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    PERCENT_CHANGE = "PERCENT_CHANGE"
    ABSOLUTE_CHANGE = "ABSOLUTE_CHANGE"
    SET_VALUE = "SET_VALUE"


@dataclass(frozen=True)
class IndicatorRule:
    indicator_key: str
    operation: RuleOperation
    value: float


@dataclass(frozen=True)
class ManualOverride:
    branch_id: str
    indicator_key: str
    operation: RuleOperation
    value: float
    source: str = "manual_override"


@dataclass(frozen=True)
class RuleValidationIssue:
    branch_id: str | None
    branch_name: str | None
    indicator_key: str | None
    indicator_name: str | None
    baseline_value: Any
    operation: str | None
    input_value: Any
    calculated_value: Any
    code: str
    message: str


@dataclass(frozen=True)
class RulePreviewRow:
    branch_id: str
    branch_code: str
    branch_name: str
    indicator_key: str
    indicator_name: str
    baseline_value: Any
    bulk_rule_operation: str | None
    bulk_rule_input: Any
    manual_override_operation: str | None
    manual_override_input: Any
    final_value: Any
    change_source: str
    validation_status: str
    validation_message: str | None


@dataclass(frozen=True)
class RulePreview:
    selected_branch_count: int
    active_bulk_rule_count: int
    unchanged_indicator_count: int
    manual_override_count: int
    generated_change_count: int
    invalid_change_count: int
    rows: list[RulePreviewRow]
    changes: list[ScenarioChange]
    issues: list[RuleValidationIssue]

    @property
    def is_valid(self) -> bool:
        return not self.issues

    @property
    def invalid_branch_count(self) -> int:
        return len({issue.branch_id for issue in self.issues if issue.branch_id is not None})


class ScenarioRuleValidationError(ValueError):
    def __init__(self, issues: list[RuleValidationIssue]) -> None:
        self.issues = issues
        super().__init__(issues[0].message if issues else "Scenario rules are invalid")


class ScenarioRuleEngine:
    """Expand rules using manual_override > bulk_rule > baseline precedence."""

    @staticmethod
    def _operation_value(operation: RuleOperation, baseline: float, value: float) -> float:
        if operation is RuleOperation.NO_CHANGE:
            return baseline
        if operation is RuleOperation.PERCENT_CHANGE:
            return baseline * (1.0 + value / 100.0)
        if operation is RuleOperation.ABSOLUTE_CHANGE:
            return baseline + value
        return value

    @staticmethod
    def _finite(value: Any) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    @classmethod
    def preview(
        cls,
        selected_branch_ids: list[str],
        baseline_df: pd.DataFrame,
        rules: Iterable[IndicatorRule],
        overrides: Iterable[ManualOverride] = (),
    ) -> RulePreview:
        branch_ids = list(dict.fromkeys(map(str, selected_branch_ids)))
        rule_list = list(rules)
        override_list = list(overrides)
        issues: list[RuleValidationIssue] = []

        rule_map: dict[str, IndicatorRule] = {}
        for rule in rule_list:
            if rule.indicator_key in rule_map:
                issues.append(cls._definition_issue("DUPLICATE_RULE", rule.indicator_key))
            else:
                rule_map[rule.indicator_key] = rule
        override_map: dict[tuple[str, str], ManualOverride] = {}
        for override in override_list:
            key = (str(override.branch_id), override.indicator_key)
            if key in override_map:
                issues.append(
                    cls._definition_issue(
                        "DUPLICATE_OVERRIDE", override.indicator_key, str(override.branch_id)
                    )
                )
            else:
                override_map[key] = override

        for indicator_key in set(rule_map) | {item[1] for item in override_map}:
            if indicator_key not in INDICATOR_REGISTRY:
                issues.append(cls._definition_issue("UNKNOWN_INDICATOR", indicator_key))
        for item in [*rule_map.values(), *override_map.values()]:
            if not isinstance(item.operation, RuleOperation):
                issues.append(cls._definition_issue("UNKNOWN_OPERATION", item.indicator_key))
        required = {BRANCH_ID, BRANCH_NAME, *INDICATOR_REGISTRY}
        missing_columns = required - set(baseline_df.columns)
        if missing_columns:
            issues.append(
                cls._definition_issue("MISSING_COLUMNS", ", ".join(sorted(missing_columns)))
            )

        baseline_ids = baseline_df[BRANCH_ID].astype(str) if BRANCH_ID in baseline_df else pd.Series(dtype=str)
        duplicate_baseline = set(baseline_ids[baseline_ids.duplicated()].tolist())
        if duplicate_baseline:
            issues.append(cls._definition_issue("DUPLICATE_BASELINE_BRANCH", ", ".join(sorted(duplicate_baseline))))
        known_ids = set(baseline_ids)
        for branch_id in branch_ids:
            if branch_id not in known_ids:
                issues.append(cls._definition_issue("UNKNOWN_BRANCH", None, branch_id))
        for branch_id, _ in override_map:
            if branch_id not in branch_ids:
                issues.append(cls._definition_issue("OVERRIDE_OUTSIDE_SELECTION", None, branch_id))
        if issues:
            return cls._empty_preview(branch_ids, rule_map, override_map, issues)

        indexed = baseline_df.assign(**{BRANCH_ID: baseline_ids}).set_index(BRANCH_ID, drop=False)
        rows: list[RulePreviewRow] = []
        changes: list[ScenarioChange] = []
        for branch_id in branch_ids:
            branch = indexed.loc[branch_id]
            branch_name = str(branch[BRANCH_NAME])
            for indicator_key, definition in INDICATOR_REGISTRY.items():
                bulk = rule_map.get(indicator_key)
                override = override_map.get((branch_id, indicator_key))
                selected = override or bulk
                source = override.source if override else "bulk_rule" if bulk else "baseline"
                baseline = branch[indicator_key]
                row_issues: list[RuleValidationIssue] = []
                final: Any = baseline
                if not cls._finite(baseline):
                    row_issues.append(
                        cls._issue(branch_id, branch_name, indicator_key, baseline, selected, None, "INVALID_BASELINE")
                    )
                elif selected is not None and not cls._finite(selected.value):
                    row_issues.append(
                        cls._issue(branch_id, branch_name, indicator_key, baseline, selected, None, "INVALID_INPUT")
                    )
                elif selected is not None:
                    final = cls._operation_value(selected.operation, float(baseline), float(selected.value))
                    if not cls._finite(final):
                        row_issues.append(
                            cls._issue(branch_id, branch_name, indicator_key, baseline, selected, final, "NON_FINITE_FINAL")
                        )
                    elif validate_indicator_value(indicator_key, final) is not None:
                        row_issues.append(
                            cls._issue(branch_id, branch_name, indicator_key, baseline, selected, final, "BELOW_MINIMUM")
                        )
                issues.extend(row_issues)
                message = row_issues[0].message if row_issues else None
                rows.append(
                    RulePreviewRow(
                        branch_id, branch_id, branch_name, indicator_key, definition.display_name,
                        baseline, bulk.operation.value if bulk else None, bulk.value if bulk else None,
                        override.operation.value if override else None, override.value if override else None,
                        final, source, "invalid" if row_issues else "valid", message,
                    )
                )
                if selected is not None and not row_issues and float(final) != float(baseline):
                    changes.append(
                        ScenarioChange(
                            branch_id, branch_name, indicator_key, float(baseline), float(final),
                            float(final) - float(baseline),
                            math.nan if float(baseline) == 0 else ((float(final) - float(baseline)) / float(baseline)) * 100,
                        )
                    )
        return RulePreview(
            len(branch_ids), len(rule_map), len(INDICATOR_REGISTRY) - len(rule_map),
            len(override_map), len(changes), len(issues), rows, changes, issues
        )

    @classmethod
    def generate_changes(cls, *args: Any, **kwargs: Any) -> list[ScenarioChange]:
        preview = cls.preview(*args, **kwargs)
        if not preview.is_valid:
            raise ScenarioRuleValidationError(preview.issues)
        return preview.changes

    @staticmethod
    def serialize_rules(rules: Iterable[IndicatorRule]) -> list[dict[str, Any]]:
        return [{**asdict(item), "operation": item.operation.value} for item in rules]

    @staticmethod
    def serialize_overrides(overrides: Iterable[ManualOverride]) -> list[dict[str, Any]]:
        return [{**asdict(item), "operation": item.operation.value} for item in overrides]

    @classmethod
    def _issue(cls, branch_id: str, branch_name: str, indicator_key: str, baseline: Any, selected: Any, final: Any, code: str) -> RuleValidationIssue:
        definition = INDICATOR_REGISTRY[indicator_key]
        if code == "BELOW_MINIMUM":
            message = f"مقدار نهایی شاخص «{definition.display_name}» برای شعبه «{branch_name}» نمی‌تواند کمتر از صفر باشد."
        elif code == "INVALID_BASELINE":
            message = f"مقدار مبنای شاخص «{definition.display_name}» برای شعبه «{branch_name}» معتبر نیست."
        else:
            message = f"مقدار محاسبه‌شده شاخص «{definition.display_name}» برای شعبه «{branch_name}» معتبر نیست."
        return RuleValidationIssue(branch_id, branch_name, indicator_key, definition.display_name, baseline, selected.operation.value if selected else None, selected.value if selected else None, final, code, message)

    @staticmethod
    def _definition_issue(code: str, indicator_key: str | None, branch_id: str | None = None) -> RuleValidationIssue:
        return RuleValidationIssue(branch_id, None, indicator_key, None, None, None, None, None, code, f"تعریف قانون سناریو نامعتبر است ({code}).")

    @staticmethod
    def _empty_preview(branch_ids: list[str], rules: dict[str, IndicatorRule], overrides: dict[tuple[str, str], ManualOverride], issues: list[RuleValidationIssue]) -> RulePreview:
        return RulePreview(len(branch_ids), len(rules), len(INDICATOR_REGISTRY) - len(rules), len(overrides), 0, len(issues), [], [], issues)
