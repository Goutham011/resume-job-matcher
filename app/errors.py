class AppError(Exception):
    def __init__(self, status_code, code, message, extra=None, headers=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}
        self.headers = headers or {}
