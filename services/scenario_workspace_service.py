"""Application boundary for the Phase 3B three-mode persisted workspace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from uuid import uuid4

import pandas as pd

from domain.scenario_contracts import ScenarioExecutionResult, ScenarioType, TargetRankSolution
from engine.comparison_engine import compare_model_outputs
from engine.indicator_registry import INDICATOR_REGISTRY
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME
from engine.scenario_engine import ScenarioChange
from persistence.models import ScenarioRecord, ScenarioResultSummary
from services.scenario_management_service import ScenarioManagementService
from ui.sensitivity_state import new_scenario_draft

DEFINITION_SCHEMA = "phase3b.1.v1"
PERSISTED_DRAFT_FIELDS = (
    "scenario_name", "period", "focus_branch_id", "focus_branch_source",
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
        elif key == "selected_indicator_ids":
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
    draft["current_step"] = max(1, min(4, int(definition.get("current_step") or 1)))
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
        return {
            "scenario_definition": serialize_sensitivity_draft(draft),
            "scenario_type": draft["scenario_type"].value,
            "phase3b_lineage": dict(lineage or self._lineage(draft)),
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
        self._store_identity(draft, record)
        return LoadedWorkspaceScenario(record, draft, tuple(results), warnings)

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
        if isinstance(result, ScenarioExecutionResult):
            changes = list(result.changes)
            comparison = result.comparison_results
            selected = list(dict.fromkeys([
                result.request.focus_branch_id,
                *(item.branch_id for item in result.modified_branches),
                *(item.branch_id for item in result.rank_affected_branches),
            ]))
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
        save_as_new = persisted.get("status") == "executed"
        lineage = self._lineage(draft)
        if save_as_new:
            lineage = {
                "lineage_id": lineage["lineage_id"],
                "version_number": int(lineage["version_number"]) + 1,
                "parent_scenario_id": persisted.get("scenario_id"),
            }
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


PERSISTENCE_STATUS_LABELS = {
    "draft": "پیش‌نویس", "executed": "اجراشده", "archived": "بایگانی‌شده",
    "dirty": "دارای تغییرات ذخیره‌نشده", "conflict": "تعارض نسخه", "error": "خطای اجرا",
}
