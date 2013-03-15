class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    def __init__(self, msg, key=None, code=None, **kwargs):
        super(ValidationError, self).__init__(msg)
        self.message = msg
        self.key = key
        self.code = code
        for k, v in kwargs.items():
            setattr(self, k, v)


class AuthError(Exception):
    pass


class MultipleChoicesError(Exception):
    def __init__(self, msg, body):
        super(MultipleChoicesError, self).__init__(msg)
        self.body = body
