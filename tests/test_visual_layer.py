"""Contract tests for reusable visual-layer helpers."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import pytest

from ui.charts import (
    IndicatorComparisonDataError,
    build_selected_indicator_score_chart,
    build_indicator_rank_lollipop,
    build_network_rank_chart,
    prepare_selected_indicator_scores,
    rank_axis_range,
    validate_indicator_score_chart_matches_table,
)
from domain.scenario_contracts import ScenarioType
from ui.navigation import (
    EN_BANK_LOGO_PATH,
    EN_BANK_LOGO_RELATIVE_PATH,
    HOME_VIEW,
    NAVIGATION_ITEMS,
    SAVED_SCENARIOS_VIEW,
    UTILITY_NAVIGATION_ITEMS,
    icon_svg,
    _logo_data_uri,
    scenario_href,
    scenario_mode_from_query,
)
from ui.formatters import format_number, format_persian_number, persian_digits
from ui.sensitivity_components import (
    indicator_cards_html,
    render_wizard_steps,
    summary_cards_html,
    value_comparison_html,
)
from ui.sensitivity_labels import SCENARIO_DEFINITIONS, SCENARIO_TYPE_LABELS
from ui.scenario_workflow import INDICATOR_LABELS, INDICATOR_ORDER
from app import home_markup, overview_markup

ROOT = Path(__file__).resolve().parents[1]


class _BalanceParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag not in self.VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        assert self.stack, f"unexpected closing tag {tag}"
        current = self.stack.pop()
        assert current == tag, f"expected closing {current}, got {tag}"


def _assert_balanced_html(fragment: str) -> None:
    parser = _BalanceParser()
    parser.feed(fragment)
    parser.close()
    assert parser.stack == []


def _indicator_comparison() -> pd.DataFrame:
    rows = []
    for branch_offset, branch_id in enumerate(("101", "202")):
        for position, indicator_key in enumerate(reversed(INDICATOR_ORDER)):
            rows.append(
                {
                    "branch_id": branch_id,
                    "indicator_key": indicator_key,
                    "baseline_score": float(100 + position + branch_offset * 100),
                    "scenario_score": float(200 + position + branch_offset * 100),
                    "baseline_weighted_score": -10_000.0 - position,
                    "scenario_weighted_score": 10_000.0 + position,
                    "raw_value": 999_999_999.0,
                }
            )
    return pd.DataFrame(rows)


def test_rank_axis_range_has_minimum_and_expands_symmetrically() -> None:
    assert rank_axis_range([]) == (-3, 3)
    assert rank_axis_range([1, -1, 0]) == (-3, 3)
    assert rank_axis_range([4, -2]) == (-4, 4)


def test_indicator_rank_chart_uses_integer_ticks_and_centered_range() -> None:
    figure = build_indicator_rank_lollipop(
        pd.Series(["شاخص یک", "شاخص دو"]), pd.Series([1, -1])
    )
    assert figure.layout.xaxis.dtick == 1
    assert tuple(figure.layout.xaxis.range) == (-3, 3)
    assert figure.layout.height == 440


def test_indicator_score_chart_uses_exact_unweighted_scores_and_persian_order() -> None:
    source = _indicator_comparison()
    prepared = prepare_selected_indicator_scores(source, "101")
    figure = build_selected_indicator_score_chart(prepared)

    assert list(prepared.columns) == [
        "branch_id",
        "indicator_key",
        "baseline_score",
        "scenario_score",
    ]
    assert prepared["indicator_key"].tolist() == list(INDICATOR_ORDER)
    assert list(figure.data[0].x) == prepared["baseline_score"].tolist()
    assert list(figure.data[1].x) == prepared["scenario_score"].tolist()
    assert list(figure.data[0].y) == [INDICATOR_LABELS[key] for key in INDICATOR_ORDER]
    assert tuple(figure.layout.xaxis.range) == (1, 1000)
    assert "baseline_weighted_score" not in prepared.columns
    assert "scenario_weighted_score" not in prepared.columns
    assert max(figure.data[0].x) < 1000
    assert max(figure.data[1].x) < 1000


def test_indicator_score_chart_filters_selected_branch_and_has_eight_unique_rows() -> None:
    prepared = prepare_selected_indicator_scores(_indicator_comparison(), "202")
    assert prepared["branch_id"].eq("202").all()
    assert len(prepared) == 8
    assert prepared["indicator_key"].nunique() == 8


def test_indicator_chart_values_validate_against_table_values() -> None:
    prepared = prepare_selected_indicator_scores(_indicator_comparison(), "101")
    table_source = prepared.copy(deep=True)
    validate_indicator_score_chart_matches_table(prepared, table_source)
    table_source.loc[0, "scenario_score"] += 0.1
    with pytest.raises(IndicatorComparisonDataError, match="do not match"):
        validate_indicator_score_chart_matches_table(prepared, table_source)


def test_indicator_score_data_rejects_duplicates_and_out_of_range_scores() -> None:
    source = _indicator_comparison()
    duplicate = pd.concat([source, source.iloc[[0]]], ignore_index=True)
    with pytest.raises(IndicatorComparisonDataError, match="duplicate branch_id"):
        prepare_selected_indicator_scores(duplicate, "101")

    out_of_range = source.copy(deep=True)
    out_of_range.loc[
        out_of_range["branch_id"].eq("101"), "baseline_score"
    ] = 1001.0
    with pytest.raises(IndicatorComparisonDataError, match="within 1–1000"):
        prepare_selected_indicator_scores(out_of_range, "101")


def test_single_network_result_uses_compact_chart() -> None:
    network = pd.DataFrame(
        {
            "branch_id": ["101"],
            "branch_name": ["غدیر"],
            "rank_change": [1],
        }
    )
    figure = build_network_rank_chart(network, improvement=True)
    assert figure is not None
    assert figure.layout.height == 270
    assert figure.layout.xaxis.dtick == 1
    assert tuple(figure.layout.xaxis.range) == (0, 2)


def test_empty_network_result_returns_no_chart() -> None:
    network = pd.DataFrame(
        {"branch_id": ["101"], "branch_name": ["غدیر"], "rank_change": [0]}
    )
    assert build_network_rank_chart(network, improvement=True) is None
    assert build_network_rank_chart(network, improvement=False) is None


def test_persian_navigation_labels_and_icons_are_complete() -> None:
    assert [label for _, label, _ in NAVIGATION_ITEMS] == [
        "سناریوی شعبه‌محور", "سناریوی چندشعبه‌ای", "سناریوی رتبه هدف",
    ]
    assert [icon for icon, _, _ in NAVIGATION_ITEMS] == ["bank", "buildings", "target"]
    assert all("<svg" in icon_svg(icon) for icon, _, _ in NAVIGATION_ITEMS)
    assert [mode for _, _, mode in NAVIGATION_ITEMS] == [item.scenario_type for item in SCENARIO_DEFINITIONS]
    assert [item.label for item in SCENARIO_DEFINITIONS] == [SCENARIO_TYPE_LABELS[mode] for mode in ScenarioType]


@pytest.mark.parametrize("mode", list(ScenarioType))
def test_scenario_links_round_trip_to_exact_mode(mode) -> None:
    assert scenario_href(mode) == f"/?scenario={mode.value}&new=1"
    assert scenario_mode_from_query(mode.value) is mode
    assert scenario_mode_from_query("OLD_SCENARIO") is None


def test_home_and_saved_scenarios_navigation_are_visible_and_clean() -> None:
    assert [label for _, label, _ in UTILITY_NAVIGATION_ITEMS] == ["صفحه اصلی", "سناریوهای ذخیره‌شده"]
    assert [icon for icon, _, _ in UTILITY_NAVIGATION_ITEMS] == ["home", "folder"]
    assert all("rd_double_arrow_left" not in item for row in UTILITY_NAVIGATION_ITEMS for item in row)


def test_sidebar_uses_real_en_bank_logo_asset() -> None:
    assert EN_BANK_LOGO_RELATIVE_PATH.as_posix() == "assets/logo-1.png"
    assert EN_BANK_LOGO_PATH == ROOT / EN_BANK_LOGO_RELATIVE_PATH
    assert EN_BANK_LOGO_PATH.is_file()
    assert EN_BANK_LOGO_PATH.stat().st_size > 0
    assert _logo_data_uri().startswith("data:image/png;base64,")


def test_sidebar_brand_has_no_synthetic_en_logo_text() -> None:
    source = (ROOT / "ui" / "navigation.py").read_text(encoding="utf-8")
    assert "سامانه تحلیل حساسیت شعب" in source
    assert "درجه‌بندی و تحلیل سناریو" in source
    assert "logo-1.png" in source
    assert ">EN<" not in source
    assert "nav-brand-mark\">EN" not in source


def test_legacy_scenario_labels_are_absent() -> None:
    legacy = {"تغییر شعبه محوری", "تغییر شعبه‌محور", "تحلیل رتبه هدف", "سناریوی چند شعبه‌ای"}
    current = {label for _, label, _ in NAVIGATION_ITEMS}
    current |= set(SCENARIO_TYPE_LABELS.values())
    assert current.isdisjoint(legacy)


def test_home_visual_contract_uses_reference_palette_and_no_underlines() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "--primary-navy" in css_source
    assert "--brand-purple" in css_source
    assert "--brand-purple-light" in css_source
    assert ".scenario-nav-link.active" in css_source
    assert "text-decoration: none !important" in css_source
    assert ".home-decision-panel" in css_source
    assert ".home-overview-grid" in css_source
    assert "home-page-reference.png" not in app_source


def test_persian_font_stack_is_centralized_and_scoped_to_app_shell() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    assert '--app-font-fa: "Vazirmatn", "IRANSansX", "IRANSans", "Segoe UI", Tahoma, Arial, sans-serif;' in css_source
    assert "--font: var(--app-font-fa);" in css_source
    assert '[data-testid="stAppViewContainer"] *' in css_source
    assert '[data-testid="stSidebar"] *' in css_source
    assert '[data-testid="stMarkdownContainer"] *' in css_source
    assert '[data-testid="stWidgetLabel"]' in css_source
    assert "button," in css_source
    assert "font-family: var(--font) !important" in css_source
    assert "@import" not in css_source
    assert "fonts.googleapis.com" not in css_source
    assert "fonts.gstatic.com" not in css_source
    assert "Times New Roman" not in css_source
    assert "serif" not in css_source.replace("sans-serif", "")


def test_local_persian_font_assets_are_not_fabricated_or_externally_loaded() -> None:
    font_assets = [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".woff", ".woff2", ".ttf", ".otf"}
    ]
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    if font_assets:
        assert "@font-face" in css_source
    else:
        assert "@font-face" not in css_source
        assert '--app-font-fa: "Vazirmatn", "IRANSansX", "IRANSans", "Segoe UI", Tahoma, Arial, sans-serif;' in css_source


def test_home_omits_duplicate_user_profile_and_header_offset_remains() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    markup = home_markup(branch_count=324, saved_count="168")
    main_rule = css_source.split(".block-container {", 1)[1].split("}", 1)[0]

    assert "home-user-chip" not in markup
    assert 'data-user-profile="current-user"' not in markup
    assert "خوش آمدید" not in markup
    assert "_workspace_service().current_user.display_name" not in app_source
    assert '[data-testid="stMainBlockContainer"],' in css_source
    assert "var(--streamlit-header-offset)" in main_rule
    assert "nth-child" not in css_source
    assert "<script" not in css_source


def test_rtl_icon_layout_puts_icon_before_persian_label_without_row_reverse() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    nav_rule = css_source.split(".scenario-nav-link {", 1)[1].split("}", 1)[0]
    icon_rule = css_source.split(".scenario-nav-link svg {", 1)[1].split("}", 1)[0]
    action_rule = css_source.split(".decision-panel-action {", 1)[1].split("}", 1)[0]
    card_action_rule = css_source.split(".scenario-card-start {", 1)[1].split("}", 1)[0]
    assert "display: flex" in nav_rule
    assert "direction: rtl" in nav_rule
    assert "flex-direction: row;" in nav_rule
    assert "row-reverse" not in nav_rule
    assert "width: 22px" in icon_rule and "height: 22px" in icon_rule
    assert "stroke-width: 1.8" in icon_rule
    assert "flex-shrink: 0" in icon_rule
    assert "direction: rtl" in action_rule and "flex-direction: row" in action_rule
    assert "direction: rtl" in card_action_rule and "flex-direction: row" in card_action_rule


def test_navigation_active_markup_is_explicit_and_exclusive() -> None:
    from ui.navigation import render_navigation

    source = (ROOT / "ui" / "navigation.py").read_text(encoding="utf-8")
    assert "active_view: str = HOME_VIEW" in source
    assert "active_scenario: ScenarioType | None = None" in source
    assert "SENSITIVITY_DRAFT_KEY" not in source
    assert 'active_scenario is None and active_view == view' in source
    assert 'active_scenario is item.scenario_type' in source
    assert HOME_VIEW == "home"
    assert SAVED_SCENARIOS_VIEW == "saved"
    assert render_navigation


def test_home_markup_excludes_saved_scenario_list_but_keeps_aggregate_metric() -> None:
    markup = home_markup(branch_count=324, saved_count="168") + overview_markup(branch_count=324, saved_count="168")
    assert "سناریوی ذخیره‌شده توسط کاربران" in markup
    assert "سناریوهای ذخیره‌شده" not in markup
    assert "saved-scenario-card" not in markup
    assert "workspace_open_" not in markup
    assert "بازکردن و ادامه" not in markup
    assert "مشاهده نتیجه" not in markup


def test_scenario_builder_without_selected_mode_returns_to_original_home() -> None:
    source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    fallback_body = source.split('if draft.get("scenario_type") is None:', 1)[1].split("try: data, outputs", 1)[0]
    home = home_markup(branch_count=324, saved_count="168") + overview_markup(branch_count=324, saved_count="168")

    assert "home-page-header" in home
    assert "home-decision-panel" in home
    assert "home-overview-grid" in home
    assert "سامانه تحلیل حساسیت و درجه‌بندی شعب" in home
    assert "تصمیم‌گیری هوشمند با تحلیل سناریو" in home
    assert 'st.switch_page("app.py")' in fallback_body
    assert "فضای تحلیل حساسیت" not in fallback_body
    assert "choose_" not in fallback_body
    assert "st.columns(3)" not in fallback_body


def test_multi_branch_sidebar_entry_still_opens_dedicated_workspace() -> None:
    nav_source = (ROOT / "ui" / "navigation.py").read_text(encoding="utf-8")
    builder_source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")

    assert "سناریوی چندشعبه‌ای" in [label for _, label, _ in NAVIGATION_ITEMS]
    assert ScenarioType.MULTI_BRANCH in [mode for _, _, mode in NAVIGATION_ITEMS]
    assert "scenario_href(item.scenario_type)" in nav_source
    assert "start_new_scenario(st.session_state, mode)" in nav_source
    assert "render_multi_branch_workspace(" in builder_source
    assert "mode is ScenarioType.MULTI_BRANCH" in builder_source


def test_management_overview_cards_have_polished_rtl_typography_and_icons() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    markup = overview_markup(branch_count=324, saved_count="168")
    article_rule = css_source.split(".home-overview-grid article {", 1)[1].split("}", 1)[0]
    content_rule = css_source.split(".overview-content {", 1)[1].split("}", 1)[0]
    value_rule = css_source.split(".home-overview-grid .overview-value {", 1)[1].split("}", 1)[0]
    label_rule = css_source.split(".home-overview-grid .overview-label {", 1)[1].split("}", 1)[0]
    icon_rule = css_source.split(".overview-icon {", 1)[1].split("}", 1)[0]
    icon_svg_rule = css_source.split(".overview-icon svg {", 1)[1].split("}", 1)[0]

    assert 'class="overview-content"' in markup
    assert 'class="overview-value numeric-fa" dir="rtl"' in markup
    assert 'class="overview-label"' in markup
    assert markup.count('class="overview-icon"') == 3
    assert markup.count("<svg") == 3
    assert "۱۴۰۴-۰۴" in markup
    assert "flex-direction: row" in article_rule
    assert "row-reverse" not in article_rule
    assert "direction: rtl" in article_rule
    assert "justify-content: flex-start" in article_rule
    assert "text-align: right" in article_rule
    assert "font-family: var(--font) !important" in article_rule
    assert "align-items: flex-start" in content_rule
    assert "text-align: right" in content_rule
    assert "font-weight: 700" in value_rule
    assert "font-family: var(--font) !important" in value_rule
    assert "line-height: 1.7" in value_rule
    assert "font-weight: 600" in label_rule
    assert "text-align: right" in label_rule
    assert "flex: 0 0 58px" in icon_rule
    assert "width: 34px" in icon_svg_rule and "height: 34px" in icon_svg_rule
    assert "stroke-width: 1.75" in icon_svg_rule


def test_saved_scenarios_are_dedicated_view_only_and_preserve_actions() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    home_body = app_source.split("def render_home_page", 1)[1].split("def render_saved_scenarios_view", 1)[0]
    saved_body = app_source.split("def render_saved_scenarios_view", 1)[1].split("def main", 1)[0]
    main_body = app_source.split("def main", 1)[1]
    assert "saved-scenario-card" not in home_body
    assert "workspace_open_" not in home_body
    assert "سناریوهای ذخیره‌شده" not in home_body
    assert "saved-scenario-card" in saved_body
    assert "workspace_open_" in saved_body
    assert "workspace_result_" in saved_body
    assert "workspace_version_" in saved_body
    assert "ask_delete_" in saved_body
    assert "render_saved_scenarios_view(data, records)" in main_body
    assert "return" in main_body.split("render_saved_scenarios_view(data, records)", 1)[1].split("render_home_page", 1)[0]


def test_result_page_action_labels_and_removed_stepper_contract() -> None:
    source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    assert '"ذخیره نتیجه"' in source
    assert '"بازگشت و ویرایش"' in source
    assert '"بروزرسانی همین سناریو"' in source
    assert '"ایجاد نسخه کپی"' not in source
    assert '"سناریوی جدید"' not in source
    assert '("وضعیت فعلی", "اعمال تغییرات", "اجرای مدل رسمی", "نتیجه سناریو")' not in source


def test_branch_focused_stepper_preserves_labels_order_and_real_state(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_markdown(markup: str, **_: object) -> None:
        captured["markup"] = markup

    monkeypatch.setattr("ui.sensitivity_components.st.markdown", fake_markdown)
    labels = ("انتخاب شعبه", "انتخاب شاخص‌ها", "تعریف تغییرات", "بازبینی و اجرا")
    render_wizard_steps(labels, 3)
    markup = captured["markup"]

    assert 'class="wizard-steps" dir="rtl"' in markup
    assert [markup.index(label) for label in labels] == sorted(markup.index(label) for label in labels)
    assert markup.count('data-step-state="completed"') == 2
    assert markup.count('data-step-state="active"') == 1
    assert markup.count('data-step-state="future"') == 1
    assert markup.count("wizard-step ") == 4
    assert markup.count("wizard-connector") == 3
    assert markup.count("wizard-step-completed") == 2
    assert markup.count("wizard-step-active") == 1
    assert markup.count("wizard-step-future") == 1
    assert ">۱<" in markup
    assert ">۲<" in markup
    assert ">۳<" in markup
    assert ">۴<" in markup
    assert "۱. انتخاب شعبه" in markup
    assert "۲. انتخاب شاخص‌ها" in markup
    assert "<svg" not in markup
    assert "Material" not in markup
    assert "keyboard_" not in markup


def test_branch_focused_step_one_uses_existing_bindings_and_no_demo_values() -> None:
    source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    expected_steps = '("انتخاب شعبه", "انتخاب شاخص‌ها", "تعریف تغییرات", "بازبینی و اجرا")'

    assert expected_steps in source
    assert 'key="sensitivity_focus_branch"' in source
    assert "set_focus_branch(draft, chosen" in source
    assert "FocusBranchSource.USER_SELECTED_BRANCH.value if chosen else None" in source
    assert "LOCAL_ADMINISTRATIVE_TESTING_MODE" in source
    assert "data-branch-step=\"focus-step-1\"" in source
    assert 'key="sensitivity_scenario_name"' in source
    assert "_save_draft(draft)" in source
    assert "scenario-name-panel" in source
    assert "scenario-save-status" in source
    assert "branch-summary-panel" in source
    assert "branch-info-card" in source
    assert "data-selected-branch-banner" in source
    assert "<bdi>" in source
    assert "persian_digits(branch_id)" in source
    assert "format_persian_number(result[\"rank\"], decimals=0)" in source
    assert "format_persian_number(result[\"final_score\"], decimals=1)" in source
    assert "_selected_branch_banner(str(draft[\"focus_branch_id\"]), names)" in source
    assert 'raw[BRANCH_NAME]' in source
    assert 'raw[BRANCH_ID]' in source
    assert 'raw[REGION]' in source
    assert 'result["rank"]' in source
    assert 'result["final_score"]' in source
    assert 'result["grade"]' in source
    assert "دولت" not in source
    assert "1135" not in source
    assert "درجه 1" not in source


    assert "پاک‌کردن سناریو" not in source.split("def _navigation", 1)[1].split("def main", 1)[0]
    state_source = (ROOT / "ui" / "sensitivity_state.py").read_text(encoding="utf-8")
    assert "def reset_sensitivity_draft" in state_source


def test_persian_digit_formatter_is_presentation_only() -> None:
    assert format_number(728, decimals=1) == "728.0"
    assert format_persian_number(728, decimals=1) == "۷۲۸٫۰"
    assert persian_digits("105,200.5") == "۱۰۵٬۲۰۰٫۵"
    assert persian_digits("-9%") == "−۹%"


def test_branch_step_styles_are_scoped_responsive_and_svg_based() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    step_rule = css_source.split(".wizard-steps {", 1)[1].split("}", 1)[0]
    branch_rule = css_source.split(".branch-step-panel {", 1)[1].split("}", 1)[0]
    card_rule = css_source.split(".branch-info-card {", 1)[1].split("}", 1)[0]
    icon_rule = css_source.split(".branch-info-icon svg {", 1)[1].split("}", 1)[0]
    header_rule = css_source.split(".scenario-builder-header {", 1)[1].split("}", 1)[0]
    header_title_rule = css_source.split(".scenario-builder-header h1 {", 1)[1].split("}", 1)[0]
    name_input_rule = css_source.split(".scenario-name-panel input {", 1)[1].split("}", 1)[0]

    assert "direction: rtl" in step_rule
    assert "grid-template-columns:" in step_rule
    assert "minmax(22px, .55fr)" in step_rule
    assert ".wizard-step-completed" in css_source
    assert ".wizard-step-future" in css_source
    assert ".wizard-connector" in css_source
    assert ".wizard-step::after" not in css_source
    assert "font-family: var(--font) !important" in css_source
    assert "background: transparent" in branch_rule
    assert "box-shadow: none" in branch_rule
    assert "flex-direction: row" in card_rule
    assert "direction: rtl" in card_rule
    assert "flex-shrink: 0" in css_source.split(".branch-info-icon {", 1)[1].split("}", 1)[0]
    assert "width: 30px" in icon_rule and "height: 30px" in icon_rule
    assert "stroke-width: 1.75" in icon_rule
    assert "justify-content: flex-start" in header_rule
    assert "direction: rtl" in header_rule
    assert "align-items: center" in header_rule
    assert "font-weight: 700" in header_title_rule
    assert "text-align: right" in header_title_rule
    assert "direction: rtl" in name_input_rule
    assert "text-align: right" in name_input_rule
    assert ".scenario-save-status" in css_source
    assert ".branch-info-alert" in css_source
    assert ".selected-branch-banner" in css_source
    assert "unicode-bidi: isolate" in css_source
    assert ".numeric-fa" in css_source
    assert ".builder-action-row" in css_source
    assert ".builder-action-row + [data-testid=\"stHorizontalBlock\"] button" in css_source
    assert "@media (max-width: 900px)" in css_source
    assert "nth-child" not in css_source


def test_sidebar_profile_card_uses_user_config_binding_and_official_logo() -> None:
    source = (ROOT / "ui" / "navigation.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")

    assert "load_current_user(ROOT / \"config\" / \"local_user.json\")" in source
    assert 'data-user-profile="current-user"' in source
    assert "display_name = current_user.display_name" in source
    assert "logo-1.png" in source
    assert ".nav-user-card" in css_source
    assert "margin-top: auto" in css_source


def test_preview_html_contains_complete_very_large_values() -> None:
    markup = value_comparison_html(4_000_000_000_000.0, 4_500_000_000_000.25)
    assert "۴٬۰۰۰٬۰۰۰٬۰۰۰٬۰۰۰" in markup
    assert "۴٬۵۰۰٬۰۰۰٬۰۰۰٬۰۰۰" in markup
    assert "۵۰۰٬۰۰۰٬۰۰۰٬۰۰۰" in markup
    assert "numeric-fa" in markup


def test_change_definition_step_uses_bound_branch_cards_and_existing_widget_keys() -> None:
    source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")

    assert "data-change-step-header" in source
    assert "_selected_branch_banner(branch_id, names)" in source
    assert "names.get(str(branch_id)" in source
    assert "persian_digits(branch_id)" in source
    assert "data-self-contained-card=\"true\"" in source
    assert "definition.display_name" in source
    assert "format_persian_number(current, 0)" in source
    assert "key=f\"focus_op_{indicator_id}\"" in source
    assert "key=f\"focus_direction_{indicator_id}_{operation.value}\"" in source
    assert "key=f\"focus_value_{indicator_id}_{operation.value}\"" in source
    assert "preview_raw_operation(raw[indicator_id], operation, value, indicator_id)" in source
    assert 'draft["focus_changes"][indicator_id]' in source
    assert "درصد تغییر" in source and "تغییر مطلق" in source and "مقدار نهایی" in source

    assert ".change-step-header" in css_source
    assert ".selected-branch-code" in css_source
    assert ".indicator-edit-title" in css_source
    assert ".value-comparison-card" in css_source
    assert ".value-comparison-item.current" in css_source
    assert ".value-comparison-item.scenario" in css_source
    assert ".value-comparison-item.success" in css_source
    assert ".value-comparison-item.danger" in css_source
    assert "[data-baseweb=\"popover\"]" in css_source


def test_value_comparison_formats_signed_persian_results_without_mutating_sources() -> None:
    positive = value_comparison_html(1000, 1200)
    negative = value_comparison_html(1000, 900)
    neutral = value_comparison_html(1000, 1000)

    assert "+۲۰۰" in positive
    assert "+۲۰٫۰٪" in positive
    assert "−۱۰۰" in negative
    assert "−۱۰٫۰٪" in negative
    assert "۰٫۰٪" in neutral
    assert "مقدار سناریو" in positive
    assert "مقدار جدید سناریو" not in positive


def test_result_context_strip_keeps_only_branch_name_code_scenario_name_and_changed_count() -> None:
    source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    body = source.split("def _result_context_html", 1)[1].split("def _result_header_html", 1)[0]

    assert 'class="results-context-icon"' in body
    assert "names.get(branch_id, branch_id)" in body
    assert "persian_digits(branch_id)" in body
    assert "نام سناریو:" in body
    assert "شاخص تغییریافته" in body
    assert "شاخص انتخاب‌شده" not in body
    assert "SCENARIO_TYPE_LABELS[result.request.scenario_type])}</span>" not in body


def test_rank_filter_uses_complete_numeric_comparison_and_stable_status_keys() -> None:
    import importlib.util
    from types import SimpleNamespace

    import pandas as pd

    module_path = ROOT / "pages" / "2_Scenario_Builder.py"
    spec = importlib.util.spec_from_file_location("scenario_builder_for_rank_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    rows = pd.DataFrame([
        {"branch_id": "190", "baseline_rank": 108, "scenario_rank": 89, "baseline_score": 1.0, "scenario_score": 2.0, "score_change": 1.0},
        {"branch_id": "191", "baseline_rank": 89, "scenario_rank": 90, "baseline_score": 2.0, "scenario_score": 1.0, "score_change": -1.0},
        {"branch_id": "192", "baseline_rank": 50, "scenario_rank": 50, "baseline_score": 3.0, "scenario_score": 3.0, "score_change": 0.0},
        {"branch_id": "193", "baseline_rank": None, "scenario_rank": 50, "baseline_score": 3.0, "scenario_score": 3.0, "score_change": 0.0},
    ])
    result = SimpleNamespace(comparison_results=SimpleNamespace(branch_comparison=rows))
    rank_rows = module._complete_rank_rows(result, {"190": "آزادی-دکتر قریب", "191": "نزولی", "192": "ثابت"}, "190")

    assert [row["branch_id"] for row in rank_rows].count("190") == 1
    assert next(row for row in rank_rows if row["branch_id"] == "190")["status_key"] == "up"
    assert next(row for row in rank_rows if row["branch_id"] == "191")["status_key"] == "down"
    assert next(row for row in rank_rows if row["branch_id"] == "192")["status_key"] == "unchanged"
    assert "193" not in {row["branch_id"] for row in rank_rows}
    assert module._rank_counter(rank_rows, "up") + module._rank_counter(rank_rows, "down") + module._rank_counter(rank_rows, "unchanged") == len(rank_rows)
    assert len(module._filter_rank_rows(rank_rows, "all", "")) == 3
    assert [row["branch_id"] for row in module._filter_rank_rows(rank_rows, "up", "")] == ["190"]
    assert [row["branch_id"] for row in module._filter_rank_rows(rank_rows, "down", "")] == ["191"]
    assert [row["branch_id"] for row in module._filter_rank_rows(rank_rows, "unchanged", "")] == ["192"]
    assert [row["branch_id"] for row in module._filter_rank_rows(rank_rows, "up", "۱۹۰")] == ["190"]
    assert module._filter_rank_rows(rank_rows, "up", "ناموجود") == []


def test_primary_indicator_card_uses_rank_and_weighted_score_not_normalized_score() -> None:
    markup = indicator_cards_html([{
        "name": "سود و زیان", "icon": "±", "weight": "3%", "tone": "success",
        "status": "2 رتبه بهبود",
        "raw": {"current": "-1,000", "scenario": "-500", "absolute": "+500", "percent": "50%"},
        "rank": {"current": "20", "scenario": "18", "change": "2 رتبه بهبود"},
        "weighted": {"current": "12.0", "scenario": "13.0", "effect": "+1.0"},
    }])
    assert "رتبه فعلی شعبه در شاخص" in markup
    assert "رتبه سناریوی شعبه در شاخص" in markup
    assert "اثر بر امتیاز کل" in markup
    assert "امتیاز نرمال‌شده" not in markup
    assert 'dir="ltr"' in markup


def test_summary_is_one_cohesive_managerial_panel() -> None:
    markup = summary_cards_html([{
        "label": "رتبه کل شعبه", "current": "82", "scenario": "69",
        "change": "13 رتبه بهبود", "tone": "success",
    }], 1)
    assert "جمع‌بندی مدیریتی سناریو" in markup
    assert "وضعیت فعلی" in markup and "وضعیت سناریو" in markup and "نتیجه تغییر" in markup


def test_step_four_uses_card_first_review_and_detail_sections() -> None:
    source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")

    assert "scenario-review-summary" in source
    assert "review-change-card" in source
    assert "review-result-strip" in source
    assert "results-workspace-header" in source
    assert "results-context-strip" in source
    assert "نتیجه اجرای سناریوی شعبه‌محور" in source
    assert "نتیجه در یک نگاه" in source
    assert "جزئیات محاسبات" in source
    assert "شاخص‌های تغییریافته" in source
    assert "شعب متأثر در رتبه‌بندی" in source
    assert "شعب دارای تغییر در داده‌ها" in source
    assert "data-default-results-tab=\"calculation-details\"" in source
    assert "امتیاز موزون" in source
    assert "سهم وزنی" not in source
    assert ".calculation-table" in css_source
    assert ".branch-impact-table" in css_source
    assert ".results-action-bar" in css_source
    assert "[data-testid=\"stTabs\"] [role=\"tablist\"]" in css_source


def test_branch_result_summary_uses_bounded_scoped_markup_and_balanced_html() -> None:
    import importlib.util
    from types import SimpleNamespace

    module_path = ROOT / "pages" / "2_Scenario_Builder.py"
    spec = importlib.util.spec_from_file_location("scenario_builder_for_result_markup_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    comparison = SimpleNamespace(
        rank_change=1,
        score_change=12.5,
        baseline_rank=4,
        scenario_rank=3,
        baseline_final_score=700.0,
        scenario_final_score=712.5,
        baseline_grade="2",
        scenario_grade="1",
        indicator_comparisons=[{}, {}],
    )
    markup = module._managerial_summary_html(comparison, 1)

    for label in ("رتبه شعبه", "امتیاز کل", "درجه شعبه", "شاخص‌های مؤثر"):
        assert label in markup
    assert markup.count('class="result-glance-card') == 4
    assert "result-trend-icon" in markup
    assert "result-change-pill" in markup
    assert "رتبه فعلی" in markup and "رتبه سناریو" in markup
    assert "امتیاز کل فعلی" in markup and "امتیاز کل سناریو" in markup
    assert "<svg" not in markup and "<path" not in markup
    _assert_balanced_html(markup)


def test_branch_result_detail_toggle_suppresses_native_triangle_marker() -> None:
    source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    table_body = source.split("def _calculation_table_html", 1)[1].split("def _changed_indicators_html", 1)[0]

    assert '<details class="result-calc-details">' in table_body
    assert 'summary class="calc-detail-toggle"' in table_body
    assert '<span class="calc-detail-chevron" aria-hidden="true">⌄</span></summary>' in table_body
    assert ".result-calc-details > summary.calc-detail-toggle" in css_source
    assert "summary.calc-detail-toggle::-webkit-details-marker" in css_source
    assert "summary.calc-detail-toggle::marker" in css_source
    assert "list-style: none" in css_source
    assert "list-style-type: none" in css_source
    assert ".calc-detail-chevron" in css_source
    toggle_css = css_source.split(".result-calc-details > summary.calc-detail-toggle", 1)[1].split(".calc-detail-panel", 1)[0]
    assert "display: block" in toggle_css
    assert "display: none" in toggle_css
    assert "max-width: 34px" in toggle_css
    assert "max-height: 30px" in toggle_css
    assert "transparent" not in toggle_css


def test_branch_result_css_does_not_use_broad_svg_path_or_triangle_rules() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    result_css = css_source.split(".results-workspace-header", 1)[1].split("@media (max-width: 1100px)", 1)[0]

    assert "\n        svg " not in result_css
    assert "\n        path " not in result_css
    assert "clip-path" not in result_css
    assert "border-left: 999" not in result_css
    assert "border-right: 999" not in result_css
    assert ".result-trend-icon {" in result_css
    assert "width: 26px" in result_css
    assert "height: 26px" in result_css


def test_focus_result_renderer_uses_html_for_result_fragments_and_no_multi_controls() -> None:
    source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    body = source.split("def _focus_result_page", 1)[1].split("def _result_page", 1)[0]

    assert "st.markdown(_result_header_html(draft), unsafe_allow_html=True)" in body
    assert "st.markdown(_result_context_html(draft, result, comparison, names), unsafe_allow_html=True)" in body
    assert "st.markdown(_managerial_summary_html(comparison, len(changed_rows)), unsafe_allow_html=True)" in body
    assert "قواعد عمومی شعب مشمول" not in body
    assert "شعبه اصلی سناریو" not in body


def test_multi_branch_result_uses_three_distinct_tabs_and_scoped_root() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    assert 'data-multi-branch-results="true"' in source
    assert '["نمای مدیریتی", "تحلیل شعب و شاخص‌ها", "جزئیات و ممیزی"]' in source
    assert "_render_overview(table, manifest, primary_branch_code)" in source
    assert "_render_analysis(table, manifest if audit_available else ())" in source
    assert "_render_details(table, manifest if audit_available else (), audit_available=audit_available)" in source
    assert 'st.markdown("</div>"' not in source
    assert '<div data-multi-branch-results="true">' not in source


def test_multi_branch_compact_table_replaces_old_primary_concatenated_audit_columns() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    compact_body = source.split("def compact_branch_table", 1)[1].split("def result_header_html", 1)[0]
    details_body = source.split("def _render_details", 1)[1].split("def render_multi_branch_results", 1)[0]
    assert "مقدار خام فعلی" not in compact_body
    assert "مقدار خام سناریویی" not in compact_body
    assert "درصد یا مقدار اعمال‌شده" not in compact_body
    assert "build_audit_long_form" in details_body
    assert "مشاهده جزئیات فنی و ممیزی" in details_body


def test_multi_branch_result_css_is_scoped_and_does_not_modify_branch_or_target_renderers() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    builder_source = (ROOT / "pages" / "2_Scenario_Builder.py").read_text(encoding="utf-8")
    scoped_css = css_source.split('[data-multi-branch-results="true"]', 1)[1].split("/* Keep Streamlit", 1)[0]
    assert '[data-multi-branch-results="true"] .multi-kpi-grid' in css_source
    assert ".multi-results-header h1" in scoped_css
    assert ".results-workspace-header" not in scoped_css
    assert "target-rank" not in source.lower()
    assert "def _focus_result_page" in builder_source
    assert "def _target_result" in builder_source


def test_multi_branch_result_header_primary_panel_and_tabs_are_visual_contract() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    scoped_css = css_source.split('[data-multi-branch-results="true"]', 1)[1].split("/* Keep Streamlit", 1)[0]
    assert "multi-results-hero" in source
    assert "multi-results-metadata" in source
    assert "multi-primary-panel" in source
    assert "multi-primary-metric-card" in source
    assert "multi-primary-rule-card" in source
    assert "multi-movers-grid" in source
    assert "multi-distribution-grid" in source
    assert "managerial_conclusion_model" in source
    assert "جمع‌بندی مدیریتی" not in source
    assert "managerial-conclusion" not in source
    assert ".multi-branch-page [data-testid=\"stTabs\"] [role=\"tablist\"]" in css_source
    assert "position: static" in css_source.split('.multi-branch-page [data-testid="stTabs"] [role="tablist"]', 1)[1].split("}", 1)[0]
    assert ".multi-results-metadata .multi-metric-item" in scoped_css
    assert '[data-multi-branch-results="true"].multi-results-hero' in css_source
    assert '[data-multi-branch-results="true"].multi-kpi-grid' in css_source
    assert '[data-multi-branch-results="true"].multi-primary-panel' in css_source
    assert '[data-multi-branch-results="true"].multi-distribution-grid' in css_source
    assert '[data-multi-branch-results="true"].multi-movers-grid' in css_source


def test_multi_branch_percentage_inputs_use_clean_scoped_placeholder() -> None:
    source = (ROOT / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    assert source.count('placeholder="تکمیل شود"') == 3
    assert "مثلاً 25" not in source
    assert "مثلاً 25 یا ۱۲٫۵" not in source
    assert "multi-compact-form" in source
    assert '.multi-branch-page .multi-compact-form [data-testid="InputInstructions"]' in css_source
    assert "\n        [data-testid=\"InputInstructions\"] { display: none" not in css_source


def test_multi_branch_builder_rows_and_primary_identity_are_compact_contract() -> None:
    source = (ROOT / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    assert "multi-rule-row navy" in source
    assert "قاعده عمومی" in source
    assert "multi-primary-identity" in source
    assert "شعبه اصلی:" in source
    assert "کد <b dir=\"ltr\"" in source
    assert ".multi-rule-list" in css_source
    assert ".multi-rule-row" in css_source
    assert ".multi-primary-identity" in css_source


def test_multi_branch_primary_indicator_uses_empty_sentinel() -> None:
    source = (ROOT / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    body = source.split("def _primary_overrides", 1)[1].split("def _build_scenario", 1)[0]
    assert "indicator_options = [None, *available]" in body
    assert '"انتخاب شاخص" if key is None' in body
    assert "index=0" in body
    assert 'key="multi_primary_indicator"' in body
    assert "available or list(INDICATOR_REGISTRY)" not in body
    assert 'raise ValueError("شاخص شعبه اصلی را انتخاب کنید.")' in body
    assert "overrides[indicator]" in body


def test_multi_branch_forms_use_stable_keys_and_do_not_clear_on_failed_submit() -> None:
    source = (ROOT / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    for key in (
        "multi_general_indicator",
        "multi_general_direction",
        "multi_exception_branch",
        "multi_exception_indicator",
        "multi_exception_direction",
        "multi_primary_indicator",
        "multi_primary_mode",
        "multi_primary_direction",
    ):
        assert f'key="{key}"' in source
    assert 'clear_on_submit=True' not in source


def test_active_exception_indicator_selectbox_uses_branch_scoped_availability_function() -> None:
    source = (ROOT / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    body = source.split("def _exceptions", 1)[1].split("def _primary_overrides", 1)[0]
    before_form, form_body = body.split('with st.form("multi_exception_form"):', 1)

    assert "def get_available_exception_indicator_keys" in source
    assert "general_rules" not in source.split("def get_available_exception_indicator_keys", 1)[1].split("def _exception_indicator_options", 1)[0]
    assert 'key="multi_exception_branch"' in before_form
    assert "available_exception_indicators = get_available_exception_indicator_keys(" in before_form
    assert "list(INDICATOR_REGISTRY), exceptions, branch" in before_form
    assert "indicator_options" in form_body
    assert "columns[0].selectbox" in form_body
    assert 'key="multi_exception_indicator"' in form_body


def test_multi_branch_archive_view_recognizes_and_opens_multi_branch_records() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "MULTI_BRANCH_SCENARIO_TYPE" in source
    assert "MultiBranchWorkspaceService" in source
    assert "_group_saved_records(records)" in source
    assert "multi_branch_logical_key(item)" in source
    assert "_multi_branch_service().create_new_version" in source


def test_saved_archive_delete_requires_confirmation_and_supports_multi_branch() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    body = source.split("def render_saved_scenarios_view", 1)[1].split("def main", 1)[0]

    assert "حذف سناریو" in body
    assert "confirm_scenario_delete" in body
    assert "حذف قطعی" in body
    assert "انصراف" in body
    assert "_delete_record_group(grouped_items)" in body
    assert "_multi_branch_service().delete_scenario" in source
    assert "mode == MULTI_BRANCH_SCENARIO_TYPE" in source
    assert 'st.session_state["multi_branch_workspace"] = loaded.workspace' in source
    assert "SCENARIO_TYPE_LABELS[ScenarioType.MULTI_BRANCH]" in source
    assert "multi_branch_definition" in source


def test_multi_branch_review_uses_cards_not_raw_dataframes() -> None:
    source = (ROOT / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    review_body = source.split("def _review(", 1)[1].split("def _persistence_error", 1)[0]
    assert "multi-review-hero" in review_body
    assert "multi-review-family-grid" in review_body
    assert "_render_review_rule_card" in review_body
    assert "_render_exception_card" in review_body
    assert "_render_primary_rule_card" in review_body
    assert "st.dataframe" not in review_body
    assert "multi-precedence" in review_body
    assert "مرحله قبل" not in review_body
    assert "مرحله بعد" not in review_body
    assert "اجرای سناریو با مدل رسمی" in review_body
    assert "جامعه رسمی" not in review_body
    assert "جامعه (کل شعب)" in review_body
    assert "_review_section_html" in review_body


def test_multi_branch_review_rule_families_use_responsive_peer_grids() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    assert ".multi-review-section.general" in css_source
    assert ".multi-review-section.exception .multi-review-card-grid" in css_source
    assert ".multi-review-section.primary .multi-review-card-grid" in css_source
    assert "repeat(3,minmax(220px,1fr))" in css_source
    assert "repeat(2,minmax(300px,1fr))" in css_source


def test_multi_branch_tab_css_has_no_sticky_or_fixed_positioning() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    tab_rules = [
        block.split("}", 1)[0]
        for block in css_source.split("[role=\"tablist\"]")[1:]
    ]
    assert tab_rules
    for rule in tab_rules:
        assert "position: sticky" not in rule
        assert "position: fixed" not in rule
        assert "z-index: 5" not in rule


def test_multi_branch_numeric_values_are_ltr_isolated_and_css_scoped() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    results_source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    page_source = (ROOT / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    scoped_css = css_source.split('[data-multi-branch-results="true"]', 1)[1].split("/* Keep Streamlit", 1)[0]
    assert 'dir="ltr"' in results_source
    assert 'dir="ltr"' in page_source
    assert "unicode-bidi: isolate" in scoped_css
    assert ".multi-primary-rule-card" in scoped_css


def test_multi_branch_results_contract_has_compact_movers_and_primary_blocks() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    scoped_css = css_source.split('[data-multi-branch-results="true"]', 1)[1].split("/* Keep Streamlit", 1)[0]
    assert "بیشترین صعود" in source
    assert "بیشترین نزول" in source
    assert "top_movers(table, improvement=True, limit=3)" in source
    assert "top_movers(table, improvement=False, limit=3)" in source
    assert "multi-primary-comparison" in source
    assert "امتیاز" in source and "رتبه" in source and "درجه" in source
    assert "شعبه اصلی در این سناریو" not in source
    assert "←" not in source.split("def _primary_panel_html", 1)[1]
    overview = source.split("def _render_overview", 1)[1].split("def _movers_panel_html", 1)[0]
    assert overview.index("multi-kpi-grid") < overview.index("_render_primary") < overview.index("_distribution_grid_html") < overview.index("multi-movers-grid")
    assert "build_impact_distribution_chart" not in overview
    assert "render_chart" not in overview
    assert "_compact_metric" in source
    assert "movement-badge" in source
    assert "multi-primary-metric-card" in source
    assert "_primary_outcome_html(row, changes, primary_branch_code)" in source
    assert "[data-multi-branch-results=\"true\"] .multi-movers-grid" in css_source
    assert "grid-template-columns: repeat(2,minmax(0,1fr))" in scoped_css


def test_multi_branch_result_terminology_and_hero_white_text() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    page_source = (ROOT / "ui" / "multi_branch_page.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    hero_css = css_source.split('[data-multi-branch-results="true"] .multi-results-hero {', 1)[1].split("}", 1)[0]
    assert "جامعه رسمی" not in source
    assert "جامعه رسمی" not in page_source
    assert "جامعه (کل شعب)" in source
    assert "جامعه (کل شعب)" in page_source
    assert "linear-gradient" in hero_css and "#17345F" in hero_css and "#65328A" in hero_css
    assert ".multi-results-hero h1" in css_source
    assert "color: #fff !important" not in css_source.split('[data-multi-branch-results="true"]', 1)[1].split("/* Keep Streamlit", 1)[0]


def test_multi_branch_hero_metadata_uses_translucent_visible_blocks() -> None:
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    scoped_css = css_source.split('[data-multi-branch-results="true"]', 1)[1].split("/* Keep Streamlit", 1)[0]
    metadata_rule = scoped_css.split(".multi-results-metadata .multi-metric-item", 1)[1].split("}", 1)[0]
    label_rule = scoped_css.split(".multi-results-hero .multi-metric-item span", 1)[1].split("}", 1)[0]
    value_rule = scoped_css.split(".multi-results-hero .multi-metric-item strong", 1)[1].split("}", 1)[0]
    assert "rgba(255,255,255,.12)" in metadata_rule
    assert "background: #fff" not in metadata_rule
    assert "rgba(255,255,255,.72)" in label_rule
    assert "color: #fff" in value_rule
    assert "[data-multi-branch-results=\"true\"]" in css_source


def test_multi_branch_active_distribution_uses_compact_html_rows() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    assert "def _distribution_grid_html" in source
    assert "multi-distribution-panel" in source
    assert "multi-distribution-row" in source
    assert "multi-distribution-bar" in source
    assert "build_impact_distribution_chart" not in source


def test_multi_branch_analysis_rank_movement_defaults_to_all_moved() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    analysis = source.split("def _render_analysis", 1)[1].split("def _render_details", 1)[0]
    assert '("all_moved", "largest_improvements", "largest_declines")' in analysis
    assert '"all_moved": "همه جابه‌جا شده"' in analysis
    assert 'key="multi_rank_movement_mode"' in analysis


def test_multi_branch_audit_tab_uses_structured_cards_filters_and_export() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    css_source = (ROOT / "ui" / "styles.py").read_text(encoding="utf-8")
    details = source.split("def _render_details", 1)[1].split("def render_multi_branch_results", 1)[0]
    assert "_audit_overview_html" in details
    assert "multi-audit-filters" in details
    assert "_branch_audit_summary_html" in details
    assert "multi-audit-warning" in details
    assert "st.download_button" in details
    assert 'with st.expander("مشاهده جزئیات فنی و ممیزی")' in details
    assert ".multi-audit-overview" in css_source
    assert ".multi-selected-branch-audit" in css_source


def test_multi_branch_executive_components_do_not_use_native_metrics_or_cross_call_roots() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    overview = source.split("def _render_overview", 1)[1].split("def _movers_panel_html", 1)[0]
    primary = source.split("def _render_primary", 1)[1].split("def _branch_detail_cards_html", 1)[0]
    assert "st.metric" not in overview
    assert "st.metric" not in primary
    assert 'data-multi-branch-results="true"' in overview
    assert 'data-multi-branch-results="true"' in primary
    assert "multi-kpi-grid" in overview
    assert "multi-primary-panel" in primary


def test_multi_branch_result_avoids_ambiguous_arrow_only_comparisons() -> None:
    source = (ROOT / "ui" / "multi_branch_results.py").read_text(encoding="utf-8")
    result_body = source.split("def _render_primary", 1)[1]
    assert "←" not in result_body
    assert "رتبه فعلی" in result_body
    assert "رتبه سناریویی" in result_body
    assert "format_rank_movement_label" in result_body
