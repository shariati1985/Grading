"""Pure presentation model and Streamlit renderer for multi-branch results."""

from __future__ import annotations

from dataclasses import dataclass
import html

import pandas as pd
try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover
    st = None

from domain.multi_branch_contracts import EffectiveChange, EffectiveChangeSource
from engine.indicator_registry import INDICATOR_REGISTRY
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME
from ui.charts import (
    build_indicator_impact_chart,
    build_multi_branch_rank_movement_chart,
    render_chart,
)
from ui.formatters import (
    format_grade,
    format_persian_number,
    format_persian_percentage,
    format_signed_persian_number,
    persian_digits,
)


GRADE_LEVEL = {"Grade 3": 0, "Grade 2": 1, "Grade 1": 2, "Excellent": 3, "Excellent Plus": 4}
STATUS_OPTIONS = {
    "all": "همه شعب",
    "rank_up": "صعود رتبه",
    "rank_down": "نزول رتبه",
    "score_up": "بهبود امتیاز",
    "score_down": "افت امتیاز",
    "grade_up": "بهبود درجه",
    "grade_down": "افت درجه",
    "unchanged": "بدون تغییر",
}
SOURCE_OPTIONS = {
    "all": "همه منابع",
    "general": "قاعده عمومی",
    "exception": "استثنای شعبه",
    "primary": "مقدار اختصاصی شعبه اصلی",
    "unchanged": "بدون قاعده مؤثر",
}
SOURCE_LABELS = {
    EffectiveChangeSource.PRIMARY_EXPLICIT: "مقدار اختصاصی شعبه اصلی",
    EffectiveChangeSource.BRANCH_EXCEPTION: "استثنای شعبه",
    EffectiveChangeSource.GENERAL_RULE: "قاعده عمومی",
    EffectiveChangeSource.UNCHANGED: "بدون تغییر",
}
SOURCE_KEYS = {
    EffectiveChangeSource.PRIMARY_EXPLICIT: "primary",
    EffectiveChangeSource.BRANCH_EXCEPTION: "exception",
    EffectiveChangeSource.GENERAL_RULE: "general",
    EffectiveChangeSource.UNCHANGED: "unchanged",
}
INPUT_MODE_LABELS = {"percent": "تغییر درصدی", "absolute": "تغییر مطلق", "final": "مقدار نهایی", None: "قاعده درصدی"}


@dataclass(frozen=True)
class MultiBranchResultSummary:
    total_branches: int
    raw_changed_branches: int
    branch_indicator_changes: int
    score_changed_branches: int
    rank_up: int
    rank_down: int
    rank_same: int
    grade_up: int
    grade_down: int
    grade_same: int
    net_rank_movement: int
    average_score_change: float
    largest_rank_up: int
    largest_rank_down: int

    @property
    def rank_moved_branches(self) -> int:
        return self.rank_up + self.rank_down


def _pct(count: int, total: int) -> float:
    return 0.0 if total <= 0 else count * 100 / total


def format_raw_display(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "—"
    decimals = 0 if abs(float(number) - round(float(number))) < 0.005 else 2
    rendered = format_persian_number(float(number), decimals)
    return rendered.rstrip("۰").rstrip("٫") if decimals else rendered


def format_score_display(value: object) -> str:
    return format_persian_number(value, 1)


def format_rank_movement_label(value: object) -> str:
    movement = int(value)
    if movement > 0:
        return f"{format_persian_number(movement, 0)} رتبه صعود"
    if movement < 0:
        return f"{format_persian_number(abs(movement), 0)} رتبه نزول"
    return "بدون جابه‌جایی"


def format_score_change_label(value: object) -> str:
    return format_signed_persian_number(value, 1)


def format_percentage_display(value: object, decimals: int = 2) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "—"
    rendered = format_persian_percentage(float(number), decimals)
    return rendered.replace("٫۰۰٪", "٪").replace("٫۰٪", "٪")


def _value(value: object, css_class: str = "") -> str:
    class_attr = f' class="{css_class}"' if css_class else ""
    return f'<strong{class_attr} dir="ltr">{html.escape(str(value))}</strong>'


def _metric_item(label: str, value: object, css_class: str = "") -> str:
    return (
        f'<div class="multi-metric-item {css_class}">'
        f"<span>{html.escape(label)}</span>{_value(value)}</div>"
    )


def _compact_metric(label: str, value: object) -> str:
    return (
        '<span class="multi-compact-metric">'
        f'<small>{html.escape(label)}</small>{_value(value)}</span>'
    )


def _grade_change(row: pd.Series) -> int:
    return GRADE_LEVEL.get(str(row["scenario_grade"]), -1) - GRADE_LEVEL.get(str(row["baseline_grade"]), -1)


def _manifest_by_branch(manifest: tuple[EffectiveChange, ...]) -> dict[str, list[EffectiveChange]]:
    grouped: dict[str, list[EffectiveChange]] = {}
    for item in manifest:
        grouped.setdefault(str(item.branch_code), []).append(item)
    return grouped


def build_audit_long_form(manifest: tuple[EffectiveChange, ...]) -> pd.DataFrame:
    rows = []
    for item in manifest:
        baseline = float(item.baseline_value)
        scenario = float(item.scenario_value)
        rows.append({
            "branch_code": str(item.branch_code),
            "indicator_key": item.indicator_key,
            "indicator_display_name": INDICATOR_REGISTRY[item.indicator_key].display_name,
            "effective_source": SOURCE_KEYS[item.effective_source],
            "effective_source_text": SOURCE_LABELS[item.effective_source],
            "input_mode": item.explicit_input_mode,
            "input_mode_text": INPUT_MODE_LABELS.get(item.explicit_input_mode, str(item.explicit_input_mode or "")),
            "entered_value": item.explicit_input_value,
            "effective_percentage": item.effective_percentage,
            "baseline_raw_value": baseline,
            "scenario_raw_value": scenario,
            "absolute_change": scenario - baseline,
            "percentage_change": None if baseline == 0 else (scenario - baseline) * 100 / baseline,
            "changed_flag": bool(item.changed),
        })
    return pd.DataFrame(rows)


def build_network_result_table(comparison: pd.DataFrame, manifest: tuple[EffectiveChange, ...]) -> pd.DataFrame:
    by_branch = _manifest_by_branch(manifest)
    result = comparison.copy(deep=True)
    result[BRANCH_ID] = result[BRANCH_ID].astype(str)
    result["grade_change"] = result.apply(_grade_change, axis=1)
    result["rank_status"] = result["rank_change"].map(lambda value: "rank_up" if value > 0 else "rank_down" if value < 0 else "rank_same")
    result["score_status"] = result["score_change"].map(lambda value: "score_up" if value > 0 else "score_down" if value < 0 else "score_same")
    result["grade_status"] = result["grade_change"].map(lambda value: "grade_up" if value > 0 else "grade_down" if value < 0 else "grade_same")
    sources, source_texts, indicators, changed_counts = [], [], [], []
    for code in result[BRANCH_ID]:
        effective = [item for item in by_branch.get(code, []) if item.changed]
        source_set = frozenset(item.effective_source for item in effective)
        sources.append(source_set)
        source_texts.append("، ".join(dict.fromkeys(SOURCE_LABELS[item.effective_source] for item in effective)) or "بدون قاعده مؤثر")
        indicators.append(frozenset(item.indicator_key for item in effective))
        changed_counts.append(len(effective))
    result["effective_sources"] = sources
    result["effective_source_text"] = source_texts
    result["affected_indicators"] = indicators
    result["changed_indicator_count"] = changed_counts
    return result


def summarize_network(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...] = ()) -> MultiBranchResultSummary:
    total = len(table)
    changed = [item for item in manifest if item.changed]
    raw_changed = len({str(item.branch_code) for item in changed}) if manifest else int(table["changed_indicator_count"].gt(0).sum())
    return MultiBranchResultSummary(
        total_branches=total,
        raw_changed_branches=raw_changed,
        branch_indicator_changes=len(changed) if manifest else int(table["changed_indicator_count"].sum()),
        score_changed_branches=int(table["score_change"].ne(0).sum()),
        rank_up=int(table["rank_change"].gt(0).sum()),
        rank_down=int(table["rank_change"].lt(0).sum()),
        rank_same=int(table["rank_change"].eq(0).sum()),
        grade_up=int(table["grade_change"].gt(0).sum()),
        grade_down=int(table["grade_change"].lt(0).sum()),
        grade_same=int(table["grade_change"].eq(0).sum()),
        net_rank_movement=int(table["rank_change"].gt(0).sum() - table["rank_change"].lt(0).sum()),
        average_score_change=float(table["score_change"].mean()) if total else 0.0,
        largest_rank_up=max(0, int(table["rank_change"].max())) if total else 0,
        largest_rank_down=min(0, int(table["rank_change"].min())) if total else 0,
    )


def managerial_conclusion(summary: MultiBranchResultSummary) -> str:
    raw_pct = _pct(summary.raw_changed_branches, summary.total_branches)
    score_pct = _pct(summary.score_changed_branches, summary.total_branches)
    rank_pct = _pct(summary.rank_moved_branches, summary.total_branches)
    grade_extent = summary.grade_up + summary.grade_down
    if raw_pct >= 50 and rank_pct < 10:
        shape = "سناریو در سطح مقادیر خام گسترده است، اما اثر آن بر رتبه‌بندی شعب محدود باقی مانده است"
    elif raw_pct < 20 and rank_pct >= 20:
        shape = "اثر سناریو محدود به بخشی کوچک‌تر از شبکه است، اما در همان بخش متمرکزتر دیده می‌شود"
    elif summary.net_rank_movement > 0 and summary.average_score_change >= 0:
        shape = "اثر سناریو عمدتاً مثبت است"
    elif summary.net_rank_movement < 0 and summary.average_score_change <= 0:
        shape = "اثر سناریو عمدتاً منفی است"
    else:
        shape = "اثر سناریو متوازن و بدون غلبه روشن یک جهت است"
    direction = "خالص حرکت رتبه مثبت است" if summary.net_rank_movement > 0 else "خالص حرکت رتبه منفی است" if summary.net_rank_movement < 0 else "خالص حرکت رتبه خنثی است"
    return (
        f"{shape}؛ {format_persian_percentage(raw_pct, 1)} از جامعه (کل شعب) تغییر مقدار داشته‌اند، "
        f"{format_persian_percentage(score_pct, 1)} تغییر امتیاز و {format_persian_percentage(rank_pct, 1)} جابه‌جایی رتبه ثبت کرده‌اند. "
        f"{direction} و تغییر درجه در {format_persian_number(grade_extent, 0)} شعبه مشاهده شده است."
    )


def managerial_conclusion_model(summary: MultiBranchResultSummary) -> dict[str, object]:
    raw_pct = _pct(summary.raw_changed_branches, summary.total_branches)
    rank_pct = _pct(summary.rank_moved_branches, summary.total_branches)
    if summary.net_rank_movement > 0 and summary.average_score_change >= 0:
        headline = "اثر سناریو عمدتاً مثبت است"
        tone = "success"
    elif summary.net_rank_movement < 0 and summary.average_score_change <= 0:
        headline = "اثر سناریو عمدتاً منفی است"
        tone = "danger"
    elif raw_pct >= 50 and rank_pct < 10:
        headline = "اثر سناریو گسترده اما کم‌عمق است"
        tone = "neutral"
    else:
        headline = "اثر سناریو ترکیبی و متوازن است"
        tone = "neutral"
    evidence = [
        ("پوشش تغییر مقدار", format_persian_percentage(raw_pct, 1)),
        ("تغییر امتیاز", format_persian_percentage(_pct(summary.score_changed_branches, summary.total_branches), 1)),
        ("جابه‌جایی رتبه", format_persian_percentage(rank_pct, 1)),
        ("خالص جهت حرکت رتبه", format_signed_persian_number(summary.net_rank_movement, 0)),
        ("تعداد تغییرات شعبه–شاخص", format_persian_number(summary.branch_indicator_changes, 0)),
    ]
    return {"headline": headline, "tone": tone, "body": managerial_conclusion(summary), "evidence": evidence}


def top_movers(table: pd.DataFrame, *, improvement: bool, limit: int = 5) -> pd.DataFrame:
    subset = table.loc[table["rank_change"].gt(0) if improvement else table["rank_change"].lt(0)].copy()
    if subset.empty:
        return subset
    subset["_rank_sort"] = subset["rank_change"].abs()
    subset["_score_sort"] = subset["score_change"] if improvement else -subset["score_change"]
    return subset.sort_values(["_rank_sort", "_score_sort"], ascending=False).head(limit).drop(columns=["_rank_sort", "_score_sort"])


def primary_branch_result(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...], branch_code: str) -> tuple[pd.Series | None, pd.DataFrame]:
    row = table.loc[table[BRANCH_ID].astype(str).eq(str(branch_code))]
    changes = build_audit_long_form(tuple(item for item in manifest if str(item.branch_code) == str(branch_code) and item.changed))
    return (None if row.empty else row.iloc[0], changes)


def aggregate_indicator_impact(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...]) -> pd.DataFrame:
    audit = build_audit_long_form(tuple(item for item in manifest if item.changed))
    if audit.empty:
        return pd.DataFrame(columns=["indicator_key", "indicator_name", "affected_branches", "affected_percentage", "rule_direction", "average_raw_percentage_change", "branches_rank_up", "branches_rank_down", "rule_sources"])
    merged = audit.merge(table[[BRANCH_ID, "rank_change", "score_change"]], left_on="branch_code", right_on=BRANCH_ID, how="left")
    rows = []
    for key, group in merged.groupby("indicator_key", sort=False):
        branches = group["branch_code"].nunique()
        avg_pct = pd.to_numeric(group["percentage_change"], errors="coerce").mean()
        rows.append({
            "indicator_key": key,
            "indicator_name": INDICATOR_REGISTRY[key].display_name,
            "affected_branches": int(branches),
            "affected_percentage": _pct(int(branches), len(table)),
            "general_rule_count": int(group["effective_source"].eq("general").sum()),
            "exception_rule_count": int(group["effective_source"].eq("exception").sum()),
            "primary_rule_count": int(group["effective_source"].eq("primary").sum()),
            "rule_direction": "افزایش" if group["absolute_change"].sum() > 0 else "کاهش" if group["absolute_change"].sum() < 0 else "خنثی",
            "average_raw_percentage_change": float(avg_pct) if pd.notna(avg_pct) else None,
            "associated_average_score_change": float(group["score_change"].mean()) if group["score_change"].notna().any() else None,
            "branches_rank_up": int(group.loc[group["rank_change"].gt(0), "branch_code"].nunique()),
            "branches_rank_down": int(group.loc[group["rank_change"].lt(0), "branch_code"].nunique()),
            "rule_sources": "، ".join(sorted(set(group["effective_source_text"]))),
        })
    return pd.DataFrame(rows).sort_values("affected_branches", ascending=False).reset_index(drop=True)


def aggregate_rule_source_coverage(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...]) -> pd.DataFrame:
    rows = []
    changed = [item for item in manifest if item.changed]
    for source, label in SOURCE_LABELS.items():
        if source is EffectiveChangeSource.UNCHANGED:
            continue
        items = [item for item in changed if item.effective_source is source]
        rows.append({"source_key": SOURCE_KEYS[source], "source_label": label, "affected_branch_count": len({str(item.branch_code) for item in items}), "branch_indicator_change_count": len(items)})
    changed_branches = {str(item.branch_code) for item in changed}
    rows.append({"source_key": "unchanged", "source_label": "بدون تغییر", "affected_branch_count": len(table) - len(changed_branches), "branch_indicator_change_count": 0})
    return pd.DataFrame(rows)


def filter_network_results(table: pd.DataFrame, *, status: str = "all", source: str = "all", indicator: str = "all", query: str = "") -> pd.DataFrame:
    mask = pd.Series(True, index=table.index)
    if status in {"rank_up", "rank_down"}:
        mask &= table["rank_status"].eq(status)
    elif status in {"score_up", "score_down"}:
        mask &= table["score_status"].eq(status)
    elif status in {"grade_up", "grade_down"}:
        mask &= table["grade_status"].eq(status)
    elif status == "unchanged":
        mask &= table["rank_change"].eq(0) & table["score_change"].eq(0) & table["grade_change"].eq(0) & table["changed_indicator_count"].eq(0)
    source_map = {"general": EffectiveChangeSource.GENERAL_RULE, "exception": EffectiveChangeSource.BRANCH_EXCEPTION, "primary": EffectiveChangeSource.PRIMARY_EXPLICIT}
    if source in source_map:
        mask &= table["effective_sources"].map(lambda values: source_map[source] in values)
    elif source == "unchanged":
        mask &= table["effective_sources"].map(lambda values: not values)
    if indicator != "all":
        mask &= table["affected_indicators"].map(lambda values: indicator in values)
    normalized = str(query).strip().casefold()
    if normalized:
        searchable = table[BRANCH_ID].astype(str) + " " + table[BRANCH_NAME].astype(str)
        mask &= searchable.str.casefold().str.contains(normalized, regex=False)
    return table.loc[mask].copy()


def compact_branch_table(filtered: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "نام شعبه": filtered[BRANCH_NAME],
        "کد شعبه": filtered[BRANCH_ID].map(persian_digits),
        "امتیاز فعلی": filtered["baseline_score"].map(format_score_display),
        "امتیاز سناریویی": filtered["scenario_score"].map(format_score_display),
        "تغییر امتیاز": filtered["score_change"].map(format_score_change_label),
        "رتبه فعلی": filtered["baseline_rank"],
        "رتبه سناریویی": filtered["scenario_rank"],
        "جابه‌جایی رتبه": filtered["rank_change"].map(format_rank_movement_label),
        "درجه فعلی": filtered["baseline_grade"].map(format_grade),
        "درجه سناریویی": filtered["scenario_grade"].map(format_grade),
        "منبع قاعده مؤثر": filtered["effective_source_text"],
        "وضعیت": filtered.apply(lambda row: "بهبود درجه" if row["grade_change"] > 0 else "افت درجه" if row["grade_change"] < 0 else "صعود رتبه" if row["rank_change"] > 0 else "نزول رتبه" if row["rank_change"] < 0 else "بدون تغییر", axis=1),
    })


def result_header_html(context: dict[str, object]) -> str:
    scenario = context.get("نام سناریو", "—")
    primary = context.get("شعبه اصلی", "—")
    population = context.get("جامعه (کل شعب)", "—")
    status = context.get("وضعیت اجرا", "اجرا شده")
    executed = context.get("زمان اجرا", "")
    strip_keys = ("قواعد عمومی", "استثناهای شعب", "مقادیر اختصاصی شعبه اصلی", "تعداد تغییرات شعبه–شاخص")
    strip = "".join(
        _metric_item(label, context.get(label, "—"))
        for label in strip_keys
        if context.get(label) not in (None, "")
    )
    return (
        '<section class="multi-results-hero" data-multi-branch-results="true">'
        '<header><div><h1>نتایج سناریوی چندشعبه‌ای</h1>'
        f'<p><span>نام سناریو</span><strong>{html.escape(str(scenario))}</strong></p></div>'
        '<div class="multi-results-status">'
        f'<span class="multi-status-badge">{html.escape(str(status))}</span>'
        f'<time dir="ltr">{html.escape(str(executed or "—"))}</time></div></header>'
        '<div class="multi-results-core">'
        f'{_metric_item("شعبه اصلی", primary, "identity")}'
        f'{_metric_item("جامعه (کل شعب)", population)}'
        '</div>'
        f'<div class="multi-results-metadata">{strip}</div></section>'
    )


def _render_kpi(label: str, count: object, total: int | None = None, tone: str = "neutral") -> str:
    sub = "" if total is None else f"<small>{format_persian_percentage(_pct(int(count), total), 1)} از جامعه (کل شعب)</small>"
    icons = {
        "شعب دارای تغییر مقدار": "◦",
        "شعب دارای تغییر امتیاز": "◆",
        "شعب دارای جابه‌جایی رتبه": "↕",
        "تغییر درجه": "◇",
    }
    return (
        f'<article class="multi-kpi {tone}">'
        f'<i aria-hidden="true">{html.escape(icons.get(label, "•"))}</i>'
        f'<span>{html.escape(label)}</span>'
        f'<strong dir="ltr">{format_persian_number(count, 0)}</strong>'
        f'{sub}<em>نتیجه محاسبه‌شده</em></article>'
    )


def _distribution_row(label: str, count: int, total: int, tone: str) -> str:
    percent = _pct(count, total)
    width = 0 if count == 0 else max(4.0, min(100.0, percent))
    return (
        f'<div class="multi-distribution-row {tone}">'
        f'<span>{html.escape(label)}</span>'
        '<div class="multi-distribution-bar" aria-hidden="true">'
        f'<i style="width:{width:.2f}%"></i></div>'
        f'<b dir="ltr">{format_persian_number(count, 0)}</b>'
        f'<small dir="ltr">{format_persian_percentage(percent, 1)}</small></div>'
    )


def _distribution_panel_html(title: str, rows: list[tuple[str, int, str]], total: int) -> str:
    return (
        '<section class="multi-distribution-panel">'
        f'<header><i aria-hidden="true">◇</i><div><h3>{html.escape(title)}</h3>'
        f'<p>{format_persian_number(total, 0)} شعبه</p></div></header>'
        + "".join(_distribution_row(label, count, max(1, total), tone) for label, count, tone in rows)
        + "</section>"
    )


def _distribution_grid_html(summary: MultiBranchResultSummary) -> str:
    rank_rows = [
        ("صعود رتبه", summary.rank_up, "success"),
        ("نزول رتبه", summary.rank_down, "danger"),
        ("بدون جابه‌جایی", summary.rank_same, "neutral"),
    ]
    grade_rows = [
        ("بهبود درجه", summary.grade_up, "success"),
        ("افت درجه", summary.grade_down, "danger"),
        ("بدون تغییر درجه", summary.grade_same, "neutral"),
    ]
    return (
        '<section class="multi-distribution-grid" data-multi-branch-results="true">'
        + _distribution_panel_html("توزیع جابه‌جایی رتبه", rank_rows, summary.total_branches)
        + _distribution_panel_html("توزیع تغییر درجه", grade_rows, summary.total_branches)
        + "</section>"
    )


def _render_overview(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...], primary_branch_code: str) -> None:
    summary = summarize_network(table, manifest)
    kpis = [
        _render_kpi("شعب دارای تغییر مقدار", summary.raw_changed_branches, summary.total_branches, "navy"),
        _render_kpi("شعب دارای تغییر امتیاز", summary.score_changed_branches, summary.total_branches, "purple"),
        _render_kpi("شعب دارای جابه‌جایی رتبه", summary.rank_moved_branches, summary.total_branches, "success" if summary.rank_up >= summary.rank_down else "danger"),
        _render_kpi("تغییر درجه", summary.grade_up + summary.grade_down, summary.total_branches, "purple"),
    ]
    st.markdown('<section class="multi-kpi-grid" data-multi-branch-results="true">' + "".join(kpis) + "</section>", unsafe_allow_html=True)
    _render_primary(table, manifest, primary_branch_code)
    st.markdown(_distribution_grid_html(summary), unsafe_allow_html=True)
    st.markdown('<section class="multi-movers-grid" data-multi-branch-results="true">' + _movers_panel_html("بیشترین صعود", top_movers(table, improvement=True, limit=3), True) + _movers_panel_html("بیشترین نزول", top_movers(table, improvement=False, limit=3), False) + "</section>", unsafe_allow_html=True)


def _movers_panel_html(title: str, data: pd.DataFrame, improvement: bool) -> str:
    tone = "success" if improvement else "danger"
    if data.empty:
        empty = "شعبه‌ای با بهبود رتبه ثبت نشده است." if improvement else "شعبه‌ای با افت رتبه ثبت نشده است."
        return f'<section class="multi-mover-panel {tone}"><header><i aria-hidden="true">↕</i><div><h3>{title}</h3><p>بدون شعبه واجد شرایط</p></div></header><div class="multi-empty-state">{empty}</div></section>'
    rows = []
    for pos, (_, row) in enumerate(data.iterrows(), start=1):
        rows.append(
            f'<article class="multi-mover-row {tone}"><b class="position" dir="ltr">{format_persian_number(pos, 0)}</b>'
            f'<div class="mover-name"><strong>{html.escape(str(row[BRANCH_NAME]))}</strong>'
            f'<small>کد <span dir="ltr">{html.escape(persian_digits(row[BRANCH_ID]))}</span></small></div>'
            f'{_compact_metric("رتبه فعلی", format_persian_number(row["baseline_rank"], 0))}'
            f'{_compact_metric("رتبه سناریویی", format_persian_number(row["scenario_rank"], 0))}'
            f'<span class="movement-badge">{format_rank_movement_label(row["rank_change"])}</span>'
            f'<span class="score-change" dir="ltr">{format_score_change_label(row["score_change"])}</span></article>'
        )
    return (
        f'<section class="multi-mover-panel {tone}"><header><i aria-hidden="true">↕</i><div>'
        f'<h3>{title}</h3><p>{format_persian_number(len(data), 0)} شعبه از بیشترین جابه‌جایی‌ها</p></div></header>'
        + "".join(rows)
        + "</section>"
    )


def _render_primary(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...], primary_branch_code: str) -> None:
    row, changes = primary_branch_result(table, manifest, primary_branch_code)
    if row is None:
        st.warning("اطلاعات شعبه اصلی در نتیجه موجود نیست.")
        return
    st.markdown(_primary_outcome_html(row, changes, primary_branch_code), unsafe_allow_html=True)


def _audit_display(audit: pd.DataFrame) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame()
    return pd.DataFrame({
        "شاخص": audit["indicator_display_name"],
        "منبع قاعده مؤثر": audit["effective_source_text"],
        "روش/جهت اعمال": audit["input_mode_text"],
        "مقدار واردشده": audit["entered_value"].map(format_raw_display),
        "مقدار خام مبنا": audit["baseline_raw_value"].map(format_raw_display),
        "مقدار خام سناریو": audit["scenario_raw_value"].map(format_raw_display),
        "تغییر مطلق": audit["absolute_change"].map(format_raw_display),
        "درصد تغییر": audit["percentage_change"].map(format_percentage_display),
    })


def _primary_metric_card(title: str, cells: str, tone: str = "neutral") -> str:
    return f'<article class="multi-primary-metric-card {tone}"><h3>{html.escape(title)}</h3><div>{cells}</div></article>'


def _primary_panel_html(row: pd.Series, primary_branch_code: str) -> str:
    score = (
        _metric_item("امتیاز فعلی", format_score_display(row["baseline_score"]))
        + _metric_item("امتیاز سناریویی", format_score_display(row["scenario_score"]))
        + _metric_item("تغییر امتیاز", format_score_change_label(row["score_change"]))
    )
    rank = (
        _metric_item("رتبه فعلی", format_persian_number(row["baseline_rank"], 0))
        + _metric_item("رتبه سناریویی", format_persian_number(row["scenario_rank"], 0))
        + _metric_item("حرکت", format_rank_movement_label(row["rank_change"]))
    )
    grade = (
        _metric_item("فعلی", format_grade(row["baseline_grade"]))
        + _metric_item("سناریو", format_grade(row["scenario_grade"]))
        + _metric_item("نتیجه", "بهبود درجه" if row["grade_change"] > 0 else "افت درجه" if row["grade_change"] < 0 else "بدون تغییر درجه")
    )
    score_tone = "success" if row["score_change"] > 0 else "danger" if row["score_change"] < 0 else "neutral"
    rank_tone = "success" if row["rank_change"] > 0 else "danger" if row["rank_change"] < 0 else "neutral"
    grade_tone = "success" if row["grade_change"] > 0 else "danger" if row["grade_change"] < 0 else "neutral"
    cards = (
        _primary_metric_card("امتیاز", score, score_tone)
        + _primary_metric_card("رتبه", rank, rank_tone)
        + _primary_metric_card("درجه", grade, grade_tone)
    )
    return (
        f'<header><h2><span aria-hidden="true">◆</span> نتیجه شعبه اصلی</h2>'
        '<div>'
        f'<p>{html.escape(str(row[BRANCH_NAME]))} — کد <span dir="ltr">{html.escape(persian_digits(primary_branch_code))}</span></p>'
        f'<b class="primary-rule-count">{format_persian_number(row["changed_indicator_count"], 0)} قاعده مؤثر</b></div></header>'
        f'<div class="multi-primary-comparison">{cards}</div>'
    )


def _primary_rule_cards_html(changes: pd.DataFrame) -> str:
    cards = []
    for _, row in changes.iterrows():
        cells = "".join([
            _metric_item("ورودی کاربر", format_raw_display(row["entered_value"])),
            _metric_item("مقدار مبنا", format_raw_display(row["baseline_raw_value"])),
            _metric_item("مقدار تغییر", format_raw_display(row["absolute_change"])),
            _metric_item("مقدار نهایی", format_raw_display(row["scenario_raw_value"])),
        ])
        cards.append(
            '<article class="multi-primary-rule-card">'
            f'<header><h3>{html.escape(str(row["indicator_display_name"]))}</h3>'
            '<span>مقدار اختصاصی شعبه اصلی</span></header>'
            f'<p>{html.escape(str(row["input_mode_text"]))}</p><div>{cells}</div></article>'
        )
    return '<section class="multi-primary-rules-grid">' + "".join(cards) + "</section>"


def _primary_outcome_html(row: pd.Series, changes: pd.DataFrame, primary_branch_code: str) -> str:
    rules = (
        '<div class="multi-empty-state compact">برای شعبه اصلی تغییر مقدار مؤثری ثبت نشده است.</div>'
        if changes.empty
        else _primary_rule_cards_html(changes)
    )
    return (
        '<section class="multi-primary-panel" data-multi-branch-results="true">'
        + _primary_panel_html(row, primary_branch_code)
        + rules
        + "</section>"
    )


def _branch_detail_cards_html(audit: pd.DataFrame) -> str:
    cards = []
    for _, row in audit.iterrows():
        cards.append(
            '<article class="multi-branch-detail-card">'
            f'<header><h3>{html.escape(str(row["indicator_display_name"]))}</h3>'
            f'<span>{html.escape(str(row["effective_source_text"]))}</span></header>'
            '<div>'
            f'{_metric_item("روش", row["input_mode_text"])}'
            f'{_metric_item("ورودی", format_raw_display(row["entered_value"]))}'
            f'{_metric_item("مبنا", format_raw_display(row["baseline_raw_value"]))}'
            f'{_metric_item("سناریو", format_raw_display(row["scenario_raw_value"]))}'
            f'{_metric_item("تغییر", format_raw_display(row["absolute_change"]))}'
            f'{_metric_item("درصد تغییر", format_percentage_display(row["percentage_change"]))}'
            '</div></article>'
        )
    return '<section class="multi-branch-detail-grid">' + "".join(cards) + "</section>"


def _audit_overview_html(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...], audit_available: bool) -> str:
    source_count = len({item.effective_source for item in manifest if item.changed})
    cards = [
        ("تعداد شعب بررسی‌شده", format_persian_number(len(table), 0), "navy"),
        ("تعداد تغییرات شعبه–شاخص", format_persian_number(sum(1 for item in manifest if item.changed), 0), "purple"),
        ("تعداد منابع قواعد مؤثر", format_persian_number(source_count, 0), "navy"),
        ("وضعیت جزئیات", "کامل" if audit_available else "محدود", "amber" if not audit_available else "success"),
    ]
    return (
        '<section class="multi-audit-overview" data-multi-branch-results="true">'
        + "".join(
            f'<article class="{tone}"><span>{html.escape(label)}</span><strong dir="ltr">{html.escape(value)}</strong></article>'
            for label, value, tone in cards
        )
        + "</section>"
    )


def _branch_audit_summary_html(row: pd.Series) -> str:
    cards = (
        _metric_item("امتیاز فعلی", format_score_display(row["baseline_score"]))
        + _metric_item("امتیاز سناریویی", format_score_display(row["scenario_score"]))
        + _metric_item("تغییر امتیاز", format_score_change_label(row["score_change"]))
        + _metric_item("رتبه فعلی", format_persian_number(row["baseline_rank"], 0))
        + _metric_item("رتبه سناریویی", format_persian_number(row["scenario_rank"], 0))
        + _metric_item("جابه‌جایی", format_rank_movement_label(row["rank_change"]))
        + _metric_item("درجه فعلی", format_grade(row["baseline_grade"]))
        + _metric_item("درجه سناریویی", format_grade(row["scenario_grade"]))
    )
    return (
        '<section class="multi-selected-branch-audit" data-multi-branch-results="true">'
        f'<header><h3>{html.escape(str(row[BRANCH_NAME]))}</h3><span>کد <b dir="ltr">{html.escape(persian_digits(row[BRANCH_ID]))}</b></span></header>'
        f'<div>{cards}</div></section>'
    )


def _render_analysis(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...]) -> None:
    impact = aggregate_indicator_impact(table, manifest)
    st.markdown('<section class="multi-analysis-section"><h2>اثر شاخص‌ها</h2>', unsafe_allow_html=True)
    if impact.empty:
        st.info("شاخص تغییریافته‌ای برای تحلیل وجود ندارد.")
    else:
        render_chart(build_indicator_impact_chart(impact), key="multi_indicator_impact")
    st.markdown("</section>", unsafe_allow_html=True)
    st.markdown('<section class="multi-analysis-section"><h2>جابه‌جایی رتبه شعب</h2>', unsafe_allow_html=True)
    mode = st.radio("نمای جابه‌جایی", ("all_moved", "largest_improvements", "largest_declines"), format_func={"largest_improvements": "بیشترین بهبودها", "largest_declines": "بیشترین افت‌ها", "all_moved": "همه جابه‌جا شده"}.get, horizontal=True, key="multi_rank_movement_mode")
    figure = build_multi_branch_rank_movement_chart(table, mode=mode)
    if figure is None:
        st.info("شعبه‌ای با جابه‌جایی رتبه وجود ندارد.")
    else:
        render_chart(figure, key=f"multi_rank_movement_{mode}")
    st.markdown("</section>", unsafe_allow_html=True)
    st.markdown('<section class="multi-analysis-section"><h2>مقایسه فشرده شعب</h2>', unsafe_allow_html=True)
    st.dataframe(compact_branch_table(table), hide_index=True, width="stretch", height=360)
    st.markdown("</section>", unsafe_allow_html=True)
    with st.expander("پوشش منبع قاعده"):
        st.dataframe(impact.rename(columns={"indicator_name": "شاخص", "affected_branches": "شعب دارای تغییر مقدار", "affected_percentage": "درصد جامعه", "general_rule_count": "تعداد قاعده عمومی", "exception_rule_count": "تعداد استثنا", "primary_rule_count": "تعداد قاعده شعبه اصلی", "rule_direction": "جهت قاعده", "average_raw_percentage_change": "میانگین درصد تغییر مقدار خام", "associated_average_score_change": "میانگین تغییر امتیاز همراه", "branches_rank_up": "شعب صعودکرده", "branches_rank_down": "شعب نزول‌کرده", "rule_sources": "منابع قواعد"}).drop(columns=["indicator_key"], errors="ignore"), hide_index=True, width="stretch")
        st.dataframe(aggregate_rule_source_coverage(table, manifest).rename(columns={"source_label": "منبع", "affected_branch_count": "تعداد شعب متأثر", "branch_indicator_change_count": "تعداد تغییرات شعبه–شاخص"}).drop(columns=["source_key"], errors="ignore"), hide_index=True, width="stretch")


def _render_details(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...], *, audit_available: bool = True) -> None:
    st.markdown(_audit_overview_html(table, manifest, audit_available), unsafe_allow_html=True)
    if not audit_available:
        st.markdown(
            '<section class="multi-audit-warning" data-multi-branch-results="true">جزئیات کامل قواعد برای این Snapshot ذخیره نشده است؛ فقط خلاصه رسمی شعب نمایش داده می‌شود.</section>',
            unsafe_allow_html=True,
        )
    changed_indicators = sorted({item.indicator_key for item in manifest if item.changed})
    st.markdown('<section class="multi-audit-filters" data-multi-branch-results="true"><h3>فیلترهای ممیزی</h3></section>', unsafe_allow_html=True)
    filters = st.columns([1, 1, 1, 1.5])
    status = filters[0].selectbox("وضعیت", list(STATUS_OPTIONS), format_func=STATUS_OPTIONS.get, key="multi_result_status")
    source = filters[1].selectbox("منبع قاعده", list(SOURCE_OPTIONS), format_func=SOURCE_OPTIONS.get, key="multi_result_source")
    indicator = filters[2].selectbox("شاخص", ["all", *changed_indicators], format_func=lambda key: "همه شاخص‌ها" if key == "all" else INDICATOR_REGISTRY[key].display_name, key="multi_result_indicator")
    query = filters[3].text_input("جست‌وجوی نام یا کد شعبه", key="multi_result_query")
    filtered = filter_network_results(table, status=status, source=source, indicator=indicator, query=query)
    st.caption(f"{format_persian_number(len(filtered), 0)} شعبه از {format_persian_number(len(table), 0)} شعبه")
    st.dataframe(compact_branch_table(filtered), hide_index=True, width="stretch", height=420)
    options = filtered[BRANCH_ID].astype(str).tolist()
    if options:
        selected = st.selectbox("انتخاب شعبه برای جزئیات", options, format_func=lambda code: f"{table.loc[table[BRANCH_ID].eq(code), BRANCH_NAME].iloc[0]} ({persian_digits(code)})")
        st.markdown(_branch_audit_summary_html(table.loc[table[BRANCH_ID].eq(selected)].iloc[0]), unsafe_allow_html=True)
        audit = build_audit_long_form(tuple(item for item in manifest if str(item.branch_code) == str(selected) and item.changed))
        if audit.empty:
            st.markdown('<div class="multi-empty-state">برای شعبه منتخب تغییر مقدار مؤثری ثبت نشده است.</div>', unsafe_allow_html=True)
        else:
            st.markdown(_branch_detail_cards_html(audit), unsafe_allow_html=True)
    with st.expander("مشاهده جزئیات فنی و ممیزی"):
        st.caption("اسکرول افقی فقط در این جدول ممیزی تفصیلی انتظار می‌رود.")
        audit = build_audit_long_form(manifest)
        if audit.empty:
            st.info("جزئیات ممیزی در این نتیجه ذخیره نشده یا تغییری وجود ندارد.")
        else:
            names = table.set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict()
            audit = audit.assign(branch_name=audit["branch_code"].map(names))
            display = audit.rename(columns={"branch_code": "کد شعبه", "branch_name": "نام شعبه", "indicator_key": "کلید شاخص", "indicator_display_name": "شاخص", "effective_source_text": "منبع قاعده مؤثر", "input_mode_text": "روش ورود", "entered_value": "مقدار واردشده", "effective_percentage": "درصد مؤثر", "baseline_raw_value": "مقدار خام مبنا", "scenario_raw_value": "مقدار خام سناریو", "changed_flag": "پرچم تغییر"})
            st.download_button("دریافت CSV ممیزی", display.to_csv(index=False).encode("utf-8-sig"), file_name="multi_branch_audit.csv", mime="text/csv")
            st.dataframe(display, hide_index=True, width="stretch")


def render_multi_branch_results(comparison, manifest, primary_branch_code: str, *, context: dict[str, object] | None = None, audit_available: bool = True) -> None:
    if st is None:
        raise RuntimeError("Streamlit is required to render multi-branch results")
    manifest = tuple(manifest or ())
    table = build_network_result_table(comparison.branch_comparison, manifest)
    st.markdown(result_header_html(context or {}), unsafe_allow_html=True)
    tabs = st.tabs(["نمای مدیریتی", "تحلیل شعب و شاخص‌ها", "جزئیات و ممیزی"])
    with tabs[0]:
        _render_overview(table, manifest, primary_branch_code)
    with tabs[1]:
        _render_analysis(table, manifest if audit_available else ())
    with tabs[2]:
        _render_details(table, manifest if audit_available else (), audit_available=audit_available)
