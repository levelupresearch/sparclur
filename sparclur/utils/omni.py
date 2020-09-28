import pandas as pd
from sparclur.utils.normalizer import clean_error, load_errors

class FormatError(Exception):

    def __init__(self, message):
        self.message = message


class Omni:
    def __init__(self, csv_path = None, raw_data = None):
        if csv_path:
            self.data = pd.read_csv(csv_path)
        else:
            try:
                self.data = pd.DataFrame(raw_data)
            except Exception as e:
                print(str(e))
                raise FormatError("Could not load data into DataFrame")

    def generate_messages(self, parsers, path_column):
        if isinstance(parsers, str):
            parsers = [parsers]
        for parser in parsers:
            col_name = '%s_messages' % parser
            self.data[col_name] = self.data.apply(lambda x: clean_error(parser, x[path_column]))