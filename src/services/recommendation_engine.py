import logging
from typing import Optional, List, Tuple
from datetime import datetime, timedelta, time

from ..models.data_models import (
    WeatherPattern, TimetableEntry, DepartureRecommendation
)
from ..core.config import settings
from ..core.exceptions import ValidationException
from .weather_service import WeatherService
from .timetable_service import TimetableService

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """天気と時刻表データを統合して最適な出発時刻を推奨するエンジン"""
    
    def __init__(
        self, 
        weather_service: WeatherService,
        timetable_service: TimetableService
    ):
        self.weather_service = weather_service
        self.timetable_service = timetable_service
    
    async def generate_recommendation(
        self,
        latitude: float,
        longitude: float,
        target_arrival_time: Optional[datetime] = None,
        current_time: Optional[datetime] = None
    ) -> DepartureRecommendation:
        """包括的な出発推奨を生成"""
        
        if current_time is None:
            current_time = datetime.now()
        
        # 天気データを取得・分析
        weather_response = await self.weather_service.fetch_weather_data(latitude, longitude)
        weather_pattern = self.weather_service.analyze_weather_pattern(weather_response)
        
        # 天候に応じた遅延バッファを計算
        delay_buffer = self._calculate_delay_buffer(weather_pattern)
        
        # 最適な出発便を選択
        optimal_departure = self._select_optimal_departure(
            weather_pattern, 
            delay_buffer, 
            target_arrival_time,
            current_time
        )
        
        # 到着予定時刻を計算
        arrival_time = self.timetable_service.calculate_arrival_time(optimal_departure)
        
        # 駅までの移動時間を考慮した実際の出発時刻を計算
        recommended_departure_time = self._calculate_departure_with_walk_time(optimal_departure.departure_time)
        
        # 信頼度を計算
        confidence_level = self._calculate_confidence_level(weather_pattern, optimal_departure)
        
        return DepartureRecommendation(
            recommended_departure=recommended_departure_time,
            arrival_time=arrival_time.strftime("%H:%M"),
            weather_impact=self._has_weather_impact(weather_pattern),
            delay_buffer=delay_buffer,
            confidence_level=confidence_level
        )
    
    def _calculate_delay_buffer(self, weather_pattern: WeatherPattern) -> int:
        """天候パターンに基づいて遅延バッファを計算"""
        base_buffer = 5  # 基本バッファ（分）
        
        # パターン別の追加バッファ
        pattern_buffers = {
            "clear": 0,
            "light_rain": 5,
            "heavy_rain": 15,
            "improving": 3
        }
        
        # リスクレベル別の追加バッファ
        risk_buffers = {
            "low": 0,
            "medium": 5,
            "high": 10
        }
        
        # 降水量に基づく追加バッファ
        rainfall_buffer = min(int(weather_pattern.max_rainfall_1h * 2), 20)
        
        total_buffer = (
            base_buffer + 
            pattern_buffers.get(weather_pattern.pattern_type, 5) +
            risk_buffers.get(weather_pattern.risk_level, 5) +
            rainfall_buffer
        )
        
        return min(total_buffer, 45)  # 最大45分に制限
    
    def _select_optimal_departure(
        self,
        weather_pattern: WeatherPattern,
        delay_buffer: int,
        target_arrival_time: Optional[datetime] = None,
        current_time: Optional[datetime] = None
    ) -> TimetableEntry:
        """最適な出発便を選択"""
        
        if target_arrival_time is not None:
            # 目標到着時刻が指定されている場合
            # 遅延バッファを考慮して逆算
            adjusted_target = target_arrival_time - timedelta(minutes=delay_buffer)
            optimal_departure = self.timetable_service.find_optimal_departure(
                adjusted_target, buffer_minutes=5
            )
            
            if optimal_departure is not None:
                return optimal_departure
        
        # 目標時刻が未指定、または適切な便が見つからない場合
        # 天候リスクに応じた候補から選択
        departure_options = self.timetable_service.get_departure_options_for_weather(
            weather_pattern.risk_level, current_time
        )
        
        if not departure_options:
            raise ValidationException("利用可能な出発便が見つかりませんでした")
        
        # 天候パターンに基づいて最適な便を選択
        return self._choose_best_option_by_weather(departure_options, weather_pattern)
    
    def _choose_best_option_by_weather(
        self, 
        options: List[TimetableEntry], 
        weather_pattern: WeatherPattern
    ) -> TimetableEntry:
        """天候パターンに基づいて最適なオプションを選択"""
        
        if weather_pattern.pattern_type == "heavy_rain":
            # 大雨の場合：なるべく早い便を選択
            return options[0]
        
        elif weather_pattern.pattern_type == "improving":
            # 天候回復中の場合：最大3つの選択肢から中間を選択
            available_options = min(3, len(options))
            mid_index = available_options // 2
            return options[mid_index]
        
        elif weather_pattern.pattern_type == "light_rain":
            # 小雨の場合：バランスを取って選択
            if weather_pattern.rainfall_trend == "increasing":
                # 雨が強くなる傾向：早めの便
                return options[0]
            else:
                # 雨が弱くなる傾向：最大3つの選択肢から選択
                available_options = min(3, len(options))
                return options[min(1, available_options - 1)]
        
        else:  # clear
            # 晴れの場合：最大3つの選択肢から最初の便を選択
            return options[0]
    
    def _has_weather_impact(self, weather_pattern: WeatherPattern) -> bool:
        """天候の影響があるかどうかを判定"""
        return (
            weather_pattern.risk_level in ["medium", "high"] or
            weather_pattern.current_rainfall > 1.0 or
            weather_pattern.max_rainfall_1h > 2.0
        )
    
    def _calculate_confidence_level(
        self, 
        weather_pattern: WeatherPattern, 
        departure_entry: TimetableEntry
    ) -> float:
        """推奨の信頼度を計算（0.0-1.0）"""
        base_confidence = 0.8
        
        # 天候パターンによる調整
        pattern_adjustments = {
            "clear": 0.1,
            "light_rain": 0.0,
            "heavy_rain": -0.2,
            "improving": 0.05
        }
        
        # リスクレベルによる調整
        risk_adjustments = {
            "low": 0.1,
            "medium": 0.0,
            "high": -0.15
        }
        
        # 降水量による調整
        rainfall_penalty = min(weather_pattern.max_rainfall_1h * 0.02, 0.2)
        
        confidence = (
            base_confidence +
            pattern_adjustments.get(weather_pattern.pattern_type, 0) +
            risk_adjustments.get(weather_pattern.risk_level, 0) -
            rainfall_penalty
        )
        
        return max(0.3, min(1.0, confidence))  # 0.3-1.0の範囲に制限
    
    def _calculate_departure_with_walk_time(self, train_departure_time: str) -> str:
        """駅までの移動時間を考慮した実際の出発時刻を計算"""
        from datetime import datetime, timedelta
        
        # 列車出発時刻をdatetimeオブジェクトに変換
        train_time = datetime.strptime(train_departure_time, "%H:%M").time()
        train_datetime = datetime.combine(datetime.today(), train_time)
        
        # 駅までの移動時間を差し引く
        actual_departure = train_datetime - timedelta(minutes=settings.walk_to_station_minutes)
        
        # 現在時刻より前の場合は現在時刻を返す（安全措置）
        current_time = datetime.now()
        if actual_departure < current_time:
            logger.warning(f"計算された出発時刻 {actual_departure.strftime('%H:%M')} が現在時刻より前のため、現在時刻を使用")
            return current_time.strftime("%H:%M")
        
        return actual_departure.strftime("%H:%M")
    
    def get_alternative_options(
        self,
        weather_pattern: WeatherPattern,
        primary_recommendation: DepartureRecommendation,
        current_time: Optional[datetime] = None
    ) -> List[TimetableEntry]:
        """代替オプションを提供"""
        departure_options = self.timetable_service.get_departure_options_for_weather(
            weather_pattern.risk_level, current_time
        )
        
        # 主要推奨を除外
        alternatives = [
            option for option in departure_options 
            if option.departure_time != primary_recommendation.recommended_departure
        ]
        
        return alternatives[:3]  # 最大3つの代替案
    
    async def generate_multiple_recommendations(
        self,
        latitude: float,
        longitude: float,
        count: int = 5,
        current_time: Optional[datetime] = None
    ) -> List[DepartureRecommendation]:
        """複数の推奨結果を生成（最大5件）"""
        
        if current_time is None:
            current_time = datetime.now()
        
        # 天気データを取得・分析
        weather_response = await self.weather_service.fetch_weather_data(latitude, longitude)
        weather_pattern = self.weather_service.analyze_weather_pattern(weather_response)
        
        # 天候に応じた遅延バッファを計算
        delay_buffer = self._calculate_delay_buffer(weather_pattern)
        
        # 複数の出発オプションを取得
        departure_options = self.timetable_service.find_next_departures(current_time, count)
        
        recommendations = []
        
        for departure_entry in departure_options:
            # 到着予定時刻を計算
            arrival_time = self.timetable_service.calculate_arrival_time(departure_entry)
            
            # 駅までの移動時間を考慮した実際の出発時刻を計算
            recommended_departure_time = self._calculate_departure_with_walk_time(departure_entry.departure_time)
            
            # 信頼度を計算
            confidence_level = self._calculate_confidence_level(weather_pattern, departure_entry)
            
            recommendation = DepartureRecommendation(
                recommended_departure=recommended_departure_time,
                arrival_time=arrival_time.strftime("%H:%M"),
                weather_impact=self._has_weather_impact(weather_pattern),
                delay_buffer=delay_buffer,
                confidence_level=confidence_level
            )
            
            recommendations.append(recommendation)
        
        return recommendations
    
    async def generate_recommendation_with_weather(
        self,
        weather_response,
        weather_pattern: WeatherPattern,
        target_arrival_time: Optional[datetime] = None,
        current_time: Optional[datetime] = None
    ) -> DepartureRecommendation:
        """事前に取得済みの天気データを使用して推奨を生成"""
        
        if current_time is None:
            current_time = datetime.now()
        
        # 天候に応じた遅延バッファを計算
        delay_buffer = self._calculate_delay_buffer(weather_pattern)
        
        # 最適な出発便を選択
        optimal_departure = self._select_optimal_departure(
            weather_pattern, 
            delay_buffer, 
            target_arrival_time,
            current_time
        )
        
        # 到着予定時刻を計算
        arrival_time = self.timetable_service.calculate_arrival_time(optimal_departure)
        
        # 駅までの移動時間を考慮した実際の出発時刻を計算
        recommended_departure_time = self._calculate_departure_with_walk_time(optimal_departure.departure_time)
        
        # 信頼度を計算
        confidence_level = self._calculate_confidence_level(weather_pattern, optimal_departure)
        
        return DepartureRecommendation(
            recommended_departure=recommended_departure_time,
            arrival_time=arrival_time.strftime("%H:%M"),
            weather_impact=self._has_weather_impact(weather_pattern),
            delay_buffer=delay_buffer,
            confidence_level=confidence_level
        )
    
    async def generate_multiple_recommendations_with_weather(
        self,
        weather_response,
        weather_pattern: WeatherPattern,
        count: int = 5,
        current_time: Optional[datetime] = None
    ) -> List[DepartureRecommendation]:
        """事前に取得済みの天気データを使用して複数の推奨結果を生成"""
        
        if current_time is None:
            current_time = datetime.now()
        
        # 天候に応じた遅延バッファを計算
        delay_buffer = self._calculate_delay_buffer(weather_pattern)
        
        # 複数の出発オプションを取得
        departure_options = self.timetable_service.find_next_departures(current_time, count)
        
        recommendations = []
        
        for departure_entry in departure_options:
            # 到着予定時刻を計算
            arrival_time = self.timetable_service.calculate_arrival_time(departure_entry)
            
            # 駅までの移動時間を考慮した実際の出発時刻を計算
            recommended_departure_time = self._calculate_departure_with_walk_time(departure_entry.departure_time)
            
            # 信頼度を計算
            confidence_level = self._calculate_confidence_level(weather_pattern, departure_entry)
            
            recommendation = DepartureRecommendation(
                recommended_departure=recommended_departure_time,
                arrival_time=arrival_time.strftime("%H:%M"),
                weather_impact=self._has_weather_impact(weather_pattern),
                delay_buffer=delay_buffer,
                confidence_level=confidence_level
            )
            
            recommendations.append(recommendation)
        
        return recommendations