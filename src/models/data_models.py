from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class WeatherData(BaseModel):
    """Yahoo天気APIからの天気データ"""
    type: Literal["observation", "forecast"] = Field(..., description="観測値 or 予測値")
    date: str = Field(..., description="日時 (YYYYMMDDHHMI形式)")
    rainfall: float = Field(..., description="降水量 (mm/h)")


class WeatherResponse(BaseModel):
    """Yahoo天気APIのレスポンス"""
    weather_data: List[WeatherData] = Field(..., description="天気データのリスト")
    coordinates: str = Field(..., description="座標情報")


class WeatherPattern(BaseModel):
    """天候パターン分析結果"""
    pattern_type: Literal["clear", "light_rain", "heavy_rain", "improving"] = Field(
        ..., description="天候パターンタイプ"
    )
    current_rainfall: float = Field(..., description="現在の降水量")
    max_rainfall_1h: float = Field(..., description="1時間以内の最大降水量")
    rainfall_trend: Literal["increasing", "decreasing", "stable"] = Field(
        ..., description="降水量の傾向"
    )
    risk_level: Literal["low", "medium", "high"] = Field(..., description="リスクレベル")


class TimetableEntry(BaseModel):
    """時刻表エントリ"""
    departure_time: str = Field(..., description="出発時刻 (HH:MM)")
    train_type: str = Field(..., description="列車種別（急行・準急等）")
    destination: str = Field(..., description="行き先")
    travel_minutes: Optional[int] = Field(None, description="所要時間（分）")


class DepartureRecommendation(BaseModel):
    """出発時刻推奨結果"""
    recommended_departure: str = Field(..., description="推奨出発時刻")
    arrival_time: str = Field(..., description="到着予定時刻")
    weather_impact: bool = Field(..., description="天候の影響があるか")
    delay_buffer: int = Field(..., description="遅延バッファ（分）")
    confidence_level: float = Field(..., description="信頼度 (0.0-1.0)")


class LLMAnalysis(BaseModel):
    """LLMによる分析結果"""
    summary: str = Field(..., description="状況の要約")
    recommendation_reason: str = Field(..., description="推奨理由")
    weather_warning: Optional[str] = Field(None, description="天候に関する警告")
    additional_advice: Optional[str] = Field(None, description="追加のアドバイス")


class KitakuRecommendation(BaseModel):
    """最終的な帰宅推奨結果"""
    departure_recommendation: DepartureRecommendation
    weather_pattern: WeatherPattern
    llm_analysis: LLMAnalysis
    generated_at: datetime = Field(default_factory=datetime.now)