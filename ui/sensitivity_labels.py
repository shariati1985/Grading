"""Persian presentation labels for the three-mode sensitivity workspace."""

from __future__ import annotations

from dataclasses import dataclass

from domain.scenario_contracts import ScenarioType, TargetRankStatus
from engine.scenario_rule_engine import RuleOperation
from services.selection_scope import SelectionScope

SCENARIO_TYPE_LABELS = {
    ScenarioType.FOCUS_BRANCH_ONLY: "سناریوی شعبه‌محور",
    ScenarioType.MULTI_BRANCH: "سناریوی چندشعبه‌ای",
    ScenarioType.TARGET_RANK: "سناریوی رتبه هدف",
}

SCENARIO_DESCRIPTIONS = {
    ScenarioType.FOCUS_BRANCH_ONLY: "اثر تغییر شاخص‌های یک شعبه را بر رتبه، امتیاز و درجه بررسی کنید.",
    ScenarioType.MULTI_BRANCH: "قواعد عمومی و تغییرات اختصاصی را برای چند شعبه اعمال کنید.",
    ScenarioType.TARGET_RANK: "رشد متوازن موردنیاز شاخص‌ها برای دستیابی به رتبه هدف را بسنجید.",
}


@dataclass(frozen=True)
class ScenarioDefinition:
    """One shared presentation/navigation definition for a scenario mode."""

    scenario_type: ScenarioType
    label: str
    description: str
    icon: str
    color: str


SCENARIO_DEFINITIONS = tuple(
    ScenarioDefinition(mode, SCENARIO_TYPE_LABELS[mode], SCENARIO_DESCRIPTIONS[mode], icon, color)
    for mode, icon, color in (
        (ScenarioType.FOCUS_BRANCH_ONLY, "bank", "purple"),
        (ScenarioType.MULTI_BRANCH, "buildings", "purple"),
        (ScenarioType.TARGET_RANK, "target", "purple"),
    )
)

OPERATION_LABELS = {
    RuleOperation.PERCENT_CHANGE: "درصد تغییر",
    RuleOperation.ABSOLUTE_CHANGE: "تغییر مطلق",
    RuleOperation.SET_VALUE: "تعیین مقدار نهایی",
}

SCOPE_LABELS = {
    SelectionScope.USER_BRANCH: "شعبه محوری",
    SelectionScope.SELECTED_BRANCHES: "شعب منتخب",
    SelectionScope.SELECTED_REGIONS: "مناطق منتخب",
    SelectionScope.ALL_BRANCHES: "کل شعب",
}

TARGET_STATUS_LABELS = {
    TargetRankStatus.NO_CHANGE_REQUIRED: "شعبه هم‌اکنون رتبه درخواستی را دارد یا از آن بهتر است",
    TargetRankStatus.TARGET_REACHED: "رتبه هدف حاصل شد",
    TargetRankStatus.TARGET_NOT_REACHABLE: "رتبه هدف با محدودیت‌های تعیین‌شده قابل دستیابی نیست",
    TargetRankStatus.MAX_ITERATIONS_REACHED: "محاسبه در محدوده تنظیمات به نتیجه قطعی نرسید",
    TargetRankStatus.INVALID_REQUEST: "اطلاعات درخواست معتبر نیست",
}

MODE_COLORS = {
    item.scenario_type: item.color for item in SCENARIO_DEFINITIONS
}

INDICATOR_TYPE_LABELS = {"benefit": "شاخص افزایشی"}


def scenario_type_label(value: ScenarioType) -> str:
    return SCENARIO_TYPE_LABELS[value]


def operation_label(value: RuleOperation) -> str:
    return OPERATION_LABELS[value]


def target_status_label(value: TargetRankStatus) -> str:
    return TARGET_STATUS_LABELS[value]
