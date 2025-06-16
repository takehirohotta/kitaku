import csv
import logging
from typing import List, Optional, Dict
from datetime import datetime, time, timedelta
from pathlib import Path

from ..core.config import settings
from ..core.exceptions import TimetableException, ValidationException
from ..models.data_models import TimetableEntry

logger = logging.getLogger(__name__)


class TimetableService:
    """時刻表データの管理を担当するサービス"""
    
    def __init__(self, timetable_file_path: Optional[str] = None):
        self.timetable_file_path = Path(timetable_file_path or settings.timetable_file_path)
        self._timetable_cache: Optional[List[TimetableEntry]] = None
    
    def load_timetable(self) -> List[TimetableEntry]:
        """時刻表データを読み込み"""
        if self._timetable_cache is not None:
            return self._timetable_cache
        
        if not self.timetable_file_path.exists():
            raise TimetableException(f"時刻表ファイルが見つかりません: {self.timetable_file_path}")
        
        try:
            timetable_entries = []
            
            with open(self.timetable_file_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row_num, row in enumerate(reader, start=2):  # ヘッダー行があるので2から開始
                    try:
                        entry = TimetableEntry(
                            departure_time=row['出発時刻'].strip(),
                            train_type=row['種別'].strip(),
                            destination=row['行き先'].strip(),
                            travel_minutes=self._estimate_travel_time(row['種別'].strip(), row['行き先'].strip())
                        )
                        timetable_entries.append(entry)
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"時刻表ファイル {row_num}行目をスキップ: {str(e)}")
                        continue
            
            if not timetable_entries:
                raise TimetableException("有効な時刻表データが見つかりませんでした")
            
            # 出発時刻でソート
            timetable_entries.sort(key=lambda x: self._parse_time(x.departure_time))
            
            self._timetable_cache = timetable_entries
            logger.info(f"時刻表データを読み込みました: {len(timetable_entries)}件")
            
            return timetable_entries
            
        except csv.Error as e:
            raise TimetableException(f"時刻表ファイルの読み込みエラー: {str(e)}")
        except Exception as e:
            raise TimetableException(f"時刻表データ処理エラー: {str(e)}")
    
    def find_next_departures(
        self, 
        current_time: Optional[datetime] = None, 
        count: int = 5
    ) -> List[TimetableEntry]:
        """現在時刻以降の次の出発便を取得（大学から駅までの移動時間を考慮）"""
        if current_time is None:
            current_time = datetime.now()
        
        # 大学から駅までの移動時間を考慮した最低必要時刻を計算
        min_departure_time = current_time + timedelta(minutes=settings.walk_to_station_minutes)
        min_departure_time_obj = min_departure_time.time()
        
        timetable = self.load_timetable()
        next_departures = []
        
        # 今日の残りの便を探す（駅での出発時刻が最低必要時刻以降）
        for entry in timetable:
            train_departure_time = self._parse_time(entry.departure_time)
            if train_departure_time >= min_departure_time_obj:
                next_departures.append(entry)
                if len(next_departures) >= count:
                    break
        
        # 今日の便が足りない場合、明日の便も含める
        if len(next_departures) < count:
            remaining_count = count - len(next_departures)
            for entry in timetable[:remaining_count]:
                next_departures.append(entry)
        
        return next_departures[:count]
    
    def find_optimal_departure(
        self, 
        target_arrival: datetime,
        buffer_minutes: int = 10
    ) -> Optional[TimetableEntry]:
        """目標到着時刻に合わせた最適な出発便を検索"""
        timetable = self.load_timetable()
        target_departure = target_arrival - timedelta(minutes=buffer_minutes)
        
        best_entry = None
        min_time_diff = float('inf')
        
        for entry in timetable:
            departure_time = self._parse_time(entry.departure_time)
            travel_minutes = entry.travel_minutes or self._estimate_travel_time(entry.train_type, entry.destination)
            arrival_time = self._calculate_arrival_time(departure_time, travel_minutes)
            
            # 目標到着時刻より前に到着し、かつ最も近い便を選択
            if arrival_time <= target_arrival.time():
                time_diff = (target_arrival.time().hour * 60 + target_arrival.time().minute) - \
                           (arrival_time.hour * 60 + arrival_time.minute)
                
                if time_diff >= 0 and time_diff < min_time_diff:
                    min_time_diff = time_diff
                    best_entry = entry
        
        return best_entry
    
    def calculate_arrival_time(self, departure_entry: TimetableEntry) -> time:
        """出発便から到着時刻を計算"""
        departure_time = self._parse_time(departure_entry.departure_time)
        travel_minutes = departure_entry.travel_minutes or self._estimate_travel_time(
            departure_entry.train_type, departure_entry.destination
        )
        return self._calculate_arrival_time(departure_time, travel_minutes)
    
    def get_departure_options_for_weather(
        self, 
        weather_risk_level: str,
        current_time: Optional[datetime] = None
    ) -> List[TimetableEntry]:
        """天候リスクレベルに応じた出発オプションを取得"""
        if current_time is None:
            current_time = datetime.now()
        
        base_options = self.find_next_departures(current_time, count=10)
        
        # リスクレベルに応じて選択肢を調整
        if weather_risk_level == "high":
            # 高リスク: 早めの便を多く含める
            return base_options[:3]
        elif weather_risk_level == "medium":
            # 中リスク: バランス良く
            return base_options[:5]
        else:
            # 低リスク: 通常通り
            return base_options[:7]
    
    def _parse_time(self, time_str: str) -> time:
        """時刻文字列をtimeオブジェクトに変換"""
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise ValidationException(f"無効な時刻形式: {time_str} (HH:MM形式で入力してください)")
    
    def _estimate_travel_time(self, train_type: str, destination: str) -> int:
        """列車種別と行き先から所要時間を推定"""
        # 京阪寝屋川市→各駅の標準所要時間（分）
        base_times = {
            "淀屋橋": 35,
            "中之島": 45,
            "守口市": 8
        }
        
        # 列車種別による速度調整
        speed_factors = {
            "通勤快急": 0.8,
            "快速急行": 0.85,  
            "急行": 0.9,
            "区間急行": 0.95,
            "準急": 1.0,
            "通勤準急": 1.05,
            "普通": 1.2,
            "ライナー": 0.75,
            "不明": 1.0
        }
        
        base_time = base_times.get(destination, 35)  # デフォルトは淀屋橋までの時間
        speed_factor = speed_factors.get(train_type, 1.0)
        
        return int(base_time * speed_factor)
    
    def _calculate_arrival_time(self, departure_time: time, travel_minutes: int) -> time:
        """出発時刻と所要時間から到着時刻を計算"""
        departure_datetime = datetime.combine(datetime.today(), departure_time)
        arrival_datetime = departure_datetime + timedelta(minutes=travel_minutes)
        return arrival_datetime.time()
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self._timetable_cache = None
        logger.info("時刻表キャッシュをクリアしました")