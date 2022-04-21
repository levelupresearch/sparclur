import unittest

from sparclur.parsers import Poppler
from test.parser_tests import ParserTestMixin, TracerTestMixin, RendererTestMixin, TextExtractorTestMixin, \
    FontExtractorTestMixin, ImageDataExtractorTestMixin, ReforgerTestMixin, TEST_PDF


class PopplerTestCase(unittest.TestCase, ParserTestMixin, TracerTestMixin, RendererTestMixin, TextExtractorTestMixin,
                      FontExtractorTestMixin, ImageDataExtractorTestMixin, ReforgerTestMixin):

    def setUp(self):
        self.parser = Poppler
        self.parser_instance = Poppler(TEST_PDF)


if __name__ == '__main__':
    unittest.main()
