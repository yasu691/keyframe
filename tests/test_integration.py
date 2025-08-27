"""フェーズ1 E2E統合テストなのだ"""
import time
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import pytest

from src.config import ConfigLoader, Config
from src.scheduler import TimeSlicer
from src.keylogger import KeyLogger, KeyEvent
from src.jsonl_writer import JsonlWriter


class TestPhase1Integration:
    """フェーズ1統合テストクラスなのだ"""
    
    def test_keylogger_scheduler_integration(self):
        """KeyLoggerとSchedulerの統合テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # モック設定なのだ
            config = Config(
                azure_openai_endpoint="https://test.com",
                azure_openai_key="test-key",
                data_dir=Path(tmp_dir),
                interval_sec=1  # 1秒間隔でテスト
            )
            
            # コンポーネント初期化なのだ
            key_logger = KeyLogger()
            jsonl_writer = JsonlWriter(config.data_dir)
            slicer = TimeSlicer(config.interval_sec)
            
            # 疑似キーイベントを事前に追加なのだ
            current_time = time.time()
            with key_logger._lock:
                for i in range(30):  # 30個のキーイベント
                    event = KeyEvent(
                        timestamp=current_time - 30 + i,
                        key_name=chr(ord('a') + (i % 26)),
                        is_backspace=(i % 5 == 4)  # 5個に1個Backspace
                    )
                    key_logger.events.append(event)
                    key_logger.total_keys_cumulative += 1
            
            # 統計記録用のコールバック関数
            records_written = {"count": 0}
            
            def record_stats():
                stats = key_logger.get_stats(reset_buffer=True)
                jsonl_writer.write_record(stats, interval_sec=config.interval_sec)
                records_written["count"] += 1
            
            slicer.add_callback(record_stats, "test_recorder")
            
            # 2.5秒間実行（2-3レコード生成予定）
            slicer.start()
            time.sleep(2.5)
            slicer.stop()
            
            # 結果確認なのだ
            assert records_written["count"] >= 2, f"期待: 2+レコード, 実際: {records_written['count']}"
            
            # JSONLファイル確認なのだ
            jsonl_file = jsonl_writer.get_today_file_path()
            assert jsonl_file.exists(), "JSONLファイルが作成されていない"
            assert jsonl_writer.count_records() >= 2, f"レコード数不足: {jsonl_writer.count_records()}"
            
            # 最初のレコード内容確認なのだ
            first_record = None
            with open(jsonl_file, 'r') as f:
                import json
                first_record = json.loads(f.readline())
            
            assert first_record is not None
            assert "ts_utc" in first_record
            assert first_record["interval_sec"] == 1
            assert "typing" in first_record
            assert first_record["typing"]["kpm"] > 0  # キーイベントがあるので0より大きい
            assert "screen" in first_record
            assert "alerts" in first_record
    
    def test_config_to_jsonl_flow(self):
        """設定→統計→JSONL出力の一連フローテストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "config.ini"
            config_file.write_text(f"""
[azure]
endpoint = https://test-flow.com
key = flow-test-key

[paths]
data_dir = {tmp_dir}/data

[timing]
interval_sec = 1
""")
            
            # 設定読み込みなのだ
            loader = ConfigLoader(config_file)
            config = loader.load()
            
            # 各コンポーネントが設定値を正しく使用することを確認なのだ
            jsonl_writer = JsonlWriter(config.data_dir)
            assert config.data_dir.exists()
            
            # ダミー統計でJSONL出力なのだ
            from src.keylogger import TypingStats
            stats = TypingStats(
                kpm=45,
                kps15=1.2,
                median_latency_ms=150.0,
                backspace_pct=3.5,
                idle=False,
                total_keys_cum=2000
            )
            
            jsonl_writer.write_record(stats, interval_sec=config.interval_sec)
            
            # 結果確認なのだ
            record = jsonl_writer.read_last_record()
            assert record["interval_sec"] == 1  # config由来
            assert record["typing"]["kpm"] == 45
            assert record["typing"]["idle"] is False
    
    @patch('src.keylogger.keyboard.Listener')
    def test_keylogger_error_handling(self, mock_listener_class):
        """KeyLoggerエラーハンドリングテストなのだ"""
        # Listenerの初期化時にエラーを発生させるのだ
        mock_listener_class.side_effect = RuntimeError("Permission denied")
        
        key_logger = KeyLogger()
        
        # エラーが適切にキャッチされることを確認なのだ
        with pytest.raises(RuntimeError, match="キーロガー開始に失敗"):
            key_logger.start()
        
        # エラー状態でも統計取得は動作することを確認なのだ
        stats = key_logger.get_stats()
        assert stats.kpm == 0
        assert stats.idle is True
    
    def test_json_structure_compliance(self):
        """JSON構造の仕様準拠テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            jsonl_writer = JsonlWriter(Path(tmp_dir))
            
            from src.keylogger import TypingStats
            stats = TypingStats(
                kpm=80,
                kps15=2.8,
                median_latency_ms=95.5,
                backspace_pct=4.1,
                idle=False,
                total_keys_cum=12345
            )
            
            test_time = datetime(2025, 8, 27, 10, 0, 0, tzinfo=timezone.utc)
            jsonl_writer.write_record(stats, ts_utc=test_time, interval_sec=60)
            
            record = jsonl_writer.read_last_record()
            
            # 仕様書の構造と完全一致することを確認なのだ
            expected_structure = {
                "ts_utc": str,
                "interval_sec": int,
                "typing": {
                    "kpm": int,
                    "kps15": float,
                    "median_latency_ms": float,
                    "backspace_pct": float,
                    "idle": bool,
                    "total_keys_cum": int
                },
                "screen": {
                    "screenshot_path": type(None),
                    "ocr_text": str,
                    "active_app": str,
                    "active_title": str
                },
                "alerts": list
            }
            
            def check_structure(actual, expected, path=""):
                for key, expected_type in expected.items():
                    assert key in actual, f"Missing key: {path}.{key}"
                    actual_value = actual[key]
                    
                    if isinstance(expected_type, dict):
                        assert isinstance(actual_value, dict), f"Type mismatch at {path}.{key}: expected dict"
                        check_structure(actual_value, expected_type, f"{path}.{key}")
                    else:
                        assert isinstance(actual_value, expected_type), \
                            f"Type mismatch at {path}.{key}: expected {expected_type}, got {type(actual_value)}"
            
            check_structure(record, expected_structure)
            
            # 値の妥当性確認なのだ
            assert record["ts_utc"] == "2025-08-27T10:00:00+00:00"
            assert record["interval_sec"] == 60
            assert record["typing"]["kpm"] == 80
            assert abs(record["typing"]["kps15"] - 2.8) < 0.01
            assert record["screen"]["screenshot_path"] is None
            assert record["screen"]["ocr_text"] == ""
            assert record["alerts"] == []
    
    def test_concurrent_access_safety(self):
        """並行アクセス時の安全性テストなのだ"""
        key_logger = KeyLogger()
        results = []
        
        def add_events_worker():
            """イベント追加ワーカー"""
            for i in range(50):
                event = KeyEvent(
                    timestamp=time.time(),
                    key_name=f"key_{i}",
                    is_backspace=(i % 10 == 0)
                )
                with key_logger._lock:
                    key_logger.events.append(event)
                    key_logger.total_keys_cumulative += 1
                time.sleep(0.001)  # 短時間待機
        
        def get_stats_worker():
            """統計取得ワーカー"""
            for _ in range(10):
                stats = key_logger.get_stats()
                results.append(stats.total_keys_cum)
                time.sleep(0.01)
        
        # 2つのワーカーを並行実行なのだ
        thread1 = threading.Thread(target=add_events_worker)
        thread2 = threading.Thread(target=get_stats_worker)
        
        thread1.start()
        thread2.start()
        
        thread1.join()
        thread2.join()
        
        # 並行アクセスでもクラッシュしないことを確認なのだ
        assert len(results) == 10
        # 累積カウントは単調増加することを確認なのだ
        assert all(results[i] <= results[i+1] for i in range(len(results)-1))
