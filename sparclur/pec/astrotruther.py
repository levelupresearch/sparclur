from sparclur.utils.normalizer import clean_error


class AstroTruther:
    def __init__(self, X = None, Y = None, full_model = True, metric_split = [.7, .3]):
        self.full_model = full_model
        self.metric_split = metric_split
        self.model = None
        self.X = X
        self.Y = Y

    def set_training_data(self, X, Y):
        self.X = X
        self.Y = Y

