from inspect import signature


def parse_init(cls):
    try:
        sig = signature(cls.__init__)
    except Exception as e:
        print(e)
        return dict()
    skip_params = ['self',
                   'args',
                   'kwargs',
                   'doc',
                   'parse_streams',
                   'verbose',
                   'stream_output'
                   ]
    init_keys = [key for key in list(sig.parameters.keys()) if key not in skip_params]
    result = dict()
    for key in init_keys:
        param = str(sig.parameters[key])
        if '=' in param and ':' in param:
            equal_split = param.split('=')
            default = equal_split[-1].replace("'", '').replace('"', '').strip()
            param_type = equal_split[0].split(':')[-1].replace("'", '').replace('"', '').strip()
        elif ':' in param:
            colon_split = param.split(':')
            default = None
            param_type = colon_split[-1].replace("'", '').replace('"', '').strip()
        elif '=' in param:
            equal_split = param.split('=')
            default = equal_split[-1].replace("'", '').replace('"', '').strip()
            param_type = 'str'
        else:
            default = None
            param_type = 'str'
        result[key] = {'default': default, 'param_type': param_type}
    return result
