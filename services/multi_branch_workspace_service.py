"""Persistence adapter for the dedicated multi-branch workspace."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
import unicodedata
from typing import Any
from uuid import uuid4

import pandas as pd

from domain.multi_branch_contracts import EffectiveChange
from engine.comparison_engine import ScenarioComparison
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME
from engine.scenario_engine import ScenarioChange
from persistence.models import ScenarioRecord, ScenarioResultSummary
from services.scenario_management_service import ScenarioManagementService


DEFINITION_KEY = "multi_branch_definition"
SCENARIO_TYPE = "MULTI_BRANCH_V1"
STAGE_DETAILS = "scenario_details"
STAGE_VALUES = {
    STAGE_DETAILS,
    "general_rules",
    "branch_exceptions",
    "primary_branch_overrides",
    "review",
}


def normalize_multi_branch_scenario_name(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_branch_code(value: object) -> str:
    return str(value or "").strip()


def multi_branch_logical_key(record: ScenarioRecord) -> tuple[str, str, str, str] | None:
    if record.summary.get("scenario_type") != SCENARIO_TYPE:
        return None
    definition = dict(record.summary.get(DEFINITION_KEY) or {})
    primary = definition.get("primary_branch_code")
    if primary is None and record.selected_branch_ids:
        primary = record.selected_branch_ids[0]
    return (
        record.owner_user_id,
        SCENARIO_TYPE,
        normalize_multi_branch_scenario_name(record.scenario_name),
        normalize_branch_code(primary),
    )


def _new_workspace() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "current_stage": STAGE_DETAILS,
        "scenario_name": "",
        "period": "1404-04",
        "primary_branch_code": None,
        "general_rules": [],
        "branch_exceptions": {},
        "primary_branch_overrides": {},
        "validation_errors": [],
        "preview": None,
        "execution_result": None,
        "show_result": False,
        "persistence": {},
        "entry_source": "new",
        "persisted_result_summaries": [],
        "show_persisted_result": False,
    }


@dataclass(frozen=True)
class LoadedMultiBranchWorkspace:
    record: ScenarioRecord
    workspace: dict[str, Any]
    results: tuple[ScenarioResultSummary, ...]
    warnings: tuple[str, ...] = ()


def serialize_multi_branch_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    """Return only JSON-safe, editable fields; calculated objects stay transient."""
    return {
        "schema_version": "1.0",
        "scenario_name": str(workspace.get("scenario_name") or ""),
        "period": str(workspace.get("period") or ""),
        "primary_branch_code": (
            str(workspace["primary_branch_code"])
            if workspace.get("primary_branch_code") is not None else None
        ),
        "general_rules": deepcopy(list(workspace.get("general_rules") or [])),
        "branch_exceptions": deepcopy(dict(workspace.get("branch_exceptions") or {})),
        "primary_branch_overrides": deepcopy(
            dict(workspace.get("primary_branch_overrides") or {})
        ),
        "current_stage": str(
            workspace.get("current_stage") or STAGE_DETAILS
        ),
    }


def restore_multi_branch_workspace(
    definition: dict[str, Any], *, branch_ids: list[str]
) -> tuple[dict[str, Any], tuple[str, ...]]:
    workspace = _new_workspace()
    known = set(map(str, branch_ids))
    warnings: list[str] = []
    primary = definition.get("primary_branch_code")
    if primary is not None and str(primary) not in known:
        warnings.append("شعبه اصلی ذخیره‌شده دیگر در جامعه رسمی موجود نیست.")
        primary = None
    exceptions = {
        str(branch): deepcopy(list(rules))
        for branch, rules in dict(definition.get("branch_exceptions") or {}).items()
        if str(branch) in known
    }
    missing = set(map(str, dict(definition.get("branch_exceptions") or {}))) - known
    if missing:
        warnings.append("استثناهای مربوط به شعب خارج از جامعه فعلی کنار گذاشته شدند.")
    stage = str(definition.get("current_stage") or STAGE_DETAILS)
    if stage not in STAGE_VALUES:
        stage = STAGE_DETAILS
    workspace.update(
        scenario_name=str(definition.get("scenario_name") or ""),
        period=str(definition.get("period") or ""),
        primary_branch_code=str(primary) if primary is not None else None,
        general_rules=deepcopy(list(definition.get("general_rules") or [])),
        branch_exceptions=exceptions,
        primary_branch_overrides=deepcopy(
            dict(definition.get("primary_branch_overrides") or {})
        ),
        current_stage=stage,
    )
    return workspace, tuple(warnings)


class MultiBranchWorkspaceService:
    def __init__(self, management: ScenarioManagementService) -> None:
        self.management = management

    @staticmethod
    def _lineage(workspace: dict[str, Any], *, new_version: bool = False) -> dict[str, Any]:
        persisted = dict(workspace.get("persistence") or {})
        version = int(persisted.get("version_number") or 1)
        return {
            "lineage_id": persisted.get("lineage_id") or str(uuid4()),
            "version_number": version + 1 if new_version else version,
            "parent_scenario_id": (
                persisted.get("scenario_id") if new_version
                else persisted.get("parent_scenario_id")
            ),
        }

    def _find_existing_logical_record(self, workspace: dict[str, Any]) -> ScenarioRecord | None:
        candidate = (
            self.management.current_user.user_id,
            SCENARIO_TYPE,
            normalize_multi_branch_scenario_name(workspace.get("scenario_name")),
            normalize_branch_code(workspace.get("primary_branch_code")),
        )
        matches = [
            item for item in self.management.list_visible(limit=100)
            if multi_branch_logical_key(item) == candidate
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: (item.updated_at, item.created_at, item.scenario_id))

    @classmethod
    def _summary(
        cls, workspace: dict[str, Any], *, new_version: bool = False
    ) -> dict[str, Any]:
        return {
            "scenario_type": SCENARIO_TYPE,
            DEFINITION_KEY: serialize_multi_branch_workspace(workspace),
            "phase3b_lineage": cls._lineage(workspace, new_version=new_version),
        }

    def _summary_with_existing_result_state(
        self, workspace: dict[str, Any], *, new_version: bool = False
    ) -> dict[str, Any]:
        summary = self._summary(workspace, new_version=new_version)
        persisted = dict(workspace.get("persistence") or {})
        scenario_id = persisted.get("scenario_id")
        if scenario_id:
            try:
                existing, _, results = self.management.load_scenario(str(scenario_id))
            except Exception:
                existing = None
                results = []
            if results or (existing is not None and existing.summary.get("has_saved_result")):
                summary["has_saved_result"] = True
        return summary

    @staticmethod
    def _store_identity(workspace: dict[str, Any], record: ScenarioRecord) -> None:
        lineage = dict(record.summary.get("phase3b_lineage") or {})
        workspace["persistence"] = {
            "scenario_id": record.scenario_id,
            "row_version": record.row_version,
            "status": record.status,
            "dirty": False,
            **lineage,
            "saved_definition": dict(record.summary.get(DEFINITION_KEY) or {}),
        }

    @staticmethod
    def has_unsaved_changes(workspace: dict[str, Any]) -> bool:
        persisted = dict(workspace.get("persistence") or {})
        current = serialize_multi_branch_workspace(workspace)
        if not persisted.get("scenario_id"):
            return any((current["scenario_name"], current["primary_branch_code"],
                        current["general_rules"], current["branch_exceptions"],
                        current["primary_branch_overrides"]))
        return persisted.get("saved_definition") != current

    def save_draft(
        self, workspace: dict[str, Any], *, save_as_new: bool = False
    ) -> ScenarioRecord:
        persisted = dict(workspace.get("persistence") or {})
        existing = None if persisted.get("scenario_id") else self._find_existing_logical_record(workspace)
        if existing is not None:
            persisted = {
                **persisted,
                "scenario_id": existing.scenario_id,
                "row_version": existing.row_version,
                "version_number": int(dict(existing.summary.get("phase3b_lineage") or {}).get("version_number") or 1),
            }
            workspace["persistence"] = persisted
        save_action = "version" if save_as_new else "updated" if persisted.get("scenario_id") else "created"
        record = self.management.save_draft(
            scenario_name=str(workspace.get("scenario_name") or ""),
            baseline_period=str(workspace.get("period") or ""),
            selected_branch_ids=(
                [str(workspace["primary_branch_code"])]
                if workspace.get("primary_branch_code") else []
            ),
            changes=[],
            summary=self._summary_with_existing_result_state(workspace, new_version=save_as_new),
            scenario_id=persisted.get("scenario_id"),
            expected_row_version=persisted.get("row_version"),
            save_as_new=False,
        )
        self._store_identity(workspace, record)
        workspace["last_save_action"] = save_action
        return record

    @staticmethod
    def _changes(
        manifest: tuple[EffectiveChange, ...], data: pd.DataFrame
    ) -> list[ScenarioChange]:
        names = data.assign(**{BRANCH_ID: data[BRANCH_ID].astype(str)}).set_index(BRANCH_ID)[BRANCH_NAME]
        return [
            ScenarioChange(
                branch_id=item.branch_code,
                branch_name=str(names.get(item.branch_code, item.branch_code)),
                indicator_key=item.indicator_key,
                baseline_value=float(item.baseline_value),
                scenario_value=float(item.scenario_value),
                absolute_change=float(item.scenario_value - item.baseline_value),
                percentage_change=(
                    float((item.scenario_value - item.baseline_value) / item.baseline_value * 100)
                    if item.baseline_value else 0.0
                ),
            )
            for item in manifest if item.changed
        ]

    def save_execution(
        self, workspace: dict[str, Any], *, data: pd.DataFrame
    ) -> ScenarioRecord:
        result = workspace.get("execution_result")
        if not result:
            raise ValueError("نتیجه رسمی اجرا برای ذخیره در دسترس نیست.")
        persisted = dict(workspace.get("persistence") or {})
        existing = None if persisted.get("scenario_id") else self._find_existing_logical_record(workspace)
        if existing is not None:
            persisted = {
                **persisted,
                "scenario_id": existing.scenario_id,
                "row_version": existing.row_version,
                "version_number": int(dict(existing.summary.get("phase3b_lineage") or {}).get("version_number") or 1),
            }
            workspace["persistence"] = persisted
        comparison: ScenarioComparison = result["comparison"]
        summary = self._summary(workspace)
        summary["has_saved_result"] = True
        record = self.management.save_executed(
            scenario_name=str(workspace.get("scenario_name") or ""),
            baseline_period=str(workspace.get("period") or ""),
            selected_branch_ids=data[BRANCH_ID].astype(str).tolist(),
            changes=self._changes(result["resolved"].manifest, data),
            comparison=comparison,
            summary=summary,
            scenario_id=persisted.get("scenario_id"),
            expected_row_version=persisted.get("row_version"),
        )
        self._store_identity(workspace, record)
        return record

    def load(
        self, scenario_id: str, *, branch_ids: list[str]
    ) -> LoadedMultiBranchWorkspace:
        record, _, results = self.management.load_scenario(scenario_id)
        definition = dict(record.summary.get(DEFINITION_KEY) or {})
        if record.summary.get("scenario_type") != SCENARIO_TYPE or not definition:
            raise ValueError("رکورد انتخاب‌شده سناریوی چندشعبه‌ای جدید نیست.")
        workspace, warnings = restore_multi_branch_workspace(
            definition, branch_ids=branch_ids
        )
        workspace["entry_source"] = "saved"
        workspace["persisted_result_summaries"] = list(results)
        workspace["show_persisted_result"] = record.status == "executed" and bool(results)
        self._store_identity(workspace, record)
        return LoadedMultiBranchWorkspace(record, workspace, tuple(results), warnings)

    def create_new_version(self, scenario_id: str, *, branch_ids: list[str]) -> ScenarioRecord:
        loaded = self.load(scenario_id, branch_ids=branch_ids)
        return self.save_draft(loaded.workspace, save_as_new=True)

    def delete_scenario(self, scenario_id: str, row_version: int) -> None:
        self.management.delete_scenario(scenario_id, row_version)
