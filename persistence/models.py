"""Typed domain records persisted for saved scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ScenarioRecord:
    scenario_id: str
    scenario_name: str
    baseline_period: str
    owner_user_id: str
    owner_display_name: str
    status: str
    visibility: str
    model_version: str
    weights_version: str
    created_at: datetime
    updated_at: datetime
    row_version: int
    selected_branch_ids: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioChangeRecord:
    scenario_id: str
    branch_id: str
    branch_name: str
    indicator_key: str
    baseline_value: float
    scenario_value: float
    absolute_change: float
    percentage_change: float
    edit_mode: str = "direct"


@dataclass(frozen=True)
class ScenarioResultSummary:
    scenario_id: str
    branch_id: str
    baseline_score: float
    scenario_score: float
    baseline_rank: int
    scenario_rank: int
    baseline_grade: str
    scenario_grade: str
    rank_change: int
    score_change: float
