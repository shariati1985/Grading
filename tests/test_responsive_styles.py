"""Static safeguards for the responsive application shell."""

from pathlib import Path


def test_navigation_releases_main_content_below_desktop_breakpoint() -> None:
    css_source = (
        Path(__file__).resolve().parents[1].joinpath("ui", "styles.py").read_text(encoding="utf-8")
    )
    assert "@media (max-width: 1100px)" in css_source
    responsive = css_source.split("@media (max-width: 1100px)", 1)[1]
    assert "margin-right: 0 !important" in responsive
    assert "width: 100% !important" in responsive
    assert "position: relative !important" in responsive
