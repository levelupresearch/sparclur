import os
import unittest
from sparclur.parsers import Arlington
from parser_tests import ParserTestMixin, TracerTestMixin, TEST_PDF


class ArlingtonTestCase(unittest.TestCase, ParserTestMixin, TracerTestMixin):

    def setUp(self):
        self.parser = Arlington
        self.parser_instance = Arlington(TEST_PDF, arlington_path=os.environ["SPARCLUR_ARLINGTON_PATH"])


if __name__ == '__main__':
    unittest.main()
