import pandas as pd

from domain.multi_branch_contracts import EffectiveChange, EffectiveChangeSource
from ui.multi_branch_results import (
    aggregate_indicator_impact,
    aggregate_rule_source_coverage,
    build_audit_long_form,
    build_network_result_table,
    compact_branch_table,
    format_raw_display,
    format_rank_movement_label,
    filter_network_results,
    managerial_conclusion,
    managerial_conclusion_model,
    result_header_html,
    primary_branch_result,
    summarize_network,
    top_movers,
)
from ui.charts import build_impact_distribution_chart


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


def test_executive_summary_distinguishes_raw_score_and_rank_changes():
    manifest = (
        _change("1", EffectiveChangeSource.BRANCH_EXCEPTION),
        _change("1", EffectiveChangeSource.GENERAL_RULE),
        _change("2", EffectiveChangeSource.GENERAL_RULE),
    )
    table = build_network_result_table(_comparison(), manifest)
    summary = summarize_network(table, manifest)
    assert summary.total_branches == 3
    assert summary.raw_changed_branches == 2
    assert summary.branch_indicator_changes == 3
    assert summary.score_changed_branches == 2
    assert summary.rank_moved_branches == 2
    assert summary.net_rank_movement == 0


def test_managerial_conclusion_is_deterministic_and_mentions_required_ratios():
    table = build_network_result_table(_comparison(), (_change("1", EffectiveChangeSource.GENERAL_RULE),))
    first = managerial_conclusion(summarize_network(table))
    second = managerial_conclusion(summarize_network(table))
    assert first == second
    assert "تغییر مقدار" in first
    assert "تغییر امتیاز" in first
    assert "جابه‌جایی رتبه" in first
    assert "خالص حرکت رتبه" in first


def test_top_improvements_and_declines_sort_by_rank_then_score():
    comparison = pd.concat([
        _comparison(),
        pd.DataFrame([{"branch_id": "4", "branch_name": "شیراز", "region": "د", "baseline_score": 8.0, "scenario_score": 9.0, "score_change": 1.0, "baseline_rank": 5, "scenario_rank": 3, "rank_change": 2, "baseline_grade": "Grade 2", "scenario_grade": "Grade 2", "grade_changed": False}]),
    ], ignore_index=True)
    table = build_network_result_table(comparison, ())
    assert top_movers(table, improvement=True)["branch_id"].tolist()[:2] == ["1", "4"]
    assert top_movers(table, improvement=False)["branch_id"].tolist() == ["2"]


def test_primary_branch_lookup_and_audit_long_form_values():
    manifest = (_change("1", EffectiveChangeSource.BRANCH_EXCEPTION),)
    table = build_network_result_table(_comparison(), manifest)
    row, audit = primary_branch_result(table, manifest, "1")
    assert row is not None
    assert row["branch_name"] == "زنجان"
    assert audit.iloc[0]["absolute_change"] == 10
    assert audit.iloc[0]["effective_source_text"] == "استثنای شعبه"


def test_indicator_impact_and_rule_source_counts_do_not_double_count_branches():
    manifest = (
        _change("1", EffectiveChangeSource.GENERAL_RULE),
        _change("1", EffectiveChangeSource.BRANCH_EXCEPTION),
        _change("2", EffectiveChangeSource.GENERAL_RULE),
    )
    table = build_network_result_table(_comparison(), manifest)
    impact = aggregate_indicator_impact(table, manifest).iloc[0]
    coverage = aggregate_rule_source_coverage(table, manifest)
    assert impact["affected_branches"] == 2
    assert impact["branches_rank_up"] == 1
    assert impact["branches_rank_down"] == 1
    assert coverage.loc[coverage["source_key"].eq("general"), "affected_branch_count"].iloc[0] == 2
    assert coverage.loc[coverage["source_key"].eq("general"), "branch_indicator_change_count"].iloc[0] == 2


def test_filters_combine_status_source_indicator_and_search():
    table = build_network_result_table(
        _comparison(),
        (_change("1", EffectiveChangeSource.BRANCH_EXCEPTION), _change("2", EffectiveChangeSource.GENERAL_RULE)),
    )
    result = filter_network_results(table, status="rank_up", source="exception", indicator="avg_deposits", query="1")
    assert result["branch_id"].tolist() == ["1"]
    assert filter_network_results(table, status="score_down", source="exception", indicator="avg_deposits").empty


def test_audit_table_is_long_form_and_compact_table_has_no_concatenated_raw_columns():
    manifest = (_change("1", EffectiveChangeSource.GENERAL_RULE), _change("2", EffectiveChangeSource.GENERAL_RULE))
    table = build_network_result_table(_comparison(), manifest)
    audit = build_audit_long_form(manifest)
    compact = compact_branch_table(table)
    assert len(audit) == 2
    assert {"branch_code", "indicator_key", "baseline_raw_value", "scenario_raw_value", "changed_flag"}.issubset(audit.columns)
    assert "مقدار خام فعلی" not in compact.columns
    assert "درصد یا مقدار اعمال‌شده" not in compact.columns


def test_zero_all_improvement_and_all_decline_scenarios():
    zero = _comparison().assign(score_change=0.0, rank_change=0, scenario_score=lambda frame: frame["baseline_score"], scenario_rank=lambda frame: frame["baseline_rank"], scenario_grade=lambda frame: frame["baseline_grade"])
    zero_summary = summarize_network(build_network_result_table(zero, ()))
    assert zero_summary.rank_moved_branches == 0
    assert zero_summary.net_rank_movement == 0

    up = _comparison().assign(rank_change=1, score_change=1.0)
    up_summary = summarize_network(build_network_result_table(up, ()))
    assert up_summary.rank_up == 3 and up_summary.net_rank_movement == 3

    down = _comparison().assign(rank_change=-1, score_change=-1.0)
    down_summary = summarize_network(build_network_result_table(down, ()))
    assert down_summary.rank_down == 3 and down_summary.net_rank_movement == -3


def test_positive_rank_movement_means_improvement():
    table = build_network_result_table(_comparison(), ())
    row = table.loc[table["branch_id"].eq("1")].iloc[0]
    assert row["rank_change"] == 2
    assert row["rank_status"] == "rank_up"
    assert format_rank_movement_label(row["rank_change"]) == "۲ رتبه بهبود"


def test_result_header_uses_separated_metadata_cards_not_crowded_pills():
    markup = result_header_html({"نام سناریو": "آزمون", "جامعه رسمی": "۳ شعبه"})
    assert 'class="multi-results-metadata"' in markup
    assert markup.count("<article>") == 2
    assert "<span>نام سناریو</span><strong>آزمون</strong>" in markup
    assert "multi-results-context" not in markup


def test_managerial_conclusion_model_has_headline_body_and_evidence_items():
    table = build_network_result_table(_comparison(), (_change("1", EffectiveChangeSource.GENERAL_RULE),))
    model = managerial_conclusion_model(summarize_network(table))
    assert model["headline"]
    assert model["body"]
    assert len(model["evidence"]) >= 3
    assert any("تعداد تغییرات شعبه–شاخص" in item for item in model["evidence"])


def test_raw_display_controls_decimal_precision_and_grouping():
    assert format_raw_display(6113152094192.348) == "۶٬۱۱۳٬۱۵۲٬۰۹۴٬۱۹۲٫۳۵"
    assert format_raw_display(1700.0) == "۱٬۷۰۰"


def test_impact_distribution_chart_is_compact_and_hides_tiny_segment_labels():
    table = build_network_result_table(_comparison(), ())
    summary = summarize_network(table)
    figure = build_impact_distribution_chart(summary)
    assert figure.layout.height == 300
    assert figure.layout.xaxis.title.text == "تعداد شعب"


def test_persisted_results_can_render_summary_without_manifest_detail():
    table = build_network_result_table(_comparison(), ())
    summary = summarize_network(table, ())
    assert summary.branch_indicator_changes == 0
    assert summary.raw_changed_branches == 0
