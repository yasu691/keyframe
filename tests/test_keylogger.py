"""KeyLogger のテストなのだ"""
import time
import threading
from unittest.mock import Mock, patch
import pytest

from src.keylogger import KeyLogger, KeyEvent, TypingStats


class TestKeyLogger:
    """KeyLogger テストクラスなのだ"""
    
    def test_stats_calculation_empty(self):
        """空の状態での統計計算テストなのだ"""
        logger = KeyLogger()
        stats = logger.get_stats()
        
        assert stats.kpm == 0
        assert stats.kps15 == 0.0
        assert stats.median_latency_ms == 0.0
        assert stats.backspace_pct == 0.0
        assert stats.idle is True
        assert stats.total_keys_cum == 0
    
    def test_stats_calculation_with_events(self):
        """イベント付きの統計計算テストなのだ"""
        logger = KeyLogger()
        current_time = time.time()
        
        # 疑似イベントを手動で追加なのだ
        with logger._lock:
            # 1分間に60個のキー（KPM=60）なのだ
            for i in range(60):
                event = KeyEvent(
                    timestamp=current_time - 59 + i,  # 59秒前から現在まで（1分間に収まる）
                    key_name=chr(ord('a') + (i % 26)),
                    is_backspace=(i % 10 == 9)  # 10個に1個がBackspace
                )
                logger.events.append(event)
                logger.total_keys_cumulative += 1
        
        stats = logger.get_stats()
        
        assert stats.kpm == 60
        assert stats.backspace_pct == 10.0  # 10%がBackspace
        assert stats.idle is False  # キーがあるのでアイドルではない
        assert stats.total_keys_cum == 60
        # KPS15は直近15秒のキー数/15 = 15/15 = 1.0
        assert abs(stats.kps15 - 1.0) < 0.1
    
    def test_median_latency_calculation(self):
        """中央値計算テストなのだ"""
        logger = KeyLogger()
        current_time = time.time()
        
        # 100ms間隔でキーイベントを作成なのだ
        intervals = [0.1, 0.15, 0.2, 0.25, 0.3]  # 100ms, 150ms, 200ms, 250ms, 300ms
        
        with logger._lock:
            timestamp = current_time - 1.0  # 1秒前から開始
            for interval in intervals:
                event = KeyEvent(
                    timestamp=timestamp,
                    key_name='a',
                    is_backspace=False
                )
                logger.events.append(event)
                timestamp += interval
                logger.total_keys_cumulative += 1
            
            # 最後のイベント
            event = KeyEvent(
                timestamp=timestamp,
                key_name='a',
                is_backspace=False
            )
            logger.events.append(event)
            logger.total_keys_cumulative += 1
        
        stats = logger.get_stats()
        
        # 中央値は200ms (0.2 * 1000)
        assert abs(stats.median_latency_ms - 200.0) < 1.0
    
    def test_idle_detection(self):
        """アイドル検出テストなのだ"""
        logger = KeyLogger()
        current_time = time.time()
        
        # 35秒前のキー（アイドル判定される）なのだ
        with logger._lock:
            old_event = KeyEvent(
                timestamp=current_time - 35.0,
                key_name='a',
                is_backspace=False
            )
            logger.events.append(old_event)
            logger.total_keys_cumulative += 1
        
        stats = logger.get_stats()
        assert stats.idle is True  # 30秒以内にキーがないのでアイドル
        
        # 25秒前のキー（アクティブ判定される）なのだ
        with logger._lock:
            recent_event = KeyEvent(
                timestamp=current_time - 25.0,
                key_name='b',
                is_backspace=False
            )
            logger.events.append(recent_event)
            logger.total_keys_cumulative += 1
        
        stats = logger.get_stats()
        assert stats.idle is False  # 30秒以内にキーがあるのでアクティブ
    
    def test_backspace_percentage(self):
        """Backspace比率計算テストなのだ"""
        logger = KeyLogger()
        current_time = time.time()
        
        # 10個中3個がBackspaceなのだ
        with logger._lock:
            for i in range(10):
                event = KeyEvent(
                    timestamp=current_time - 30 + i * 3,
                    key_name='backspace' if i < 3 else chr(ord('a') + i),
                    is_backspace=(i < 3)
                )
                logger.events.append(event)
                logger.total_keys_cumulative += 1
        
        stats = logger.get_stats()
        assert abs(stats.backspace_pct - 30.0) < 0.1  # 30%
    
    def test_kps15_calculation(self):
        """KPS15計算テストなのだ"""
        logger = KeyLogger()
        current_time = time.time()
        
        # 直近15秒に30個のキー（KPS15=2.0）なのだ
        with logger._lock:
            for i in range(30):
                event = KeyEvent(
                    timestamp=current_time - 15.0 + i * 0.5,  # 0.5秒間隔
                    key_name=chr(ord('a') + (i % 26)),
                    is_backspace=False
                )
                logger.events.append(event)
                logger.total_keys_cumulative += 1
        
        stats = logger.get_stats()
        assert abs(stats.kps15 - 2.0) < 0.1  # 30キー/15秒 = 2.0
    
    def test_buffer_reset(self):
        """バッファリセット機能テストなのだ"""
        logger = KeyLogger()
        current_time = time.time()
        
        # 古いイベント（70秒前）と新しいイベント（30秒前）を追加なのだ
        with logger._lock:
            old_event = KeyEvent(
                timestamp=current_time - 70.0,
                key_name='old',
                is_backspace=False
            )
            recent_event = KeyEvent(
                timestamp=current_time - 30.0,
                key_name='recent',
                is_backspace=False
            )
            logger.events.extend([old_event, recent_event])
            logger.total_keys_cumulative += 2
        
        # リセットなしで取得
        stats1 = logger.get_stats(reset_buffer=False)
        assert logger.get_event_count() == 2
        
        # リセットありで取得
        stats2 = logger.get_stats(reset_buffer=True)
        # 1分以内のイベントのみ残る（30秒前のイベント1個）
        assert logger.get_event_count() == 1
    
    @patch('src.keylogger.keyboard.Listener')
    def test_start_stop_lifecycle(self, mock_listener_class):
        """開始・停止ライフサイクルテストなのだ"""
        mock_listener = Mock()
        mock_listener_class.return_value = mock_listener
        
        logger = KeyLogger()
        
        assert not logger.is_running()
        
        # 開始テスト
        logger.start()
        assert logger.is_running()
        mock_listener_class.assert_called_once()
        mock_listener.start.assert_called_once()
        
        # 停止テスト
        logger.stop()
        assert not logger.is_running()
        mock_listener.stop.assert_called_once()
    
    def test_get_key_name(self):
        """キー名取得テストなのだ"""
        logger = KeyLogger()
        
        # 通常文字キーのモック
        class CharKey:
            def __init__(self, char):
                self.char = char
        
        # 特殊キーのモック
        class SpecialKey:
            def __str__(self):
                return "Key.space"
        
        assert logger._get_key_name(CharKey('a')) == 'a'
        assert logger._get_key_name(SpecialKey()) == 'space'  # Key.が削除される
