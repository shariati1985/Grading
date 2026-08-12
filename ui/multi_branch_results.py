"""Pure presentation model and Streamlit renderer for multi-branch results."""

from __future__ import annotations

from dataclasses import dataclass
import html

import pandas as pd
try:  # Keep the presentation model importable in engine-only test environments.
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - renderer is not called without Streamlit.
    st = None

from domain.multi_branch_contracts import EffectiveChange, EffectiveChangeSource
from engine.indicator_registry import INDICATOR_REGISTRY
from engine.ranking_engine import BRANCH_ID, BRANCH_NAME
from ui.formatters import (
    format_grade,
    format_persian_number,
    format_signed_persian_number,
    format_signed_persian_percentage,
    persian_digits,
)


GRADE_LEVEL = {
    "Grade 3": 0,
    "Grade 2": 1,
    "Grade 1": 2,
    "Excellent": 3,
    "Excellent Plus": 4,
}

STATUS_OPTIONS = {
    "all": "همه شعب",
    "rank_up": "صعود رتبه",
    "rank_down": "نزول رتبه",
    "rank_same": "بدون تغییر رتبه",
    "grade_up": "بهبود درجه",
    "grade_down": "افت درجه",
    "grade_same": "بدون تغییر درجه",
}

SOURCE_OPTIONS = {
    "all": "همه منابع قواعد",
    "general": "مشمول قاعده عمومی",
    "exception": "شعب استثنا",
    "primary": "شعبه اصلی با مقدار اختصاصی",
    "unchanged": "بدون قاعده مؤثر",
}

SOURCE_LABELS = {
    EffectiveChangeSource.PRIMARY_EXPLICIT: "مقدار اختصاصی شعبه اصلی",
    EffectiveChangeSource.BRANCH_EXCEPTION: "قاعده اختصاصی شعبه",
    EffectiveChangeSource.GENERAL_RULE: "قاعده عمومی",
    EffectiveChangeSource.UNCHANGED: "بدون تغییر",
}

INPUT_MODE_LABELS = {
    "percent": "تغییر درصدی",
    "absolute": "تغییر مطلق",
    "final": "مقدار نهایی",
}


@dataclass(frozen=True)
class MultiBranchResultSummary:
    rank_up: int
    rank_down: int
    rank_same: int
    grade_up: int
    grade_down: int
    grade_same: int
    largest_rank_up: int
    largest_rank_down: int
    average_score_change: float


def _grade_change(row: pd.Series) -> int:
    return GRADE_LEVEL.get(str(row["scenario_grade"]), -1) - GRADE_LEVEL.get(
        str(row["baseline_grade"]), -1
    )


def build_network_result_table(
    comparison: pd.DataFrame,
    manifest: tuple[EffectiveChange, ...],
) -> pd.DataFrame:
    """Enrich one-row-per-branch comparison with rule and raw-value audit data."""
    by_branch: dict[str, list[EffectiveChange]] = {}
    for item in manifest:
        by_branch.setdefault(str(item.branch_code), []).append(item)

    result = comparison.copy(deep=True)
    result[BRANCH_ID] = result[BRANCH_ID].astype(str)
    result["grade_change"] = result.apply(_grade_change, axis=1)
    result["rank_status"] = result["rank_change"].map(
        lambda value: "rank_up" if value > 0 else "rank_down" if value < 0 else "rank_same"
    )
    result["grade_status"] = result["grade_change"].map(
        lambda value: "grade_up" if value > 0 else "grade_down" if value < 0 else "grade_same"
    )

    source_sets: list[frozenset[EffectiveChangeSource]] = []
    source_texts: list[str] = []
    applied_texts: list[str] = []
    baseline_raw_texts: list[str] = []
    scenario_raw_texts: list[str] = []
    for branch_code in result[BRANCH_ID]:
        effective = [item for item in by_branch.get(branch_code, []) if item.changed]
        sources = frozenset(item.effective_source for item in effective)
        source_sets.append(sources)
        source_texts.append("، ".join(dict.fromkeys(SOURCE_LABELS[item.effective_source] for item in effective)) or "بدون تغییر")
        applied: list[str] = []
        baseline_values: list[str] = []
        scenario_values: list[str] = []
        for item in effective:
            label = INDICATOR_REGISTRY[item.indicator_key].display_name
            if item.effective_source is EffectiveChangeSource.PRIMARY_EXPLICIT:
                mode = INPUT_MODE_LABELS.get(str(item.explicit_input_mode), str(item.explicit_input_mode))
                operation = f"{mode}: {format_persian_number(item.explicit_input_value, 0)}"
            else:
                operation = format_signed_persian_percentage(item.effective_percentage, 1)
            applied.append(f"{label}: {operation}")
            baseline_values.append(f"{label}: {format_persian_number(item.baseline_value, 0)}")
            scenario_values.append(f"{label}: {format_persian_number(item.scenario_value, 0)}")
        applied_texts.append(" | ".join(applied) or "—")
        baseline_raw_texts.append(" | ".join(baseline_values) or "—")
        scenario_raw_texts.append(" | ".join(scenario_values) or "—")
    result["effective_sources"] = source_sets
    result["effective_source_text"] = source_texts
    result["applied_change_text"] = applied_texts
    result["baseline_raw_text"] = baseline_raw_texts
    result["scenario_raw_text"] = scenario_raw_texts
    return result


def summarize_network(table: pd.DataFrame) -> MultiBranchResultSummary:
    return MultiBranchResultSummary(
        rank_up=int(table["rank_change"].gt(0).sum()),
        rank_down=int(table["rank_change"].lt(0).sum()),
        rank_same=int(table["rank_change"].eq(0).sum()),
        grade_up=int(table["grade_change"].gt(0).sum()),
        grade_down=int(table["grade_change"].lt(0).sum()),
        grade_same=int(table["grade_change"].eq(0).sum()),
        largest_rank_up=max(0, int(table["rank_change"].max())),
        largest_rank_down=min(0, int(table["rank_change"].min())),
        average_score_change=float(table["score_change"].mean()),
    )


def filter_network_results(
    table: pd.DataFrame,
    *,
    status: str = "all",
    source: str = "all",
    query: str = "",
) -> pd.DataFrame:
    """Apply status, source, and search predicates conjunctively."""
    mask = pd.Series(True, index=table.index)
    if status.startswith("rank_") and status != "all":
        mask &= table["rank_status"].eq(status)
    elif status.startswith("grade_"):
        mask &= table["grade_status"].eq(status)
    source_map = {
        "general": EffectiveChangeSource.GENERAL_RULE,
        "exception": EffectiveChangeSource.BRANCH_EXCEPTION,
        "primary": EffectiveChangeSource.PRIMARY_EXPLICIT,
    }
    if source in source_map:
        mask &= table["effective_sources"].map(lambda values: source_map[source] in values)
    elif source == "unchanged":
        mask &= table["effective_sources"].map(lambda values: not values)
    normalized_query = str(query).strip().casefold()
    if normalized_query:
        searchable = table[BRANCH_ID].astype(str) + " " + table[BRANCH_NAME].astype(str)
        mask &= searchable.str.casefold().str.contains(normalized_query, regex=False)
    return table.loc[mask].copy()


def _render_summary(summary: MultiBranchResultSummary) -> None:
    st.markdown('<section class="multi-network-summary"><h2>اثر سناریو بر شبکه شعب</h2></section>', unsafe_allow_html=True)
    first = st.columns(4)
    first[0].metric("شعب صعودکرده", format_persian_number(summary.rank_up, 0))
    first[1].metric("شعب نزول‌کرده", format_persian_number(summary.rank_down, 0))
    first[2].metric("بدون تغییر رتبه", format_persian_number(summary.rank_same, 0))
    first[3].metric("بهبود / افت درجه", f"{format_persian_number(summary.grade_up, 0)} / {format_persian_number(summary.grade_down, 0)}")
    second = st.columns(4)
    second[0].metric("بیشترین صعود", format_persian_number(summary.largest_rank_up, 0))
    second[1].metric("بیشترین نزول", format_persian_number(abs(summary.largest_rank_down), 0))
    second[2].metric("میانگین تغییر امتیاز", format_signed_persian_number(summary.average_score_change, 1))
    second[3].metric("بدون تغییر درجه", format_persian_number(summary.grade_same, 0))


def _render_primary_branch(table: pd.DataFrame, branch_code: str) -> None:
    row = table.loc[table[BRANCH_ID].eq(str(branch_code))].iloc[0]
    st.markdown(
        '<section class="multi-primary-result"><header><div><h2>نتیجه شعبه اصلی</h2>'
        f'<p>{html.escape(str(row[BRANCH_NAME]))} · کد {html.escape(persian_digits(branch_code))}</p>'
        '</div></header></section>',
        unsafe_allow_html=True,
    )
    cards = st.columns(4)
    cards[0].metric("امتیاز", format_persian_number(row["scenario_score"], 1), format_signed_persian_number(row["score_change"], 1))
    cards[1].metric("رتبه", format_persian_number(row["scenario_rank"], 0), format_signed_persian_number(row["rank_change"], 0))
    cards[2].metric("درجه فعلی", format_grade(row["baseline_grade"]))
    cards[3].metric("درجه سناریویی", format_grade(row["scenario_grade"]))


def _display_frame(filtered: pd.DataFrame) -> pd.DataFrame:
    status = filtered.apply(
        lambda row: "بهبود درجه" if row["grade_change"] > 0 else "افت درجه" if row["grade_change"] < 0
        else "صعود رتبه" if row["rank_change"] > 0 else "نزول رتبه" if row["rank_change"] < 0 else "بدون تغییر",
        axis=1,
    )
    return pd.DataFrame({
        "کد شعبه": filtered[BRANCH_ID].map(persian_digits),
        "نام شعبه": filtered[BRANCH_NAME],
        "منبع قاعده مؤثر": filtered["effective_source_text"],
        "درصد یا مقدار اعمال‌شده": filtered["applied_change_text"],
        "مقدار خام فعلی": filtered["baseline_raw_text"],
        "مقدار خام سناریویی": filtered["scenario_raw_text"],
        "امتیاز فعلی": filtered["baseline_score"].map(lambda value: format_persian_number(value, 1)),
        "امتیاز سناریویی": filtered["scenario_score"].map(lambda value: format_persian_number(value, 1)),
        "تغییر امتیاز": filtered["score_change"].map(lambda value: format_signed_persian_number(value, 1)),
        "رتبه فعلی": filtered["baseline_rank"].map(lambda value: format_persian_number(value, 0)),
        "رتبه سناریویی": filtered["scenario_rank"].map(lambda value: format_persian_number(value, 0)),
        "جابه‌جایی رتبه": filtered["rank_change"].map(lambda value: format_signed_persian_number(value, 0)),
        "درجه فعلی": filtered["baseline_grade"].map(format_grade),
        "درجه سناریویی": filtered["scenario_grade"].map(format_grade),
        "وضعیت تغییر": status,
    })


def render_multi_branch_results(comparison, manifest, primary_branch_code: str) -> None:
    if st is None:  # Defensive guard for accidental use outside the application runtime.
        raise RuntimeError("Streamlit is required to render multi-branch results")
    table = build_network_result_table(comparison.branch_comparison, manifest)
    _render_summary(summarize_network(table))
    _render_primary_branch(table, primary_branch_code)
    st.markdown("### جدول مقایسه تمام شعب")
    filters = st.columns([1.2, 1.3, 2])
    status = filters[0].selectbox("وضعیت تغییر", list(STATUS_OPTIONS), format_func=STATUS_OPTIONS.get, key="multi_result_status")
    source = filters[1].selectbox("منبع قاعده", list(SOURCE_OPTIONS), format_func=SOURCE_OPTIONS.get, key="multi_result_source")
    query = filters[2].text_input("جست‌وجوی نام یا کد شعبه", key="multi_result_query")
    filtered = filter_network_results(table, status=status, source=source, query=query)
    st.caption(f"{format_persian_number(len(filtered), 0)} شعبه از {format_persian_number(len(table), 0)} شعبه · همه فیلترها با شرط «و» اعمال شده‌اند.")
    st.dataframe(_display_frame(filtered), hide_index=True, width="stretch", height=520)
