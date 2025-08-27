"""keyframe フェーズ3: 設定＋キーログ＋スクリーンショット＋OCR＋JSONL出力なのだ"""
import signal
import sys
from datetime import datetime, timezone
from src.config import ConfigLoader
from src.scheduler import TimeSlicer
from src.keylogger import KeyLogger
from src.jsonl_writer import JsonlWriter
from src.screenshot import ScreenshotService
from src.active_window import ActiveWindowService
from src.ocr_worker import OcrWorker


def main():
    print("🎵 keyframe フェーズ3 開始なのだ")
    
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
        screenshot_service = ScreenshotService(config.data_dir / "cache")
        active_window_service = ActiveWindowService()
        ocr_worker = OcrWorker(config, jsonl_writer, config.data_dir / "cache")
        slicer = TimeSlicer(config.interval_sec)
        
        def record_typing_stats():
            """タイピング統計とスクリーンショットを記録してOCR処理するのだ"""
            now = datetime.now(timezone.utc)
            
            # スクリーンショット撮影なのだ
            screenshot_path = screenshot_service.capture_and_save(timestamp=now)
            screenshot_path_str = str(screenshot_path) if screenshot_path else None
            
            # アクティブウィンドウ情報取得なのだ
            window_info = active_window_service.get_active_window_info()
            
            # キーロガーから統計を取得（バッファもリセット）なのだ
            stats = key_logger.get_stats(reset_buffer=True)
            
            # JSONLに書き出し（OCR結果は後で更新）なのだ
            jsonl_writer.write_record(
                stats, 
                ts_utc=now, 
                interval_sec=config.interval_sec,
                screenshot_path=screenshot_path_str,
                active_app=window_info["active_app"],
                active_title=window_info["active_title"],
                ocr_text=""  # OCR結果は後で更新
            )
            
            # OCRワーカーにスクリーンショットを渡す（成功/失敗問わず削除される）
            ocr_success = False
            if screenshot_path:
                ocr_success = ocr_worker.add_screenshot_for_ocr(
                    screenshot_path, 
                    timestamp=now,
                    delete_original=True
                )
            
            # ログ出力なのだ
            print(f"⏰ {now.isoformat()} - KPM:{stats.kpm} KPS15:{stats.kps15:.1f} "
                  f"MedianMS:{stats.median_latency_ms:.1f} BS%:{stats.backspace_pct:.1f} "
                  f"Idle:{stats.idle} Total:{stats.total_keys_cum} "
                  f"App:{window_info['active_app']} SS:{'✅' if screenshot_path else '❌'} "
                  f"OCR:{'✅' if ocr_success else '🔄' if screenshot_path else '❌'}")
        
        slicer.add_callback(record_typing_stats, "typing_recorder")
        
        # OCRワーカーの定期処理を追加
        slicer.add_callback(ocr_worker.create_periodic_callback(), "ocr_worker")
        
        # Ctrl+C ハンドラなのだ
        def signal_handler(sig, frame):
            print("\n🛑 停止シグナル受信、終了処理中なのだ...")
            key_logger.stop()
            slicer.stop()
            print(f"📁 データファイル: {jsonl_writer.get_today_file_path()}")
            print(f"📊 今日のレコード数: {jsonl_writer.count_records()}")
            
            # キャッシュ統計表示
            cache_stats = screenshot_service.get_cache_stats()
            print(f"🖼️  キャッシュファイル数: {cache_stats.get('file_count', 0)}")
            print(f"💾 キャッシュサイズ: {cache_stats.get('total_size_mb', 0):.1f}MB")
            
            # OCR統計表示
            ocr_stats = ocr_worker.get_stats()
            print(f"🔍 OCR処理数: {ocr_stats['successful_ocr']}成功/{ocr_stats['failed_ocr']}失敗")
            print(f"🔄 リトライキュー: {ocr_stats['retry_queue'].get('total_tasks', 0)}個")
            
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
        
        # アクティブウィンドウサービス状態確認
        if active_window_service.is_available():
            print("✅ アクティブウィンドウ取得利用可能なのだ")
        else:
            print("⚠️  アクティブウィンドウ取得利用不可（OS非対応 or 権限不足）")
        
        # スクリーンショットサービス確認
        monitors = screenshot_service.get_available_monitors()
        if monitors and not any("error" in m for m in monitors):
            print(f"✅ スクリーンショット利用可能（{len(monitors)}モニタ検出）")
        else:
            print("⚠️  スクリーンショット取得でエラーが発生する可能性あり")
        
        # OCRサービス確認
        if config.ocr_enabled:
            if ocr_worker.test_ocr_connection():
                print(f"✅ Azure OpenAI OCR利用可能（モデル: {config.azure_openai_model}）")
            else:
                print("⚠️  Azure OpenAI OCR接続失敗（APIキー・エンドポイントを確認）")
        else:
            print("ℹ️  OCRは無効化されています")
        
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
