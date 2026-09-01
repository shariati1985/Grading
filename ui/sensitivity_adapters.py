"""Pure UI adapters for Phase 2 sensitivity contracts."""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

import pandas as pd

from domain.scenario_contracts import (
    BulkRule,
    IndicatorChange,
    IndicatorProposal,
    ScenarioExecutionResult,
    ScenarioRequest,
    ScenarioType,
    TargetRankRequest,
    TargetRankComparisonResult,
    TargetRankSolution,
)
from engine.indicator_registry import INDICATOR_REGISTRY, PROFIT_LOSS_KEY, validate_indicator_value
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME, REGION, WEIGHTS
from engine.scenario_rule_engine import ManualOverride, RuleOperation
from services.selection_scope import SelectionScope
from ui.formatters import (
    format_compact_number, format_grade, format_percentage,
    format_persian_number, format_persian_percentage, format_rank, format_score,
    format_signed_persian_number, persian_digits,
)


def filter_branches(frame: pd.DataFrame, query: str) -> pd.DataFrame:
    """Search real branches by normalized code or name without inventing rows."""
    text = str(query or "").strip().casefold()
    if not text:
        return frame.copy()
    mask = frame[BRANCH_ID].astype(str).str.casefold().str.contains(text, regex=False)
    mask |= frame[BRANCH_NAME].astype(str).str.casefold().str.contains(text, regex=False)
    return frame.loc[mask].copy()


def unique_indicator_ids(values: Iterable[str]) -> tuple[str, ...]:
    selected = tuple(str(value) for value in values)
    if len(selected) != len(set(selected)):
        raise ValueError("هر شاخص فقط یک‌بار قابل انتخاب است.")
    unknown = set(selected) - set(INDICATOR_REGISTRY)
    if unknown:
        raise ValueError("شاخص انتخاب‌شده معتبر نیست.")
    return selected


def preview_raw_operation(baseline: Any, operation: RuleOperation, value: Any, indicator_id: str) -> float:
    try:
        base, amount = float(baseline), float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("مقدار تغییر باید عددی باشد.") from exc
    if not math.isfinite(base) or not math.isfinite(amount):
        raise ValueError("مقدار تغییر باید عددی و متناهی باشد.")
    if operation is RuleOperation.PERCENT_CHANGE:
        proposed = base * (1.0 + amount / 100.0)
    elif operation is RuleOperation.ABSOLUTE_CHANGE:
        proposed = base + amount
    elif operation is RuleOperation.SET_VALUE:
        proposed = amount
    else:
        raise ValueError("نوع تغییر معتبر نیست.")
    code = validate_indicator_value(indicator_id, proposed)
    if code:
        if code == "BELOW_MINIMUM":
            raise ValueError("مقدار نهایی این شاخص نمی‌تواند منفی باشد.")
        raise ValueError("مقدار نهایی شاخص معتبر نیست.")
    return proposed


def build_focus_request(draft: dict[str, Any]) -> ScenarioRequest:
    if draft.get("scenario_type") is not ScenarioType.FOCUS_BRANCH_ONLY:
        raise ValueError("اطلاعات این حالت با سناریوی شعبه محوری سازگار نیست.")
    focus = str(draft.get("focus_branch_id") or "").strip()
    selected = unique_indicator_ids(draft.get("selected_indicator_ids", []))
    changes = []
    for indicator_id in selected:
        row = draft.get("focus_changes", {}).get(indicator_id)
        if not row:
            raise ValueError("برای همه شاخص‌های منتخب، تغییر را تعیین کنید.")
        changes.append(IndicatorChange(indicator_id, RuleOperation(row["operation"]), float(row["value"])))
    if not focus or not changes:
        raise ValueError("شعبه و حداقل یک تغییر معتبر باید انتخاب شود.")
    return ScenarioRequest(
        ScenarioType.FOCUS_BRANCH_ONLY,
        str(draft.get("scenario_name") or "سناریوی شعبه محوری").strip(),
        focus,
        draft.get("focus_branch_source"),
        draft.get("period"),
        focus_branch_changes=tuple(changes),
    )


def build_multi_request(draft: dict[str, Any]) -> ScenarioRequest:
    if draft.get("scenario_type") is not ScenarioType.MULTI_BRANCH:
        raise ValueError("اطلاعات این حالت با سناریوی چندشعبه‌ای سازگار نیست.")
    focus = str(draft.get("focus_branch_id") or "").strip()
    rules = tuple(
        BulkRule(
            str(row["indicator_id"]), RuleOperation(row["operation"]), float(row["value"]),
            SelectionScope(row["target_scope"]), tuple(map(str, row.get("selected_branch_ids", ()))),
            tuple(map(str, row.get("selected_regions", ()))),
        ) for row in draft.get("bulk_rules", [])
    )
    overrides = tuple(
        ManualOverride(str(row["branch_id"]), str(row["indicator_id"]),
                       RuleOperation(row["operation"]), float(row["value"]))
        for row in draft.get("manual_overrides", [])
    )
    if not focus or (not rules and not overrides):
        raise ValueError("شعبه محوری و حداقل یک قاعده یا تغییر اختصاصی لازم است.")
    return ScenarioRequest(
        ScenarioType.MULTI_BRANCH,
        str(draft.get("scenario_name") or "سناریوی چندشعبه‌ای").strip(), focus,
        draft.get("focus_branch_source"), draft.get("period"),
        bulk_rules=rules, manual_overrides=overrides,
    )


def build_target_request(draft: dict[str, Any]) -> TargetRankRequest:
    if draft.get("scenario_type") is not ScenarioType.TARGET_RANK:
        raise ValueError("اطلاعات این حالت با سناریوی رتبه هدف سازگار نیست.")
    settings = draft.get("target_rank_request", {})
    selected = unique_indicator_ids(draft.get("selected_indicator_ids", []))
    focus = str(draft.get("focus_branch_id") or "").strip()
    if not focus or not selected:
        raise ValueError("شعبه و حداقل یک شاخص قابل تغییر لازم است.")
    return TargetRankRequest(
        focus_branch_id=focus,
        target_rank=int(settings["target_rank"]),
        selected_indicator_ids=selected,
        max_growth_percent=float(settings.get("max_growth_percent", 100.0)),
        tolerance_percent=float(settings.get("tolerance_percent", 0.01)),
        max_iterations=int(settings.get("max_iterations", 40)),
        minimum_growth_percent=float(settings.get("minimum_growth_percent", 0.0)),
        search_precision_percent=float(settings.get("search_precision_percent", 0.01)),
        allow_profit_loss=PROFIT_LOSS_KEY in selected,
        period=draft.get("period"),
    )


def build_target_comparison_request(draft: dict[str, Any]) -> TargetRankRequest:
    if draft.get("scenario_type") is not ScenarioType.TARGET_RANK:
        raise ValueError("اطلاعات این حالت با سناریوی رتبه هدف سازگار نیست.")
    settings = draft.get("target_rank_request", {})
    selected = unique_indicator_ids(draft.get("selected_indicator_ids", []))
    focus = str(draft.get("focus_branch_id") or "").strip()
    if not focus:
        raise ValueError("شعبه هدف باید انتخاب شود.")
    if not selected:
        raise ValueError("برای مسیر شاخص‌های منتخب کاربر، حداقل یک شاخص لازم است.")
    return TargetRankRequest(
        focus_branch_id=focus,
        target_rank=int(settings["target_rank"]),
        selected_indicator_ids=selected,
        max_growth_percent=100.0,
        tolerance_percent=0.01,
        max_iterations=80,
        minimum_growth_percent=0.0,
        search_precision_percent=0.01,
        allow_profit_loss=True,
        period=draft.get("period"),
    )


def result_sections(result: ScenarioExecutionResult) -> dict[str, tuple[Any, ...]]:
    return {
        "modified_branches": result.modified_branches,
        "rank_affected_branches": result.rank_affected_branches,
    }


def result_branch_options(result: ScenarioExecutionResult) -> tuple[str, ...]:
    """Focus-first union of modified and ranking-affected official results."""
    return tuple(dict.fromkeys([
        str(result.request.focus_branch_id),
        *(str(item.branch_id) for item in result.modified_branches),
        *(str(item.branch_id) for item in result.rank_affected_branches),
    ]))


def select_official_branch_result(result: ScenarioExecutionResult, branch_id: str):
    candidates = (
        result.focus_branch_comparison, *result.modified_branches, *result.rank_affected_branches
    )
    for item in candidates:
        if str(item.branch_id) == str(branch_id):
            return item
    raise ValueError("نتیجه رسمی شعبه انتخاب‌شده در این اجرا موجود نیست.")


def rank_change_presentation(value: int) -> tuple[str, str]:
    if value > 0:
        return f"{value} رتبه بهبود", "improvement"
    if value < 0:
        return f"{abs(value)} رتبه افت", "decline"
    return "بدون تغییر رتبه", "unchanged"


def _semantic_tone(value: float, tolerance: float = 1e-9) -> str:
    if value > tolerance: return "success"
    if value < -tolerance: return "danger"
    return "neutral"


def focus_result_presentation(comparison) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build Persian cards solely from an official branch comparison."""
    rank_text, _ = rank_change_presentation(comparison.rank_change)
    rank_text = persian_digits(rank_text)
    score_change = float(comparison.score_change)
    score_text = (
        f"{format_persian_number(abs(score_change), 1)} امتیاز بهبود" if score_change > 0
        else f"{format_persian_number(abs(score_change), 1)} امتیاز افت" if score_change < 0
        else "بدون تغییر"
    )
    grade_changed = comparison.baseline_grade != comparison.scenario_grade
    grade_text = (
        f"تغییر از {format_grade(comparison.baseline_grade)} به {format_grade(comparison.scenario_grade)}"
        if grade_changed else "بدون تغییر درجه"
    )
    changed = [item for item in comparison.indicator_comparisons if abs(float(item["raw_value_change"])) > 1e-9]
    summaries = [
        {"label": "رتبه کل شعبه", "current": format_persian_number(comparison.baseline_rank, 0), "scenario": format_persian_number(comparison.scenario_rank, 0), "change": rank_text, "tone": _semantic_tone(comparison.rank_change)},
        {"label": "امتیاز کل", "current": format_persian_number(comparison.baseline_final_score, 1), "scenario": format_persian_number(comparison.scenario_final_score, 1), "change": score_text, "tone": _semantic_tone(score_change)},
        {"label": "درجه شعبه", "current": format_grade(comparison.baseline_grade), "scenario": format_grade(comparison.scenario_grade), "change": grade_text, "tone": _semantic_tone(score_change) if grade_changed else "neutral"},
    ]
    indicators = []
    for item in changed:
        normalized_current = float(item["baseline_score"])
        normalized_scenario = float(item["scenario_score"])
        normalized_delta = normalized_scenario - normalized_current
        weight = float(WEIGHTS[item["indicator_key"]])
        weight_factor = weight / 100.0 if weight > 1.0 else weight
        weighted_current = normalized_current * weight_factor
        weighted_scenario = normalized_scenario * weight_factor
        overall_effect = weighted_scenario - weighted_current
        indicator_rank_change = int(item["indicator_rank_change"])
        indicator_rank_text, rank_tone = rank_change_presentation(indicator_rank_change)
        indicators.append({
            "indicator_key": item["indicator_key"],
            "icon": {"profit_loss": "±", "deposit_count": "#", "loan_count": "#", "commitment_count": "#"}.get(item["indicator_key"], "◈"),
            "name": INDICATOR_REGISTRY[item["indicator_key"]].display_name,
            "weight": format_persian_percentage(weight_factor * 100, decimals=0),
            "tone": "success" if rank_tone == "improvement" else "danger" if rank_tone == "decline" else _semantic_tone(overall_effect),
            "status": indicator_rank_text,
            "raw": {
                "current": format_persian_number(item["baseline_raw_value"], 0),
                "scenario": format_persian_number(item["scenario_raw_value"], 0),
                "absolute": format_signed_persian_number(item["raw_value_change"], 0),
                "percent": format_persian_percentage(item["raw_value_change_pct"], decimals=1),
                "current_exact": format_compact_number(item["baseline_raw_value"]),
                "scenario_exact": format_compact_number(item["scenario_raw_value"]),
                "absolute_exact": format_compact_number(item["raw_value_change"]),
            },
            "normalized": {
                "current": f"{format_persian_number(normalized_current, 1)} از ۱۰۰۰",
                "scenario": f"{format_persian_number(normalized_scenario, 1)} از ۱۰۰۰",
                "change": format_signed_persian_number(normalized_delta, 1),
                "current_percent": max(0.0, min(100.0, normalized_current / 10.0)),
                "scenario_percent": max(0.0, min(100.0, normalized_scenario / 10.0)),
            },
            "rank": {
                "current": format_persian_number(item["baseline_indicator_rank"], 0),
                "scenario": format_persian_number(item["scenario_indicator_rank"], 0),
                "change": persian_digits(indicator_rank_text),
                "change_numeric": indicator_rank_change,
            },
            "weighted": {
                "current": format_persian_number(weighted_current, 1),
                "scenario": format_persian_number(weighted_scenario, 1),
                "effect": format_signed_persian_number(overall_effect, 1),
                "current_numeric": weighted_current, "scenario_numeric": weighted_scenario,
                "effect_numeric": overall_effect, "weight_factor": weight_factor,
            },
        })
    return summaries, indicators


def count_proposal_presentation(proposal: IndicatorProposal) -> dict[str, Any]:
    return {
        "applicable_value": int(proposal.proposed_raw_value) if proposal.is_count_indicator else proposal.proposed_raw_value,
        "numeric_candidate": proposal.numeric_candidate_raw_value,
        "show_ceiling_note": proposal.is_count_indicator,
    }


def action_priority(proposals: Iterable[IndicatorProposal], near_tolerance: float = 1e-9) -> tuple[list[dict[str, Any]], bool]:
    rows = []
    for proposal in proposals:
        before = proposal.baseline_weighted_contribution
        after = proposal.scenario_weighted_contribution
        if before is None or after is None:
            continue
        delta = float(after) - float(before)
        if delta > 0:
            rows.append({"indicator_id": proposal.indicator_id, "weighted_contribution_delta": delta})
    rows.sort(key=lambda row: (-row["weighted_contribution_delta"], row["indicator_id"]))
    indistinguishable = len(rows) > 1 and max(row["weighted_contribution_delta"] for row in rows) - min(
        row["weighted_contribution_delta"] for row in rows
    ) <= near_tolerance
    return rows, indistinguishable


def target_solution_comparison(solution: TargetRankSolution) -> pd.DataFrame:
    if solution.baseline_outputs is None or solution.scenario_outputs is None:
        return pd.DataFrame()
    from engine.comparison_engine import compare_model_outputs
    return compare_model_outputs(solution.baseline_outputs, solution.scenario_outputs).branch_comparison


def target_path_results(comparison: TargetRankComparisonResult) -> tuple[Any, Any]:
    return comparison.balanced_all_indicators, comparison.user_selected_indicators


def service_error_message(message: str) -> str:
    """Translate known service validation failures without leaking internal keys."""
    if "overlapping bulk rules" in message:
        match = re.search(r"\(([^,]+),\s*([^)]+)\)", message)
        if match:
            branch_id, indicator_id = match.groups()
            indicator = INDICATOR_REGISTRY.get(indicator_id.strip())
            indicator_name = indicator.display_name if indicator else "شاخص انتخاب‌شده"
            return f"قاعده‌های عمومی برای شعبه {branch_id.strip()} و شاخص «{indicator_name}» هم‌پوشانی دارند."
        return "قاعده‌های عمومی برای یک شعبه و شاخص مشترک هم‌پوشانی دارند."
    if "focus_branch" in message:
        return "شعبه محوری معتبر نیست."
    if "mixed" in message or "does not accept" in message:
        return "اطلاعات واردشده با نوع سناریو سازگار نیست."
    return "سناریو معتبر نیست. لطفاً اطلاعات واردشده را بازبینی کنید."
