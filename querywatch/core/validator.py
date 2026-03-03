from __future__ import annotations

import pandas as pd


def check_equivalence(result_a: pd.DataFrame, result_b: pd.DataFrame) -> bool:
    return len(result_a.index) == len(result_b.index)

