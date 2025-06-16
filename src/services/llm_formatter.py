import json
import logging
from typing import Optional
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import settings
from ..core.exceptions import LLMException, ValidationException
from ..models.data_models import (
    WeatherPattern, DepartureRecommendation, LLMAnalysis
)

logger = logging.getLogger(__name__)


class LLMFormatter:
    """Google Gemini APIを使用して推奨結果を自然な日本語で表現するサービス"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        
        if not self.api_key:
            raise ValidationException("Gemini APIキーが設定されていません")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def format_recommendation(
        self,
        weather_pattern: WeatherPattern,
        departure_recommendation: DepartureRecommendation
    ) -> LLMAnalysis:
        """推奨結果を自然な日本語で表現"""
        
        # プロンプトを構築
        prompt = self._build_prompt(weather_pattern, departure_recommendation)
        
        try:
            # Gemini APIを呼び出し
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            logger.info("LLM応答を取得しました")
            
            # JSONレスポンスをパース
            return self._parse_llm_response(response_text)
            
        except Exception as e:
            logger.error(f"Gemini API呼び出しエラー: {str(e)}")
            raise LLMException(f"LLM分析に失敗しました: {str(e)}", model_error=str(e))
    
    def _build_prompt(
        self,
        weather_pattern: WeatherPattern,
        departure_recommendation: DepartureRecommendation
    ) -> str:
        """LLM用のプロンプトを構築"""
        
        # 天候情報の日本語表現
        pattern_descriptions = {
            "clear": "晴天",
            "light_rain": "小雨",
            "heavy_rain": "大雨",
            "improving": "天候回復中"
        }
        
        risk_descriptions = {
            "low": "低",
            "medium": "中程度",
            "high": "高"
        }
        
        trend_descriptions = {
            "increasing": "強くなる傾向",
            "decreasing": "弱くなる傾向",
            "stable": "安定"
        }
        
        weather_desc = pattern_descriptions.get(weather_pattern.pattern_type, "不明")
        risk_desc = risk_descriptions.get(weather_pattern.risk_level, "未評価")
        trend_desc = trend_descriptions.get(weather_pattern.rainfall_trend, "不明")
        
        prompt = f"""
あなたは天候を考慮した帰宅時刻推奨システムのアシスタントです。
以下の情報に基づいて、ユーザーに対する推奨内容を自然な日本語で表現してください。

【天候情報】
- 天候パターン: {weather_desc}
- 現在の降水量: {weather_pattern.current_rainfall}mm/h
- 1時間以内の最大降水量: {weather_pattern.max_rainfall_1h}mm/h
- 降水量の傾向: {trend_desc}
- リスクレベル: {risk_desc}

【推奨結果】
- 推奨出発時刻（大学）: {departure_recommendation.recommended_departure}
- 天候の影響: {"あり" if departure_recommendation.weather_impact else "なし"}
- 遅延バッファ: {departure_recommendation.delay_buffer}分
- 信頼度: {departure_recommendation.confidence_level:.1%}

以下の JSON 形式で回答してください：
{{
    "summary": "現在の状況を簡潔に要約（50文字以内）",
    "recommendation_reason": "なぜこの時刻を推奨するのかの理由（100文字以内）",
    "weather_warning": "天候に関する注意点（該当する場合のみ、80文字以内）",
    "additional_advice": "追加のアドバイス（該当する場合のみ、80文字以内）"
}}

注意事項：
- 親しみやすく、かつ実用的な表現を心がけてください
- 天候リスクが高い場合は適切な注意喚起を含めてください
- JSONフォーマットを厳密に守ってください
- 各フィールドの文字数制限を遵守してください
"""
        return prompt
    
    def _parse_llm_response(self, response_text: str) -> LLMAnalysis:
        """LLMの応答をパースしてLLMAnalysisオブジェクトを作成"""
        try:
            # JSONブロックを抽出（```json で囲まれている場合があるため）
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            # JSONをパース
            data = json.loads(response_text.strip())
            
            return LLMAnalysis(
                summary=data.get("summary", "現在の状況を分析中..."),
                recommendation_reason=data.get("recommendation_reason", "最適な時刻を計算しました"),
                weather_warning=data.get("weather_warning"),
                additional_advice=data.get("additional_advice")
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"LLMレスポンスのJSONパースに失敗、フォールバック使用: {str(e)}")
            return self._create_fallback_analysis(response_text)
        except KeyError as e:
            logger.warning(f"LLMレスポンスに必須フィールドが不足、フォールバック使用: {str(e)}")
            return self._create_fallback_analysis(response_text)
    
    def _create_fallback_analysis(self, raw_response: str) -> LLMAnalysis:
        """LLM応答のパースに失敗した場合のフォールバック分析"""
        # rawResponseの最初の200文字を要約として使用
        summary = raw_response[:50] + "..." if len(raw_response) > 50 else raw_response
        
        return LLMAnalysis(
            summary=summary or "天候を考慮した推奨時刻を算出しました",
            recommendation_reason="現在の天候状況と交通状況を総合的に判断しました",
            weather_warning=None,
            additional_advice="詳細な分析結果の表示に問題が発生しました"
        )
    
    def format_simple_message(
        self,
        weather_pattern: WeatherPattern,
        departure_recommendation: DepartureRecommendation
    ) -> str:
        """LLMを使わないシンプルなメッセージ生成（フォールバック用）"""
        
        pattern_messages = {
            "clear": "晴天です",
            "light_rain": "軽い雨が予想されます",
            "heavy_rain": "強い雨が予想されます",
            "improving": "天候が回復傾向です"
        }
        
        weather_msg = pattern_messages.get(weather_pattern.pattern_type, "天候を確認中")
        
        message = f"""
{departure_recommendation.recommended_departure}の出発をお勧めします。
{weather_msg}。
"""
        
        if departure_recommendation.weather_impact:
            message += f"\n天候による遅延を考慮し、{departure_recommendation.delay_buffer}分のバッファを設けています。"
        
        return message.strip()