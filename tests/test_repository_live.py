"""Живой тест структуры: проверка на настоящем дереве ядра (F-25)."""
from pathlib import Path

from repository_structure import check_repository

ROOT = Path(__file__).resolve().parent.parent


def test_repository_structure_live():
    assert check_repository(ROOT) == []
