import abc
from docstring_inheritance import NumpyDocstringInheritanceMeta


class Meta(abc.ABCMeta, NumpyDocstringInheritanceMeta):
    pass
