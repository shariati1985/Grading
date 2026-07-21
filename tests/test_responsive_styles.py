"""Static safeguards for the responsive application shell."""

from pathlib import Path


def test_sidebar_uses_streamlit_reserved_layout_space_without_fixed_overlap() -> None:
    css_source = (
        Path(__file__).resolve().parents[1].joinpath("ui", "styles.py").read_text(encoding="utf-8")
    )
    sidebar = css_source.split('[data-testid="stSidebar"] {', 1)[1].split("}", 1)[0]
    assert "position: fixed" not in sidebar
    assert "right: 0" not in sidebar
    assert "margin-right: var(--nav-width)" not in css_source


def test_scenario_card_grid_has_three_two_and_one_column_layouts() -> None:
    css_source = Path(__file__).resolve().parents[1].joinpath("ui", "styles.py").read_text(encoding="utf-8")
    assert "grid-template-columns: repeat(3" in css_source
    assert "@container (max-width: 1080px)" in css_source
    assert "grid-template-columns: repeat(2" in css_source
    assert "@container (max-width: 620px)" in css_source
    assert "grid-template-columns: minmax(0, 1fr)" in css_source


def test_large_numeric_result_values_are_isolated_and_never_split() -> None:
    css_source = Path(__file__).resolve().parents[1].joinpath("ui", "styles.py").read_text(encoding="utf-8")
    assert ".value-comparison-card" in css_source
    assert ".indicator-result-grid" in css_source
    numeric_rule = css_source.split(".numeric-ltr {", 1)[1].split("}", 1)[0]
    assert "unicode-bidi: isolate" in numeric_rule
    assert "white-space: nowrap" in numeric_rule
    assert "word-break: keep-all" in numeric_rule
