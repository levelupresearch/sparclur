import os
import site
import sys
from typing import List

from sparclur.utils._tools import if_dir_not_exists

import yaml


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
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    _cloned_path = os.path.realpath('../../sparclur.yaml')
    _user_path = os.path.join(site.USER_BASE, 'etc', 'sparclur', 'sparclur.yaml')
    _env_path = os.path.join(sys.prefix, 'etc', 'sparclur', 'sparclur.yaml')
    if os.path.isfile(_cloned_path):
        yaml_path = _cloned_path
    elif os.path.isfile(os.path.join(_user_path)):
        yaml_path = _user_path
    elif os.path.isfile(_env_path):
        yaml_path = _env_path
    else:
        yaml_path = None
    return yaml_path

def _load_config():
    yaml_path = _get_yaml_path()
    if yaml_path is None:
        return dict()
    else:
        with open(yaml_path, 'r') as yaml_in:
            config = yaml.full_load(yaml_in)
        return config or dict()


def get_config():
    return _load_config()


def update_config(updated_values: dict):
    config = _load_config()
    yaml_path = _get_yaml_path()
    try:
        if yaml_path is None:
            yaml_path = _user_path = os.path.join(site.USER_BASE, 'etc', 'sparclur', 'sparclur.yaml')
            if_dir_not_exists(os.path.join(site.USER_BASE, 'etc', 'sparclur'))
        config.update(updated_values)
        with open(yaml_path, 'w') as yaml_out:
            yaml.dump(config, yaml_out)
    except Exception as e:
        print('Update failed: %s' % str(e))
