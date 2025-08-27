"""ScreenshotService のテストなのだ"""
import tempfile
import time
import os
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import pytest

from src.screenshot import ScreenshotService


class TestScreenshotService:
    """ScreenshotService テストクラスなのだ"""
    
    def test_service_initialization(self):
        """サービス初期化テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "screenshots"
            service = ScreenshotService(cache_dir, max_files=100, max_size_gb=1.0)
            
            assert service.cache_dir == cache_dir
            assert service.max_files == 100
            assert service.max_size_bytes == 1024 * 1024 * 1024  # 1GB
            assert cache_dir.exists()  # 自動作成される
    
    def test_resize_to_max_dimension(self):
        """画像リサイズテストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            # PIL.Imageのモック作成
            mock_img = Mock()
            mock_img.size = (2560, 1440)  # 2560px > 1920px
            mock_resized = Mock()
            mock_img.resize.return_value = mock_resized
            
            result = service._resize_to_max_dimension(mock_img, 1920)
            
            # 長辺2560pxを1920pxに縮小：scale = 1920/2560 = 0.75
            expected_width = int(2560 * 0.75)  # 1920
            expected_height = int(1440 * 0.75)  # 1080
            
            mock_img.resize.assert_called_once()
            call_args = mock_img.resize.call_args[0]
            assert call_args[0] == (expected_width, expected_height)
            assert result == mock_resized
    
    def test_resize_no_change_needed(self):
        """リサイズ不要の場合のテストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            mock_img = Mock()
            mock_img.size = (1600, 900)  # 1600px < 1920px
            
            result = service._resize_to_max_dimension(mock_img, 1920)
            
            # リサイズは呼ばれない
            mock_img.resize.assert_not_called()
            assert result == mock_img
    
    @patch('src.screenshot.mss.mss')
    @patch('src.screenshot.Image')
    def test_capture_and_save_success(self, mock_image_class, mock_mss_class):
        """スクリーンショット撮影・保存成功テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            # mssのモックセットアップ
            mock_sct = Mock()
            mock_mss_class.return_value.__enter__.return_value = mock_sct
            
            mock_monitors = [
                {"width": 3840, "height": 2160},  # 全画面
                {"width": 1920, "height": 1080}   # モニタ1
            ]
            mock_sct.monitors = mock_monitors
            
            mock_screenshot = Mock()
            mock_screenshot.size = (1920, 1080)
            mock_screenshot.bgra = b"fake_bgra_data"
            mock_sct.grab.return_value = mock_screenshot
            
            # PIL.Imageのモックセットアップ
            mock_img = Mock()
            mock_image_class.frombytes.return_value = mock_img
            mock_img.size = (1920, 1080)
            
            # テスト実行
            test_time = datetime(2025, 8, 27, 15, 30, 45, 123456, timezone.utc)
            result_path = service.capture_and_save(timestamp=test_time, monitor_index=1)
            
            # 検証
            assert result_path is not None
            expected_filename = "15-30-45-123.jpg"  # HH-MM-SS-mmm.jpg
            assert result_path.name == expected_filename
            assert "2025-08-27" in str(result_path)  # 日別ディレクトリ
            
            # mssが適切に呼ばれたことを確認
            mock_sct.grab.assert_called_once_with(mock_monitors[1])
            
            # 画像保存が呼ばれたことを確認
            mock_img.save.assert_called_once()
            save_args = mock_img.save.call_args
            assert save_args[0][1] == "JPEG"
            assert save_args[1]["quality"] == 70
    
    @patch('src.screenshot.mss.mss')
    def test_capture_and_save_failure(self, mock_mss_class):
        """スクリーンショット撮影失敗テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            # mssで例外発生
            mock_mss_class.side_effect = Exception("Screenshot failed")
            
            result = service.capture_and_save()
            
            # Noneが返される（例外は再発生しない）
            assert result is None
    
    def test_cache_stats(self):
        """キャッシュ統計テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            # テストファイルを作成
            daily_dir = service.cache_dir / "2025-08-27"
            daily_dir.mkdir(parents=True)
            
            test_files = [
                daily_dir / "10-00-00-000.jpg",
                daily_dir / "10-01-00-000.jpg"
            ]
            
            for file_path in test_files:
                file_path.write_bytes(b"fake_image_data")  # 15バイトずつ
            
            stats = service.get_cache_stats()
            
            assert stats["file_count"] == 2
            assert stats["total_size_mb"] > 0
            assert str(service.cache_dir) == stats["cache_dir"]
    
    def test_cleanup_old_files(self):
        """古いファイル掃除テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            # 古いファイルと新しいファイルを作成
            daily_dir = service.cache_dir / "2025-08-27"
            daily_dir.mkdir(parents=True)
            
            old_file = daily_dir / "old.jpg"
            new_file = daily_dir / "new.jpg"
            
            # ファイル作成
            old_file.write_bytes(b"old")
            new_file.write_bytes(b"new")
            
            # 古いファイルの作成時刻を24時間以上前に設定
            old_time = time.time() - (25 * 3600)  # 25時間前
            os.utime(old_file, (old_time, old_time))
            
            # 掃除実行
            cleaned = service.cleanup_old_files(max_age_hours=24)
            
            assert cleaned == 1
            assert not old_file.exists()  # 古いファイルは削除
            assert new_file.exists()      # 新しいファイルは残存
    
    def test_get_available_monitors(self):
        """利用可能モニタ情報取得テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = ScreenshotService(Path(tmp_dir))
            
            with patch('src.screenshot.mss.mss') as mock_mss:
                mock_sct = Mock()
                mock_mss.return_value.__enter__.return_value = mock_sct
                
                mock_monitors = [
                    {"width": 3840, "height": 2160, "left": 0, "top": 0},
                    {"width": 1920, "height": 1080, "left": 100, "top": 50}
                ]
                mock_sct.monitors = mock_monitors
                
                monitors = service.get_available_monitors()
                
                assert len(monitors) == 2
                assert monitors[0]["width"] == 3840
                assert monitors[1]["height"] == 1080
                assert monitors[1]["left"] == 100
