"""Contract tests for Power BI export tables."""

from pathlib import Path

import pandas as pd

from branch_ranking_new_model import generate_powerbi_outputs
from engine.ranking_engine import run_ranking_model


def test_powerbi_branch_and_fact_schemas(input_df: pd.DataFrame, tmp_path: Path) -> None:
    generate_powerbi_outputs(run_ranking_model(input_df), tmp_path)
    dim = pd.read_csv(tmp_path / "Dim_Branch.csv", dtype={"branch_id": str})
    ranking = pd.read_csv(tmp_path / "Fact_Branch_Ranking.csv")
    indicators = pd.read_csv(tmp_path / "Fact_Indicator_Scores.csv")
    assert list(dim.columns) == ["branch_id", "branch_name", "region"]
    assert list(ranking.columns) == [
        "period", "branch_id", "final_score", "rank", "grade", "excellent_group"
    ]
    assert list(indicators.columns) == [
        "period", "branch_id", "indicator_key", "raw_value", "log_value", "score",
        "weighted_score", "indicator_rank",
    ]
