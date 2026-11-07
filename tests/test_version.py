# tests/test_version.py
import re

from src.version import __version__


def test_version_is_semver():
    """版本号为语义化版本 MAJOR.MINOR.PATCH。"""
    assert re.fullmatch(r'\d+\.\d+\.\d+', __version__)
