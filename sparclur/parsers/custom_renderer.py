from sparclur.parsers._renderer import Renderer


class CustomRenderer(Renderer):

    def __init__(self, name, renderer_wrapper):
        self.name = name
        self.render_method = renderer_wrapper

    def get_name(self):
        return self.name

    def render_page(self, path, page, args=dict()):
        return self.render_method(path, page, args)
