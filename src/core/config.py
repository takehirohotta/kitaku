import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    """アプリケーション設定"""
    yahoo_client_id: str = Field(..., description="Yahoo APIのクライアントID")
    gemini_api_key: str = Field(..., description="Google Gemini APIキー")
    gemini_model: str = Field("gemini-2.0-flash-lite", description="使用するGeminiモデル名")
    
    # デフォルト座標（環境変数で設定可能）
    default_latitude: float = Field(34.7619, description="デフォルト緯度")
    default_longitude: float = Field(135.6283, description="デフォルト経度")
    
    # API設定
    yahoo_api_base_url: str = Field("https://map.yahooapis.jp/weather/V1/place", description="Yahoo天気APIのベースURL")
    max_retries: int = Field(3, description="API呼び出しの最大リトライ回数")
    retry_delay: float = Field(1.0, description="リトライ間隔（秒）")
    
    # 時刻表設定
    timetable_file_path: str = Field("keihan_neyagawa.csv", description="時刻表ファイルのパス")
    walk_to_station_minutes: int = Field(10, description="現在地から駅までの徒歩時間（分）")
    
    class Config:
        env_file = ".env"
        extra = "forbid"


def get_settings() -> Settings:
    """設定を取得する"""
    from .exceptions import ConfigurationException
    
    yahoo_client_id = os.getenv("YAHOO_CLIENT_ID", "")
    if not yahoo_client_id:
        raise ConfigurationException("YAHOO_CLIENT_IDが設定されていません")
    
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_api_key:
        raise ConfigurationException("GEMINI_API_KEYが設定されていません")
    
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
    
    # 位置情報（環境変数から取得、デフォルト値あり）
    default_latitude = float(os.getenv("DEFAULT_LATITUDE", "34.7619"))
    default_longitude = float(os.getenv("DEFAULT_LONGITUDE", "135.6283"))
    
    # 時刻表ファイルパス（環境変数から取得、デフォルト値あり）
    timetable_file_path = os.getenv("TIMETABLE_FILE_PATH", "keihan_neyagawa.csv")
    
    # 移動時間（環境変数から取得、デフォルト値あり）
    walk_to_station_minutes = int(os.getenv("WALK_TO_STATION_MINUTES", "10"))
    
    return Settings(
        yahoo_client_id=yahoo_client_id,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        default_latitude=default_latitude,
        default_longitude=default_longitude,
        timetable_file_path=timetable_file_path,
        walk_to_station_minutes=walk_to_station_minutes,
    )


# グローバル設定インスタンス
settings = get_settings()