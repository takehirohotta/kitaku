"""カスタム例外クラス"""


class KitakuException(Exception):
    """Kitakuアプリケーションのベース例外"""
    pass


class WeatherAPIException(KitakuException):
    """天気API関連の例外"""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class TimetableException(KitakuException):
    """時刻表関連の例外"""
    pass


class LLMException(KitakuException):
    """LLM API関連の例外"""
    def __init__(self, message: str, model_error: str = None):
        super().__init__(message)
        self.model_error = model_error


class ConfigurationException(KitakuException):
    """設定関連の例外"""
    pass


class ValidationException(KitakuException):
    """データバリデーション関連の例外"""
    pass