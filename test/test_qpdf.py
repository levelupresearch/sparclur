import unittest

from sparclur.parsers import QPDF
from test.parser_tests import ParserTestMixin, TracerTestMixin, MetadataExtractorTestMixin, TEST_PDF


class QPDFTestCase(unittest.TestCase, ParserTestMixin, TracerTestMixin, MetadataExtractorTestMixin):

    def setUp(self):
        self.parser = QPDF
        self.parser_instance = QPDF(TEST_PDF)


if __name__ == '__main__':
    unittest.main()
