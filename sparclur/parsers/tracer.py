from sparclur.utils.normalizer import clean_messages


class ParserMessages:

    def __init__(self, parser_name, messages):
        self.parser = parser_name
        self.messages = messages
        self.cleaned = clean_messages(parser_name, messages)