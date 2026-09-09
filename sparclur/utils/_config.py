"""YAML configuration discovery, loading, and user-scoped updates."""

import os
import site
import sys
from collections.abc import Mapping
from pathlib import Path

import yaml
from platformdirs import user_config_path


_SOURCE_ROOT = Path(__file__).resolve().parents[2]
_ENV_CONFIG = Path(sys.prefix) / "etc" / "sparclur" / "sparclur.yaml"
_PROJECT_CONFIG = _SOURCE_ROOT / "sparclur.yaml"
_LEGACY_USER_CONFIG = Path(site.USER_BASE) / "etc" / "sparclur" / "sparclur.yaml"
_CONFIG_ENV_VAR = "SPARCLUR_CONFIG"


class ConfigurationError(ValueError):
    """Raised when a SPARCLUR configuration file cannot be interpreted."""


def get_config_path() -> Path:
    """Return the user-editable configuration file path.

    ``SPARCLUR_CONFIG`` selects an explicit configuration file. Otherwise, the
    platform's standard per-user configuration directory is used.
    """
    configured_path = os.environ.get(_CONFIG_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser()
    return user_config_path("sparclur") / "sparclur.yaml"


def _config_paths() -> tuple[Path, ...]:
    """Return configuration layers from lowest to highest precedence."""
    paths = [_ENV_CONFIG, _PROJECT_CONFIG, _LEGACY_USER_CONFIG]
    user_config = get_config_path()
    if user_config not in paths:
        paths.append(user_config)
    return tuple(paths)


def _read_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as yaml_in:
            config = yaml.safe_load(yaml_in)
    except yaml.YAMLError as error:
        raise ConfigurationError(f"Invalid SPARCLUR configuration at {path}: {error}") from error

    if config is None:
        return {}
    if not isinstance(config, Mapping):
        raise ConfigurationError(f"SPARCLUR configuration at {path} must be a YAML mapping")
    return dict(config)


def _merge_config(base: dict, override: Mapping) -> dict:
    """Recursively merge a higher-precedence configuration mapping."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def _get_config_param(cls, config, key, value, default):
    if value is not None:
        return value
    try:
        inheritance: list[type] = cls.mro()[0:-1]
        for parent in inheritance:
            config_param = config.get(parent.__name__, {}).get(key)
            if config_param is not None:
                return config_param
    except (AttributeError, TypeError):
        pass
    return default


def _get_yaml_path():
    """Return the highest-precedence existing configuration path, if any."""
    return next((path for path in reversed(_config_paths()) if path.is_file()), None)


def _load_config():
    """Load and merge all available configuration layers."""
    config = {}
    for yaml_path in _config_paths():
        if yaml_path.is_file():
            config = _merge_config(config, _read_config(yaml_path))
    return config


def get_config():
    """Return the effective merged SPARCLUR configuration."""
    return _load_config()


def update_config(updated_values: Mapping) -> Path:
    """Merge values into the user-editable configuration file and return its path."""
    if not isinstance(updated_values, Mapping):
        raise TypeError("updated_values must be a mapping")

    yaml_path = get_config_path()
    existing_config = _read_config(yaml_path) if yaml_path.is_file() else {}
    config = _merge_config(existing_config, updated_values)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with yaml_path.open("w", encoding="utf-8") as yaml_out:
        yaml.safe_dump(config, yaml_out, sort_keys=False)
    return yaml_path
