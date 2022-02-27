import unittest
from sparclur.parsers import Ghostscript
from parser_tests import ParserTestMixin, RendererTestMixin, ReforgerTestMixin, TEST_PDF


class GhostscriptTestCase(unittest.TestCase, ParserTestMixin, RendererTestMixin, ReforgerTestMixin):

    def setUp(self):
        self.parser = Ghostscript
        self.parser_instance = Ghostscript(TEST_PDF)


if __name__ == '__main__':
    unittest.main()
