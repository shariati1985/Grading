"""Application boundary for the Phase 3B three-mode persisted workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from uuid import uuid4

import pandas as pd

from domain.scenario_contracts import ScenarioExecutionResult, ScenarioType, TargetRankComparisonResult, TargetRankSolution
from engine.comparison_engine import compare_model_outputs
from engine.indicator_registry import INDICATOR_REGISTRY
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME
from engine.scenario_engine import ScenarioChange
from persistence.models import ScenarioRecord, ScenarioResultSummary
from services.scenario_management_service import ScenarioManagementService
from ui.sensitivity_state import new_scenario_draft

DEFINITION_SCHEMA = "phase3b.1.v1"
PERSISTED_DRAFT_FIELDS = (
    "scenario_name", "period", "focus_branch_id", "focus_branch_source", "selected_branch_ids",
    "selected_indicator_ids", "focus_changes", "bulk_rules", "manual_overrides",
    "target_rank_request", "current_step",
)


@dataclass(frozen=True)
class LoadedWorkspaceScenario:
    record: ScenarioRecord
    draft: dict[str, Any]
    results: tuple[ScenarioResultSummary, ...]
    warnings: tuple[str, ...] = ()


def serialize_sensitivity_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe definition without Streamlit/backend artifacts."""
    mode = draft.get("scenario_type")
    if not isinstance(mode, ScenarioType):
        raise ValueError("نوع سناریو برای ذخیره معتبر نیست.")
    definition: dict[str, Any] = {
        "schema": DEFINITION_SCHEMA,
        "scenario_type": mode.value,
    }
    for key in PERSISTED_DRAFT_FIELDS:
        value = draft.get(key)
        if key == "focus_changes":
            value = {
                str(indicator): {
                    "operation": str(item["operation"]), "value": float(item["value"])
                }
                for indicator, item in dict(value or {}).items()
            }
        elif key in {"bulk_rules", "manual_overrides"}:
            value = [dict(item) for item in list(value or [])]
        elif key in {"selected_indicator_ids", "selected_branch_ids"}:
            value = list(map(str, value or []))
        elif key == "target_rank_request":
            value = dict(value or {})
        definition[key] = value
    return definition


def restore_sensitivity_draft(
    definition: dict[str, Any], *, branch_ids: Iterable[str], periods: Iterable[str],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Restore compatible fields and report unavailable real-data references."""
    if definition.get("schema") != DEFINITION_SCHEMA:
        raise ValueError("ساختار سناریوی ذخیره‌شده با فضای جدید سازگار نیست.")
    try:
        mode = ScenarioType(str(definition["scenario_type"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("نوع سناریوی ذخیره‌شده معتبر نیست.") from exc
    draft = new_scenario_draft(mode)
    warnings: list[str] = []
    known_branches = set(map(str, branch_ids))
    known_periods = set(map(str, periods))
    stored_period = str(definition.get("period") or "")
    draft["period"] = stored_period
    if stored_period not in known_periods:
        warnings.append("دوره ذخیره‌شده در اطلاعات مبنای فعلی در دسترس نیست.")
    focus = str(definition.get("focus_branch_id") or "")
    if focus and focus not in known_branches:
        warnings.append(f"شعبه ذخیره‌شده با کد {focus} دیگر در فهرست شعب فعال نیست.")
        focus = ""
    draft["focus_branch_id"] = focus or None
    draft["focus_branch_source"] = definition.get("focus_branch_source") if focus else None
    draft["selected_branch_ids"] = [
        str(item) for item in definition.get("selected_branch_ids", [])
        if str(item) in known_branches
    ]
    selected = []
    for indicator in definition.get("selected_indicator_ids", []):
        if indicator in INDICATOR_REGISTRY:
            selected.append(str(indicator))
        else:
            warnings.append("یک شاخص ذخیره‌شده دیگر در مدل جاری وجود ندارد.")
    draft["selected_indicator_ids"] = list(dict.fromkeys(selected))
    draft["focus_changes"] = {
        key: dict(value) for key, value in dict(definition.get("focus_changes") or {}).items()
        if key in draft["selected_indicator_ids"]
    }
    draft["bulk_rules"] = [
        dict(item) for item in definition.get("bulk_rules", [])
        if item.get("indicator_id") in INDICATOR_REGISTRY
    ]
    draft["manual_overrides"] = [
        dict(item) for item in definition.get("manual_overrides", [])
        if item.get("indicator_id") in INDICATOR_REGISTRY
        and str(item.get("branch_id")) in known_branches
    ]
    draft["target_rank_request"] = dict(definition.get("target_rank_request") or {})
    draft["scenario_name"] = str(definition.get("scenario_name") or "")
    stored_step = int(definition.get("current_step") or 1)
    draft["current_step"] = max(1, min(4, stored_step))
    if mode is ScenarioType.TARGET_RANK:
        draft["current_step"] = max(1, min(2, stored_step))
    return draft, tuple(dict.fromkeys(warnings))


class ScenarioWorkspaceService:
    """Persist and restore new-UX scenarios through existing services."""

    def __init__(self, management: ScenarioManagementService) -> None:
        self.management = management

    @property
    def current_user(self):
        return self.management.current_user

    @staticmethod
    def _lineage(draft: dict[str, Any]) -> dict[str, Any]:
        persisted = dict(draft.get("persistence") or {})
        return {
            "lineage_id": persisted.get("lineage_id") or str(uuid4()),
            "version_number": int(persisted.get("version_number") or 1),
            "parent_scenario_id": persisted.get("parent_scenario_id"),
        }

    def _summary(self, draft: dict[str, Any], lineage: dict[str, Any] | None = None) -> dict[str, Any]:
        summary = {
            "scenario_definition": serialize_sensitivity_draft(draft),
            "scenario_type": draft["scenario_type"].value,
            "phase3b_lineage": dict(lineage or self._lineage(draft)),
        }
        target_summary = self._target_result_summary(draft.get("target_comparison_result"))
        if target_summary is not None:
            summary["target_rank_result_summary"] = target_summary
            summary["has_saved_result"] = True
        return summary

    @staticmethod
    def _target_result_summary(comparison: Any) -> dict[str, Any] | None:
        if not isinstance(comparison, TargetRankComparisonResult):
            return None

        def path_summary(path_result: Any) -> dict[str, Any]:
            solution = path_result.solution
            final_grade = solution.comparison.scenario_grade if solution.comparison else None
            baseline_grade = solution.comparison.baseline_grade if solution.comparison else None
            return {
                "path_id": str(path_result.path.path_id),
                "display_name": str(path_result.path.display_name),
                "indicator_ids": list(map(str, path_result.path.selected_indicator_ids)),
                "required_common_growth_percent": float(solution.required_common_growth_percent),
                "target_reached": bool(solution.target_reached),
                "status": str(solution.status.value),
                "baseline_rank": None if solution.baseline_rank is None else int(solution.baseline_rank),
                "target_rank": int(solution.target_rank),
                "achieved_rank": None if solution.achieved_rank is None else int(solution.achieved_rank),
                "baseline_score": None if solution.baseline_score is None else float(solution.baseline_score),
                "achieved_score": None if solution.achieved_score is None else float(solution.achieved_score),
                "baseline_grade": None if baseline_grade is None else str(baseline_grade),
                "achieved_grade": None if final_grade is None else str(final_grade),
                "iterations": int(solution.iterations),
                "message": str(solution.message),
                "indicator_proposals": [
                    {
                        "indicator_id": str(item.indicator_id),
                        "baseline_raw_value": float(item.baseline_raw_value),
                        "numeric_candidate_raw_value": float(item.numeric_candidate_raw_value),
                        "proposed_raw_value": float(item.proposed_raw_value),
                        "is_count_indicator": bool(item.is_count_indicator),
                        "absolute_change": float(item.absolute_change),
                        "percent_change": float(item.percent_change),
                        "baseline_weighted_contribution": None if item.baseline_weighted_contribution is None else float(item.baseline_weighted_contribution),
                        "scenario_weighted_contribution": None if item.scenario_weighted_contribution is None else float(item.scenario_weighted_contribution),
                        "note": None if item.note is None else str(item.note),
                    }
                    for item in solution.indicator_proposals
                ],
            }

        return {
            "focus_branch_id": str(comparison.focus_branch_id),
            "target_rank": int(comparison.target_rank),
            "target_reached": bool(comparison.target_reached),
            "iterations": int(comparison.iterations),
            "message": str(comparison.message),
            "paths": {
                comparison.balanced_all_indicators.path.path_id: path_summary(comparison.balanced_all_indicators),
                comparison.user_selected_indicators.path.path_id: path_summary(comparison.user_selected_indicators),
            },
        }

    def list_scenarios(self, *, status: str | None = None, search: str | None = None,
                       limit: int = 100, offset: int = 0) -> list[ScenarioRecord]:
        return self.management.list_visible(status=status, search=search, limit=limit, offset=offset)

    def save_draft(self, draft: dict[str, Any], *, save_as_new: bool = False) -> ScenarioRecord:
        persisted = dict(draft.get("persistence") or {})
        save_as_new = save_as_new or persisted.get("status") == "executed"
        lineage = self._lineage(draft)
        if save_as_new and persisted.get("scenario_id"):
            lineage = {
                "lineage_id": lineage["lineage_id"],
                "version_number": int(lineage["version_number"]) + 1,
                "parent_scenario_id": persisted["scenario_id"],
            }
        record = self.management.save_draft(
            scenario_name=str(draft.get("scenario_name") or "").strip(),
            baseline_period=str(draft.get("period") or ""),
            selected_branch_ids=([str(draft["focus_branch_id"])] if draft.get("focus_branch_id") else []),
            changes=[], summary=self._summary(draft, lineage),
            scenario_id=persisted.get("scenario_id"),
            expected_row_version=persisted.get("row_version"),
            save_as_new=save_as_new,
        )
        self._store_identity(draft, record)
        return record

    @staticmethod
    def _store_identity(draft: dict[str, Any], record: ScenarioRecord) -> None:
        lineage = dict(record.summary.get("phase3b_lineage") or {})
        draft["persistence"] = {
            "scenario_id": record.scenario_id, "row_version": record.row_version,
            "status": record.status, "dirty": False, **lineage,
            "saved_definition": dict(record.summary.get("scenario_definition") or {}),
        }

    @staticmethod
    def has_unsaved_changes(draft: dict[str, Any]) -> bool:
        persisted = dict(draft.get("persistence") or {})
        if not persisted.get("scenario_id"):
            return bool(draft.get("scenario_name") or draft.get("focus_branch_id")
                        or draft.get("selected_indicator_ids") or draft.get("bulk_rules")
                        or draft.get("manual_overrides") or draft.get("target_rank_request"))
        return persisted.get("saved_definition") != serialize_sensitivity_draft(draft)

    def load_scenario(self, scenario_id: str, *, branch_ids: Iterable[str],
                      periods: Iterable[str]) -> LoadedWorkspaceScenario:
        record, _, results = self.management.load_scenario(scenario_id)
        definition = dict(record.summary.get("scenario_definition") or {})
        draft, warnings = restore_sensitivity_draft(
            definition, branch_ids=branch_ids, periods=periods
        )
        draft["entry_source"] = "saved"
        self._store_identity(draft, record)
        if draft["scenario_type"] is ScenarioType.TARGET_RANK and record.status != "executed":
            draft["current_step"] = 1
            draft["target_execution_completed"] = False
        return LoadedWorkspaceScenario(record, draft, tuple(results), warnings)

    def load_focus_scenario(
        self, scenario_id: str, *, baseline_data: pd.DataFrame, periods: Iterable[str],
        restore_execution: bool = False,
    ) -> LoadedWorkspaceScenario:
        """Load a Branch-Centric definition and optionally rerun its official result."""
        loaded = self.load_scenario(
            scenario_id, branch_ids=baseline_data[BRANCH_ID].astype(str), periods=periods
        )
        if loaded.draft["scenario_type"] is not ScenarioType.FOCUS_BRANCH_ONLY:
            raise ValueError("سناریوی انتخاب‌شده از نوع تغییر شعبه محوری نیست.")
        if not restore_execution:
            return loaded
        if loaded.record.status != "executed":
            loaded.draft["show_result"] = False
            return LoadedWorkspaceScenario(
                loaded.record, loaded.draft, loaded.results,
                (*loaded.warnings, "این پیش‌نویس هنوز نتیجه محاسبه‌شده ندارد؛ تغییرات را بازبینی و سناریو را اجرا کنید."),
            )
        from services.scenario_execution_service import ScenarioExecutionService
        from ui.sensitivity_adapters import build_focus_request

        loaded.draft["execution_result"] = ScenarioExecutionService().execute(
            build_focus_request(loaded.draft), baseline_data
        )
        loaded.draft["show_result"] = True
        return loaded

    def load_target_scenario(
        self, scenario_id: str, *, baseline_data: pd.DataFrame, periods: Iterable[str],
        restore_execution: bool = False,
    ) -> LoadedWorkspaceScenario:
        loaded = self.load_scenario(
            scenario_id, branch_ids=baseline_data[BRANCH_ID].astype(str), periods=periods
        )
        if loaded.draft["scenario_type"] is not ScenarioType.TARGET_RANK:
            raise ValueError("سناریوی انتخاب‌شده از نوع رتبه هدف نیست.")
        if not restore_execution:
            loaded.draft["current_step"] = 1
            loaded.draft["target_execution_completed"] = False
            return loaded
        if loaded.record.status != "executed":
            loaded.draft["show_result"] = False
            return LoadedWorkspaceScenario(
                loaded.record, loaded.draft, loaded.results,
                (*loaded.warnings, "این پیش‌نویس هنوز نتیجه محاسبه‌شده ندارد؛ تغییرات را بازبینی و سناریو را اجرا کنید."),
            )
        from services.scenario_execution_service import ScenarioExecutionService
        from ui.sensitivity_adapters import build_target_comparison_request

        loaded.draft["target_comparison_result"] = ScenarioExecutionService().solve_target_rank_comparison(
            build_target_comparison_request(loaded.draft), baseline_data
        )
        loaded.draft["target_execution_timestamp"] = loaded.record.updated_at.isoformat(timespec="seconds")
        loaded.draft["target_execution_completed"] = True
        loaded.draft["current_step"] = 2
        return loaded

    @staticmethod
    def _target_changes(solution: TargetRankSolution) -> list[ScenarioChange]:
        if solution.scenario_data is None:
            return []
        branch = solution.scenario_data.loc[
            solution.scenario_data[BRANCH_ID].astype(str).eq(str(solution.focus_branch_id))
        ].iloc[0]
        return [
            ScenarioChange(str(solution.focus_branch_id), str(branch[BRANCH_NAME]), item.indicator_id,
                           item.baseline_raw_value, item.proposed_raw_value,
                           item.absolute_change, item.percent_change)
            for item in solution.indicator_proposals if item.absolute_change != 0
        ]

    def save_execution(self, draft: dict[str, Any]) -> ScenarioRecord:
        result = draft.get("execution_result")
        solution = draft.get("target_solution")
        target_comparison = draft.get("target_comparison_result")
        if isinstance(result, ScenarioExecutionResult):
            changes = list(result.changes)
            comparison = result.comparison_results
            selected = list(dict.fromkeys([
                result.request.focus_branch_id,
                *(item.branch_id for item in result.modified_branches),
                *(item.branch_id for item in result.rank_affected_branches),
            ]))
        elif isinstance(target_comparison, TargetRankComparisonResult):
            canonical = target_comparison.user_selected_indicators.solution
            changes = self._target_changes(canonical)
            comparison = compare_model_outputs(canonical.baseline_outputs, canonical.scenario_outputs)
            affected = comparison.branch_comparison.loc[
                comparison.branch_comparison["rank_change"].ne(0)
                | comparison.branch_comparison["score_change"].ne(0)
                | comparison.branch_comparison["grade_changed"]
            ][BRANCH_ID].astype(str).tolist()
            selected = list(dict.fromkeys([target_comparison.focus_branch_id, *affected]))
        elif isinstance(solution, TargetRankSolution) and solution.baseline_outputs is not None and solution.scenario_outputs is not None:
            changes = self._target_changes(solution)
            comparison = compare_model_outputs(solution.baseline_outputs, solution.scenario_outputs)
            affected = comparison.branch_comparison.loc[
                comparison.branch_comparison["rank_change"].ne(0)
                | comparison.branch_comparison["score_change"].ne(0)
                | comparison.branch_comparison["grade_changed"]
            ][BRANCH_ID].astype(str).tolist()
            selected = list(dict.fromkeys([solution.focus_branch_id, *affected]))
        else:
            raise ValueError("نتیجه رسمی اجرا برای ذخیره در دسترس نیست.")
        persisted = dict(draft.get("persistence") or {})
        save_as_new = False
        lineage = self._lineage(draft)
        record = self.management.save_executed(
            scenario_name=str(draft.get("scenario_name") or "").strip(),
            baseline_period=str(draft.get("period") or ""), selected_branch_ids=selected,
            changes=changes, comparison=comparison, summary=self._summary(draft, lineage),
            scenario_id=persisted.get("scenario_id"),
            expected_row_version=persisted.get("row_version"), save_as_new=save_as_new,
        )
        self._store_identity(draft, record)
        return record

    def create_new_version(self, scenario_id: str, new_name: str | None = None) -> ScenarioRecord:
        parent, changes, _ = self.management.load_scenario(scenario_id)
        definition = dict(parent.summary.get("scenario_definition") or {})
        lineage = dict(parent.summary.get("phase3b_lineage") or {})
        next_lineage = {
            "lineage_id": lineage.get("lineage_id") or parent.scenario_id,
            "version_number": int(lineage.get("version_number") or 1) + 1,
            "parent_scenario_id": parent.scenario_id,
        }
        summary = dict(parent.summary)
        summary.update(scenario_definition=definition, phase3b_lineage=next_lineage)
        return self.management.save_draft(
            scenario_name=(new_name or parent.scenario_name).strip(),
            baseline_period=parent.baseline_period,
            selected_branch_ids=list(parent.selected_branch_ids), changes=list(changes),
            summary=summary, save_as_new=True,
        )

    def delete_scenario(self, scenario_id: str, row_version: int) -> None:
        self.management.delete_scenario(scenario_id, row_version)


PERSISTENCE_STATUS_LABELS = {
    "draft": "پیش‌نویس", "executed": "اجراشده", "archived": "بایگانی‌شده",
    "dirty": "دارای تغییرات ذخیره‌نشده", "conflict": "تعارض نسخه", "error": "خطای اجرا",
}
