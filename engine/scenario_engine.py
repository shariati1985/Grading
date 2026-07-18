"""Create complete scenario datasets from one or more branch edits."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from .ranking_engine import (
    BRANCH_ID,
    BRANCH_NAME,
    INDICATOR_KEYS,
    prepare_input_data,
)


@dataclass(frozen=True)
class ScenarioChange:
    """One direct indicator-value edit and its baseline-relative change."""

    branch_id: str
    branch_name: str
    indicator_key: str
    baseline_value: float
    scenario_value: float
    absolute_change: float
    percentage_change: float


def _numeric_value(value: object, *, field: str) -> float:
    """Return a finite float or raise a useful validation error."""
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric; got {value!r}") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{field} must be finite; got {value!r}")
    return numeric


def _validate_scenario_value(indicator_key: str, value: object) -> float:
    numeric = _numeric_value(value, field=f"scenario value for {indicator_key}")
    if numeric < 0 and indicator_key != "profit_loss":
        raise ValueError(f"Negative values are only allowed for profit_loss, not {indicator_key}")
    return numeric


def apply_scenario_changes(
    baseline_df: pd.DataFrame, changes: list[ScenarioChange]
) -> pd.DataFrame:
    """Apply validated edits to a deep copy and return all canonical branch rows."""
    scenario = prepare_input_data(baseline_df).copy(deep=True)
    known_branches = set(scenario[BRANCH_ID])

    for change in changes:
        branch_id = str(change.branch_id)
        if branch_id not in known_branches:
            raise ValueError(f"Branch ID not found in baseline data: {change.branch_id}")
        if change.indicator_key not in INDICATOR_KEYS:
            raise ValueError(f"Unknown indicator key: {change.indicator_key}")
        scenario_value = _validate_scenario_value(change.indicator_key, change.scenario_value)
        mask = scenario[BRANCH_ID].eq(branch_id)
        scenario.loc[mask, change.indicator_key] = scenario_value
    return scenario


def build_scenario_changes(
    baseline_df: pd.DataFrame, edited_values: pd.DataFrame
) -> list[ScenarioChange]:
    """Build changes from wide edited values or a long scenario-value table.

    Wide input contains ``branch_id`` and any indicator columns. Long input
    contains ``branch_id``, ``indicator_key``, and ``scenario_value``.
    Missing wide values mean "not edited" and unchanged values are omitted.
    """
    baseline = prepare_input_data(baseline_df)
    baseline_by_branch = baseline.set_index(BRANCH_ID)
    if BRANCH_ID not in edited_values.columns:
        raise ValueError(f"edited_values must contain {BRANCH_ID}")

    rows: list[tuple[object, object, object]] = []
    long_columns = {BRANCH_ID, "indicator_key", "scenario_value"}
    if long_columns.issubset(edited_values.columns):
        rows = list(
            edited_values.loc[:, [BRANCH_ID, "indicator_key", "scenario_value"]]
            .itertuples(index=False, name=None)
        )
    else:
        unknown = [
            column
            for column in edited_values.columns
            if column not in {BRANCH_ID, BRANCH_NAME} and column not in INDICATOR_KEYS
        ]
        if unknown:
            raise ValueError(f"Unknown indicator keys: {', '.join(map(str, unknown))}")
        for record in edited_values.to_dict("records"):
            for indicator_key in INDICATOR_KEYS:
                if indicator_key in record and not pd.isna(record[indicator_key]):
                    rows.append((record[BRANCH_ID], indicator_key, record[indicator_key]))

    changes: list[ScenarioChange] = []
    known_branches = set(baseline_by_branch.index)
    for raw_branch_id, raw_indicator, raw_value in rows:
        branch_id = str(raw_branch_id)
        indicator_key = str(raw_indicator)
        if branch_id not in known_branches:
            raise ValueError(f"Branch ID not found in baseline data: {raw_branch_id}")
        if indicator_key not in INDICATOR_KEYS:
            raise ValueError(f"Unknown indicator key: {indicator_key}")
        scenario_value = _validate_scenario_value(indicator_key, raw_value)
        baseline_value = float(baseline_by_branch.at[branch_id, indicator_key])
        absolute_change = scenario_value - baseline_value
        if absolute_change == 0.0:
            continue
        percentage_change = (
            (absolute_change / baseline_value) * 100.0 if baseline_value != 0 else np.nan
        )
        changes.append(
            ScenarioChange(
                branch_id=branch_id,
                branch_name=str(baseline_by_branch.at[branch_id, BRANCH_NAME]),
                indicator_key=indicator_key,
                baseline_value=baseline_value,
                scenario_value=scenario_value,
                absolute_change=absolute_change,
                percentage_change=percentage_change,
            )
        )
    return changes
