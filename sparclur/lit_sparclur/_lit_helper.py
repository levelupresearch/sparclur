from inspect import Parameter, signature


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
    result = dict()
    for key, parameter in sig.parameters.items():
        if key in skip_params:
            continue
        default = None if parameter.default is Parameter.empty else parameter.default
        annotation = str(parameter.annotation).lower()
        if 'bool' in annotation:
            param_type = 'bool'
        elif 'tuple' in annotation and 'int' in annotation:
            param_type = 'Tuple[int]'
        elif 'int' in annotation:
            param_type = 'int'
        else:
            param_type = 'str'
        result[key] = {'default': default, 'param_type': param_type}
    return result
