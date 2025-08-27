"""タイムスライサ: 定期的にコールバックを実行するスケジューラなのだ"""
import threading
import time
from typing import Callable, List
from dataclasses import dataclass


@dataclass
class CallbackInfo:
    """コールバック情報なのだ"""
    callback: Callable[[], None]
    name: str


class TimeSlicer:
    """定期実行スケジューラなのだ"""
    
    def __init__(self, interval_sec: int = 60):
        self.interval_sec = interval_sec
        self.callbacks: List[CallbackInfo] = []
        self._timer: threading.Timer | None = None
        self._running = False
        self._lock = threading.Lock()
    
    def add_callback(self, callback: Callable[[], None], name: str = "unnamed") -> None:
        """コールバックを登録するのだ"""
        with self._lock:
            self.callbacks.append(CallbackInfo(callback, name))
    
    def start(self) -> None:
        """スケジューラを開始するのだ"""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._schedule_next()
    
    def stop(self) -> None:
        """スケジューラを停止するのだ"""
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None
    
    def _schedule_next(self) -> None:
        """次のタイマーをセットするのだ"""
        if not self._running:
            return
        
        self._timer = threading.Timer(self.interval_sec, self._execute_callbacks)
        self._timer.daemon = True
        self._timer.start()
    
    def _execute_callbacks(self) -> None:
        """全コールバックを実行して次をスケジュールするのだ"""
        with self._lock:
            if not self._running:
                return
            
            # コールバック実行なのだ
            for callback_info in self.callbacks:
                try:
                    callback_info.callback()
                except Exception as e:
                    # TODO: ログ出力を後で整備するのだ
                    print(f"コールバック '{callback_info.name}' でエラー: {e}")
            
            # 次をスケジュールなのだ
            self._schedule_next()
    
    def is_running(self) -> bool:
        """実行中かどうかを返すのだ"""
        with self._lock:
            return self._running
    
    def get_callback_count(self) -> int:
        """登録されたコールバック数を返すのだ"""
        with self._lock:
            return len(self.callbacks)
