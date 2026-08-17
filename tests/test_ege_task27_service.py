from pathlib import Path

from src.services.ege_task27_service import (
    OPEN_VARIANT_TASK27_A,
    OPEN_VARIANT_TASK27_B,
    StarPoint,
    cluster_center,
    is_orange_giant,
    is_red_giant,
    is_yellow_dwarf,
    normalize_two_number_answer,
    parse_star_line,
    solve_open_variant_a,
    solve_open_variant_b,
    solve_open_variant_task27,
)


def test_parse_star_line_supports_comma_decimal_separator():
    point = parse_star_line("5,384507 8,788353 F6II")
    assert point == StarPoint(5.384507, 8.788353, "F6II")


def test_star_classes_are_read_by_spectral_letter_and_luminosity():
    assert is_red_giant(StarPoint(0, 0, "M4III"))
    assert is_orange_giant(StarPoint(0, 0, "K2III"))
    assert is_yellow_dwarf(StarPoint(0, 0, "G7V"))
    assert not is_yellow_dwarf(StarPoint(0, 0, "G7VI"))
    assert not is_red_giant(StarPoint(0, 0, "VII"))


def test_center_is_existing_point_with_minimum_distance_sum():
    points = [
        StarPoint(0, 0, "G0V"),
        StarPoint(0, 2, "G0V"),
        StarPoint(0, 4, "G0V"),
    ]
    assert cluster_center(points) == points[1]


def test_open_variant_file_a_matches_official_reference_answer():
    result = solve_open_variant_a()
    assert Path(OPEN_VARIANT_TASK27_A).exists()
    assert result["point_count"] == 235
    assert result["cluster_sizes"] == (114, 121)
    assert result["centers"][0].xy == (4.960398, 7.34545)
    assert result["nearest_red_giant"].xy == (4.469472, 6.975433)
    assert result["answer"] == (44694, 69754)


def test_open_variant_file_b_matches_official_reference_answer():
    result = solve_open_variant_b()
    assert Path(OPEN_VARIANT_TASK27_B).exists()
    assert result["point_count"] == 1850
    assert result["cluster_sizes"] == (1170, 393, 287)
    assert tuple(center.xy for center in result["centers"]) == (
        (11.746691, 24.957689),
        (13.223572, 36.619979),
        (18.794456, 36.905542),
    )
    assert result["orange_giant_counts"] == (87, 28, 25)
    assert result["answer"] == (138716, 34029)


def test_full_open_variant_task27_matches_two_official_answer_rows():
    assert solve_open_variant_task27() == ((44694, 69754), (138716, 34029))


def test_exam_level_answer_normalizer_accepts_common_separators():
    assert normalize_two_number_answer("44694 69754") == (44694, 69754)
    assert normalize_two_number_answer("44694; 69754") == (44694, 69754)
    assert normalize_two_number_answer("44694,69754") == (44694, 69754)
    assert normalize_two_number_answer("44694") is None
