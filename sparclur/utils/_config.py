import site
import sys
from pathlib import Path
from typing import List

import yaml


_SOURCE_ROOT = Path(__file__).resolve().parents[2]
_USER_CONFIG = Path(site.USER_BASE) / 'etc' / 'sparclur' / 'sparclur.yaml'
_ENV_CONFIG = Path(sys.prefix) / 'etc' / 'sparclur' / 'sparclur.yaml'


def _get_config_param(cls, config, key, value, default):
    if value is not None:
        return value
    else:
        try:
            inheritance: List[type] = cls.mro()[0:-1]
            inheritance = [i.__name__ for i in inheritance]
            for i in inheritance:
                config_param = config.get(i, dict()).get(key, None)
                if config_param is not None:
                    break
            if config_param is None:
                return default
            else:
                return config_param
        except Exception as e:
            return default


def _get_yaml_path():
    """Return the first existing configuration path without changing the CWD."""
    for yaml_path in (_SOURCE_ROOT / 'sparclur.yaml', _USER_CONFIG, _ENV_CONFIG):
        if yaml_path.is_file():
            return yaml_path
    return None

def _load_config():
    yaml_path = _get_yaml_path()
    if yaml_path is None:
        return dict()
    else:
        with yaml_path.open('r') as yaml_in:
            config = yaml.full_load(yaml_in)
        return config or dict()


def get_config():
    return _load_config()


def update_config(updated_values: dict):
    config = _load_config()
    yaml_path = _get_yaml_path()
    try:
        if yaml_path is None:
            yaml_path = _USER_CONFIG
            yaml_path.parent.mkdir(parents=True, exist_ok=True)
        config.update(updated_values)
        with yaml_path.open('w') as yaml_out:
            yaml.dump(config, yaml_out)
    except Exception as e:
        print('Update failed: %s' % str(e))
