"""JsonlWriter のテストなのだ"""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pytest

from src.jsonl_writer import JsonlWriter
from src.keylogger import TypingStats


class TestJsonlWriter:
    """JsonlWriter テストクラスなのだ"""
    
    def test_write_single_record(self):
        """単一レコード書き込みテストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            writer = JsonlWriter(Path(tmp_dir))
            
            stats = TypingStats(
                kpm=120,
                kps15=2.5,
                median_latency_ms=95.5,
                backspace_pct=4.2,
                idle=False,
                total_keys_cum=1000
            )
            
            test_time = datetime(2025, 8, 27, 10, 30, 0, tzinfo=timezone.utc)
            writer.write_record(stats, ts_utc=test_time, interval_sec=60)
            
            # ファイルが作成されることを確認
            expected_file = Path(tmp_dir) / "2025-08-27.jsonl"
            assert expected_file.exists()
            
            # レコード数の確認
            assert writer.count_records(expected_file) == 1
            
            # 内容の確認
            record = writer.read_last_record(expected_file)
            assert record is not None
            assert record["ts_utc"] == "2025-08-27T10:30:00+00:00"
            assert record["interval_sec"] == 60
            assert record["typing"]["kpm"] == 120
            assert record["typing"]["kps15"] == 2.5
            assert record["typing"]["median_latency_ms"] == 95.5
            assert record["typing"]["backspace_pct"] == 4.2
            assert record["typing"]["idle"] is False
            assert record["typing"]["total_keys_cum"] == 1000
            
            # フェーズ1では空/nullの項目確認
            assert record["screen"]["screenshot_path"] is None
            assert record["screen"]["ocr_text"] == ""
            assert record["screen"]["active_app"] == ""
            assert record["screen"]["active_title"] == ""
            assert record["alerts"] == []
    
    def test_write_multiple_records(self):
        """複数レコード書き込みテストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            writer = JsonlWriter(Path(tmp_dir))
            
            # 3つのレコードを書き込み
            base_time = datetime(2025, 8, 27, 10, 0, 0, tzinfo=timezone.utc)
            
            for i in range(3):
                stats = TypingStats(
                    kpm=100 + i * 10,
                    kps15=2.0 + i * 0.1,
                    median_latency_ms=100.0,
                    backspace_pct=5.0,
                    idle=(i == 2),  # 最後だけidle
                    total_keys_cum=500 + i * 100
                )
                
                # 1分ずつ増加
                record_time = datetime(
                    base_time.year, base_time.month, base_time.day,
                    base_time.hour, base_time.minute + i, 0,
                    tzinfo=timezone.utc
                )
                
                writer.write_record(stats, ts_utc=record_time)
            
            # レコード数の確認
            file_path = Path(tmp_dir) / "2025-08-27.jsonl"
            assert writer.count_records(file_path) == 3
            
            # 最後のレコードの確認
            last_record = writer.read_last_record(file_path)
            assert last_record["typing"]["kpm"] == 120  # 100 + 2*10
            assert last_record["typing"]["idle"] is True
    
    def test_different_date_files(self):
        """異なる日付のファイル作成テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            writer = JsonlWriter(Path(tmp_dir))
            
            stats = TypingStats(kpm=50, total_keys_cum=200)
            
            # 2つの異なる日付でレコード作成
            date1 = datetime(2025, 8, 27, 23, 59, 0, tzinfo=timezone.utc)
            date2 = datetime(2025, 8, 28, 0, 1, 0, tzinfo=timezone.utc)
            
            writer.write_record(stats, ts_utc=date1)
            writer.write_record(stats, ts_utc=date2)
            
            # 2つのファイルが作成されることを確認
            file1 = Path(tmp_dir) / "2025-08-27.jsonl"
            file2 = Path(tmp_dir) / "2025-08-28.jsonl"
            
            assert file1.exists()
            assert file2.exists()
            assert writer.count_records(file1) == 1
            assert writer.count_records(file2) == 1
    
    def test_append_to_existing_file(self):
        """既存ファイルへの追記テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            writer = JsonlWriter(Path(tmp_dir))
            
            stats = TypingStats(kpm=30, total_keys_cum=100)
            test_date = datetime(2025, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
            
            # 最初の書き込み
            writer.write_record(stats, ts_utc=test_date)
            
            # 同じ日に再度書き込み
            stats2 = TypingStats(kpm=40, total_keys_cum=150)
            test_date2 = datetime(2025, 8, 27, 13, 0, 0, tzinfo=timezone.utc)
            writer.write_record(stats2, ts_utc=test_date2)
            
            # レコード数が2になることを確認
            file_path = Path(tmp_dir) / "2025-08-27.jsonl"
            assert writer.count_records(file_path) == 2
    
    def test_data_dir_creation(self):
        """データディレクトリ自動作成テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 存在しないサブディレクトリを指定
            subdir = Path(tmp_dir) / "nested" / "data"
            assert not subdir.exists()
            
            writer = JsonlWriter(subdir)
            assert subdir.exists()  # 自動作成される
    
    def test_nonexistent_file_operations(self):
        """存在しないファイルに対する操作テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            writer = JsonlWriter(Path(tmp_dir))
            
            nonexistent_file = Path(tmp_dir) / "nonexistent.jsonl"
            
            # 存在しないファイルのレコード数は0
            assert writer.count_records(nonexistent_file) == 0
            
            # 存在しないファイルの最後のレコードはNone
            assert writer.read_last_record(nonexistent_file) is None
    
    def test_rounding_precision(self):
        """数値の丸め精度テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            writer = JsonlWriter(Path(tmp_dir))
            
            stats = TypingStats(
                kpm=120,
                kps15=2.3456789,      # 小数点第2位で丸め
                median_latency_ms=95.789,  # 小数点第1位で丸め
                backspace_pct=4.15678,     # 小数点第1位で丸め
                idle=False,
                total_keys_cum=1000
            )
            
            writer.write_record(stats)
            record = writer.read_last_record()
            
            assert record["typing"]["kps15"] == 2.35  # 第2位で丸め
            assert record["typing"]["median_latency_ms"] == 95.8  # 第1位で丸め
            assert record["typing"]["backspace_pct"] == 4.2  # 第1位で丸め
    
    def test_default_timestamp(self):
        """デフォルトタイムスタンプテストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            writer = JsonlWriter(Path(tmp_dir))
            
            stats = TypingStats(kpm=100, total_keys_cum=500)
            writer.write_record(stats)  # ts_utcを指定しない
            
            record = writer.read_last_record()
            # タイムスタンプが設定されていることを確認（正確な時刻は不要）
            assert "ts_utc" in record
            assert record["ts_utc"].endswith("+00:00")  # UTCであることを確認
