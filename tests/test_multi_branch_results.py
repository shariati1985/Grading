import pandas as pd

from domain.multi_branch_contracts import EffectiveChange, EffectiveChangeSource
from ui.multi_branch_results import build_network_result_table, filter_network_results, summarize_network


def _change(branch, source, *, changed=True):
    return EffectiveChange(
        branch_code=branch,
        indicator_key="avg_deposits",
        baseline_value=100,
        scenario_value=110 if changed else 100,
        effective_source=source,
        effective_percentage=10 if changed else None,
    )


def _comparison():
    return pd.DataFrame([
        {"branch_id": "1", "branch_name": "زنجان", "region": "الف", "baseline_score": 10.0, "scenario_score": 12.0, "score_change": 2.0, "baseline_rank": 3, "scenario_rank": 1, "rank_change": 2, "baseline_grade": "Grade 2", "scenario_grade": "Grade 1", "grade_changed": True},
        {"branch_id": "2", "branch_name": "تهران", "region": "ب", "baseline_score": 20.0, "scenario_score": 19.0, "score_change": -1.0, "baseline_rank": 1, "scenario_rank": 2, "rank_change": -1, "baseline_grade": "Grade 1", "scenario_grade": "Grade 2", "grade_changed": True},
        {"branch_id": "3", "branch_name": "تبریز", "region": "ج", "baseline_score": 15.0, "scenario_score": 15.0, "score_change": 0.0, "baseline_rank": 2, "scenario_rank": 2, "rank_change": 0, "baseline_grade": "Excellent", "scenario_grade": "Excellent", "grade_changed": False},
    ])


def test_summary_classifies_rank_and_grade_direction():
    table = build_network_result_table(
        _comparison(),
        (_change("1", EffectiveChangeSource.BRANCH_EXCEPTION), _change("2", EffectiveChangeSource.GENERAL_RULE)),
    )
    summary = summarize_network(table)
    assert (summary.rank_up, summary.rank_down, summary.rank_same) == (1, 1, 1)
    assert (summary.grade_up, summary.grade_down, summary.grade_same) == (1, 1, 1)
    assert summary.largest_rank_up == 2
    assert summary.largest_rank_down == -1


def test_filters_are_combined_with_and():
    table = build_network_result_table(
        _comparison(),
        (_change("1", EffectiveChangeSource.BRANCH_EXCEPTION), _change("2", EffectiveChangeSource.GENERAL_RULE)),
    )
    assert filter_network_results(table, status="rank_up", source="exception", query="زنجان")["branch_id"].tolist() == ["1"]
    assert filter_network_results(table, status="rank_up", source="general", query="زنجان").empty


def test_unchanged_source_filter_includes_branch_without_effective_change():
    table = build_network_result_table(_comparison(), (_change("1", EffectiveChangeSource.GENERAL_RULE),))
    assert filter_network_results(table, source="unchanged")["branch_id"].tolist() == ["2", "3"]
