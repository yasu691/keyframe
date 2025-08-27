"""JSONL形式でタイピング統計を記録するのだ"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.keylogger import TypingStats


class JsonlWriter:
    """JSONL形式でデータを書き出すクラスなのだ"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def write_record(
        self, 
        stats: TypingStats, 
        ts_utc: Optional[datetime] = None,
        interval_sec: int = 60,
        screenshot_path: Optional[str] = None,
        active_app: str = "",
        active_title: str = "",
        ocr_text: str = ""
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
                "kps15": round(stats.kps15, 1),
                "median_latency_ms": round(stats.median_latency_ms, 1),
                "backspace_pct": round(stats.backspace_pct, 1),
                "idle": stats.idle,
                "total_keys_cum": stats.total_keys_cum
            },
            "screen": {
                "screenshot_path": screenshot_path,  # フェーズ3ではOCR後にnull化
                "ocr_text": ocr_text,               # フェーズ3でOCR結果を記録
                "active_app": active_app,
                "active_title": active_title
            },
            "alerts": []                  # フェーズ1では空配列
        }
        
        # 日別ファイルパスなのだ
        date_str = ts_utc.strftime("%Y-%m-%d")
        file_path = self.data_dir / f"{date_str}.jsonl"
        
        # JSONL追記なのだ
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    def update_record_ocr(
        self,
        timestamp: datetime,
        ocr_text: str,
        screenshot_path_to_null: bool = True
    ) -> bool:
        """既存レコードのOCR結果を更新するのだ"""
        date_str = timestamp.strftime("%Y-%m-%d")
        file_path = self.data_dir / f"{date_str}.jsonl"
        
        if not file_path.exists():
            return False
        
        try:
            # ファイル全体を読み込み
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # 該当レコードを検索・更新
            target_iso = timestamp.isoformat()
            updated = False
            
            for i, line in enumerate(lines):
                try:
                    record = json.loads(line.strip())
                    if record.get("ts_utc") == target_iso:
                        # OCR結果を更新
                        record["screen"]["ocr_text"] = ocr_text
                        if screenshot_path_to_null:
                            record["screen"]["screenshot_path"] = None
                        
                        lines[i] = json.dumps(record, ensure_ascii=False) + "\n"
                        updated = True
                        break
                except json.JSONDecodeError:
                    continue
            
            if updated:
                # ファイルを書き戻し
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return True
            
        except Exception as e:
            print(f"⚠️ JSONL OCR更新エラー: {e}")
        
        return False
    
    def get_today_file_path(self) -> Path:
        """今日のJSONLファイルパスを取得するのだ"""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.data_dir / f"{today_str}.jsonl"
    
    def count_records(self, date: Optional[datetime] = None) -> int:
        """指定日（デフォルトは今日）のレコード数を取得するのだ"""
        if date is None:
            date = datetime.now(timezone.utc)
        
        date_str = date.strftime("%Y-%m-%d")
        file_path = self.data_dir / f"{date_str}.jsonl"
        
        if not file_path.exists():
            return 0
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def read_last_record(self, date: Optional[datetime] = None) -> Optional[dict]:
        """指定日（デフォルトは今日）の最新レコードを取得するのだ"""
        if date is None:
            date = datetime.now(timezone.utc)
        
        date_str = date.strftime("%Y-%m-%d")
        file_path = self.data_dir / f"{date_str}.jsonl"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    return json.loads(last_line)
        except Exception:
            pass
        
        return None
