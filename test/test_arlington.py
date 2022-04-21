import unittest
from sparclur.parsers import Arlington
from parser_tests import ParserTestMixin, TracerTestMixin, TEST_PDF


class ArlingtonTestCase(unittest.TestCase, ParserTestMixin, TracerTestMixin):

    def setUp(self):
        self.parser = Arlington
        self.parser_instance = Arlington(TEST_PDF)


if __name__ == '__main__':
    unittest.main()
