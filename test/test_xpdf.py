import unittest

from sparclur.parsers import XPDF
from test.parser_tests import ParserTestMixin, TracerTestMixin, RendererTestMixin, TextExtractorTestMixin, \
    FontExtractorTestMixin, TEST_PDF


class XPDFTestCase(unittest.TestCase, ParserTestMixin, TracerTestMixin, RendererTestMixin, TextExtractorTestMixin,
                   FontExtractorTestMixin):

    def setUp(self):
        self.parser = XPDF
        self.parser_instance = XPDF(TEST_PDF)


if __name__ == '__main__':
    unittest.main()
