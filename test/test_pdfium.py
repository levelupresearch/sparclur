import unittest
from sparclur.parsers import PDFium
from parser_tests import ParserTestMixin, RendererTestMixin, TEST_PDF


class PDFiumTestCase(unittest.TestCase, ParserTestMixin, RendererTestMixin):

    def setUp(self):
        self.parser = PDFium
        self.parser_instance = PDFium(TEST_PDF)


if __name__ == '__main__':
    unittest.main()
