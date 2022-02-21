import unittest

from sparclur.parsers import PDFCPU
from test.parser_tests import ParserTestMixin, TracerTestMixin, TEST_PDF


class PDFCPUTestCase(unittest.TestCase, ParserTestMixin, TracerTestMixin):

    def setUp(self):
        self.parser = PDFCPU
        self.parser_instance = PDFCPU(TEST_PDF)


if __name__ == '__main__':
    unittest.main()
