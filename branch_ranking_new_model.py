"""Command-line entry point for branch ranking Excel and Power BI outputs."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Final

import numpy as np
import pandas as pd

from data.excel_repository import ExcelBranchRepository
from engine.ranking_engine import (
    BRANCH_ID,
    BRANCH_NAME,
    REGION,
    GRADE_ORDER,
    GRADE_PERCENTAGES,
    INDICATOR_KEYS,
    INDICATOR_TYPES,
    ModelOutputs,
    WEIGHTS,
    run_ranking_model,
)

BASE_DIR: Final[Path] = Path(__file__).resolve().parent
INPUT_FILE: Final[Path] = BASE_DIR / "Data.xlsx"
OUTPUT_FILE: Final[Path] = BASE_DIR / "Branch_Ranking_New_Model.xlsx"
POWERBI_OUTPUT_DIR: Final[Path] = BASE_DIR / "PowerBI_Output"
PERIOD: Final[str] = "1404-04"

INDICATOR_NAMES: Final[dict[str, str]] = {
    "avg_deposits": "Average Deposits",
    "deposit_count": "Deposit Count",
    "avg_loans": "Average Loans",
    "loan_count": "Loan Count",
    "avg_commitments": "Average Commitments",
    "commitment_count": "Commitment Count",
    "transaction_volume": "Transaction Volume",
    "profit_loss": "Profit / Loss",
}
GRADE_KEYS: Final[dict[str, str]] = {
    "Excellent": "EXCELLENT",
    "Grade 1": "GRADE_1",
    "Grade 2": "GRADE_2",
    "Grade 3": "GRADE_3",
}


def create_weights_sheet() -> pd.DataFrame:
    """Create the legacy workbook weights sheet."""
    return pd.DataFrame(
        {
            "indicator": INDICATOR_KEYS,
            "weight": [WEIGHTS[key] for key in INDICATOR_KEYS],
            "indicator_type": [INDICATOR_TYPES[key] for key in INDICATOR_KEYS],
        }
    )


def write_outputs(outputs: ModelOutputs, output_file: Path) -> None:
    """Write the unchanged legacy workbook sheet layout."""
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        outputs.final_result.to_excel(writer, sheet_name="Final_Result", index=False)
        outputs.weighted_matrix.to_excel(writer, sheet_name="Weighted_Matrix", index=False)
        outputs.normalized_scores.to_excel(writer, sheet_name="Normalized_Scores", index=False)
        outputs.log_values.to_excel(writer, sheet_name="Log_Values", index=False)
        create_weights_sheet().to_excel(writer, sheet_name="Weights", index=False)
        outputs.grade_distribution.to_excel(writer, sheet_name="Grade_Distribution", index=False)


def generate_powerbi_outputs(outputs: ModelOutputs, output_folder: Path) -> None:
    """Write the same six Power BI-ready CSV tables as the original script."""
    output_folder.mkdir(parents=True, exist_ok=True)
    branch_dim = outputs.final_result.loc[:, [BRANCH_ID, BRANCH_NAME, REGION]].copy()

    ranking = outputs.final_result.copy()
    ranking["period"] = PERIOD
    ranking["excellent_group"] = np.select(
        [ranking["grade"].eq("Excellent Plus"), ranking["grade"].eq("Excellent")],
        ["Excellent Plus", "Excellent"],
        default="",
    )
    ranking["grade"] = ranking["grade"].replace({"Excellent Plus": "Excellent"})
    ranking = ranking.loc[
        :, ["period", BRANCH_ID, "final_score", "rank", "grade", "excellent_group"]
    ]

    indicators = outputs.indicator_results.copy()
    indicators["period"] = PERIOD
    indicators = indicators.loc[
        :,
        [
            "period",
            BRANCH_ID,
            "indicator_key",
            "raw_value",
            "log_value",
            "score",
            "weighted_score",
            "indicator_rank",
        ],
    ]

    dim_indicator = pd.DataFrame(
        [
            {
                "indicator_key": key,
                "indicator_name": INDICATOR_NAMES[key],
                "weight": WEIGHTS[key],
                "indicator_type": INDICATOR_TYPES[key],
                "indicator_order": order,
            }
            for order, key in enumerate(INDICATOR_KEYS, start=1)
        ]
    )
    dim_grade = pd.DataFrame(
        [
            {
                "grade_key": GRADE_KEYS[grade],
                "grade_label": grade,
                "grade_order": order,
                "target_percentage": GRADE_PERCENTAGES[grade],
            }
            for order, grade in enumerate(GRADE_ORDER, start=1)
        ]
    )
    match = re.fullmatch(r"(\d{4})-(\d{2})", PERIOD)
    if match is None:
        raise ValueError(f"PERIOD must use YYYY-MM format: {PERIOD}")
    year, month = match.groups()
    dim_period = pd.DataFrame(
        [{"period": PERIOD, "year": int(year), "month": int(month), "period_label": f"{year}/{month}"}]
    )
    outputs_by_name = {
        "Fact_Branch_Ranking.csv": ranking,
        "Fact_Indicator_Scores.csv": indicators,
        "Dim_Branch.csv": branch_dim,
        "Dim_Indicator.csv": dim_indicator,
        "Dim_Grade.csv": dim_grade,
        "Dim_Period.csv": dim_period,
    }
    for name, dataframe in outputs_by_name.items():
        dataframe.to_csv(output_folder / name, index=False, encoding="utf-8-sig")


def run() -> None:
    """Read Data.xlsx, run the engine, and generate all production outputs."""
    print("Starting branch ranking model...")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file was not found: {INPUT_FILE}")
    input_df = ExcelBranchRepository(INPUT_FILE).load_branch_data(PERIOD)
    outputs = run_ranking_model(input_df)
    generate_powerbi_outputs(outputs, POWERBI_OUTPUT_DIR)
    write_outputs(outputs, OUTPUT_FILE)
    print(f"Generated output workbook: {OUTPUT_FILE}")
    print(f"Generated Power BI CSV outputs: {POWERBI_OUTPUT_DIR}")
    print(f"Ranked branches: {len(outputs.final_result):,}")


if __name__ == "__main__":
    run()
