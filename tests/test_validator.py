import pandas as pd

from querywatch.core.validator import check_equivalence


def test_check_equivalence_true_when_row_counts_match() -> None:
    result_a = pd.DataFrame({"x": [1, 2, 3]})
    result_b = pd.DataFrame({"y": ["a", "b", "c"]})

    assert check_equivalence(result_a, result_b) is True


def test_check_equivalence_false_when_row_counts_differ() -> None:
    result_a = pd.DataFrame({"x": [1, 2, 3]})
    result_b = pd.DataFrame({"y": ["a"]})

    assert check_equivalence(result_a, result_b) is False


def test_check_equivalence_true_for_two_empty_results() -> None:
    result_a = pd.DataFrame(columns=["x"])
    result_b = pd.DataFrame(columns=["y"])

    assert check_equivalence(result_a, result_b) is True


def test_check_equivalence_supports_count_frames() -> None:
    result_a = pd.DataFrame({"__row_count__": [100]})
    result_b = pd.DataFrame({"__row_count__": [100]})

    assert check_equivalence(result_a, result_b) is True


def test_check_equivalence_count_frames_detect_mismatch() -> None:
    result_a = pd.DataFrame({"__row_count__": [100]})
    result_b = pd.DataFrame({"__row_count__": [99]})

    assert check_equivalence(result_a, result_b) is False
