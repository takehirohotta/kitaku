import asyncio
import logging
from typing import List, Optional
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import settings
from ..core.exceptions import WeatherAPIException, ValidationException
from ..models.data_models import WeatherData, WeatherResponse, WeatherPattern

logger = logging.getLogger(__name__)


class WeatherService:
    """Yahoo天気APIとの連携を担当するサービス"""
    
    def __init__(self, client_id: Optional[str] = None):
        self.client_id = client_id or settings.yahoo_client_id
        self.base_url = settings.yahoo_api_base_url
        self.max_retries = settings.max_retries
        
        if not self.client_id:
            raise ValidationException("Yahoo Client IDが設定されていません")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def fetch_weather_data(
        self, 
        latitude: float, 
        longitude: float
    ) -> WeatherResponse:
        """指定座標の天気データを取得"""
        coordinates = f"{longitude},{latitude}"
        params = {
            "coordinates": coordinates,
            "appid": self.client_id,
            "output": "json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                logger.info(f"天気データを取得しました: 座標={coordinates}")
                
                return self._parse_weather_response(data, coordinates)
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Yahoo天気API HTTPエラー: {e.response.status_code}")
                raise WeatherAPIException(
                    f"天気データの取得に失敗しました: {e.response.status_code}",
                    status_code=e.response.status_code
                )
            except httpx.RequestError as e:
                logger.error(f"Yahoo天気API 通信エラー: {str(e)}")
                raise WeatherAPIException(f"天気API通信エラー: {str(e)}")
            except Exception as e:
                logger.error(f"予期しないエラー: {str(e)}")
                raise WeatherAPIException(f"天気データ処理エラー: {str(e)}")
    
    def _parse_weather_response(self, data: dict, coordinates: str) -> WeatherResponse:
        """Yahoo天気APIのレスポンスをパース"""
        try:
            weather_list = []
            
            # Yahoo天気APIのレスポンス構造に基づいてパース
            if "Feature" in data and len(data["Feature"]) > 0:
                weather_info = data["Feature"][0]["Property"]["WeatherList"]["Weather"]
                
                for weather_item in weather_info:
                    weather_data = WeatherData(
                        type=weather_item["Type"],
                        date=weather_item["Date"],
                        rainfall=float(weather_item["Rainfall"])
                    )
                    weather_list.append(weather_data)
            
            return WeatherResponse(
                weather_data=weather_list,
                coordinates=coordinates
            )
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"天気データのパースエラー: {str(e)}")
            raise WeatherAPIException(f"天気データの形式が不正です: {str(e)}")
    
    def analyze_weather_pattern(self, weather_response: WeatherResponse) -> WeatherPattern:
        """天気データから天候パターンを分析"""
        if not weather_response.weather_data:
            raise ValidationException("天気データが空です")
        
        # 現在の降水量（観測値から取得）
        current_data = [w for w in weather_response.weather_data if w.type == "observation"]
        current_rainfall = current_data[-1].rainfall if current_data else 0.0
        
        # 予測データから1時間以内の最大降水量を取得
        forecast_data = [w for w in weather_response.weather_data if w.type == "forecast"]
        max_rainfall_1h = max([w.rainfall for w in forecast_data[:6]], default=0.0)  # 10分間隔で6回 = 1時間
        
        # 降水量の傾向を分析
        rainfall_trend = self._analyze_rainfall_trend(forecast_data[:6])
        
        # パターンタイプを決定
        pattern_type = self._determine_pattern_type(current_rainfall, max_rainfall_1h, rainfall_trend)
        
        # リスクレベルを決定
        risk_level = self._determine_risk_level(current_rainfall, max_rainfall_1h, pattern_type)
        
        return WeatherPattern(
            pattern_type=pattern_type,
            current_rainfall=current_rainfall,
            max_rainfall_1h=max_rainfall_1h,
            rainfall_trend=rainfall_trend,
            risk_level=risk_level
        )
    
    def _analyze_rainfall_trend(self, forecast_data: List[WeatherData]) -> str:
        """降水量の傾向を分析"""
        if len(forecast_data) < 2:
            return "stable"
        
        rainfalls = [w.rainfall for w in forecast_data]
        avg_first_half = sum(rainfalls[:len(rainfalls)//2]) / (len(rainfalls)//2)
        avg_second_half = sum(rainfalls[len(rainfalls)//2:]) / (len(rainfalls) - len(rainfalls)//2)
        
        threshold = 0.5  # mm/h
        
        if avg_second_half > avg_first_half + threshold:
            return "increasing"
        elif avg_first_half > avg_second_half + threshold:
            return "decreasing"
        else:
            return "stable"
    
    def _determine_pattern_type(self, current: float, max_1h: float, trend: str) -> str:
        """天候パターンタイプを決定"""
        if current <= 0.5 and max_1h <= 1.0:
            return "clear"
        elif current <= 2.0 and max_1h <= 5.0:
            if trend == "decreasing":
                return "improving"
            else:
                return "light_rain"
        else:
            return "heavy_rain"
    
    def _determine_risk_level(self, current: float, max_1h: float, pattern_type: str) -> str:
        """リスクレベルを決定"""
        if pattern_type == "heavy_rain" or max_1h > 10.0:
            return "high"
        elif pattern_type == "light_rain" or max_1h > 2.0:
            return "medium"
        else:
            return "low"