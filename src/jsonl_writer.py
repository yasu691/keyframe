"""JSONL形式でデータを書き出すライタなのだ"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from .keylogger import TypingStats


class JsonlWriter:
    """JSONL形式でタイピング統計を出力するライタなのだ"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def write_record(
        self, 
        stats: TypingStats, 
        ts_utc: Optional[datetime] = None,
        interval_sec: int = 60
    ) -> None:
        """1レコードをJSONL形式で書き出すのだ"""
        if ts_utc is None:
            ts_utc = datetime.now(timezone.utc)
        
        # JSONLレコード作成なのだ
        record = {
            "ts_utc": ts_utc.isoformat(),
            "interval_sec": interval_sec,
            "typing": {
                "kpm": stats.kpm,
                "kps15": round(stats.kps15, 2),
                "median_latency_ms": round(stats.median_latency_ms, 1),
                "backspace_pct": round(stats.backspace_pct, 1),
                "idle": stats.idle,
                "total_keys_cum": stats.total_keys_cum
            },
            "screen": {
                "screenshot_path": None,  # フェーズ1では常にnull
                "ocr_text": "",           # フェーズ1では空
                "active_app": "",         # フェーズ1では空
                "active_title": ""        # フェーズ1では空
            },
            "alerts": []                  # フェーズ1では空配列
        }
        
        # 日別ファイルパスなのだ
        date_str = ts_utc.strftime("%Y-%m-%d")
        file_path = self.data_dir / f"{date_str}.jsonl"
        
        # JSONL追記なのだ
        with open(file_path, 'a', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n')
    
    def get_today_file_path(self) -> Path:
        """今日のJSONLファイルパスを取得するのだ"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.data_dir / f"{today}.jsonl"
    
    def get_file_path(self, date: datetime) -> Path:
        """指定日付のJSONLファイルパスを取得するのだ"""
        date_str = date.strftime("%Y-%m-%d")
        return self.data_dir / f"{date_str}.jsonl"
    
    def count_records(self, file_path: Optional[Path] = None) -> int:
        """指定ファイル（デフォルト：今日）のレコード数をカウントするのだ"""
        if file_path is None:
            file_path = self.get_today_file_path()
        
        if not file_path.exists():
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for line in f if line.strip())
    
    def read_last_record(self, file_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
        """最後のレコードを読み込むのだ（テスト用）"""
        if file_path is None:
            file_path = self.get_today_file_path()
        
        if not file_path.exists():
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                return None
            
            last_line = lines[-1].strip()
            if not last_line:
                return None
            
            return json.loads(last_line)
