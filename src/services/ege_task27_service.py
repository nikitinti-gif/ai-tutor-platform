"""Deterministic helpers for the 2026 open-variant KЕГЭ task 27.

This module intentionally contains no LLM logic. It parses the official text
files, performs the mathematical operations required by the task, and provides
a reference solver used by tests and by the tutor's exam-level stage.

The cluster rectangles below are reference partitions for the official open
variant only. A learner is expected to discover the groups from a plot/data;
the verifier must not rely on an LLM judgement for the canonical answer.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import dist
from pathlib import Path
import re
from typing import Sequence


OPEN_VARIANT_TASK27_DIR = Path("Доп. файлы")
OPEN_VARIANT_TASK27_A = OPEN_VARIANT_TASK27_DIR / "1_27_A.txt"
OPEN_VARIANT_TASK27_B = OPEN_VARIANT_TASK27_DIR / "1_27_B.txt"


@dataclass(frozen=True, slots=True)
class StarPoint:
    x: float
    y: float
    code: str

    @property
    def xy(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class RectangleRule:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def contains(self, point: StarPoint) -> bool:
        return self.x_min < point.x < self.x_max and self.y_min < point.y < self.y_max


A_REFERENCE_RULES: tuple[RectangleRule, ...] = (
    RectangleRule(3.0, 8.0, 5.0, 10.0),
)
B_REFERENCE_RULES: tuple[RectangleRule, ...] = (
    RectangleRule(9.0, 15.0, 22.0, 28.0),
    RectangleRule(11.0, 16.0, 34.0, 39.0),
    RectangleRule(16.0, 21.0, 34.0, 39.0),
)


def parse_star_line(line: str) -> StarPoint:
    parts = line.strip().split()
    if len(parts) != 3:
        raise ValueError("Строка задания №27 должна содержать x, y и код звезды.")
    x_text, y_text, code = parts
    try:
        x = float(x_text.replace(",", "."))
        y = float(y_text.replace(",", "."))
    except ValueError as exc:
        raise ValueError("Координаты задания №27 должны быть числами.") from exc
    if not code:
        raise ValueError("У звезды должен быть указан класс светимости или VII.")
    return StarPoint(x=x, y=y, code=code)


def load_star_points(path: str | Path) -> list[StarPoint]:
    path = Path(path)
    points: list[StarPoint] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            points.append(parse_star_line(line))
    if not points:
        raise ValueError("Файл задания №27 не содержит точек.")
    return points


def partition_by_reference_rules(
    points: Sequence[StarPoint],
    rules: Sequence[RectangleRule],
    *,
    final_else_cluster: bool = False,
    allow_unassigned: bool = False,
) -> list[list[StarPoint]]:
    """Partition points using reference rectangles for the official variant."""
    clusters: list[list[StarPoint]] = [[] for _ in rules]
    remainder: list[StarPoint] = []
    for point in points:
        matches = [index for index, rule in enumerate(rules) if rule.contains(point)]
        if len(matches) > 1:
            raise ValueError("Точка попала сразу в несколько эталонных кластеров.")
        if matches:
            clusters[matches[0]].append(point)
        else:
            remainder.append(point)
    if final_else_cluster:
        clusters.append(remainder)
    elif remainder and not allow_unassigned:
        raise ValueError(f"Не удалось отнести {len(remainder)} точек к эталонным кластерам.")
    if any(not cluster for cluster in clusters):
        raise ValueError("Обнаружен пустой кластер.")
    return clusters


def cluster_center(cluster: Sequence[StarPoint]) -> StarPoint:
    """Return the task-defined center: an existing point with min distance sum."""
    if not cluster:
        raise ValueError("Нельзя найти центр пустого кластера.")
    return min(
        cluster,
        key=lambda point: sum(dist(point.xy, other.xy) for other in cluster),
    )


def nearest_point(origin: StarPoint, candidates: Sequence[StarPoint]) -> StarPoint:
    if not candidates:
        raise ValueError("Нет точек, удовлетворяющих условию отбора.")
    return min(candidates, key=lambda point: dist(origin.xy, point.xy))


def maximum_pair_distance(points: Sequence[StarPoint]) -> float:
    if len(points) < 2:
        raise ValueError("Для расстояния между двумя объектами нужны минимум две точки.")
    maximum = 0.0
    for index, point in enumerate(points):
        for other in points[index + 1 :]:
            maximum = max(maximum, dist(point.xy, other.xy))
    return maximum


def _star_type(point: StarPoint) -> tuple[str, str] | None:
    """Return spectral letter and exact luminosity class.

    Codes look like ``G7V`` or ``M4III``. Exact parsing matters: a naive
    ``endswith('V')`` would incorrectly classify luminosity ``IV`` and ``VI``
    as class V and changes the official B2 answer.
    """
    match = re.fullmatch(r"([OBAFGKM])\d(III|II|IV|VI|V|I)", point.code)
    if not match:
        return None
    return match.group(1), match.group(2)


def is_red_giant(point: StarPoint) -> bool:
    return _star_type(point) == ("M", "III")


def is_orange_giant(point: StarPoint) -> bool:
    return _star_type(point) == ("K", "III")


def is_yellow_dwarf(point: StarPoint) -> bool:
    return _star_type(point) == ("G", "V")


def _scaled_abs(value: float) -> int:
    return int(abs(value) * 10_000)


def _scaled(value: float) -> int:
    return int(value * 10_000)


def solve_open_variant_a(path: str | Path = OPEN_VARIANT_TASK27_A) -> dict[str, object]:
    points = load_star_points(path)
    clusters = partition_by_reference_rules(points, A_REFERENCE_RULES, final_else_cluster=True)
    centers = [cluster_center(cluster) for cluster in clusters]
    smallest_index = min(range(len(clusters)), key=lambda index: len(clusters[index]))
    smallest = clusters[smallest_index]
    center = centers[smallest_index]
    red_giants = [point for point in smallest if is_red_giant(point)]
    target = nearest_point(center, red_giants)
    answer = (_scaled_abs(target.x), _scaled_abs(target.y))
    return {
        "point_count": len(points),
        "assigned_point_count": sum(map(len, clusters)),
        "unassigned_point_count": len(points) - sum(map(len, clusters)),
        "cluster_sizes": tuple(len(cluster) for cluster in clusters),
        "centers": tuple(centers),
        "smallest_cluster_index": smallest_index,
        "nearest_red_giant": target,
        "answer": answer,
    }


def solve_open_variant_b(path: str | Path = OPEN_VARIANT_TASK27_B) -> dict[str, object]:
    points = load_star_points(path)
    clusters = partition_by_reference_rules(
        points,
        B_REFERENCE_RULES,
        allow_unassigned=True,
    )
    assigned = sum(map(len, clusters))
    centers = [cluster_center(cluster) for cluster in clusters]
    orange_counts = [sum(is_orange_giant(point) for point in cluster) for cluster in clusters]
    min_index = min(range(len(clusters)), key=lambda index: orange_counts[index])
    max_index = max(range(len(clusters)), key=lambda index: orange_counts[index])
    b1 = dist(centers[min_index].xy, centers[max_index].xy)

    yellow_dwarf_groups = [
        [point for point in cluster if is_yellow_dwarf(point)]
        for cluster in clusters
    ]
    b2 = max(maximum_pair_distance(group) for group in yellow_dwarf_groups)
    answer = (_scaled(b1), _scaled(b2))
    return {
        "point_count": len(points),
        "assigned_point_count": assigned,
        "unassigned_point_count": len(points) - assigned,
        "cluster_sizes": tuple(len(cluster) for cluster in clusters),
        "centers": tuple(centers),
        "orange_giant_counts": tuple(orange_counts),
        "yellow_dwarf_counts": tuple(len(group) for group in yellow_dwarf_groups),
        "answer": answer,
    }


def solve_open_variant_task27(
    path_a: str | Path = OPEN_VARIANT_TASK27_A,
    path_b: str | Path = OPEN_VARIANT_TASK27_B,
) -> tuple[tuple[int, int], tuple[int, int]]:
    return solve_open_variant_a(path_a)["answer"], solve_open_variant_b(path_b)["answer"]


def normalize_two_number_answer(answer: str) -> tuple[int, int] | None:
    parts = answer.replace(";", " ").replace(",", " ").split()
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None
