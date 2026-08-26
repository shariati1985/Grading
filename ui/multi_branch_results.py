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
    build_impact_distribution_chart,
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
        return f"{format_persian_number(movement, 0)} رتبه بهبود"
    if movement < 0:
        return f"{format_persian_number(abs(movement), 0)} رتبه افت"
    return "بدون تغییر رتبه"


def format_score_change_label(value: object) -> str:
    return format_signed_persian_number(value, 1)


def format_percentage_display(value: object, decimals: int = 2) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "—"
    rendered = format_persian_percentage(float(number), decimals)
    return rendered.replace("٫۰۰٪", "٪").replace("٫۰٪", "٪")


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
        f"{shape}؛ {format_persian_percentage(raw_pct, 1)} از جامعه رسمی تغییر مقدار داشته‌اند، "
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
        f"پوشش تغییر مقدار: {format_persian_percentage(raw_pct, 1)}",
        f"تغییر امتیاز: {format_persian_percentage(_pct(summary.score_changed_branches, summary.total_branches), 1)}",
        f"جابه‌جایی رتبه: {format_persian_percentage(rank_pct, 1)}",
        f"خالص جهت حرکت رتبه: {format_signed_persian_number(summary.net_rank_movement, 0)}",
        f"تعداد تغییرات شعبه–شاخص: {format_persian_number(summary.branch_indicator_changes, 0)}",
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
    cards = "".join(
        f'<article><span>{html.escape(str(label))}</span><strong>{html.escape(str(value))}</strong></article>'
        for label, value in context.items()
        if value not in (None, "")
    )
    return (
        '<div data-multi-branch-results="true"><header class="multi-results-header">'
        "<div><h1>نتایج سناریوی چندشعبه‌ای</h1><p>نمای مدیریتی، تحلیل شبکه و ممیزی تغییرات سناریو</p></div></header>"
        f'<section class="multi-results-metadata">{cards}</section>'
    )


def _render_kpi(label: str, count: object, total: int | None = None, tone: str = "neutral") -> str:
    sub = "" if total is None else f"<small>{format_persian_percentage(_pct(int(count), total), 1)} از جامعه رسمی</small>"
    return f'<article class="multi-kpi {tone}"><span>{label}</span><strong>{format_persian_number(count, 0)}</strong>{sub}</article>'


def _render_overview(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...]) -> None:
    summary = summarize_network(table, manifest)
    conclusion = managerial_conclusion_model(summary)
    evidence = "".join(f"<li>{html.escape(item)}</li>" for item in conclusion["evidence"])
    st.markdown(
        f'<section class="managerial-conclusion {conclusion["tone"]}"><h2>{html.escape(str(conclusion["headline"]))}</h2>'
        f'<p>{html.escape(str(conclusion["body"]))}</p><ul>{evidence}</ul></section>',
        unsafe_allow_html=True,
    )
    kpis = [
        _render_kpi("جامعه رسمی", summary.total_branches),
        _render_kpi("شعب دارای تغییر مقدار", summary.raw_changed_branches, summary.total_branches),
        _render_kpi("شعب دارای تغییر امتیاز", summary.score_changed_branches, summary.total_branches),
        _render_kpi("شعب دارای جابه‌جایی رتبه", summary.rank_moved_branches, summary.total_branches),
        _render_kpi("خالص جهت حرکت", summary.net_rank_movement, None, "success" if summary.net_rank_movement > 0 else "danger" if summary.net_rank_movement < 0 else "neutral"),
        f'<article class="multi-kpi"><span>تغییر درجه</span><strong>{format_persian_number(summary.grade_up, 0)} / {format_persian_number(summary.grade_down, 0)}</strong><small>بهبود درجه / افت درجه</small></article>',
    ]
    st.markdown('<section class="multi-kpi-grid">' + "".join(kpis) + "</section>", unsafe_allow_html=True)
    render_chart(build_impact_distribution_chart(summary), key="multi_impact_distribution")
    st.markdown('<section class="multi-movers-grid">' + _movers_panel_html("بیشترین بهبودها", top_movers(table, improvement=True), True) + _movers_panel_html("بیشترین افت‌ها", top_movers(table, improvement=False), False) + "</section>", unsafe_allow_html=True)


def _movers_panel_html(title: str, data: pd.DataFrame, improvement: bool) -> str:
    if data.empty:
        empty = "شعبه‌ای با بهبود رتبه ثبت نشده است." if improvement else "شعبه‌ای با افت رتبه ثبت نشده است."
        return f'<section class="multi-mover-panel"><h3>{title}</h3><div class="multi-empty-state">{empty}</div></section>'
    rows = []
    for _, row in data.iterrows():
        tone = "success" if improvement else "danger"
        grade = ""
        if row["grade_change"] != 0:
            grade = f"<span>{'بهبود درجه' if row['grade_change'] > 0 else 'افت درجه'}: {format_grade(row['baseline_grade'])} / {format_grade(row['scenario_grade'])}</span>"
        rows.append(
            f'<article class="multi-mover-row {tone}"><header><strong>{html.escape(str(row[BRANCH_NAME]))}</strong>'
            f'<small>کد {persian_digits(row[BRANCH_ID])}</small></header><div>'
            f'<span>رتبه فعلی: {format_persian_number(row["baseline_rank"], 0)}</span>'
            f'<span>رتبه سناریویی: {format_persian_number(row["scenario_rank"], 0)}</span>'
            f'<b>{format_rank_movement_label(row["rank_change"])}</b>'
            f'<span>تغییر امتیاز: {format_score_change_label(row["score_change"])}</span>{grade}</div></article>'
        )
    return f'<section class="multi-mover-panel"><h3>{title}</h3>{"".join(rows)}</section>'


def _render_primary(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...], primary_branch_code: str) -> None:
    row, changes = primary_branch_result(table, manifest, primary_branch_code)
    if row is None:
        st.warning("اطلاعات شعبه اصلی در نتیجه موجود نیست.")
        return
    st.markdown(_primary_panel_html(row, primary_branch_code), unsafe_allow_html=True)
    if changes.empty:
        st.info("برای شعبه اصلی تغییر مقدار مؤثری ثبت نشده است.")
    else:
        st.dataframe(_audit_display(changes), hide_index=True, width="stretch", height=220)


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


def _primary_panel_html(row: pd.Series, primary_branch_code: str) -> str:
    items = [
        ("امتیاز فعلی", format_score_display(row["baseline_score"])),
        ("امتیاز سناریویی", format_score_display(row["scenario_score"])),
        ("تغییر امتیاز", format_score_change_label(row["score_change"])),
        ("رتبه فعلی", format_persian_number(row["baseline_rank"], 0)),
        ("رتبه سناریویی", format_persian_number(row["scenario_rank"], 0)),
        ("جابه‌جایی رتبه", format_rank_movement_label(row["rank_change"])),
        ("درجه فعلی", format_grade(row["baseline_grade"])),
        ("درجه سناریویی", format_grade(row["scenario_grade"])),
        ("قواعد مؤثر", format_persian_number(row["changed_indicator_count"], 0)),
    ]
    cards = "".join(f"<span><small>{label}</small><b>{value}</b></span>" for label, value in items)
    return (
        f'<section class="multi-primary-panel"><header><h2>نتیجه شعبه اصلی</h2>'
        f'<p>{html.escape(str(row[BRANCH_NAME]))} · کد {html.escape(persian_digits(primary_branch_code))}</p></header>'
        f"<div>{cards}</div></section>"
    )


def _render_analysis(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...]) -> None:
    impact = aggregate_indicator_impact(table, manifest)
    st.markdown("### اثر قواعد به تفکیک شاخص")
    if impact.empty:
        st.info("شاخص تغییریافته‌ای برای تحلیل وجود ندارد.")
    else:
        render_chart(build_indicator_impact_chart(impact), key="multi_indicator_impact")
        st.dataframe(impact.rename(columns={"indicator_name": "شاخص", "affected_branches": "شعب دارای تغییر مقدار", "affected_percentage": "درصد جامعه", "general_rule_count": "تعداد قاعده عمومی", "exception_rule_count": "تعداد استثنا", "primary_rule_count": "تعداد قاعده شعبه اصلی", "rule_direction": "جهت قاعده", "average_raw_percentage_change": "میانگین درصد تغییر مقدار خام", "associated_average_score_change": "میانگین تغییر امتیاز همراه", "branches_rank_up": "شعب صعودکرده", "branches_rank_down": "شعب نزول‌کرده", "rule_sources": "منابع قواعد"}).drop(columns=["indicator_key"], errors="ignore"), hide_index=True, width="stretch")
    st.markdown("### جابه‌جایی رتبه شعب")
    mode = st.radio("نمای جابه‌جایی", ("largest_improvements", "largest_declines", "all_moved"), format_func={"largest_improvements": "بیشترین بهبودها", "largest_declines": "بیشترین افت‌ها", "all_moved": "همه شعب جابه‌جاشده"}.get, horizontal=True)
    figure = build_multi_branch_rank_movement_chart(table, mode=mode)
    if figure is None:
        st.info("شعبه‌ای با جابه‌جایی رتبه وجود ندارد.")
    else:
        render_chart(figure, key=f"multi_rank_movement_{mode}")
    st.markdown("### پوشش منبع قاعده")
    st.dataframe(aggregate_rule_source_coverage(table, manifest).rename(columns={"source_label": "منبع", "affected_branch_count": "تعداد شعب متأثر", "branch_indicator_change_count": "تعداد تغییرات شعبه–شاخص"}).drop(columns=["source_key"], errors="ignore"), hide_index=True, width="stretch")
    st.markdown("### مقایسه فشرده شعب")
    st.dataframe(compact_branch_table(table), hide_index=True, width="stretch", height=360)


def _render_details(table: pd.DataFrame, manifest: tuple[EffectiveChange, ...]) -> None:
    changed_indicators = sorted({item.indicator_key for item in manifest if item.changed})
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
        st.markdown("### جزئیات تغییرات شعبه منتخب")
        audit = build_audit_long_form(tuple(item for item in manifest if str(item.branch_code) == str(selected) and item.changed))
        if audit.empty:
            st.markdown('<div class="multi-empty-state">برای شعبه منتخب تغییر مقدار مؤثری ثبت نشده است.</div>', unsafe_allow_html=True)
        else:
            st.dataframe(_audit_display(audit), hide_index=True, width="stretch", height=260)
    with st.expander("مشاهده جزئیات فنی و ممیزی"):
        audit = build_audit_long_form(manifest)
        if audit.empty:
            st.info("جزئیات ممیزی در این نتیجه ذخیره نشده یا تغییری وجود ندارد.")
        else:
            names = table.set_index(BRANCH_ID)[BRANCH_NAME].astype(str).to_dict()
            audit = audit.assign(branch_name=audit["branch_code"].map(names))
            st.dataframe(audit.rename(columns={"branch_code": "کد شعبه", "branch_name": "نام شعبه", "indicator_key": "کلید شاخص", "indicator_display_name": "شاخص", "effective_source_text": "منبع قاعده مؤثر", "input_mode_text": "روش ورود", "entered_value": "مقدار واردشده", "effective_percentage": "درصد مؤثر", "baseline_raw_value": "مقدار خام مبنا", "scenario_raw_value": "مقدار خام سناریو", "changed_flag": "پرچم تغییر"}), hide_index=True, width="stretch")


def render_multi_branch_results(comparison, manifest, primary_branch_code: str, *, context: dict[str, object] | None = None, audit_available: bool = True) -> None:
    if st is None:
        raise RuntimeError("Streamlit is required to render multi-branch results")
    manifest = tuple(manifest or ())
    table = build_network_result_table(comparison.branch_comparison, manifest)
    st.markdown(result_header_html(context or {}), unsafe_allow_html=True)
    tabs = st.tabs(["نمای مدیریتی", "تحلیل شعب و شاخص‌ها", "جزئیات و ممیزی"])
    with tabs[0]:
        _render_overview(table, manifest)
        _render_primary(table, manifest, primary_branch_code)
    with tabs[1]:
        _render_analysis(table, manifest if audit_available else ())
    with tabs[2]:
        if not audit_available:
            st.warning("جزئیات کامل قواعد و ممیزی برای این نتیجه ذخیره نشده است؛ جدول مدیریتی از Snapshot رسمی نمایش داده می‌شود.")
        _render_details(table, manifest if audit_available else ())
    st.markdown("</div>", unsafe_allow_html=True)
