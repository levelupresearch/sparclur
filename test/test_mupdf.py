import unittest

from parser_tests import ParserTestMixin, TracerTestMixin, RendererTestMixin, TextExtractorTestMixin, TEST_PDF, \
    ReforgerTestMixin
from sparclur.parsers import MuPDF


class MuPDFTestCase(unittest.TestCase, ParserTestMixin, TracerTestMixin, RendererTestMixin, TextExtractorTestMixin,
                    ReforgerTestMixin):

    def setUp(self):
        self.parser = MuPDF
        self.parser_instance = MuPDF(TEST_PDF)
        

if __name__ == '__main__':
    unittest.main()
