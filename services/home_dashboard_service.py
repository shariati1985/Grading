"""Aggregation-only service for the home management overview."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class HomeDashboardOverview:
    branch_count: int
    region_count: int
    average_final_score: float | None
    period_id: str
    grade_distribution: pd.DataFrame
    region_summary: pd.DataFrame
    indicator_profile: pd.DataFrame
    rank_movers: pd.DataFrame


def build_home_dashboard_overview(
    branch_summary: pd.DataFrame,
    branch_indicators: pd.DataFrame,
    *,
    period_id: str,
    permitted_branch_ids: set[str] | None = None,
) -> HomeDashboardOverview:
    """Build presentation aggregates without recalculating official model values."""
    summary = branch_summary.copy()
    indicators = branch_indicators.copy()

    summary = summary.loc[summary["period_id"].astype(str).eq(str(period_id))]
    indicators = indicators.loc[indicators["period_id"].astype(str).eq(str(period_id))]

    if permitted_branch_ids is not None:
        allowed = {str(value) for value in permitted_branch_ids}
        summary = summary.loc[summary["branch_id"].astype(str).isin(allowed)]
        indicators = indicators.loc[indicators["branch_id"].astype(str).isin(allowed)]

    grade_distribution = (
        summary.groupby("grade", dropna=False)
        .size()
        .rename("branch_count")
        .reset_index()
        .sort_values(["branch_count", "grade"], ascending=[False, True])
        .reset_index(drop=True)
    )

    region_summary = (
        summary.groupby(["region_id", "region_name"], dropna=False)
        .agg(
            branch_count=("branch_id", "nunique"),
            average_final_score=("final_score", "mean"),
        )
        .reset_index()
        .sort_values(["average_final_score", "region_name"], ascending=[False, True])
        .reset_index(drop=True)
    )

    indicator_profile = (
        indicators.groupby(["indicator_id", "indicator_name"], dropna=False)
        .agg(
            average_normalized_score=("normalized_score", "mean"),
            branch_count=("branch_id", "nunique"),
        )
        .reset_index()
        .sort_values("indicator_id")
        .reset_index(drop=True)
    )

    movers = summary.loc[
        summary["rank_change"].notna(),
        ["branch_id", "branch_name", "region_name", "previous_rank", "final_rank", "rank_change"],
    ].copy()
    if not movers.empty:
        movers = movers.sort_values(
            ["rank_change", "branch_name"], ascending=[False, True]
        ).reset_index(drop=True)

    average_score = (
        None if summary.empty else float(summary["final_score"].astype(float).mean())
    )
    region_count = 0 if summary.empty else int(summary["region_id"].nunique())

    return HomeDashboardOverview(
        branch_count=int(summary["branch_id"].nunique()),
        region_count=region_count,
        average_final_score=average_score,
        period_id=str(period_id),
        grade_distribution=grade_distribution,
        region_summary=region_summary,
        indicator_profile=indicator_profile,
        rank_movers=movers,
    )
