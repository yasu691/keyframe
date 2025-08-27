"""OCRバックグラウンドワーカー：リトライキャッシュを定期的に処理するのだ"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.config import Config
from src.ocr_client import OcrClient, OcrResult
from src.retry_cache import RetryCache
from src.jsonl_writer import JsonlWriter


class OcrWorker:
    """OCRバックグラウンドワーカークラスなのだ"""
    
    def __init__(
        self, 
        config: Config, 
        jsonl_writer: JsonlWriter,
        cache_dir: Optional[Path] = None
    ):
        self.config = config
        self.jsonl_writer = jsonl_writer
        
        # OCRクライアントとリトライキャッシュを初期化
        self.ocr_client = OcrClient(config) if config.ocr_enabled else None
        
        if cache_dir is None:
            cache_dir = config.data_dir / "cache"
        
        self.retry_cache = RetryCache(
            cache_dir=cache_dir,
            max_attempts=config.retry_max_attempts,
            base_delay=config.retry_base_delay_sec
        )
        
        self.stats = {
            "total_processed": 0,
            "successful_ocr": 0,
            "failed_ocr": 0,
            "tasks_cleaned": 0
        }
    
    def add_screenshot_for_ocr(
        self, 
        screenshot_path: Path, 
        timestamp: datetime,
        delete_original: bool = True
    ) -> bool:
        """スクリーンショットをOCRキューに追加するのだ"""
        if not self.config.ocr_enabled or not self.ocr_client:
            # OCRが無効な場合はスクリーンショットを削除
            if delete_original and screenshot_path.exists():
                screenshot_path.unlink(missing_ok=True)
            return False
        
        try:
            # 即座にOCRを試行
            result = self.ocr_client.extract_text_from_image(screenshot_path)
            
            if result.is_success():
                # OCR成功：JSONLを更新してスクリーンショット削除
                self._update_jsonl_with_ocr_result(timestamp, result.get_text())
                
                if delete_original and screenshot_path.exists():
                    screenshot_path.unlink(missing_ok=True)
                
                self.stats["successful_ocr"] += 1
                print(f"✅ OCR成功: {len(result.get_text())}文字抽出")
                return True
            else:
                # OCR失敗：リトライキャッシュに追加
                task_id = self.retry_cache.add_failed_task(
                    image_path=screenshot_path,
                    original_timestamp=timestamp.isoformat(),
                    error_message=result.get_error() or "Unknown error"
                )
                
                if delete_original and screenshot_path.exists():
                    screenshot_path.unlink(missing_ok=True)
                
                self.stats["failed_ocr"] += 1
                print(f"❌ OCR失敗（リトライ追加）: {result.get_error()}")
                return bool(task_id)
                
        except Exception as e:
            print(f"⚠️ OCRキュー追加エラー: {e}")
            
            # エラー時もスクリーンショットを削除
            if delete_original and screenshot_path.exists():
                screenshot_path.unlink(missing_ok=True)
            
            return False
    
    def process_retry_queue(self) -> int:
        """リトライキューを処理するのだ（定期実行用）"""
        if not self.config.ocr_enabled or not self.ocr_client:
            return 0
        
        processed_count = 0
        ready_tasks = self.retry_cache.get_ready_tasks()
        
        if not ready_tasks:
            return 0
        
        print(f"🔄 リトライタスク処理開始: {len(ready_tasks)}個")
        
        for task in ready_tasks:
            try:
                # OCR再試行
                result = self.ocr_client.extract_text_from_image(task.image_path)
                
                if result.is_success():
                    # 成功：JSONLを更新
                    original_timestamp = datetime.fromisoformat(
                        task.original_timestamp.replace('Z', '+00:00')
                    )
                    self._update_jsonl_with_ocr_result(original_timestamp, result.get_text())
                    
                    # タスクを成功として記録
                    self.retry_cache.mark_task_attempted(task.task_id, True)
                    self.stats["successful_ocr"] += 1
                    
                    print(f"✅ リトライOCR成功: {task.task_id}")
                    
                else:
                    # 失敗：リトライ回数を更新
                    self.retry_cache.mark_task_attempted(
                        task.task_id, 
                        False, 
                        result.get_error() or "Retry failed"
                    )
                    self.stats["failed_ocr"] += 1
                
                processed_count += 1
                
            except Exception as e:
                print(f"⚠️ リトライタスク処理エラー: {task.task_id} - {e}")
                
                # エラー時も失敗として記録
                self.retry_cache.mark_task_attempted(task.task_id, False, str(e))
                processed_count += 1
        
        return processed_count
    
    def cleanup_old_tasks(self) -> int:
        """古いリトライタスクを掃除するのだ"""
        cleaned_count = self.retry_cache.cleanup_old_tasks(max_age_hours=24)
        self.stats["tasks_cleaned"] += cleaned_count
        return cleaned_count
    
    def _update_jsonl_with_ocr_result(self, timestamp: datetime, ocr_text: str) -> bool:
        """JSONLファイルのOCR結果を更新するのだ"""
        try:
            success = self.jsonl_writer.update_record_ocr(
                timestamp=timestamp,
                ocr_text=ocr_text,
                screenshot_path_to_null=True
            )
            
            if success:
                self.stats["total_processed"] += 1
            
            return success
            
        except Exception as e:
            print(f"⚠️ JSONL OCR更新エラー: {e}")
            return False
    
    def get_stats(self) -> dict:
        """ワーカーの統計情報を返すのだ"""
        retry_stats = self.retry_cache.get_cache_stats()
        
        return {
            "ocr_enabled": self.config.ocr_enabled,
            "total_processed": self.stats["total_processed"],
            "successful_ocr": self.stats["successful_ocr"],
            "failed_ocr": self.stats["failed_ocr"],
            "tasks_cleaned": self.stats["tasks_cleaned"],
            "retry_queue": retry_stats
        }
    
    def test_ocr_connection(self) -> bool:
        """OCR接続テストを実行するのだ"""
        if not self.config.ocr_enabled or not self.ocr_client:
            print("❌ OCRが無効になっています")
            return False
        
        return self.ocr_client.test_connection()
    
    def force_clear_retry_queue(self) -> int:
        """リトライキューを強制クリアするのだ（デバッグ用）"""
        return self.retry_cache.force_clear_all_tasks()
    
    def create_periodic_callback(self):
        """定期実行用コールバック関数を作成するのだ"""
        def ocr_worker_callback():
            """OCRワーカーの定期処理なのだ"""
            try:
                # リトライキューを処理
                processed = self.process_retry_queue()
                if processed > 0:
                    print(f"🔄 リトライキュー処理完了: {processed}個")
                
                # 古いタスクを掃除（10分間隔で実行判定）
                import time
                if int(time.time()) % 600 == 0:  # 10分ごと
                    cleaned = self.cleanup_old_tasks()
                    if cleaned > 0:
                        print(f"🗑️ 古いリトライタスク掃除: {cleaned}個")
                
            except Exception as e:
                print(f"⚠️ OCRワーカー定期処理エラー: {e}")
        
        return ocr_worker_callback

