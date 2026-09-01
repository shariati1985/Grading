"""Pure dataframe implementation of the official branch-ranking model.

This module deliberately performs no file I/O.  Its constants and calculations
mirror the original production script so unchanged input produces unchanged
scores, ranks, and grades.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from data.contracts import CANONICAL_COLUMNS
from data.excel_repository import normalize_text

BRANCH_ID: Final[str] = "branch_id"
BRANCH_NAME: Final[str] = "branch_name"
REGION: Final[str] = "region"
IDENTITY_COLUMNS: Final[tuple[str, ...]] = (BRANCH_ID, BRANCH_NAME, REGION)
BENEFIT: Final[str] = "benefit"
COST: Final[str] = "cost"

WEIGHTS: Final[dict[str, float]] = {
    "avg_deposits": 0.500,
    "deposit_count": 0.005,
    "avg_loans": 0.260,
    "loan_count": 0.010,
    "avg_commitments": 0.170,
    "commitment_count": 0.010,
    "transaction_volume": 0.015,
    "profit_loss": 0.030,
}
INDICATOR_KEYS: Final[tuple[str, ...]] = tuple(WEIGHTS)
INDICATOR_TYPES: Final[dict[str, str]] = {key: BENEFIT for key in INDICATOR_KEYS}

GRADE_PERCENTAGES: Final[dict[str, float]] = {
    "Excellent": 0.08,
    "Grade 1": 0.27,
    "Grade 2": 0.30,
    "Grade 3": 0.35,
}
GRADE_ORDER: Final[tuple[str, ...]] = ("Excellent", "Grade 1", "Grade 2", "Grade 3")
EXCELLENT_PLUS_COUNT: Final[int] = 3


@dataclass(frozen=True)
class ModelOutputs:
    """Final result and every model intermediate needed for analysis."""

    final_result: pd.DataFrame
    raw_data: pd.DataFrame
    shifted_values: pd.DataFrame
    log_values: pd.DataFrame
    normalized_scores: pd.DataFrame
    weighted_matrix: pd.DataFrame
    indicator_results: pd.DataFrame
    grade_distribution: pd.DataFrame


def normalize_columns(input_df: pd.DataFrame) -> pd.DataFrame:
    """Validate that an engine input uses the canonical repository schema."""
    if not isinstance(input_df, pd.DataFrame):
        raise TypeError("input_df must be a pandas DataFrame")

    normalized = input_df.copy(deep=True)
    missing = [column for column in CANONICAL_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing canonical columns: {', '.join(missing)}")
    return normalized


def prepare_input_data(input_df: pd.DataFrame) -> pd.DataFrame:
    """Return clean, canonical, numeric branch data ready for calculations."""
    normalized = normalize_columns(input_df)
    selected = normalized.loc[:, CANONICAL_COLUMNS].copy().reset_index(drop=True)
    selected[BRANCH_ID] = selected[BRANCH_ID].map(normalize_text).astype(object)
    selected[BRANCH_NAME] = selected[BRANCH_NAME].map(normalize_text)
    selected[REGION] = selected[REGION].map(normalize_text)
    if selected[BRANCH_ID].eq("").any():
        raise ValueError("Blank branch_id values are not allowed")
    duplicates = selected.loc[
        selected[BRANCH_ID].duplicated(keep=False), BRANCH_ID
    ].unique()
    if len(duplicates):
        raise ValueError("Duplicate branch_id values: " + ", ".join(map(str, duplicates)))
    if selected[BRANCH_NAME].eq("").any():
        raise ValueError("Blank branch_name values are not allowed")

    for column in INDICATOR_KEYS:
        numeric = pd.to_numeric(selected[column], errors="coerce")
        selected[column] = numeric.fillna(0.0).astype(float)
    return selected


def _create_shifted_values(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Shift every indicator to a strictly positive pre-log value."""
    result = raw_data[list(IDENTITY_COLUMNS)].copy()
    for column in INDICATOR_KEYS:
        series = raw_data[column].astype(float)
        minimum = float(series.min())
        shift = abs(minimum) + 1.0 if minimum < 0 else 1.0
        result[column] = series + shift
    return result


def _apply_log_transform(raw_data: pd.DataFrame) -> pd.DataFrame:
    result = raw_data[list(IDENTITY_COLUMNS)].copy()
    shifted_values = _create_shifted_values(raw_data)
    for column in INDICATOR_KEYS:
        result[column] = np.log(shifted_values[column])
    return result


def _normalize_indicators(log_values: pd.DataFrame) -> pd.DataFrame:
    result = log_values[list(IDENTITY_COLUMNS)].copy()
    for column, indicator_type in INDICATOR_TYPES.items():
        series = log_values[column].astype(float)
        minimum, maximum = float(series.min()), float(series.max())
        if np.isclose(maximum, minimum):
            result[column] = 1.0
        elif indicator_type == BENEFIT:
            result[column] = ((series - minimum) / (maximum - minimum)) * 999.0 + 1.0
        elif indicator_type == COST:
            result[column] = ((maximum - series) / (maximum - minimum)) * 999.0 + 1.0
        else:
            raise ValueError(f"Unsupported indicator type for {column}: {indicator_type}")
    return result


def _create_weighted_matrix(normalized_scores: pd.DataFrame) -> pd.DataFrame:
    result = normalized_scores[list(IDENTITY_COLUMNS)].copy()
    for column, weight in WEIGHTS.items():
        result[column] = normalized_scores[column] * weight
    return result


def _largest_remainder_counts(total_count: int) -> dict[str, int]:
    exact = {grade: total_count * percentage for grade, percentage in GRADE_PERCENTAGES.items()}
    counts = {grade: int(np.floor(value)) for grade, value in exact.items()}
    remaining = total_count - sum(counts.values())
    remainders = sorted(
        ((grade, exact[grade] - counts[grade]) for grade in GRADE_ORDER),
        key=lambda item: (-item[1], GRADE_ORDER.index(item[0])),
    )
    for grade, _ in remainders[:remaining]:
        counts[grade] += 1

    minimum_excellent = min(EXCELLENT_PLUS_COUNT, total_count)
    if counts["Excellent"] < minimum_excellent:
        needed = minimum_excellent - counts["Excellent"]
        counts["Excellent"] += needed
        for grade in reversed(GRADE_ORDER[1:]):
            removable = min(needed, counts[grade])
            counts[grade] -= removable
            needed -= removable
            if needed == 0:
                break
    if sum(counts.values()) != total_count:
        raise RuntimeError("Grade count assignment failed to match total branch count")
    return counts


def _calculate_final_result(weighted_matrix: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    final = weighted_matrix[list(IDENTITY_COLUMNS)].copy()
    final["final_score"] = weighted_matrix[list(INDICATOR_KEYS)].sum(axis=1).round(1)
    final["final_score"] = final["final_score"].clip(lower=1.0, upper=1000.0)
    final = final.sort_values(
        ["final_score", BRANCH_NAME], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    final["rank"] = np.arange(1, len(final) + 1)

    counts = _largest_remainder_counts(len(final))
    grades: list[str] = []
    for grade in GRADE_ORDER:
        grades.extend([grade] * counts[grade])
    final["grade"] = grades
    plus_indices = final.index[final["grade"].eq("Excellent")].tolist()[:EXCELLENT_PLUS_COUNT]
    final.loc[plus_indices, "grade"] = "Excellent Plus"
    final = final.loc[:, [*IDENTITY_COLUMNS, "final_score", "rank", "grade"]]

    rows: list[dict[str, object]] = []
    for grade in ("Excellent Plus", "Excellent", "Grade 1", "Grade 2", "Grade 3"):
        model_group = "Excellent" if grade == "Excellent Plus" else grade
        assigned = int(final["grade"].eq(grade).sum())
        rows.append(
            {
                "grade": grade,
                "model_group": model_group,
                "assigned_count": assigned,
                "assigned_percentage": round(assigned / len(final), 6) if len(final) else 0.0,
                "target_count": counts[model_group],
                "target_percentage": GRADE_PERCENTAGES[model_group],
            }
        )
    return final, pd.DataFrame(rows)


def _create_indicator_results(
    raw_data: pd.DataFrame,
    shifted_values: pd.DataFrame,
    log_values: pd.DataFrame,
    normalized_scores: pd.DataFrame,
    weighted_matrix: pd.DataFrame,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for indicator_key in INDICATOR_KEYS:
        frame = pd.DataFrame(
            {
                BRANCH_ID: raw_data[BRANCH_ID],
                BRANCH_NAME: raw_data[BRANCH_NAME],
                REGION: raw_data[REGION],
                "indicator_key": indicator_key,
                "raw_value": raw_data[indicator_key],
                "shifted_value": shifted_values[indicator_key],
                "log_value": log_values[indicator_key],
                "score": normalized_scores[indicator_key],
                "weighted_score": weighted_matrix[indicator_key],
            }
        )
        ordered_index = frame.sort_values(
            ["score", BRANCH_NAME], ascending=[False, True], kind="mergesort"
        ).index
        ranks = pd.Series(np.arange(1, len(frame) + 1), index=ordered_index)
        frame["indicator_rank"] = ranks.reindex(frame.index).astype(int)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def run_ranking_model(input_df: pd.DataFrame) -> ModelOutputs:
    """Run the official model against an input dataframe without file I/O."""
    if not np.isclose(sum(WEIGHTS.values()), 1.0):
        raise ValueError(f"Model weights must sum to 1; got {sum(WEIGHTS.values()):.6f}")
    raw_data = prepare_input_data(input_df)
    shifted_values = _create_shifted_values(raw_data)
    log_values = _apply_log_transform(raw_data)
    normalized_scores = _normalize_indicators(log_values)
    weighted_matrix = _create_weighted_matrix(normalized_scores)
    final_result, grade_distribution = _calculate_final_result(weighted_matrix)
    indicator_results = _create_indicator_results(
        raw_data, shifted_values, log_values, normalized_scores, weighted_matrix
    )
    return ModelOutputs(
        final_result=final_result,
        raw_data=raw_data,
        shifted_values=shifted_values,
        log_values=log_values,
        normalized_scores=normalized_scores,
        weighted_matrix=weighted_matrix,
        indicator_results=indicator_results,
        grade_distribution=grade_distribution,
    )
