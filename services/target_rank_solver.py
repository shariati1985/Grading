"""Deterministic target-rank search using only the official ranking engine."""

from __future__ import annotations

import math

import pandas as pd

from domain.scenario_contracts import (
    IndicatorProposal,
    TargetRankRequest,
    TargetRankSolution,
    TargetRankStatus,
)
from engine.indicator_registry import INDICATOR_REGISTRY, PROFIT_LOSS_KEY
from engine.ranking_engine import BRANCH_ID, INDICATOR_KEYS, ModelOutputs, prepare_input_data, run_ranking_model
from engine.scenario_engine import ScenarioChange, apply_scenario_changes
from services.scenario_execution_service import branch_comparison_from_results
from engine.comparison_engine import compare_model_outputs

COUNT_INDICATOR_IDS = frozenset({"deposit_count", "loan_count", "commitment_count"})


def applicable_count_value(numeric_candidate: float) -> int:
    """V1 operational policy: round positive-growth count proposals upward.

    The project has no pre-existing count rounding policy. Ceiling avoids
    presenting fractional counts and does not reduce the improvement that the
    bounded search established.
    """
    return math.ceil(numeric_candidate)


class TargetRankSolver:
    """Find the smallest bounded common growth percentage for a target rank.

    Count indicators retain the project's existing float policy. A zero raw value
    remains zero under relative growth, including zero Profit/Loss; no artificial
    absolute increment is invented.
    """

    def solve_target_rank(
        self, request: TargetRankRequest, baseline_data: pd.DataFrame
    ) -> TargetRankSolution:
        baseline = prepare_input_data(baseline_data)
        validation = self._validate(request, baseline)
        if validation:
            return self._invalid(request, validation)

        baseline_outputs = run_ranking_model(baseline)
        baseline_row = self._branch_result(baseline_outputs, request.focus_branch_id)
        baseline_rank = int(baseline_row["rank"])
        baseline_score = float(baseline_row["final_score"])
        selected = tuple(request.selected_indicator_ids)
        if request.target_rank >= baseline_rank:
            comparison = compare_model_outputs(baseline_outputs, baseline_outputs)
            return TargetRankSolution(
                TargetRankStatus.NO_CHANGE_REQUIRED, str(request.focus_branch_id),
                baseline_rank, request.target_rank, baseline_rank, baseline_score,
                baseline_score, 0.0, selected, (), 0, True,
                "The focus branch already meets the requested target rank.",
                baseline.copy(deep=True), baseline_outputs, baseline_outputs,
                branch_comparison_from_results(comparison, request.focus_branch_id),
            )

        iterations = 0
        high = float(request.max_growth_percent)
        high_data, high_outputs = self._run_candidate(request, baseline, high)
        iterations += 1
        high_rank = int(self._branch_result(high_outputs, request.focus_branch_id)["rank"])
        if high_rank > request.target_rank:
            return self._solution(
                request, baseline, baseline_outputs, high_data, high_outputs, high,
                iterations, TargetRankStatus.TARGET_NOT_REACHABLE, False,
                "Target rank is not reachable within max_growth_percent.",
            )

        low = float(request.minimum_growth_percent)
        best_data, best_outputs = high_data, high_outputs
        if low > 0 and iterations < request.max_iterations:
            low_data, low_outputs = self._run_candidate(request, baseline, low)
            iterations += 1
            if int(self._branch_result(low_outputs, request.focus_branch_id)["rank"]) <= request.target_rank:
                return self._solution(
                    request, baseline, baseline_outputs, low_data, low_outputs, low,
                    iterations, TargetRankStatus.TARGET_REACHED, True,
                    "minimum_growth_percent already achieves the requested target rank.",
                )

        precision = min(request.search_precision_percent, request.tolerance_percent)
        while high - low > precision and iterations < request.max_iterations:
            middle = (low + high) / 2.0
            candidate_data, candidate_outputs = self._run_candidate(request, baseline, middle)
            iterations += 1
            rank = int(self._branch_result(candidate_outputs, request.focus_branch_id)["rank"])
            if rank <= request.target_rank:
                high = middle
                best_data, best_outputs = candidate_data, candidate_outputs
            else:
                low = middle

        converged = high - low <= precision
        status = (
            TargetRankStatus.TARGET_REACHED
            if converged else TargetRankStatus.MAX_ITERATIONS_REACHED
        )
        message = (
            "Smallest bounded common growth found within configured precision."
            if converged else "Target was reached, but search precision was not achieved before max_iterations."
        )
        return self._solution(
            request, baseline, baseline_outputs, best_data, best_outputs, high,
            iterations, status, True, message,
        )

    @staticmethod
    def _validate(request: TargetRankRequest, baseline: pd.DataFrame) -> str | None:
        if isinstance(request.target_rank, bool) or not isinstance(request.target_rank, int):
            return "target_rank must be an integer"
        if request.target_rank < 1:
            return "target_rank must be at least 1"
        if str(request.focus_branch_id) not in set(baseline[BRANCH_ID]):
            return "focus_branch_id is not present in baseline data"
        selected = tuple(request.selected_indicator_ids)
        if not selected:
            return "At least one selected indicator is required"
        if len(selected) != len(set(selected)):
            return "selected_indicator_ids must be unique"
        unknown = set(selected) - set(INDICATOR_KEYS)
        if unknown:
            return "Unknown selected indicators: " + ", ".join(sorted(unknown))
        if PROFIT_LOSS_KEY in selected and not request.allow_profit_loss:
            return "Profit/Loss selection requires allow_profit_loss=True"
        numeric = (
            request.minimum_growth_percent, request.max_growth_percent,
            request.tolerance_percent, request.search_precision_percent,
        )
        if not all(math.isfinite(float(value)) for value in numeric):
            return "Growth and precision values must be finite"
        if request.minimum_growth_percent < 0 or request.max_growth_percent < request.minimum_growth_percent:
            return "Growth bounds are invalid"
        if request.tolerance_percent <= 0 or request.search_precision_percent <= 0:
            return "Tolerance and search precision must be positive"
        if isinstance(request.max_iterations, bool) or not isinstance(request.max_iterations, int) or request.max_iterations < 1:
            return "max_iterations must be a positive integer"
        return None

    def _run_candidate(
        self, request: TargetRankRequest, baseline: pd.DataFrame, percent: float
    ) -> tuple[pd.DataFrame, ModelOutputs]:
        branch = baseline.loc[baseline[BRANCH_ID].eq(str(request.focus_branch_id))].iloc[0]
        changes: list[ScenarioChange] = []
        for indicator_id in dict.fromkeys(request.selected_indicator_ids):
            raw = float(branch[indicator_id])
            ratio = percent / 100.0
            if indicator_id == PROFIT_LOSS_KEY and raw < 0:
                proposed = raw + abs(raw) * ratio
            else:
                proposed = raw * (1.0 + ratio)
            changes.append(
                ScenarioChange(
                    str(request.focus_branch_id), str(branch["branch_name"]), indicator_id,
                    raw, proposed, proposed - raw,
                    0.0 if raw == 0 else (proposed - raw) / abs(raw) * 100.0,
                )
            )
        scenario = apply_scenario_changes(baseline, changes)
        return scenario, run_ranking_model(scenario)

    def _solution(
        self, request: TargetRankRequest, baseline: pd.DataFrame,
        baseline_outputs: ModelOutputs, scenario: pd.DataFrame,
        scenario_outputs: ModelOutputs, percent: float, iterations: int,
        status: TargetRankStatus, target_reached: bool, message: str,
    ) -> TargetRankSolution:
        numeric_scenario_outputs = scenario_outputs
        scenario, scenario_outputs = self._verify_applicable_count_values(
            request, baseline, scenario, scenario_outputs
        )
        baseline_row = self._branch_result(baseline_outputs, request.focus_branch_id)
        scenario_row = self._branch_result(scenario_outputs, request.focus_branch_id)
        verified_reached = int(scenario_row["rank"]) <= request.target_rank
        if target_reached and not verified_reached:
            status = TargetRankStatus.TARGET_NOT_REACHABLE
            message = "Applicable proposal did not achieve the target under official reranking."
        elif not target_reached and verified_reached:
            status = TargetRankStatus.MAX_ITERATIONS_REACHED
            message = (
                "Applicable count conversion reaches the target, but minimum growth "
                "was not established within search precision."
            )
        target_reached = verified_reached
        proposals = self._proposals(
            request, baseline_outputs, numeric_scenario_outputs, scenario_outputs
        )
        comparison = compare_model_outputs(baseline_outputs, scenario_outputs)
        return TargetRankSolution(
            status, str(request.focus_branch_id), int(baseline_row["rank"]),
            request.target_rank, int(scenario_row["rank"]),
            float(baseline_row["final_score"]), float(scenario_row["final_score"]),
            percent, tuple(dict.fromkeys(request.selected_indicator_ids)), proposals,
            iterations, target_reached, message, scenario, baseline_outputs,
            scenario_outputs, branch_comparison_from_results(comparison, request.focus_branch_id),
        )

    @staticmethod
    def _verify_applicable_count_values(
        request: TargetRankRequest, baseline: pd.DataFrame, scenario: pd.DataFrame,
        scenario_outputs: ModelOutputs,
    ) -> tuple[pd.DataFrame, ModelOutputs]:
        selected_counts = set(request.selected_indicator_ids) & COUNT_INDICATOR_IDS
        if not selected_counts:
            return scenario, scenario_outputs
        branch = scenario.loc[scenario[BRANCH_ID].eq(str(request.focus_branch_id))].iloc[0]
        changes = []
        for indicator_id in selected_counts:
            numeric = float(branch[indicator_id])
            applicable = float(applicable_count_value(numeric))
            if applicable != numeric:
                changes.append(
                    ScenarioChange(
                        str(request.focus_branch_id), str(branch["branch_name"]),
                        indicator_id, numeric, applicable, applicable - numeric,
                        0.0 if numeric == 0 else (applicable - numeric) / abs(numeric) * 100.0,
                    )
                )
        if not changes:
            return scenario, scenario_outputs
        applicable_scenario = apply_scenario_changes(scenario, changes)
        return applicable_scenario, run_ranking_model(applicable_scenario)

    @staticmethod
    def _proposals(
        request: TargetRankRequest, baseline: ModelOutputs,
        numeric_scenario: ModelOutputs, scenario: ModelOutputs,
    ) -> tuple[IndicatorProposal, ...]:
        keys = [BRANCH_ID, "indicator_key"]
        left = baseline.indicator_results.set_index(keys)
        numeric = numeric_scenario.indicator_results.set_index(keys)
        right = scenario.indicator_results.set_index(keys)
        proposals = []
        for indicator_id in request.selected_indicator_ids:
            key = (str(request.focus_branch_id), indicator_id)
            before, numeric_after, after = left.loc[key], numeric.loc[key], right.loc[key]
            raw, proposed = float(before["raw_value"]), float(after["raw_value"])
            is_count = indicator_id in COUNT_INDICATOR_IDS
            numeric_candidate = float(numeric_after["raw_value"])
            note = None
            if is_count:
                note = "Count proposal uses the named V1 ceiling-to-integer policy."
            elif indicator_id == PROFIT_LOSS_KEY and raw == 0:
                note = (
                    "Zero Profit/Loss was unchanged because percentage growth has "
                    "no non-zero base."
                )
            proposals.append(
                IndicatorProposal(
                    indicator_id, raw, numeric_candidate, proposed, is_count,
                    proposed - raw,
                    0.0 if raw == 0 else (proposed - raw) / abs(raw) * 100.0,
                    float(before["score"]), float(after["score"]),
                    float(before["weighted_score"]), float(after["weighted_score"]),
                    note,
                )
            )
        return tuple(proposals)

    @staticmethod
    def _branch_result(outputs: ModelOutputs, branch_id: str) -> pd.Series:
        return outputs.final_result.loc[
            outputs.final_result[BRANCH_ID].astype(str).eq(str(branch_id))
        ].iloc[0]

    @staticmethod
    def _invalid(request: TargetRankRequest, message: str) -> TargetRankSolution:
        return TargetRankSolution(
            TargetRankStatus.INVALID_REQUEST, str(request.focus_branch_id), None,
            request.target_rank, None, None, None, 0.0,
            tuple(request.selected_indicator_ids), (), 0, False, message,
        )


def solve_target_rank(
    request: TargetRankRequest, baseline_data: pd.DataFrame
) -> TargetRankSolution:
    return TargetRankSolver().solve_target_rank(request, baseline_data)
