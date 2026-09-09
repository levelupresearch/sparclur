"""Tests for YAML configuration loading and updates."""

from pathlib import Path

import pytest

import sparclur.utils._config as config


def _write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def config_locations(monkeypatch, tmp_path):
    locations = {
        "environment": tmp_path / "environment.yaml",
        "project": tmp_path / "project.yaml",
        "legacy": tmp_path / "legacy.yaml",
        "user": tmp_path / "user" / "sparclur.yaml",
    }
    monkeypatch.setattr(config, "_ENV_CONFIG", locations["environment"])
    monkeypatch.setattr(config, "_PROJECT_CONFIG", locations["project"])
    monkeypatch.setattr(config, "_LEGACY_USER_CONFIG", locations["legacy"])
    monkeypatch.setattr(config, "get_config_path", lambda: locations["user"])
    return locations


def test_configuration_layers_merge_in_precedence_order(config_locations):
    _write_yaml(config_locations["environment"], "Parser:\n  timeout: 60\n  dpi: 72\n")
    _write_yaml(config_locations["project"], "PDFium:\n  dpi: 144\n")
    _write_yaml(config_locations["legacy"], "Parser:\n  cache_renders: true\n")
    _write_yaml(config_locations["user"], "Parser:\n  timeout: 120\n")

    assert config.get_config() == {
        "Parser": {"timeout": 120, "dpi": 72, "cache_renders": True},
        "PDFium": {"dpi": 144},
    }


def test_update_config_writes_only_the_user_configuration(config_locations):
    _write_yaml(config_locations["project"], "Parser:\n  timeout: 30\n")

    written_path = config.update_config({"Parser": {"dpi": 144}})

    assert written_path == config_locations["user"]
    assert config_locations["project"].read_text(encoding="utf-8") == "Parser:\n  timeout: 30\n"
    assert config.get_config() == {"Parser": {"timeout": 30, "dpi": 144}}


def test_invalid_configuration_has_a_clear_error(config_locations):
    _write_yaml(config_locations["environment"], "Parser: [\n")

    with pytest.raises(config.ConfigurationError, match="Invalid SPARCLUR configuration"):
        config.get_config()
