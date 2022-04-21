import unittest
from sparclur.parsers import PDFMiner
from parser_tests import ParserTestMixin, TextExtractorTestMixin, MetadataExtractorTestMixin, TEST_PDF


class PDFMinerTestCase(unittest.TestCase, ParserTestMixin, TextExtractorTestMixin, MetadataExtractorTestMixin):

    def setUp(self):
        self.parser = PDFMiner
        self.parser_instance = PDFMiner(TEST_PDF)


if __name__ == '__main__':
    unittest.main()
