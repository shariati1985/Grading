"""Versioned, UI-independent contracts for multi-branch scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


MULTI_BRANCH_SCHEMA_VERSION = "1.0"


class ActorScope(str, Enum):
    """Authorization-ready actor scopes; no identity-provider logic lives here."""

    BRANCH = "branch"
    HEAD_OFFICE = "head_office"
    STAFF = "staff"


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    actor_scope: ActorScope
    assigned_branch_code: str | None = None
    can_select_primary_branch: bool = True


class PercentageDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"


class EffectiveChangeSource(str, Enum):
    PRIMARY_EXPLICIT = "primary_explicit"
    BRANCH_EXCEPTION = "branch_exception"
    GENERAL_RULE = "general_rule"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class PercentageRule:
    indicator_key: str
    direction: PercentageDirection
    percentage: float


@dataclass(frozen=True)
class BranchException:
    branch_code: str
    indicator_rules: tuple[PercentageRule, ...]


@dataclass(frozen=True)
class PrimaryBranchOverride:
    indicator_key: str
    input_mode: str
    input_value: float
    resolved_raw_value: float


@dataclass(frozen=True)
class PopulationDefinition:
    """Auditable reference to the official eligible ranking population."""

    policy_id: str
    period: str | None = None
    expected_branch_count: int | None = None


@dataclass(frozen=True)
class EffectiveChange:
    branch_code: str
    indicator_key: str
    baseline_value: float
    scenario_value: float
    effective_source: EffectiveChangeSource
    effective_percentage: float | None = None
    explicit_input_mode: str | None = None
    explicit_input_value: float | None = None

    @property
    def changed(self) -> bool:
        return self.scenario_value != self.baseline_value


@dataclass(frozen=True)
class CalculationMetadata:
    engine_contract: str
    baseline_fingerprint: str | None = None
    calculated_at: datetime | None = None


@dataclass(frozen=True)
class MultiBranchScenarioV1:
    scenario_id: str
    scenario_name: str
    created_at: datetime
    updated_at: datetime
    actor_context: ActorContext
    primary_branch_code: str
    population_definition: PopulationDefinition
    general_rules: tuple[PercentageRule, ...] = ()
    branch_exceptions: tuple[BranchException, ...] = ()
    primary_branch_overrides: tuple[PrimaryBranchOverride, ...] = ()
    calculation_metadata: CalculationMetadata | None = None
    effective_change_manifest: tuple[EffectiveChange, ...] = field(default=(), repr=False)
    scenario_type: str = "MULTI_BRANCH"
    schema_version: str = MULTI_BRANCH_SCHEMA_VERSION
    optional_notes: str | None = None
    extension_data: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)
