from __future__ import annotations

import pandas as pd

ROW_COUNT_COLUMN = "__row_count__"


def check_equivalence(result_a: pd.DataFrame, result_b: pd.DataFrame) -> bool:
    if _is_row_count_frame(result_a) and _is_row_count_frame(result_b):
        return int(result_a[ROW_COUNT_COLUMN].iloc[0]) == int(result_b[ROW_COUNT_COLUMN].iloc[0])
    return len(result_a.index) == len(result_b.index)


def _is_row_count_frame(result: pd.DataFrame) -> bool:
    return (
        ROW_COUNT_COLUMN in result.columns
        and len(result.index) == 1
        and pd.notna(result[ROW_COUNT_COLUMN].iloc[0])
    )
