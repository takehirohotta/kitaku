import asyncio
import logging
from datetime import datetime
from typing import Optional, List

from src.core.config import settings
from src.core.exceptions import KitakuException
from src.services.weather_service import WeatherService
from src.services.timetable_service import TimetableService
from src.services.recommendation_engine import RecommendationEngine
from src.services.llm_formatter import LLMFormatter
from src.models.data_models import KitakuRecommendation, WeatherPattern

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KitakuApp:
    """Kitaku帰宅推奨アプリケーション"""
    
    def __init__(self):
        self.weather_service = WeatherService()
        self.timetable_service = TimetableService()
        self.recommendation_engine = RecommendationEngine(
            self.weather_service, 
            self.timetable_service
        )
        self.llm_formatter = LLMFormatter()
    
    async def get_recommendation(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        target_arrival_time: Optional[datetime] = None
    ) -> KitakuRecommendation:
        """帰宅推奨を取得"""
        
        # デフォルト座標を使用（東京駅）
        if latitude is None:
            latitude = settings.default_latitude
        if longitude is None:
            longitude = settings.default_longitude
        
        try:
            logger.info(f"帰宅推奨を計算中... 座標: ({latitude}, {longitude})")
            
            # 天気データを取得・分析
            weather_response = await self.weather_service.fetch_weather_data(latitude, longitude)
            weather_pattern = self.weather_service.analyze_weather_pattern(weather_response)
            
            # 取得済みの天気データを使用して推奨を生成
            departure_recommendation = await self.recommendation_engine.generate_recommendation_with_weather(
                weather_response, weather_pattern, target_arrival_time
            )
            
            # LLMで自然な表現に変換
            try:
                llm_analysis = await self.llm_formatter.format_recommendation(
                    weather_pattern, departure_recommendation
                )
            except Exception as e:
                logger.warning(f"LLM分析に失敗、シンプルメッセージを使用: {str(e)}")
                # フォールバック: シンプルメッセージ
                simple_message = self.llm_formatter.format_simple_message(
                    weather_pattern, departure_recommendation
                )
                from src.models.data_models import LLMAnalysis
                llm_analysis = LLMAnalysis(
                    summary="天候を考慮した推奨時刻を算出しました",
                    recommendation_reason=simple_message,
                    weather_warning=None,
                    additional_advice=None
                )
            
            return KitakuRecommendation(
                departure_recommendation=departure_recommendation,
                weather_pattern=weather_pattern,
                llm_analysis=llm_analysis
            )
            
        except Exception as e:
            logger.error(f"推奨計算エラー: {str(e)}")
            raise KitakuException(f"推奨の取得に失敗しました: {str(e)}")
    
    def display_recommendation(self, recommendation: KitakuRecommendation):
        """推奨結果を表示"""
        print("\n" + "="*50)
        print("🚶 Kitaku - 帰宅推奨システム")
        print("="*50)
        
        # 基本情報
        print(f"\n📅 生成日時: {recommendation.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 推奨結果 - 大学出発時刻と電車発車時刻をセットで表示
        dep_rec = recommendation.departure_recommendation
        print(f"\n🕐 推奨出発時刻（大学）: {dep_rec.recommended_departure}")
        
        # 電車の発車時刻と詳細情報を取得して表示
        train_info = self._get_train_info_for_departure(dep_rec.recommended_departure)
        if train_info:
            print(f"🚃 電車発車時刻（駅）: {train_info['departure_time']}")
            print(f"   種別: {train_info['train_type']} | 行き先: {train_info['destination']}")
        else:
            # フォールバック: 計算した発車時刻のみ表示
            train_departure_time = self._calculate_train_departure_time(dep_rec.recommended_departure)
            print(f"🚃 電車発車時刻（駅）: {train_departure_time}")
        
        # 天候情報
        weather = recommendation.weather_pattern
        print(f"\n🌤️  天候情報:")
        print(f"   パターン: {weather.pattern_type}")
        print(f"   現在の降水量: {weather.current_rainfall}mm/h")
        print(f"   1時間以内最大降水量: {weather.max_rainfall_1h}mm/h")
        print(f"   リスクレベル: {weather.risk_level}")
        
        # LLM分析結果
        analysis = recommendation.llm_analysis
        print(f"\n💭 状況分析:")
        print(f"   {analysis.summary}")
        print(f"\n📝 推奨理由:")
        print(f"   {analysis.recommendation_reason}")
        
        if analysis.weather_warning:
            print(f"\n⚠️  天候注意:")
            print(f"   {analysis.weather_warning}")
        
        if analysis.additional_advice:
            print(f"\n💡 追加アドバイス:")
            print(f"   {analysis.additional_advice}")
        
        # 詳細情報
        if dep_rec.weather_impact:
            print(f"\n🌧️  遅延バッファ: {dep_rec.delay_buffer}分")
        
        print(f"\n📊 信頼度: {dep_rec.confidence_level:.1%}")
        print("\n" + "="*50)
    
    def _calculate_train_departure_time(self, recommended_departure: str) -> str:
        """推奨出発時刻から電車の発車時刻を計算"""
        from datetime import datetime, timedelta
        departure_time = datetime.strptime(recommended_departure, "%H:%M")
        train_departure_time = departure_time + timedelta(minutes=settings.walk_to_station_minutes)
        return train_departure_time.strftime("%H:%M")
    
    def _get_train_info_for_departure(self, recommended_departure: str) -> Optional[dict]:
        """推奨出発時刻に対応する電車の詳細情報を取得"""
        from datetime import datetime, timedelta
        
        # 大学出発時刻から駅到着時刻を計算
        departure_time = datetime.strptime(recommended_departure, "%H:%M")
        station_arrival_time = departure_time + timedelta(minutes=settings.walk_to_station_minutes)
        
        # 駅到着時刻以降の最初の電車を探す
        timetable = self.timetable_service.load_timetable()
        
        for entry in timetable:
            train_departure_time = datetime.strptime(entry.departure_time, "%H:%M")
            if train_departure_time >= station_arrival_time:
                return {
                    'departure_time': entry.departure_time,
                    'train_type': entry.train_type,
                    'destination': entry.destination
                }
        
        # 当日の電車が見つからない場合、翌日の最初の電車を返す
        if timetable:
            first_train = timetable[0]
            return {
                'departure_time': first_train.departure_time,
                'train_type': first_train.train_type,
                'destination': first_train.destination
            }
        
        return None
    
    async def get_multiple_recommendations(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        count: int = 5
    ) -> List[KitakuRecommendation]:
        """複数の帰宅推奨を取得"""
        
        # デフォルト座標を使用
        if latitude is None:
            latitude = settings.default_latitude
        if longitude is None:
            longitude = settings.default_longitude
        
        try:
            logger.info(f"複数の帰宅推奨を計算中... 座標: ({latitude}, {longitude})")
            
            # 天気データを一度だけ取得・分析
            weather_response = await self.weather_service.fetch_weather_data(latitude, longitude)
            weather_pattern = self.weather_service.analyze_weather_pattern(weather_response)
            
            # 取得済みの天気データを使用して複数の推奨を生成
            departure_recommendations = await self.recommendation_engine.generate_multiple_recommendations_with_weather(
                weather_response, weather_pattern, count
            )
            
            recommendations = []
            
            for i, departure_recommendation in enumerate(departure_recommendations):
                # 最初の推奨のみLLM分析を実行（コスト節約のため）
                if i == 0:
                    try:
                        llm_analysis = await self.llm_formatter.format_recommendation(
                            weather_pattern, departure_recommendation
                        )
                    except Exception as e:
                        logger.warning(f"LLM分析に失敗、シンプルメッセージを使用: {str(e)}")
                        simple_message = self.llm_formatter.format_simple_message(
                            weather_pattern, departure_recommendation
                        )
                        from src.models.data_models import LLMAnalysis
                        llm_analysis = LLMAnalysis(
                            summary="天候を考慮した推奨時刻を算出しました",
                            recommendation_reason=simple_message,
                            weather_warning=None,
                            additional_advice=None
                        )
                else:
                    # 2番目以降はシンプルな分析
                    from src.models.data_models import LLMAnalysis
                    llm_analysis = LLMAnalysis(
                        summary=f"選択肢{i+1}: 天候を考慮した代替案",
                        recommendation_reason="次の出発オプションです",
                        weather_warning=None,
                        additional_advice=None
                    )
                
                recommendation = KitakuRecommendation(
                    departure_recommendation=departure_recommendation,
                    weather_pattern=weather_pattern,
                    llm_analysis=llm_analysis
                )
                
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"複数推奨計算エラー: {str(e)}")
            raise KitakuException(f"複数推奨の取得に失敗しました: {str(e)}")
    
    def display_multiple_recommendations(self, recommendations: List[KitakuRecommendation]):
        """複数の推奨結果を表示"""
        print("\n" + "="*60)
        print("🚶 Kitaku - 帰宅推奨システム（複数オプション）")
        print("="*60)
        
        # 天候情報（共通）
        if recommendations:
            weather = recommendations[0].weather_pattern
            print(f"\n🌤️  天候情報:")
            print(f"   パターン: {weather.pattern_type}")
            print(f"   現在の降水量: {weather.current_rainfall}mm/h")
            print(f"   1時間以内最大降水量: {weather.max_rainfall_1h}mm/h")
            print(f"   リスクレベル: {weather.risk_level}")
        
        print(f"\n📋 推奨オプション一覧:")
        print("-" * 60)
        
        for i, recommendation in enumerate(recommendations, 1):
            dep_rec = recommendation.departure_recommendation
            
            # 電車の発車時刻と詳細情報を取得
            train_info = self._get_train_info_for_departure(dep_rec.recommended_departure)
            
            print(f"\n【オプション {i}】")
            print(f"🕐 推奨出発時刻（大学）: {dep_rec.recommended_departure}")
            if train_info:
                print(f"🚃 電車発車時刻（駅）: {train_info['departure_time']} ({train_info['train_type']} {train_info['destination']}行き)")
            else:
                train_departure_time = self._calculate_train_departure_time(dep_rec.recommended_departure)
                print(f"🚃 電車発車時刻（駅）: {train_departure_time}")
            print(f"📊 信頼度: {dep_rec.confidence_level:.1%}")
            
            if dep_rec.weather_impact:
                print(f"🌧️  遅延バッファ: {dep_rec.delay_buffer}分")
            
            # 最初のオプションのみ詳細分析を表示
            if i == 1:
                analysis = recommendation.llm_analysis
                print(f"💭 分析: {analysis.summary}")
                if analysis.weather_warning:
                    print(f"⚠️  注意: {analysis.weather_warning}")
        
        print("\n" + "="*60)


async def main():
    """メイン関数"""
    try:
        app = KitakuApp()
        
        print("Kitaku - 天候を考慮した帰宅推奨システム")
        print("現在地の天候情報を取得し、最適な帰宅時刻を提案します...\n")
        
        # 単一の推奨を取得してLLMの詳細応答を確認
        recommendation = await app.get_recommendation()
        
        # 結果を表示
        app.display_recommendation(recommendation)
        
    except KitakuException as e:
        logger.error(f"アプリケーションエラー: {str(e)}")
        print(f"\n❌ エラー: {str(e)}")
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        print(f"\n❌ 予期しないエラーが発生しました: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
