"""TimeSlicer のテストなのだ"""
import time
import threading
from src.scheduler import TimeSlicer


class TestTimeSlicer:
    """TimeSlicer テストクラスなのだ"""
    
    def test_callback_registration(self):
        """コールバック登録のテストなのだ"""
        slicer = TimeSlicer(interval_sec=1)
        
        def dummy_callback():
            pass
        
        # コールバック登録なのだ
        slicer.add_callback(dummy_callback, "test_callback")
        
        assert slicer.get_callback_count() == 1
        assert not slicer.is_running()
    
    def test_callback_execution(self):
        """コールバックが実行されることをテストするのだ"""
        slicer = TimeSlicer(interval_sec=1)  # 1秒間隔でテストなのだ
        
        # カウンタ用の共有状態なのだ
        call_count = {"value": 0}
        call_times = []
        
        def test_callback():
            call_count["value"] += 1
            call_times.append(time.time())
        
        # コールバック登録して開始なのだ
        slicer.add_callback(test_callback, "test_counter")
        slicer.start()
        
        try:
            # 2.5秒待って、2回呼ばれることを確認なのだ
            time.sleep(2.5)
            slicer.stop()
            
            assert call_count["value"] == 2, f"期待: 2回, 実際: {call_count['value']}回"
            
            # 呼び出し間隔が約1秒であることを確認なのだ
            if len(call_times) >= 2:
                interval = call_times[1] - call_times[0]
                assert 0.8 <= interval <= 1.2, f"間隔が異常: {interval}秒"
        
        finally:
            slicer.stop()
    
    def test_multiple_callbacks(self):
        """複数のコールバックが実行されることをテストするのだ"""
        slicer = TimeSlicer(interval_sec=1)
        
        results = {"callback1": 0, "callback2": 0}
        
        def callback1():
            results["callback1"] += 1
        
        def callback2():
            results["callback2"] += 1
        
        # 複数コールバック登録なのだ
        slicer.add_callback(callback1, "cb1")
        slicer.add_callback(callback2, "cb2")
        slicer.start()
        
        try:
            time.sleep(1.5)  # 1回実行される時間なのだ
            slicer.stop()
            
            assert results["callback1"] == 1
            assert results["callback2"] == 1
            assert slicer.get_callback_count() == 2
        
        finally:
            slicer.stop()
    
    def test_callback_error_handling(self):
        """コールバックエラーが他のコールバックに影響しないことをテストするのだ"""
        slicer = TimeSlicer(interval_sec=1)
        
        success_count = {"value": 0}
        
        def error_callback():
            raise ValueError("テスト例外なのだ")
        
        def success_callback():
            success_count["value"] += 1
        
        # エラーを出すコールバックと正常なコールバックを登録なのだ
        slicer.add_callback(error_callback, "error_cb")
        slicer.add_callback(success_callback, "success_cb")
        slicer.start()
        
        try:
            time.sleep(1.5)
            slicer.stop()
            
            # エラーがあっても正常なコールバックは実行されるのだ
            assert success_count["value"] == 1
        
        finally:
            slicer.stop()
    
    def test_start_stop_lifecycle(self):
        """開始・停止のライフサイクルをテストするのだ"""
        slicer = TimeSlicer(interval_sec=1)
        
        assert not slicer.is_running()
        
        # 開始なのだ
        slicer.start()
        assert slicer.is_running()
        
        # 二重開始は無視されるのだ
        slicer.start()
        assert slicer.is_running()
        
        # 停止なのだ
        slicer.stop()
        assert not slicer.is_running()
        
        # 二重停止も安全なのだ
        slicer.stop()
        assert not slicer.is_running()
