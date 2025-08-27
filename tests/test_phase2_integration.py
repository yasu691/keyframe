"""フェーズ2統合テスト（キュー容量制限）なのだ"""
import os
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone
import pytest

from src.screenshot import ScreenshotService


class TestPhase2Integration:
    """フェーズ2統合テストクラスなのだ"""
    
    def test_screenshot_queue_file_limit(self):
        """スクリーンショットキュー上限（ファイル数）テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 上限を3ファイルに設定
            service = ScreenshotService(Path(tmp_dir), max_files=3, max_size_gb=1.0)
            
            # テスト用の疑似スクリーンショットファイルを作成
            daily_dir = service.cache_dir / "2025-08-27"
            daily_dir.mkdir(parents=True)
            
            test_files = []
            for i in range(5):  # 5ファイル作成（上限3を超える）
                file_path = daily_dir / f"test-{i:03d}.jpg"
                file_path.write_bytes(b"fake_image_data" * 100)  # 1.5KB程度
                test_files.append(file_path)
                time.sleep(0.01)  # ファイル作成時刻に差をつける
            
            # キャッシュ管理を実行
            service._manage_cache_size()
            
            # 上限3ファイルまで削減されることを確認
            remaining_files = list(daily_dir.glob("*.jpg"))
            assert len(remaining_files) == 3, f"期待: 3ファイル, 実際: {len(remaining_files)}ファイル"
            
            # 古いファイル（test-000, test-001）が削除され、新しいファイルが残ることを確認
            remaining_names = [f.name for f in remaining_files]
            assert "test-000.jpg" not in remaining_names
            assert "test-001.jpg" not in remaining_names
            assert "test-004.jpg" in remaining_names  # 最新ファイルは残存
    
    def test_screenshot_queue_size_limit(self):
        """スクリーンショットキュー上限（サイズ）テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 上限を1MBに設定（実際は小さめ）
            service = ScreenshotService(Path(tmp_dir), max_files=100, max_size_gb=0.001)  # 1MB
            
            daily_dir = service.cache_dir / "2025-08-27"
            daily_dir.mkdir(parents=True)
            
            # 500KB ずつのファイルを作成（合計で上限を超える）
            large_data = b"x" * (500 * 1024)  # 500KB
            
            test_files = []
            for i in range(4):  # 4ファイル = 2MB（上限1MB超）
                file_path = daily_dir / f"large-{i:03d}.jpg"
                file_path.write_bytes(large_data)
                test_files.append(file_path)
                time.sleep(0.01)
            
            # キャッシュ管理を実行
            service._manage_cache_size()
            
            # ファイルサイズが上限以下になることを確認
            remaining_files = list(daily_dir.glob("*.jpg"))
            total_size = sum(f.stat().st_size for f in remaining_files)
            max_size_bytes = int(0.001 * 1024 * 1024 * 1024)  # 1MB
            
            assert total_size <= max_size_bytes, f"サイズ超過: {total_size} > {max_size_bytes}"
            assert len(remaining_files) < 4, "ファイル数が削減されていない"
    
    def test_screenshot_cache_cleanup_old_files(self):
        """古いキャッシュファイル掃除テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            # 複数日のディレクトリを作成
            old_dir = service.cache_dir / "2025-08-25"  # 2日前
            today_dir = service.cache_dir / "2025-08-27"  # 今日
            
            old_dir.mkdir(parents=True)
            today_dir.mkdir(parents=True)
            
            # ファイル作成
            old_file = old_dir / "old-screenshot.jpg"
            today_file = today_dir / "today-screenshot.jpg"
            
            old_file.write_bytes(b"old_image")
            today_file.write_bytes(b"today_image")
            
            # 古いファイルのタイムスタンプを25時間前に設定
            old_timestamp = time.time() - (25 * 3600)
            os.utime(old_file, (old_timestamp, old_timestamp))
            
            # 掃除実行（24時間より古いファイル削除）
            cleaned_count = service.cleanup_old_files(max_age_hours=24)
            
            # 古いファイルが削除され、新しいファイルが残ることを確認
            assert not old_file.exists(), "古いファイルが削除されていない"
            assert today_file.exists(), "新しいファイルが誤って削除された"
            assert cleaned_count == 1, f"削除ファイル数が不正: {cleaned_count}"
            
            # 空になったディレクトリも削除されることを確認
            assert not old_dir.exists(), "空ディレクトリが削除されていない"
            assert today_dir.exists(), "ファイルがあるディレクトリが誤って削除された"
    
    def test_screenshot_service_stats(self):
        """スクリーンショットサービス統計テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            # テストファイル作成
            daily_dir = service.cache_dir / "2025-08-27"
            daily_dir.mkdir(parents=True)
            
            for i in range(3):
                file_path = daily_dir / f"stats-test-{i}.jpg"
                file_path.write_bytes(b"test_data" * 1000)  # 9KB程度
            
            # 統計取得
            stats = service.get_cache_stats()
            
            assert stats["file_count"] == 3
            assert stats["total_size_mb"] > 0
            assert str(service.cache_dir) in stats["cache_dir"]
    
    def test_monitor_detection(self):
        """モニタ検出テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            monitors = service.get_available_monitors()
            
            # 少なくとも1つのモニタが検出されることを期待
            assert len(monitors) >= 1, "モニタが検出されない"
            
            # 最初のモニタの構造確認
            first_monitor = monitors[0]
            required_keys = ["index", "width", "height", "left", "top"]
            
            for key in required_keys:
                assert key in first_monitor, f"モニタ情報に {key} が含まれていない"
                assert isinstance(first_monitor[key], (int, float)), f"{key} が数値でない"
