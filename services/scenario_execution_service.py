"""Backend orchestration for focus-only and multi-branch scenarios."""

from __future__ import annotations

import pandas as pd

from domain.scenario_contracts import (
    BranchScenarioComparison,
    BulkRule,
    ScenarioExecutionResult,
    ScenarioRequest,
    ScenarioType,
    TargetRankRequest,
    TargetRankSolution,
)
from engine.comparison_engine import ScenarioComparison, compare_model_outputs
from engine.ranking_engine import BRANCH_ID, prepare_input_data, run_ranking_model
from engine.scenario_engine import ScenarioChange, apply_scenario_changes
from engine.scenario_rule_engine import IndicatorRule, ManualOverride, ScenarioRuleEngine
from services.selection_scope import SelectionResolver
from services.user_context import CurrentUser


class ScenarioRequestValidationError(ValueError):
    """Raised before ranking when scenario mode contracts are invalid."""


def branch_comparison_from_results(
    comparison: ScenarioComparison, branch_id: str
) -> BranchScenarioComparison:
    branch = comparison.branch_comparison.loc[
        comparison.branch_comparison[BRANCH_ID].astype(str).eq(str(branch_id))
    ]
    if len(branch) != 1:
        raise ValueError(f"Comparison missing branch: {branch_id}")
    row = branch.iloc[0]
    indicators = comparison.indicator_comparison.loc[
        comparison.indicator_comparison[BRANCH_ID].astype(str).eq(str(branch_id))
    ].to_dict("records")
    return BranchScenarioComparison(
        branch_id=str(branch_id),
        baseline_rank=int(row["baseline_rank"]),
        scenario_rank=int(row["scenario_rank"]),
        rank_change=int(row["rank_change"]),
        baseline_final_score=float(row["baseline_score"]),
        scenario_final_score=float(row["scenario_score"]),
        score_change=float(row["score_change"]),
        baseline_grade=str(row["baseline_grade"]),
        scenario_grade=str(row["scenario_grade"]),
        indicator_comparisons=tuple(indicators),
    )


class ScenarioExecutionService:
    """Execute scenarios while the official engine remains the sole calculator."""

    def solve_target_rank(
        self, request: TargetRankRequest, baseline_data: pd.DataFrame
    ) -> TargetRankSolution:
        """Route target-rank execution through the application service boundary."""
        from services.target_rank_solver import solve_target_rank

        return solve_target_rank(request, baseline_data)

    def execute(
        self, request: ScenarioRequest, baseline_data: pd.DataFrame
    ) -> ScenarioExecutionResult:
        self._validate_request(request)
        focus_id = str(request.focus_branch_id).strip()
        baseline = prepare_input_data(baseline_data)
        if not focus_id or focus_id not in set(baseline[BRANCH_ID]):
            raise ScenarioRequestValidationError("A valid focus_branch_id is required")
        if request.scenario_type is ScenarioType.TARGET_RANK:
            raise ScenarioRequestValidationError(
                "TARGET_RANK must be executed by TargetRankSolver"
            )

        changes = (
            self._focus_changes(request, baseline)
            if request.scenario_type is ScenarioType.FOCUS_BRANCH_ONLY
            else self._multi_changes(request, baseline)
        )
        scenario = apply_scenario_changes(baseline, changes)
        baseline_outputs = run_ranking_model(baseline)
        scenario_outputs = run_ranking_model(scenario)
        comparison = compare_model_outputs(baseline_outputs, scenario_outputs)
        modified_ids = list(dict.fromkeys(change.branch_id for change in changes))
        modified = tuple(
            branch_comparison_from_results(comparison, branch_id)
            for branch_id in modified_ids
        )
        affected_rows = comparison.branch_comparison.loc[
            comparison.branch_comparison["rank_change"].ne(0)
            | comparison.branch_comparison["score_change"].ne(0)
            | comparison.branch_comparison["grade_changed"]
        ]
        rank_affected = tuple(
            branch_comparison_from_results(comparison, str(branch_id))
            for branch_id in affected_rows[BRANCH_ID]
        )
        return ScenarioExecutionResult(
            request=request,
            changes=tuple(changes),
            baseline_data=baseline.copy(deep=True),
            scenario_data=scenario,
            baseline_outputs=baseline_outputs,
            scenario_outputs=scenario_outputs,
            comparison_results=comparison,
            focus_branch_comparison=branch_comparison_from_results(comparison, focus_id),
            modified_branches=modified,
            rank_affected_branches=rank_affected,
        )

    @staticmethod
    def _validate_request(request: ScenarioRequest) -> None:
        if not isinstance(request.scenario_type, ScenarioType):
            raise ScenarioRequestValidationError("scenario_type is invalid")
        if not request.scenario_name.strip():
            raise ScenarioRequestValidationError("scenario_name is required")
        if not str(request.focus_branch_id).strip():
            raise ScenarioRequestValidationError("focus_branch_id is required")
        if request.scenario_type is ScenarioType.FOCUS_BRANCH_ONLY:
            if request.target_rank_request is not None or request.bulk_rules:
                raise ScenarioRequestValidationError(
                    "FOCUS_BRANCH_ONLY does not accept target-rank or bulk rules"
                )
            outside = [
                item for item in request.manual_overrides
                if str(item.branch_id) != str(request.focus_branch_id)
            ]
            if outside:
                raise ScenarioRequestValidationError(
                    "FOCUS_BRANCH_ONLY manual overrides must target the focus branch"
                )
        elif request.scenario_type is ScenarioType.MULTI_BRANCH:
            if request.target_rank_request is not None:
                raise ScenarioRequestValidationError(
                    "MULTI_BRANCH does not accept target_rank_request"
                )
        else:
            if request.target_rank_request is None:
                raise ScenarioRequestValidationError(
                    "TARGET_RANK requires target_rank_request"
                )
            if request.focus_branch_changes or request.bulk_rules or request.manual_overrides:
                raise ScenarioRequestValidationError(
                    "TARGET_RANK does not accept ordinary changes, bulk rules, or overrides"
                )
            if str(request.target_rank_request.focus_branch_id) != str(request.focus_branch_id):
                raise ScenarioRequestValidationError(
                    "TARGET_RANK request focus_branch_id must match ScenarioRequest"
                )

        for item in request.manual_overrides:
            if not str(item.branch_id).strip() or not str(item.indicator_key).strip():
                raise ScenarioRequestValidationError(
                    "ManualOverride must target exactly one branch and one indicator"
                )

    @staticmethod
    def _focus_changes(request: ScenarioRequest, baseline: pd.DataFrame) -> list[ScenarioChange]:
        overrides = [
            ManualOverride(
                str(request.focus_branch_id), change.indicator_id,
                change.operation, change.value, "focus_branch_only"
            )
            for change in request.focus_branch_changes
        ]
        overrides.extend(request.manual_overrides)
        return ScenarioRuleEngine.generate_changes(
            [str(request.focus_branch_id)], baseline, [], overrides
        )

    def _multi_changes(self, request: ScenarioRequest, baseline: pd.DataFrame) -> list[ScenarioChange]:
        change_map: dict[tuple[str, str], ScenarioChange] = {}
        bulk_targets: set[tuple[str, str]] = set()
        for rule in request.bulk_rules:
            branch_ids = self._resolve_rule_scope(rule, request, baseline)
            resolved_targets = {(branch_id, rule.indicator_id) for branch_id in branch_ids}
            overlap = bulk_targets & resolved_targets
            if overlap:
                branch_id, indicator_id = sorted(overlap)[0]
                raise ScenarioRequestValidationError(
                    "V1 forbids overlapping bulk rules for the same branch-indicator "
                    f"pair ({branch_id}, {indicator_id})"
                )
            bulk_targets.update(resolved_targets)
            generated = ScenarioRuleEngine.generate_changes(
                branch_ids, baseline,
                [IndicatorRule(rule.indicator_id, rule.operation, rule.value)],
            )
            for change in generated:
                key = (change.branch_id, change.indicator_key)
                change_map[key] = change

        focus_overrides = [
            ManualOverride(
                str(request.focus_branch_id), item.indicator_id,
                item.operation, item.value, "focus_branch_change"
            )
            for item in request.focus_branch_changes
        ]
        all_overrides = [*request.manual_overrides, *focus_overrides]
        if all_overrides:
            override_ids = list(dict.fromkeys(str(item.branch_id) for item in all_overrides))
            generated = ScenarioRuleEngine.generate_changes(
                override_ids, baseline, [], all_overrides
            )
            for change in generated:
                change_map[(change.branch_id, change.indicator_key)] = change
        return list(change_map.values())

    @staticmethod
    def _resolve_rule_scope(
        rule: BulkRule, request: ScenarioRequest, baseline: pd.DataFrame
    ) -> list[str]:
        user = CurrentUser("scenario", "Scenario", (), branch_id=str(request.focus_branch_id))
        return SelectionResolver.resolve(
            rule.target_scope,
            baseline,
            user,
            selected_branch_ids=list(rule.selected_branch_ids),
            selected_regions=list(rule.selected_regions),
        )
