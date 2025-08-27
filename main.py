"""keyframe フェーズ1: 設定＋キーログ＋JSONL出力なのだ"""
import signal
import sys
from datetime import datetime, timezone
from src.config import ConfigLoader
from src.scheduler import TimeSlicer
from src.keylogger import KeyLogger
from src.jsonl_writer import JsonlWriter


def main():
    print("🎵 keyframe フェーズ1 開始なのだ")
    
    try:
        # 設定読み込みなのだ
        loader = ConfigLoader()
        config = loader.load()
        
        print(f"✅ 設定読み込み完了なのだ")
        print(f"   - Azure エンドポイント: {config.azure_openai_endpoint}")
        print(f"   - データディレクトリ: {config.data_dir}")
        print(f"   - 実行間隔: {config.interval_sec}秒")
        
        # コンポーネント初期化なのだ
        key_logger = KeyLogger()
        jsonl_writer = JsonlWriter(config.data_dir)
        slicer = TimeSlicer(config.interval_sec)
        
        def record_typing_stats():
            """タイピング統計を記録するのだ"""
            now = datetime.now(timezone.utc)
            
            # キーロガーから統計を取得（バッファもリセット）なのだ
            stats = key_logger.get_stats(reset_buffer=True)
            
            # JSONLに書き出しなのだ
            jsonl_writer.write_record(stats, ts_utc=now, interval_sec=config.interval_sec)
            
            # ログ出力なのだ
            print(f"⏰ {now.isoformat()} - KPM:{stats.kpm} KPS15:{stats.kps15:.1f} "
                  f"MedianMS:{stats.median_latency_ms:.1f} BS%:{stats.backspace_pct:.1f} "
                  f"Idle:{stats.idle} Total:{stats.total_keys_cum}")
        
        slicer.add_callback(record_typing_stats, "typing_recorder")
        
        # Ctrl+C ハンドラなのだ
        def signal_handler(sig, frame):
            print("\n🛑 停止シグナル受信、終了処理中なのだ...")
            key_logger.stop()
            slicer.stop()
            print(f"📁 データファイル: {jsonl_writer.get_today_file_path()}")
            print(f"📊 今日のレコード数: {jsonl_writer.count_records()}")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # キーロガー開始なのだ
        try:
            key_logger.start()
            print("✅ キーロガー開始成功なのだ")
        except RuntimeError as e:
            print(f"⚠️  キーロガー開始失敗: {e}")
            print("macOSでは「システム環境設定 > プライバシーとセキュリティ > アクセシビリティ」で許可が必要なのだ")
            print("それでも統計記録は継続するのだ（キー数は0になる）")
        
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
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
