"""Regression tests for the Makefile's upstream and fork version commands."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("version", "target", "expected"),
    [
        ("2.6.2", "version-patch", "2.6.3"),
        ("2.6.2", "version-minor", "2.7.0"),
        ("2.6.2", "version-major", "3.0.0"),
        ("2.6.2.1", "version-patch", "2.6.2.2"),
        ("2.6.2.9", "version-patch", "2.6.2.10"),
        ("2.6.2.12", "version-patch", "2.6.2.13"),
        ("2.6.2.1", "version-minor", None),
        ("2.6.2.1", "version-major", None),
    ],
)
def test_version_bump(
    tmp_path: Path, version: str, target: str, expected: str | None
) -> None:
    shutil.copyfile(ROOT / "Makefile", tmp_path / "Makefile")
    manifest = tmp_path / "custom_components" / "melcloudhome" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    original = {"domain": "melcloudhome", "version": version}
    manifest.write_text(json.dumps(original), encoding="utf-8")
    changelog = tmp_path / "CHANGELOG.md"
    original_changelog = "# Changelog\n" + "\n" * 6 + f"## [{version}]\n"
    changelog.write_text(original_changelog, encoding="utf-8")

    make = shutil.which("make")
    assert make is not None
    result = subprocess.run(  # noqa: S603 - fixed test targets in an isolated fixture
        [make, target], cwd=tmp_path, capture_output=True, text=True, check=False
    )

    if expected is None:
        assert result.returncode != 0
        assert "merge the upstream release" in result.stdout
        assert json.loads(manifest.read_text(encoding="utf-8")) == original
        assert changelog.read_text(encoding="utf-8") == original_changelog
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads(manifest.read_text(encoding="utf-8")) == {
            **original,
            "version": expected,
        }
        assert f"## [{expected}] - " in changelog.read_text(encoding="utf-8")
