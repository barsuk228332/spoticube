"""Тесты форматирования: длительность, просмотры, размеры, скорость, ETA."""

from __future__ import annotations

import pytest

from spoticube import util


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "—"),
        (0, "прямой эфир"),
        (1, "0:01"),
        (59, "0:59"),
        (60, "1:00"),
        (125, "2:05"),
        (125.9, "2:05"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        (36000, "10:00:00"),
    ],
)
def test_format_duration(value, expected):
    assert util.format_duration(value) == expected


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (1, "просмотр"),
        (2, "просмотра"),
        (4, "просмотра"),
        (5, "просмотров"),
        (11, "просмотров"),
        (14, "просмотров"),
        (21, "просмотр"),
        (22, "просмотра"),
        (25, "просмотров"),
        (111, "просмотров"),
        (1001, "просмотр"),
    ],
)
def test_plural(number, expected):
    assert util._plural(number, "просмотр", "просмотра", "просмотров") == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (None, ""),
        (0, ""),
        (1, "1 просмотр"),
        (2, "2 просмотра"),
        (999, "999 просмотров"),
        (1000, "1 тыс. просмотров"),
        (1500, "1,5 тыс. просмотров"),
        (2_000_000, "2 млн просмотров"),
        (3_000_000_000, "3 млрд просмотров"),
    ],
)
def test_format_views(count, expected):
    assert util.format_views(count) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (None, "0 Б"),
        (0, "0 Б"),
        (512, "512 Б"),
        (1024, "1.0 КБ"),
        (1536, "1.5 КБ"),
        (1024**2, "1.0 МБ"),
        (1024**3, "1.0 ГБ"),
    ],
)
def test_format_bytes(size, expected):
    assert util.format_bytes(size) == expected


def test_format_speed():
    assert util.format_speed(None) == ""
    assert util.format_speed(0) == ""
    assert util.format_speed(1024) == "1.0 КБ/с"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (None, ""),
        (0, "0 с"),
        (59, "59 с"),
        (60, "1 мин 0 с"),
        (90, "1 мин 30 с"),
        (3599, "59 мин 59 с"),
        (3600, "1 ч 0 мин"),
        (3700, "1 ч 1 мин"),
    ],
)
def test_format_eta(seconds, expected):
    assert util.format_eta(seconds) == expected
