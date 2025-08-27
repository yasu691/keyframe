"""リトライキャッシュ：失敗したOCRタスクを管理して再試行するのだ"""
import json
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class RetryTask:
    """リトライタスクデータクラスなのだ"""
    task_id: str
    image_path: Path
    created_at: float
    last_attempt_at: float
    attempt_count: int
    next_retry_at: float
    original_timestamp: str  # 元のスクリーンショットタイムスタンプ
    error_message: str
    
    def should_retry_now(self) -> bool:
        """今すぐリトライすべきかどうかを判定するのだ"""
        return time.time() >= self.next_retry_at
    
    def calculate_next_retry_time(self, base_delay: float) -> float:
        """次のリトライ時刻を指数バックオフで計算するのだ"""
        # 指数バックオフ: base_delay * (2 ^ attempt_count) + jitter
        delay = base_delay * (2 ** self.attempt_count)
        # 最大60秒に制限
        delay = min(delay, 60.0)
        # 多少のジッタを追加（±20%）
        import random
        jitter = delay * 0.2 * (random.random() - 0.5)
        return time.time() + delay + jitter


class RetryCache:
    """OCR失敗時のリトライキャッシュ管理なのだ"""
    
    def __init__(self, cache_dir: Path, max_attempts: int = 3, base_delay: float = 1.0):
        self.cache_dir = Path(cache_dir) / "retry"
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.tasks_file = self.cache_dir / "retry_tasks.json"
        
        # ディレクトリ作成
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # タスクリストを読み込み
        self._tasks: List[RetryTask] = self._load_tasks()
    
    def add_failed_task(
        self, 
        image_path: Path, 
        original_timestamp: str,
        error_message: str
    ) -> str:
        """失敗したOCRタスクをキャッシュに追加するのだ"""
        # タスクIDを生成（タイムスタンプベース）
        task_id = f"retry_{int(time.time() * 1000)}"
        
        # 画像ファイルをリトライキャッシュにコピー
        cached_image_path = self.cache_dir / f"{task_id}.jpg"
        
        try:
            shutil.copy2(image_path, cached_image_path)
            
            # リトライタスクを作成
            task = RetryTask(
                task_id=task_id,
                image_path=cached_image_path,
                created_at=time.time(),
                last_attempt_at=time.time(),
                attempt_count=1,  # 最初の失敗を1回目とカウント
                next_retry_at=time.time() + self.base_delay,
                original_timestamp=original_timestamp,
                error_message=error_message
            )
            
            # タスクリストに追加
            self._tasks.append(task)
            self._save_tasks()
            
            print(f"🔄 リトライタスク追加: {task_id} (次回: {self.base_delay}秒後)")
            return task_id
            
        except Exception as e:
            print(f"⚠️ リトライタスク追加失敗: {e}")
            return ""
    
    def get_ready_tasks(self) -> List[RetryTask]:
        """実行準備が整ったリトライタスクを取得するのだ"""
        ready_tasks = []
        current_time = time.time()
        
        for task in self._tasks:
            if task.should_retry_now() and task.attempt_count < self.max_attempts:
                ready_tasks.append(task)
        
        return ready_tasks
    
    def mark_task_attempted(self, task_id: str, success: bool, error_message: str = "") -> bool:
        """タスクの試行結果を記録するのだ"""
        for task in self._tasks:
            if task.task_id == task_id:
                task.last_attempt_at = time.time()
                task.attempt_count += 1
                
                if success:
                    # 成功時はタスクを削除
                    self._remove_task(task_id)
                    print(f"✅ リトライタスク成功: {task_id}")
                else:
                    # 失敗時は次のリトライ時間を設定
                    task.error_message = error_message
                    
                    if task.attempt_count >= self.max_attempts:
                        # 最大試行回数に達した場合は削除
                        self._remove_task(task_id)
                        print(f"❌ リトライタスク諦め: {task_id} (最大{self.max_attempts}回達成)")
                    else:
                        # 次のリトライ時間を計算
                        task.next_retry_at = task.calculate_next_retry_time(self.base_delay)
                        print(f"🔄 リトライタスク再スケジュール: {task_id} (試行{task.attempt_count}/{self.max_attempts})")
                
                self._save_tasks()
                return True
        
        return False
    
    def _remove_task(self, task_id: str) -> bool:
        """タスクとその画像ファイルを削除するのだ"""
        for i, task in enumerate(self._tasks):
            if task.task_id == task_id:
                # 画像ファイルを削除
                if task.image_path.exists():
                    task.image_path.unlink(missing_ok=True)
                
                # タスクリストから削除
                del self._tasks[i]
                return True
        
        return False
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """古いリトライタスクを削除するのだ"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0
        
        tasks_to_remove = []
        for task in self._tasks:
            if task.created_at < cutoff_time:
                tasks_to_remove.append(task.task_id)
        
        for task_id in tasks_to_remove:
            if self._remove_task(task_id):
                cleaned_count += 1
                print(f"🗑️ 古いリトライタスク削除: {task_id}")
        
        if cleaned_count > 0:
            self._save_tasks()
        
        return cleaned_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を返すのだ"""
        ready_count = len(self.get_ready_tasks())
        total_size = 0
        
        try:
            for task in self._tasks:
                if task.image_path.exists():
                    total_size += task.image_path.stat().st_size
        except Exception:
            pass
        
        return {
            "total_tasks": len(self._tasks),
            "ready_tasks": ready_count,
            "total_size_mb": total_size / (1024 * 1024),
            "cache_dir": str(self.cache_dir)
        }
    
    def _load_tasks(self) -> List[RetryTask]:
        """保存されたタスクリストを読み込むのだ"""
        if not self.tasks_file.exists():
            return []
        
        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            
            tasks = []
            for task_data in tasks_data:
                # Pathオブジェクトに変換
                task_data['image_path'] = Path(task_data['image_path'])
                tasks.append(RetryTask(**task_data))
            
            return tasks
            
        except Exception as e:
            print(f"⚠️ リトライタスクファイル読み込みエラー: {e}")
            return []
    
    def _save_tasks(self) -> None:
        """タスクリストを保存するのだ"""
        try:
            tasks_data = []
            for task in self._tasks:
                task_dict = asdict(task)
                # Pathオブジェクトを文字列に変換
                task_dict['image_path'] = str(task.image_path)
                tasks_data.append(task_dict)
            
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            print(f"⚠️ リトライタスクファイル保存エラー: {e}")
    
    def force_clear_all_tasks(self) -> int:
        """すべてのリトライタスクを強制削除するのだ（デバッグ用）"""
        cleared_count = len(self._tasks)
        
        # すべての画像ファイルを削除
        for task in self._tasks:
            if task.image_path.exists():
                task.image_path.unlink(missing_ok=True)
        
        # タスクリストをクリア
        self._tasks.clear()
        self._save_tasks()
        
        print(f"🗑️ 全リトライタスククリア: {cleared_count}個")
        return cleared_count

