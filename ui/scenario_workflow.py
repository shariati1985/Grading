"""Pure orchestration helpers for the interactive Scenario Builder."""

from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any, Final

import pandas as pd

from engine.comparison_engine import ScenarioComparison, compare_model_outputs
from engine.ranking_engine import (
    BRANCH_ID,
    BRANCH_NAME,
    INDICATOR_KEYS,
    ModelOutputs,
    run_ranking_model,
)
from engine.scenario_engine import ScenarioChange, apply_scenario_changes, build_scenario_changes

INDICATOR_LABELS: Final[dict[str, str]] = {
    "deposit_count": "تعداد سپرده‌ها",
    "avg_deposits": "میانگین سپرده‌ها",
    "loan_count": "تعداد تسهیلات",
    "avg_loans": "میانگین تسهیلات",
    "commitment_count": "تعداد تعهدات",
    "avg_commitments": "میانگین تعهدات",
    "transaction_volume": "حجم عملیات",
    "profit_loss": "سود و زیان",
}
INDICATOR_ORDER: Final[tuple[str, ...]] = tuple(INDICATOR_LABELS)
EDIT_MODES: Final[tuple[str, ...]] = ("percent", "direct")

NETWORK_FILTERS: Final[tuple[str, ...]] = (
    "همه شعب",
    "فقط شعب دارای تغییر رتبه",
    "فقط شعب دارای تغییر درجه",
    "فقط شعب دارای بهبود رتبه",
    "فقط شعب دارای افت رتبه",
)

SCENARIO_RESET_VALUES: Final[dict[str, Any]] = {
    "scenario_name": "",
    "selected_regions": [],
    "selected_branches": [],
    "scenario_changes": [],
    "scenario_dataframe": None,
    "scenario_results": None,
    "scenario_outputs": None,
    "comparison_results": None,
    "scenario_executed": False,
    "current_scenario_id": None,
    "current_scenario_row_version": None,
    "current_scenario_dirty": False,
    "loaded_scenario_changes": [],
    "current_scenario_record": None,
    "indicator_editor_state": {},
    "loaded_scenario_edit_modes": {},
}


@dataclass(frozen=True)
class ScenarioExecution:
    """All calculated artifacts from one full-network scenario run."""

    changes: list[ScenarioChange]
    scenario_dataframe: pd.DataFrame
    scenario_outputs: ModelOutputs
    comparison_results: ScenarioComparison


def calculate_scenario_value(
    baseline_value: float, change_percent: float
) -> float:
    """Calculate a scenario value from an unrestricted percentage change."""
    return float(baseline_value) * (1.0 + float(change_percent) / 100.0)


def calculate_change_percent(
    baseline_value: float, scenario_value: float
) -> float | None:
    """Calculate percentage change, returning None for a zero baseline."""
    baseline = float(baseline_value)
    if baseline == 0.0:
        return None
    return ((float(scenario_value) - baseline) / baseline) * 100.0


def indicator_widget_key(branch_id: str, indicator_key: str, field_name: str) -> str:
    """Return the stable collision-free key used by one row widget."""
    return f"scenario_{branch_id}_{indicator_key}_{field_name}"


def build_indicator_editor_state(baseline_rows: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Build default percent-mode state from ordered baseline editor rows."""
    required = {
        BRANCH_ID,
        BRANCH_NAME,
        "indicator_key",
        "indicator_name",
        "baseline_value",
    }
    missing = required - set(baseline_rows.columns)
    if missing:
        raise ValueError(f"Missing editor baseline columns: {', '.join(sorted(missing))}")
    state: dict[str, dict[str, Any]] = {}
    for row in baseline_rows.to_dict("records"):
        branch_id = str(row[BRANCH_ID])
        indicator_key = str(row["indicator_key"])
        if indicator_key not in INDICATOR_KEYS:
            raise ValueError(f"Unknown indicator key: {indicator_key}")
        baseline_value = float(row["baseline_value"])
        row_id = f"{branch_id}:{indicator_key}"
        state[row_id] = {
            BRANCH_ID: branch_id,
            BRANCH_NAME: str(row[BRANCH_NAME]),
            "indicator_key": indicator_key,
            "indicator_name": str(row["indicator_name"]),
            "baseline_value": baseline_value,
            "edit_mode": "percent",
            "change_percent": 0.0,
            "scenario_value": baseline_value,
            "absolute_change": 0.0,
        }
    return state


def update_indicator_editor_state(
    editor_state: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Derive the disabled field and absolute change for every editor row."""
    updated = deepcopy(editor_state)
    for row in updated.values():
        mode = str(row.get("edit_mode", "percent"))
        if mode not in EDIT_MODES:
            raise ValueError(f"Unknown edit mode: {mode}")
        baseline = float(row["baseline_value"])
        if mode == "percent":
            percent = float(row.get("change_percent", 0.0))
            if not math.isfinite(percent):
                raise ValueError("Percentage change must be finite")
            scenario_value = calculate_scenario_value(baseline, percent)
            row["change_percent"] = percent
            row["scenario_value"] = scenario_value
        else:
            scenario_value = float(row.get("scenario_value", baseline))
            if not math.isfinite(scenario_value):
                raise ValueError("Scenario value must be finite")
            row["scenario_value"] = scenario_value
            row["change_percent"] = calculate_change_percent(baseline, scenario_value)
        row["absolute_change"] = scenario_value - baseline
    return updated


def build_scenario_changes_from_editor_state(
    editor_state: dict[str, dict[str, Any]],
) -> list[ScenarioChange]:
    """Create validated engine changes from the final synchronized state."""
    synchronized = update_indicator_editor_state(editor_state)
    changes: list[ScenarioChange] = []
    for row in synchronized.values():
        indicator_key = str(row["indicator_key"])
        scenario_value = float(row["scenario_value"])
        if scenario_value < 0 and indicator_key != "profit_loss":
            raise ValueError(
                f"مقدار منفی فقط برای سود و زیان مجاز است؛ شاخص «{INDICATOR_LABELS[indicator_key]}» نامعتبر است."
            )
        absolute_change = float(row["absolute_change"])
        if absolute_change == 0.0:
            continue
        percentage = row["change_percent"]
        changes.append(
            ScenarioChange(
                branch_id=str(row[BRANCH_ID]),
                branch_name=str(row[BRANCH_NAME]),
                indicator_key=indicator_key,
                baseline_value=float(row["baseline_value"]),
                scenario_value=scenario_value,
                absolute_change=absolute_change,
                percentage_change=(math.nan if percentage is None else float(percentage)),
            )
        )
    return changes


def reset_indicator_row(
    editor_state: dict[str, dict[str, Any]], branch_id: str, indicator_key: str
) -> dict[str, dict[str, Any]]:
    """Reset exactly one row without mutating the supplied editor state."""
    reset = deepcopy(editor_state)
    row_id = f"{branch_id}:{indicator_key}"
    if row_id not in reset:
        raise ValueError(f"Editor row not found: {row_id}")
    baseline = float(reset[row_id]["baseline_value"])
    reset[row_id].update(
        edit_mode="percent",
        change_percent=0.0,
        scenario_value=baseline,
        absolute_change=0.0,
    )
    return reset


def reset_all_indicator_rows(
    editor_state: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Reset all indicator values while preserving branch/editor identities."""
    reset = deepcopy(editor_state)
    for row_id, row in list(reset.items()):
        reset = reset_indicator_row(
            reset, str(row[BRANCH_ID]), str(row["indicator_key"])
        )
    return reset


def restore_indicator_editor_state(
    editor_state: dict[str, dict[str, Any]],
    changes: list[ScenarioChange],
    edit_modes: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Restore exact persisted values and modes without display-value rounding."""
    restored = deepcopy(editor_state)
    modes = edit_modes or {}
    for change in changes:
        row_id = f"{change.branch_id}:{change.indicator_key}"
        if row_id not in restored:
            continue
        mode = modes.get(row_id, "direct")
        restored[row_id]["edit_mode"] = mode
        restored[row_id]["scenario_value"] = float(change.scenario_value)
        restored[row_id]["change_percent"] = (
            None
            if not math.isfinite(change.percentage_change)
            else float(change.percentage_change)
        )
        restored[row_id]["absolute_change"] = float(change.absolute_change)
    return restored


def editor_edit_modes(editor_state: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Return persistence mode mappings for changed editor rows."""
    synchronized = update_indicator_editor_state(editor_state)
    return {
        row_id: str(row["edit_mode"])
        for row_id, row in synchronized.items()
        if float(row["absolute_change"]) != 0.0
    }


def build_editor_data(
    baseline_df: pd.DataFrame, selected_branch_ids: list[str]
) -> pd.DataFrame:
    """Create eight ordered editor rows for every selected branch."""
    baseline_by_branch = baseline_df.set_index(BRANCH_ID)
    rows: list[dict[str, object]] = []
    for branch_id in selected_branch_ids:
        if branch_id not in baseline_by_branch.index:
            raise ValueError(f"کد شعبه در اطلاعات مبنا یافت نشد: {branch_id}")
        branch_name = str(baseline_by_branch.at[branch_id, BRANCH_NAME])
        for indicator_key in INDICATOR_ORDER:
            baseline_value = float(baseline_by_branch.at[branch_id, indicator_key])
            rows.append(
                {
                    BRANCH_ID: branch_id,
                    BRANCH_NAME: branch_name,
                    "indicator_key": indicator_key,
                    "indicator_name": INDICATOR_LABELS[indicator_key],
                    "baseline_value": baseline_value,
                    "change_percent": 0.0,
                    "scenario_value": baseline_value,
                }
            )
    return pd.DataFrame(rows)


def synchronize_edited_values(edited_df: pd.DataFrame) -> pd.DataFrame:
    """Resolve editor inputs deterministically and preserve model precision.

    A changed scenario value is authoritative. Otherwise the percentage is
    applied to baseline. The returned percentage is always recalculated and
    rounded to two decimal places.
    """
    required = {
        BRANCH_ID,
        BRANCH_NAME,
        "indicator_key",
        "indicator_name",
        "baseline_value",
        "change_percent",
        "scenario_value",
    }
    missing = required - set(edited_df.columns)
    if missing:
        raise ValueError(f"ستون‌های لازم در جدول وجود ندارند: {', '.join(sorted(missing))}")

    synchronized = edited_df.copy(deep=True)
    for index, row in synchronized.iterrows():
        indicator_key = str(row["indicator_key"])
        if indicator_key not in INDICATOR_KEYS:
            raise ValueError(f"شاخص ناشناخته است: {indicator_key}")
        try:
            baseline_value = float(row["baseline_value"])
            entered_percent = float(row["change_percent"])
            entered_value = float(row["scenario_value"])
        except (TypeError, ValueError) as exc:
            raise ValueError("تمام مقادیر سناریو و درصد تغییر باید عددی باشند.") from exc
        if not all(
            math.isfinite(value)
            for value in (baseline_value, entered_percent, entered_value)
        ):
            raise ValueError("مقادیر خالی، نامعتبر یا نامتناهی مجاز نیستند.")

        if entered_value != baseline_value:
            scenario_value = entered_value
        else:
            scenario_value = baseline_value * (1.0 + entered_percent / 100.0)
        if scenario_value < 0 and indicator_key != "profit_loss":
            raise ValueError(
                f"مقدار منفی فقط برای سود و زیان مجاز است؛ شاخص «{INDICATOR_LABELS[indicator_key]}» نامعتبر است."
            )
        if baseline_value == 0:
            calculated_percent = 0.0 if scenario_value == 0 else math.nan
        else:
            calculated_percent = round(
                ((scenario_value - baseline_value) / baseline_value) * 100.0, 2
            )
        synchronized.at[index, "scenario_value"] = scenario_value
        synchronized.at[index, "change_percent"] = calculated_percent
    return synchronized


def resolved_change_values(synchronized_df: pd.DataFrame) -> pd.DataFrame:
    """Select the long-form columns consumed by the scenario engine."""
    return synchronized_df.loc[
        :, [BRANCH_ID, "indicator_key", "scenario_value"]
    ].copy()


def changes_from_editor(
    baseline_df: pd.DataFrame, edited_df: pd.DataFrame
) -> list[ScenarioChange]:
    """Build engine changes from editor values without running the ranking model."""
    synchronized = synchronize_edited_values(edited_df)
    return build_scenario_changes(baseline_df, resolved_change_values(synchronized))


def apply_saved_changes_to_editor(
    editor_df: pd.DataFrame, changes: list[ScenarioChange]
) -> pd.DataFrame:
    """Initialize editor scenario values from a loaded persisted scenario."""
    initialized = editor_df.copy(deep=True)
    for change in changes:
        mask = initialized[BRANCH_ID].eq(change.branch_id) & initialized[
            "indicator_key"
        ].eq(change.indicator_key)
        initialized.loc[mask, "scenario_value"] = change.scenario_value
        initialized.loc[mask, "change_percent"] = change.percentage_change
    return initialized


def execute_scenario(
    baseline_df: pd.DataFrame,
    baseline_outputs: ModelOutputs,
    edited_df: pd.DataFrame,
    scenario_name: str,
    selected_branch_ids: list[str],
) -> ScenarioExecution:
    """Validate and execute one scenario against the complete branch network."""
    if not scenario_name.strip():
        raise ValueError("نام سناریو نمی‌تواند خالی باشد.")
    if not selected_branch_ids:
        raise ValueError("حداقل یک شعبه را انتخاب کنید.")
    known_ids = set(baseline_df[BRANCH_ID])
    missing_ids = [branch_id for branch_id in selected_branch_ids if branch_id not in known_ids]
    if missing_ids:
        raise ValueError("کد شعبه در اطلاعات مبنا یافت نشد: " + "، ".join(missing_ids))

    synchronized = synchronize_edited_values(edited_df)
    changes = build_scenario_changes(baseline_df, resolved_change_values(synchronized))
    scenario_df = apply_scenario_changes(baseline_df.copy(deep=True), changes)
    scenario_outputs = run_ranking_model(scenario_df)
    comparison = compare_model_outputs(baseline_outputs, scenario_outputs)
    return ScenarioExecution(changes, scenario_df, scenario_outputs, comparison)


def execute_scenario_from_editor_state(
    baseline_df: pd.DataFrame,
    baseline_outputs: ModelOutputs,
    editor_state: dict[str, dict[str, Any]],
    scenario_name: str,
    selected_branch_ids: list[str],
) -> ScenarioExecution:
    """Execute the existing full-network workflow from synchronized row state."""
    if not scenario_name.strip():
        raise ValueError("نام سناریو نمی‌تواند خالی باشد.")
    if not selected_branch_ids:
        raise ValueError("حداقل یک شعبه را انتخاب کنید.")
    known_ids = set(baseline_df[BRANCH_ID])
    missing_ids = [item for item in selected_branch_ids if item not in known_ids]
    if missing_ids:
        raise ValueError("کد شعبه در اطلاعات مبنا یافت نشد: " + "، ".join(missing_ids))
    changes = build_scenario_changes_from_editor_state(editor_state)
    scenario_df = apply_scenario_changes(baseline_df.copy(deep=True), changes)
    scenario_outputs = run_ranking_model(scenario_df)
    comparison = compare_model_outputs(baseline_outputs, scenario_outputs)
    return ScenarioExecution(changes, scenario_df, scenario_outputs, comparison)


def selected_branch_results(
    comparison: ScenarioComparison, selected_branch_ids: list[str]
) -> pd.DataFrame:
    """Return selected comparison rows in the user's selection order."""
    order = {branch_id: position for position, branch_id in enumerate(selected_branch_ids)}
    selected = comparison.branch_comparison.loc[
        comparison.branch_comparison[BRANCH_ID].isin(selected_branch_ids)
    ].copy()
    selected["_selection_order"] = selected[BRANCH_ID].map(order)
    return selected.sort_values("_selection_order").drop(columns="_selection_order").reset_index(drop=True)


def filter_network_impact(network_impact: pd.DataFrame, filter_name: str) -> pd.DataFrame:
    """Apply one supported network-impact filter without mutating its input."""
    if filter_name not in NETWORK_FILTERS:
        raise ValueError(f"فیلتر اثر شبکه ناشناخته است: {filter_name}")
    filtered = network_impact.copy(deep=True)
    if filter_name == "فقط شعب دارای تغییر رتبه":
        filtered = filtered.loc[filtered["rank_change"].ne(0)]
    elif filter_name == "فقط شعب دارای تغییر درجه":
        filtered = filtered.loc[filtered["grade_changed"]]
    elif filter_name == "فقط شعب دارای بهبود رتبه":
        filtered = filtered.loc[filtered["rank_change"].gt(0)]
    elif filter_name == "فقط شعب دارای افت رتبه":
        filtered = filtered.loc[filtered["rank_change"].lt(0)]
    return filtered.reset_index(drop=True)


def reset_scenario_state(state: MutableMapping[str, Any]) -> None:
    """Clear scenario artifacts and widget state while retaining baseline cache."""
    for key, value in SCENARIO_RESET_VALUES.items():
        state[key] = value.copy() if isinstance(value, list) else value
    for key in (
        "_scenario_name_input",
        "_selected_region_input",
        "_selected_branches_input",
        "_editor_branches",
        "_network_filter",
        "_scenario_visibility",
    ):
        state.pop(key, None)
    widget_suffixes = ("_edit_mode", "_change_percent", "_scenario_value")
    for key in list(state):
        if str(key).startswith("scenario_") and str(key).endswith(widget_suffixes):
            state.pop(key, None)
    state["editor_version"] = int(state.get("editor_version", 0)) + 1
