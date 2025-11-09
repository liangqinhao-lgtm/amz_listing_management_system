"""异常系统"""
class AppException(Exception):
    def __init__(self, message: str, code: str = "APP_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class ValidationException(AppException):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")
