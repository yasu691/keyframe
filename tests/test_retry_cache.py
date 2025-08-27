"""RetryCache のテストなのだ"""
import tempfile
import time
import json
from pathlib import Path
from datetime import datetime, timezone
import pytest

from src.retry_cache import RetryCache, RetryTask


class TestRetryTask:
    """RetryTask テストクラスなのだ"""
    
    def test_should_retry_now(self):
        """リトライ判定テストなのだ"""
        current_time = time.time()
        
        # 過去の時刻（リトライすべき）
        past_task = RetryTask(
            task_id="test1",
            image_path=Path("/tmp/test1.jpg"),
            created_at=current_time - 100,
            last_attempt_at=current_time - 50,
            attempt_count=1,
            next_retry_at=current_time - 10,  # 10秒前
            original_timestamp="2025-08-27T10:00:00+00:00",
            error_message="Test error"
        )
        assert past_task.should_retry_now() is True
        
        # 未来の時刻（まだリトライしない）
        future_task = RetryTask(
            task_id="test2",
            image_path=Path("/tmp/test2.jpg"),
            created_at=current_time - 100,
            last_attempt_at=current_time - 50,
            attempt_count=1,
            next_retry_at=current_time + 100,  # 100秒後
            original_timestamp="2025-08-27T10:00:00+00:00",
            error_message="Test error"
        )
        assert future_task.should_retry_now() is False
    
    def test_calculate_next_retry_time(self):
        """次のリトライ時間計算テストなのだ"""
        current_time = time.time()
        
        task = RetryTask(
            task_id="test",
            image_path=Path("/tmp/test.jpg"),
            created_at=current_time,
            last_attempt_at=current_time,
            attempt_count=2,  # 3回目の試行
            next_retry_at=current_time,
            original_timestamp="2025-08-27T10:00:00+00:00",
            error_message="Test error"
        )
        
        base_delay = 2.0
        next_time = task.calculate_next_retry_time(base_delay)
        
        # 指数バックオフ: 2.0 * (2^2) = 8.0秒 + ジッタ
        expected_min = current_time + 8.0 - (8.0 * 0.2)  # ジッタ -20%
        expected_max = current_time + 8.0 + (8.0 * 0.2)  # ジッタ +20%
        
        assert expected_min <= next_time <= expected_max


class TestRetryCache:
    """RetryCache テストクラスなのだ"""
    
    def test_initialization(self):
        """初期化テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir, max_attempts=5, base_delay=2.0)
            
            assert cache.cache_dir == cache_dir / "retry"
            assert cache.max_attempts == 5
            assert cache.base_delay == 2.0
            assert cache.cache_dir.exists()
            assert cache.tasks_file == cache.cache_dir / "retry_tasks.json"
    
    def test_add_failed_task(self):
        """失敗タスク追加テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir)
            
            # テスト用画像ファイルを作成
            test_image = Path(tmp_dir) / "test_image.jpg"
            test_image.write_bytes(b"fake image data")
            
            # タスクを追加
            task_id = cache.add_failed_task(
                image_path=test_image,
                original_timestamp="2025-08-27T10:00:00+00:00",
                error_message="OCR failed"
            )
            
            assert task_id.startswith("retry_")
            assert len(cache._tasks) == 1
            
            # キャッシュファイルが作成されることを確認
            cached_files = list(cache.cache_dir.glob("*.jpg"))
            assert len(cached_files) == 1
            assert cached_files[0].name == f"{task_id}.jpg"
            
            # タスク内容を確認
            task = cache._tasks[0]
            assert task.task_id == task_id
            assert task.original_timestamp == "2025-08-27T10:00:00+00:00"
            assert task.error_message == "OCR failed"
            assert task.attempt_count == 1
    
    def test_get_ready_tasks(self):
        """準備済みタスク取得テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir, max_attempts=3)
            
            # テスト用画像ファイルを作成
            test_image = Path(tmp_dir) / "test_image.jpg"
            test_image.write_bytes(b"fake image data")
            
            # タスクを追加
            task_id = cache.add_failed_task(
                image_path=test_image,
                original_timestamp="2025-08-27T10:00:00+00:00",
                error_message="OCR failed"
            )
            
            # まだリトライ時刻に達していない
            ready_tasks = cache.get_ready_tasks()
            assert len(ready_tasks) == 0
            
            # リトライ時刻を過去に設定
            cache._tasks[0].next_retry_at = time.time() - 100
            
            # リトライ準備完了
            ready_tasks = cache.get_ready_tasks()
            assert len(ready_tasks) == 1
            assert ready_tasks[0].task_id == task_id
    
    def test_mark_task_attempted_success(self):
        """タスク試行成功記録テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir)
            
            # テスト用画像ファイルを作成
            test_image = Path(tmp_dir) / "test_image.jpg"
            test_image.write_bytes(b"fake image data")
            
            # タスクを追加
            task_id = cache.add_failed_task(
                image_path=test_image,
                original_timestamp="2025-08-27T10:00:00+00:00",
                error_message="OCR failed"
            )
            
            initial_count = len(cache._tasks)
            assert initial_count == 1
            
            # 成功として記録
            success = cache.mark_task_attempted(task_id, True)
            
            assert success is True
            assert len(cache._tasks) == 0  # 成功時はタスクが削除される
            
            # 画像ファイルも削除されることを確認
            cached_files = list(cache.cache_dir.glob("*.jpg"))
            assert len(cached_files) == 0
    
    def test_mark_task_attempted_failure(self):
        """タスク試行失敗記録テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir, max_attempts=3)
            
            # テスト用画像ファイルを作成
            test_image = Path(tmp_dir) / "test_image.jpg"
            test_image.write_bytes(b"fake image data")
            
            # タスクを追加
            task_id = cache.add_failed_task(
                image_path=test_image,
                original_timestamp="2025-08-27T10:00:00+00:00",
                error_message="OCR failed"
            )
            
            # 失敗として記録（1回目）
            success = cache.mark_task_attempted(task_id, False, "Retry failed")
            
            assert success is True
            assert len(cache._tasks) == 1  # まだタスクは残る
            
            task = cache._tasks[0]
            assert task.attempt_count == 2
            assert task.error_message == "Retry failed"
            assert task.next_retry_at > time.time()  # 次のリトライ時間が設定される
    
    def test_mark_task_attempted_max_attempts(self):
        """最大試行回数到達テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir, max_attempts=2)  # 最大2回
            
            # テスト用画像ファイルを作成
            test_image = Path(tmp_dir) / "test_image.jpg"
            test_image.write_bytes(b"fake image data")
            
            # タスクを追加（1回目の失敗）
            task_id = cache.add_failed_task(
                image_path=test_image,
                original_timestamp="2025-08-27T10:00:00+00:00",
                error_message="OCR failed"
            )
            
            # 2回目も失敗（最大回数到達）
            success = cache.mark_task_attempted(task_id, False, "Final failure")
            
            assert success is True
            assert len(cache._tasks) == 0  # 最大回数到達でタスクが削除される
    
    def test_cleanup_old_tasks(self):
        """古いタスク掃除テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir)
            
            # テスト用画像ファイルを作成
            test_image = Path(tmp_dir) / "test_image.jpg"
            test_image.write_bytes(b"fake image data")
            
            # タスクを追加
            task_id = cache.add_failed_task(
                image_path=test_image,
                original_timestamp="2025-08-27T10:00:00+00:00",
                error_message="OCR failed"
            )
            
            # 作成時刻を25時間前に設定
            old_time = time.time() - (25 * 3600)
            cache._tasks[0].created_at = old_time
            
            # 掃除実行
            cleaned_count = cache.cleanup_old_tasks(max_age_hours=24)
            
            assert cleaned_count == 1
            assert len(cache._tasks) == 0
            
            # 画像ファイルも削除されることを確認
            cached_files = list(cache.cache_dir.glob("*.jpg"))
            assert len(cached_files) == 0
    
    def test_get_cache_stats(self):
        """キャッシュ統計取得テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir)
            
            # 初期状態の統計
            stats = cache.get_cache_stats()
            assert stats["total_tasks"] == 0
            assert stats["ready_tasks"] == 0
            assert stats["total_size_mb"] == 0.0
            
            # テスト用画像ファイルを作成してタスク追加
            test_image = Path(tmp_dir) / "test_image.jpg"
            test_image.write_bytes(b"fake image data" * 100)  # 1.5KB程度
            
            task_id = cache.add_failed_task(
                image_path=test_image,
                original_timestamp="2025-08-27T10:00:00+00:00",
                error_message="OCR failed"
            )
            
            # タスク追加後の統計
            stats = cache.get_cache_stats()
            assert stats["total_tasks"] == 1
            assert stats["ready_tasks"] == 0  # まだリトライ時刻でない
            assert stats["total_size_mb"] > 0
    
    def test_tasks_persistence(self):
        """タスク永続化テストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            
            # 最初のキャッシュインスタンス
            cache1 = RetryCache(cache_dir)
            
            # テスト用画像ファイルを作成
            test_image = Path(tmp_dir) / "test_image.jpg"
            test_image.write_bytes(b"fake image data")
            
            # タスクを追加
            task_id = cache1.add_failed_task(
                image_path=test_image,
                original_timestamp="2025-08-27T10:00:00+00:00",
                error_message="OCR failed"
            )
            
            assert len(cache1._tasks) == 1
            
            # 新しいキャッシュインスタンス（永続化されたタスクを読み込み）
            cache2 = RetryCache(cache_dir)
            
            assert len(cache2._tasks) == 1
            assert cache2._tasks[0].task_id == task_id
            assert cache2._tasks[0].original_timestamp == "2025-08-27T10:00:00+00:00"
    
    def test_force_clear_all_tasks(self):
        """全タスク強制クリアテストなのだ"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir) / "retry_test"
            cache = RetryCache(cache_dir)
            
            # 複数のタスクを追加
            for i in range(3):
                test_image = Path(tmp_dir) / f"test_image_{i}.jpg"
                test_image.write_bytes(b"fake image data")
                
                cache.add_failed_task(
                    image_path=test_image,
                    original_timestamp=f"2025-08-27T10:{i:02d}:00+00:00",
                    error_message=f"OCR failed {i}"
                )
            
            assert len(cache._tasks) == 3
            
            # 全クリア実行
            cleared_count = cache.force_clear_all_tasks()
            
            assert cleared_count == 3
            assert len(cache._tasks) == 0
            
            # 画像ファイルも全て削除されることを確認
            cached_files = list(cache.cache_dir.glob("*.jpg"))
            assert len(cached_files) == 0

