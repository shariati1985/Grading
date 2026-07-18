"""Ensure every direct Streamlit Plotly render has explicit identity."""

from __future__ import annotations

import ast
from pathlib import Path


def test_every_streamlit_plotly_chart_has_an_explicit_key() -> None:
    root = Path(__file__).resolve().parents[1]
    missing: list[str] = []
    for path in [*root.joinpath("pages").glob("*.py"), *root.joinpath("ui").glob("*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == "plotly_chart" and not any(
                keyword.arg == "key" for keyword in node.keywords
            ):
                missing.append(f"{path.name}:{node.lineno}")
    assert missing == []
