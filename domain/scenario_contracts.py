"""Typed, UI-independent contracts for the three sensitivity modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd

from engine.comparison_engine import ScenarioComparison
from engine.ranking_engine import ModelOutputs
from engine.scenario_engine import ScenarioChange
from engine.scenario_rule_engine import ManualOverride, RuleOperation
from services.selection_scope import SelectionScope


class ScenarioType(str, Enum):
    FOCUS_BRANCH_ONLY = "FOCUS_BRANCH_ONLY"
    MULTI_BRANCH = "MULTI_BRANCH"
    TARGET_RANK = "TARGET_RANK"


class TargetRankStatus(str, Enum):
    TARGET_REACHED = "TARGET_REACHED"
    NO_CHANGE_REQUIRED = "NO_CHANGE_REQUIRED"
    TARGET_NOT_REACHABLE = "TARGET_NOT_REACHABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    MAX_ITERATIONS_REACHED = "MAX_ITERATIONS_REACHED"


@dataclass(frozen=True)
class IndicatorChange:
    indicator_id: str
    operation: RuleOperation
    value: float


@dataclass(frozen=True)
class BulkRule:
    indicator_id: str
    operation: RuleOperation
    value: float
    target_scope: SelectionScope
    selected_branch_ids: tuple[str, ...] = ()
    selected_regions: tuple[str, ...] = ()


@dataclass(frozen=True)
class TargetRankRequest:
    focus_branch_id: str
    target_rank: int
    selected_indicator_ids: tuple[str, ...]
    max_growth_percent: float
    tolerance_percent: float
    max_iterations: int
    minimum_growth_percent: float = 0.0
    search_precision_percent: float = 0.01
    allow_profit_loss: bool = False
    period: str | None = None


@dataclass(frozen=True)
class TargetRankPath:
    path_id: str
    display_name: str
    selected_indicator_ids: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class IndicatorProposal:
    indicator_id: str
    baseline_raw_value: float
    numeric_candidate_raw_value: float
    proposed_raw_value: float
    is_count_indicator: bool
    absolute_change: float
    percent_change: float
    baseline_normalized_score: float | None = None
    scenario_normalized_score: float | None = None
    baseline_weighted_contribution: float | None = None
    scenario_weighted_contribution: float | None = None
    note: str | None = None


@dataclass(frozen=True)
class BranchScenarioComparison:
    branch_id: str
    baseline_rank: int
    scenario_rank: int
    rank_change: int
    baseline_final_score: float
    scenario_final_score: float
    score_change: float
    baseline_grade: str
    scenario_grade: str
    indicator_comparisons: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class TargetRankSolution:
    status: TargetRankStatus
    focus_branch_id: str
    baseline_rank: int | None
    target_rank: int
    achieved_rank: int | None
    baseline_score: float | None
    achieved_score: float | None
    required_common_growth_percent: float
    selected_indicator_ids: tuple[str, ...]
    indicator_proposals: tuple[IndicatorProposal, ...]
    iterations: int
    target_reached: bool
    message: str
    scenario_data: pd.DataFrame | None = field(default=None, repr=False, compare=False)
    baseline_outputs: ModelOutputs | None = field(default=None, repr=False, compare=False)
    scenario_outputs: ModelOutputs | None = field(default=None, repr=False, compare=False)
    comparison: BranchScenarioComparison | None = field(default=None, repr=False)

    @property
    def rank_change(self) -> int | None:
        """Positive means improvement: baseline_rank - achieved_rank."""
        if self.baseline_rank is None or self.achieved_rank is None:
            return None
        return self.baseline_rank - self.achieved_rank

    @property
    def minimum_growth_established(self) -> bool:
        """Whether required_common_growth_percent is precision-established."""
        return self.status in {
            TargetRankStatus.TARGET_REACHED,
            TargetRankStatus.NO_CHANGE_REQUIRED,
        }


@dataclass(frozen=True)
class TargetRankPathResult:
    path: TargetRankPath
    solution: TargetRankSolution

    @property
    def target_reached(self) -> bool:
        return self.solution.target_reached


@dataclass(frozen=True)
class TargetRankComparisonResult:
    focus_branch_id: str
    target_rank: int
    balanced_all_indicators: TargetRankPathResult
    user_selected_indicators: TargetRankPathResult
    baseline_outputs: ModelOutputs | None = field(default=None, repr=False, compare=False)
    target_reached: bool = False
    iterations: int = 0
    message: str = ""


@dataclass(frozen=True)
class ScenarioRequest:
    scenario_type: ScenarioType
    scenario_name: str
    focus_branch_id: str
    focus_branch_source: str | None = None
    period: str | None = None
    focus_branch_changes: tuple[IndicatorChange, ...] = ()
    bulk_rules: tuple[BulkRule, ...] = ()
    manual_overrides: tuple[ManualOverride, ...] = ()
    target_rank_request: TargetRankRequest | None = None
    optional_notes: str | None = None


@dataclass(frozen=True)
class ScenarioExecutionResult:
    request: ScenarioRequest
    changes: tuple[ScenarioChange, ...]
    baseline_data: pd.DataFrame
    scenario_data: pd.DataFrame
    baseline_outputs: ModelOutputs
    scenario_outputs: ModelOutputs
    comparison_results: ScenarioComparison
    focus_branch_comparison: BranchScenarioComparison
    modified_branches: tuple[BranchScenarioComparison, ...]
    rank_affected_branches: tuple[BranchScenarioComparison, ...]
    target_rank_solution: TargetRankSolution | None = None
