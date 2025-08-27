"""keyframe プロトタイプ: フェーズ0 設定＋スケジューラのサンプルなのだ"""
import signal
import sys
from datetime import datetime, timezone
from src.config import ConfigLoader
from src.scheduler import TimeSlicer


def main():
    print("🎵 keyframe プロトタイプ開始なのだ")
    
    try:
        # 設定読み込みなのだ
        loader = ConfigLoader()
        config = loader.load()
        
        print(f"✅ 設定読み込み完了なのだ")
        print(f"   - Azure エンドポイント: {config.azure_openai_endpoint}")
        print(f"   - データディレクトリ: {config.data_dir}")
        print(f"   - 実行間隔: {config.interval_sec}秒")
        
        # スケジューラ開始なのだ
        slicer = TimeSlicer(config.interval_sec)
        
        def tick_callback():
            now = datetime.now(timezone.utc).isoformat()
            print(f"⏰ {now} - tick! (フェーズ0プロトタイプ)")
        
        slicer.add_callback(tick_callback, "prototype_tick")
        
        # Ctrl+C ハンドラなのだ
        def signal_handler(sig, frame):
            print("\n🛑 停止シグナル受信、終了するのだ...")
            slicer.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        print("🚀 スケジューラ開始なのだ (Ctrl+C で停止)")
        slicer.start()
        
        # メインスレッドは待機なのだ
        try:
            while slicer.is_running():
                signal.pause()
        except AttributeError:
            # Windows では signal.pause() がないので time.sleep を使うのだ
            import time
            while slicer.is_running():
                time.sleep(0.5)
        
    except ValueError as e:
        print(f"❌ 設定エラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
