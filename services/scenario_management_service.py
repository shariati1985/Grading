"""Ownership-aware scenario persistence orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import math
from typing import Any
from uuid import uuid4

from engine.comparison_engine import ScenarioComparison
from engine.indicator_registry import INDICATOR_REGISTRY, validate_indicator_value
from engine.scenario_engine import ScenarioChange
from persistence.contracts import AuthorizationError, ScenarioRepository
from persistence.models import ScenarioChangeRecord, ScenarioRecord, ScenarioResultSummary

from .user_context import CurrentUser

ALLOWED_STATUSES = frozenset({"draft", "executed", "archived"})
ALLOWED_EDIT_MODES = frozenset({"percent", "direct"})


class ScenarioManagementService:
    """Validate and persist scenarios without duplicating model calculations."""

    def __init__(
        self,
        repository: ScenarioRepository,
        current_user: CurrentUser,
        *,
        model_version: str = "1.0",
        weights_version: str = "1.0",
    ) -> None:
        if not current_user.user_id.strip() or not current_user.display_name.strip():
            raise ValueError("Current user identity is required")
        self.repository = repository
        self.current_user = current_user
        self.model_version = model_version
        self.weights_version = weights_version

    @staticmethod
    def _validate(name: str, status: str) -> str:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("نام سناریو نمی‌تواند خالی باشد.")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"وضعیت سناریو نامعتبر است: {status}")
        return cleaned_name

    @staticmethod
    def _change_records(
        scenario_id: str,
        changes: list[ScenarioChange],
        edit_modes: dict[str, str] | None = None,
    ) -> list[ScenarioChangeRecord]:
        modes = edit_modes or {}
        invalid_modes = set(modes.values()) - ALLOWED_EDIT_MODES
        if invalid_modes:
            raise ValueError(f"روش ویرایش نامعتبر است: {sorted(invalid_modes)[0]}")
        for item in changes:
            code = validate_indicator_value(item.indicator_key, item.scenario_value)
            if code is not None:
                name = INDICATOR_REGISTRY.get(item.indicator_key)
                label = name.display_name if name else item.indicator_key
                raise ValueError(
                    f"مقدار نهایی شاخص «{label}» برای شعبه «{item.branch_name}» معتبر نیست ({code})."
                )
            if not math.isfinite(float(item.baseline_value)):
                raise ValueError(
                    f"مقدار مبنای شاخص «{item.indicator_key}» برای شعبه «{item.branch_name}» معتبر نیست."
                )
        return [
            ScenarioChangeRecord(
                scenario_id=scenario_id,
                branch_id=item.branch_id,
                branch_name=item.branch_name,
                indicator_key=item.indicator_key,
                baseline_value=float(item.baseline_value),
                scenario_value=float(item.scenario_value),
                absolute_change=float(item.absolute_change),
                percentage_change=float(item.percentage_change),
                edit_mode=modes.get(
                    f"{item.branch_id}:{item.indicator_key}", "direct"
                ),
            )
            for item in changes
        ]

    @staticmethod
    def _result_records(
        scenario_id: str,
        comparison: ScenarioComparison,
        selected_branch_ids: list[str],
    ) -> list[ScenarioResultSummary]:
        selected = comparison.branch_comparison.loc[
            comparison.branch_comparison["branch_id"].isin(selected_branch_ids)
        ]
        return [
            ScenarioResultSummary(
                scenario_id=scenario_id,
                branch_id=str(row.branch_id),
                baseline_score=float(row.baseline_score),
                scenario_score=float(row.scenario_score),
                baseline_rank=int(row.baseline_rank),
                scenario_rank=int(row.scenario_rank),
                baseline_grade=str(row.baseline_grade),
                scenario_grade=str(row.scenario_grade),
                rank_change=int(row.rank_change),
                score_change=float(row.score_change),
            )
            for row in selected.itertuples(index=False)
        ]

    def _save(
        self,
        *,
        scenario_name: str,
        baseline_period: str,
        status: str,
        selected_branch_ids: list[str],
        changes: list[ScenarioChange],
        summary: dict[str, Any] | None,
        comparison: ScenarioComparison | None,
        scenario_id: str | None,
        expected_row_version: int | None,
        save_as_new: bool,
        edit_modes: dict[str, str] | None,
    ) -> ScenarioRecord:
        name = self._validate(scenario_name, status)
        branch_ids = list(dict.fromkeys(map(str, selected_branch_ids)))
        scenario_summary = dict(summary or {})
        scenario_summary.setdefault("selected_branch_count", len(branch_ids))
        scenario_summary.setdefault(
            "changed_branch_count", len({item.branch_id for item in changes})
        )
        if comparison is not None:
            scenario_summary.update(comparison.summary)

        should_create = not scenario_id or save_as_new
        effective_id = str(uuid4()) if should_create else str(scenario_id)
        now = datetime.now(timezone.utc)
        results = (
            self._result_records(effective_id, comparison, branch_ids)
            if comparison is not None
            else []
        )
        change_records = self._change_records(effective_id, changes, edit_modes)
        if should_create:
            record = ScenarioRecord(
                scenario_id=effective_id,
                scenario_name=name,
                baseline_period=baseline_period,
                owner_user_id=self.current_user.user_id,
                owner_display_name=self.current_user.display_name,
                status=status,
                visibility="private",
                model_version=self.model_version,
                weights_version=self.weights_version,
                created_at=now,
                updated_at=now,
                row_version=1,
                selected_branch_ids=branch_ids,
                summary=scenario_summary,
            )
            return self.repository.create_scenario(record, change_records, results)

        if expected_row_version is None:
            raise ValueError("برای به‌روزرسانی، نسخه رکورد سناریو لازم است.")
        existing, _, _ = self.repository.get_scenario(
            effective_id, self.current_user.user_id
        )
        if existing.owner_user_id != self.current_user.user_id:
            raise AuthorizationError("Only the scenario owner may update this scenario")
        updated = replace(
            existing,
            scenario_name=name,
            baseline_period=baseline_period,
            status=status,
            visibility="private",
            model_version=self.model_version,
            weights_version=self.weights_version,
            selected_branch_ids=branch_ids,
            summary=scenario_summary,
        )
        return self.repository.update_scenario(
            updated,
            change_records,
            expected_row_version,
            results,
            requesting_user_id=self.current_user.user_id,
        )

    def save_draft(
        self,
        *,
        scenario_name: str,
        baseline_period: str,
        selected_branch_ids: list[str],
        changes: list[ScenarioChange],
        summary: dict[str, Any] | None = None,
        scenario_id: str | None = None,
        expected_row_version: int | None = None,
        save_as_new: bool = False,
        edit_modes: dict[str, str] | None = None,
    ) -> ScenarioRecord:
        return self._save(
            scenario_name=scenario_name,
            baseline_period=baseline_period,
            status="draft",
            selected_branch_ids=selected_branch_ids,
            changes=changes,
            summary=summary,
            comparison=None,
            scenario_id=scenario_id,
            expected_row_version=expected_row_version,
            save_as_new=save_as_new,
            edit_modes=edit_modes,
        )

    def save_executed(
        self,
        *,
        scenario_name: str,
        baseline_period: str,
        selected_branch_ids: list[str],
        changes: list[ScenarioChange],
        comparison: ScenarioComparison,
        summary: dict[str, Any] | None = None,
        scenario_id: str | None = None,
        expected_row_version: int | None = None,
        save_as_new: bool = False,
        edit_modes: dict[str, str] | None = None,
    ) -> ScenarioRecord:
        return self._save(
            scenario_name=scenario_name,
            baseline_period=baseline_period,
            status="executed",
            selected_branch_ids=selected_branch_ids,
            changes=changes,
            summary=summary,
            comparison=comparison,
            scenario_id=scenario_id,
            expected_row_version=expected_row_version,
            save_as_new=save_as_new,
            edit_modes=edit_modes,
        )

    def load_scenario(
        self, scenario_id: str
    ) -> tuple[ScenarioRecord, list[ScenarioChange], list[ScenarioResultSummary]]:
        record, changes, results = self.repository.get_scenario(
            scenario_id, self.current_user.user_id
        )
        engine_changes = [
            ScenarioChange(
                branch_id=item.branch_id,
                branch_name=item.branch_name,
                indicator_key=item.indicator_key,
                baseline_value=item.baseline_value,
                scenario_value=item.scenario_value,
                absolute_change=item.absolute_change,
                percentage_change=item.percentage_change,
            )
            for item in changes
        ]
        return record, engine_changes, results

    def load_scenario_editor(
        self, scenario_id: str
    ) -> tuple[
        ScenarioRecord,
        list[ScenarioChange],
        list[ScenarioResultSummary],
        dict[str, str],
    ]:
        """Load engine changes plus the persisted per-indicator editing method."""
        record, stored_changes, results = self.repository.get_scenario(
            scenario_id, self.current_user.user_id
        )
        engine_changes = [
            ScenarioChange(
                branch_id=item.branch_id,
                branch_name=item.branch_name,
                indicator_key=item.indicator_key,
                baseline_value=item.baseline_value,
                scenario_value=item.scenario_value,
                absolute_change=item.absolute_change,
                percentage_change=item.percentage_change,
            )
            for item in stored_changes
        ]
        edit_modes = {
            f"{item.branch_id}:{item.indicator_key}": item.edit_mode
            for item in stored_changes
        }
        return record, engine_changes, results, edit_modes

    def list_visible(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[ScenarioRecord]:
        return self.repository.list_scenarios(
            self.current_user.user_id,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )

    def copy_scenario(self, scenario_id: str, new_name: str) -> ScenarioRecord:
        return self.repository.copy_scenario(
            scenario_id,
            self.current_user.user_id,
            self.current_user.display_name,
            new_name.strip(),
        )

    def archive_scenario(self, scenario_id: str, row_version: int) -> ScenarioRecord:
        return self.repository.archive_scenario(
            scenario_id, self.current_user.user_id, row_version
        )

    def delete_scenario(self, scenario_id: str, row_version: int) -> None:
        self.repository.delete_scenario(
            scenario_id, self.current_user.user_id, row_version
        )
