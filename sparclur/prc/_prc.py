from sparclur._renderer import Renderer
from sparclur.parsers.present_parsers import get_sparclur_renderers
from inspect import isclass


def _parse_renderers(renderers):
    renderer_dict = {renderer.get_name(): renderer for renderer in get_sparclur_renderers()}
    result = []
    for renderer in renderers:
        if isinstance(renderer, str):
            if renderer in renderer_dict:
                result.append(renderer)
        elif isclass(renderer):
            if issubclass(renderer, Renderer):
                result.append(renderer.get_name())
        elif isinstance(renderer, Renderer):
            result.append(renderer.get_name())
    assert len(result) > 1, "At least two renderers must be selected"
    return result
