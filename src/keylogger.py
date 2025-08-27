"""タイピング指標を記録するキーロガーなのだ"""
import time
import statistics
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pynput import keyboard
import threading


@dataclass
class KeyEvent:
    """キーイベント情報なのだ"""
    timestamp: float
    key_name: str
    is_backspace: bool = False


@dataclass
class TypingStats:
    """タイピング統計なのだ"""
    kpm: int = 0                    # Keys Per Minute
    kps15: float = 0.0              # Keys Per Second (直近15秒)
    median_latency_ms: float = 0.0  # キー間隔の中央値 (ms)
    backspace_pct: float = 0.0      # Backspace比率 (%)
    idle: bool = True               # アイドル状態 (直近30秒でキー入力なし)
    total_keys_cum: int = 0         # 累積キー数


class KeyLogger:
    """キー入力を記録して統計を計算するロガーなのだ"""
    
    def __init__(self):
        self.events: List[KeyEvent] = []
        self.total_keys_cumulative = 0
        self._listener: Optional[keyboard.Listener] = None
        self._running = False
        self._lock = threading.Lock()
        
        # 統計計算用の時間窓なのだ
        self.WINDOW_15SEC = 15.0
        self.WINDOW_IDLE = 30.0
    
    def start(self) -> None:
        """キーロギングを開始するのだ"""
        if self._running:
            return
        
        self._running = True
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._listener.start()
        except Exception as e:
            self._running = False
            raise RuntimeError(f"キーロガー開始に失敗: {e}")
    
    def stop(self) -> None:
        """キーロギングを停止するのだ"""
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None
    
    def _on_key_press(self, key) -> None:
        """キー押下イベントハンドラなのだ"""
        if not self._running:
            return
        
        key_name = self._get_key_name(key)
        is_backspace = (key == keyboard.Key.backspace)
        
        event = KeyEvent(
            timestamp=time.time(),
            key_name=key_name,
            is_backspace=is_backspace
        )
        
        with self._lock:
            self.events.append(event)
            self.total_keys_cumulative += 1
    
    def _on_key_release(self, key) -> None:
        """キーリリースイベントハンドラ（使用しない）なのだ"""
        pass
    
    def _get_key_name(self, key) -> str:
        """キー名を文字列として取得するのだ"""
        try:
            if hasattr(key, 'char') and key.char:
                return key.char
            else:
                return str(key).replace('Key.', '')
        except AttributeError:
            return str(key)
    
    def get_stats(self, reset_buffer: bool = False) -> TypingStats:
        """現在の統計を取得するのだ"""
        with self._lock:
            current_time = time.time()
            
            # 1分間のイベントを取得なのだ
            minute_events = [
                e for e in self.events 
                if current_time - e.timestamp <= 60.0
            ]
            
            # 直近15秒のイベントを取得なのだ
            recent_events = [
                e for e in self.events 
                if current_time - e.timestamp <= self.WINDOW_15SEC
            ]
            
            # 直近30秒のイベントを取得（アイドル判定用）なのだ
            idle_events = [
                e for e in self.events 
                if current_time - e.timestamp <= self.WINDOW_IDLE
            ]
            
            # 統計計算なのだ
            stats = self._calculate_stats(
                minute_events, 
                recent_events, 
                idle_events,
                current_time
            )
            
            # バッファリセットが要求されている場合なのだ
            if reset_buffer:
                # 直近1分より古いイベントを削除なのだ
                self.events = minute_events
            
            return stats
    
    def _calculate_stats(
        self, 
        minute_events: List[KeyEvent], 
        recent_events: List[KeyEvent],
        idle_events: List[KeyEvent],
        current_time: float
    ) -> TypingStats:
        """統計を計算するのだ"""
        
        # KPM: Keys Per Minute (1分間のキー数)
        kpm = len(minute_events)
        
        # KPS15: 直近15秒間の平均キー数/秒
        kps15 = len(recent_events) / self.WINDOW_15SEC if recent_events else 0.0
        
        # median_latency_ms: キー間隔の中央値 (ms)
        median_latency_ms = self._calculate_median_latency(minute_events)
        
        # backspace_pct: Backspace比率 (%)
        backspace_count = sum(1 for e in minute_events if e.is_backspace)
        backspace_pct = (backspace_count / len(minute_events) * 100.0) if minute_events else 0.0
        
        # idle: アイドル状態判定（直近30秒でキー入力なし）
        idle = len(idle_events) == 0
        
        return TypingStats(
            kpm=kpm,
            kps15=kps15,
            median_latency_ms=median_latency_ms,
            backspace_pct=backspace_pct,
            idle=idle,
            total_keys_cum=self.total_keys_cumulative
        )
    
    def _calculate_median_latency(self, events: List[KeyEvent]) -> float:
        """キー間隔の中央値を計算するのだ (ms)"""
        if len(events) < 2:
            return 0.0
        
        # タイムスタンプ順にソート済みと仮定
        intervals = []
        for i in range(1, len(events)):
            interval_ms = (events[i].timestamp - events[i-1].timestamp) * 1000.0
            intervals.append(interval_ms)
        
        return statistics.median(intervals) if intervals else 0.0
    
    def is_running(self) -> bool:
        """実行中かどうかを返すのだ"""
        return self._running
    
    def get_event_count(self) -> int:
        """現在のイベント数を返すのだ（デバッグ用）"""
        with self._lock:
            return len(self.events)
