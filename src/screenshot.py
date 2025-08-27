"""スクリーンショット撮影・保存サービスなのだ"""
import time
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import mss


class ScreenshotService:
    """スクリーンショット撮影・保存サービスなのだ"""
    
    def __init__(self, cache_dir: Path, max_files: int = 500, max_size_gb: float = 2.0):
        self.cache_dir = Path(cache_dir)
        self.max_files = max_files
        self.max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)  # GB to bytes
        
        # キャッシュディレクトリを作成
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def capture_and_save(
        self, 
        timestamp: Optional[datetime] = None,
        monitor_index: int = 1  # 0=全画面, 1=メインモニタ
    ) -> Optional[Path]:
        """スクリーンショットを撮影し、キャッシュに保存するのだ"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        try:
            # mssでスクリーンショット撮影
            with mss.mss() as sct:
                monitors = sct.monitors
                
                # モニタ選択（インデックス範囲外なら最初のモニタ）
                if monitor_index >= len(monitors):
                    monitor_index = 1 if len(monitors) > 1 else 0
                
                monitor = monitors[monitor_index]
                screenshot = sct.grab(monitor)
            
            # PIL Imageに変換（BGRAからRGBへ）
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # 1920px長辺リサイズ
            resized_img = self._resize_to_max_dimension(img, 1920)
            
            # 日別サブディレクトリを作成
            date_str = timestamp.strftime("%Y-%m-%d")
            daily_dir = self.cache_dir / date_str
            daily_dir.mkdir(exist_ok=True)
            
            # ファイル名生成（タイムスタンプ + ミリ秒）
            file_name = timestamp.strftime("%H-%M-%S") + f"-{timestamp.microsecond // 1000:03d}.jpg"
            file_path = daily_dir / file_name
            
            # JPEG品質70で保存
            resized_img.save(file_path, "JPEG", quality=70, optimize=True)
            
            # キュー管理（上限チェック＋古いファイル削除）
            self._manage_cache_size()
            
            return file_path
            
        except Exception as e:
            # 撮影失敗時はログ出力のみ（例外は再発生させない）
            print(f"⚠️ スクリーンショット撮影失敗: {e}")
            return None
    
    def _resize_to_max_dimension(self, img: Image.Image, max_dim: int) -> Image.Image:
        """長辺を指定サイズにリサイズするのだ"""
        width, height = img.size
        max_current = max(width, height)
        
        if max_current <= max_dim:
            return img  # リサイズ不要
        
        # アスペクト比を維持してリサイズ
        scale = max_dim / max_current
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def _manage_cache_size(self) -> None:
        """キャッシュサイズ管理: 上限超過時は古いファイルを削除するのだ"""
        try:
            # 全ファイルを取得（作成時刻順）
            all_files = []
            for file_path in self.cache_dir.rglob("*.jpg"):
                if file_path.is_file():
                    stat = file_path.stat()
                    all_files.append((stat.st_ctime, stat.st_size, file_path))
            
            # 作成時刻順でソート（古い順）
            all_files.sort(key=lambda x: x[0])
            
            # ファイル数チェック
            if len(all_files) > self.max_files:
                excess_count = len(all_files) - self.max_files
                for i in range(excess_count):
                    _, _, file_path = all_files[i]
                    file_path.unlink(missing_ok=True)
                    print(f"🗑️ キャッシュファイル削除（枚数上限）: {file_path.name}")
                
                # 削除されたファイルをリストから除外
                all_files = all_files[excess_count:]
            
            # サイズチェック
            total_size = sum(size for _, size, _ in all_files)
            if total_size > self.max_size_bytes:
                # 古い順にファイルを削除してサイズ上限以下にする
                for _, size, file_path in all_files:
                    if total_size <= self.max_size_bytes:
                        break
                    
                    file_path.unlink(missing_ok=True)
                    total_size -= size
                    print(f"🗑️ キャッシュファイル削除（サイズ上限）: {file_path.name}")
            
        except Exception as e:
            print(f"⚠️ キャッシュ管理エラー: {e}")
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """指定時間より古いファイルを削除（孤児掃除）するのだ"""
        cleaned_count = 0
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        try:
            for file_path in self.cache_dir.rglob("*.jpg"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink(missing_ok=True)
                    cleaned_count += 1
                    print(f"🗑️ 古いキャッシュファイル削除: {file_path.name}")
            
            # 空の日別ディレクトリも削除
            for dir_path in self.cache_dir.iterdir():
                if dir_path.is_dir():
                    try:
                        # ディレクトリが空なら削除
                        dir_path.rmdir()
                        print(f"🗑️ 空ディレクトリ削除: {dir_path.name}")
                    except OSError:
                        # 空でない場合は何もしない
                        pass
            
        except Exception as e:
            print(f"⚠️ 古いファイル掃除エラー: {e}")
        
        return cleaned_count
    
    def get_cache_stats(self) -> dict:
        """キャッシュ統計を返すのだ（デバッグ用）"""
        try:
            files = list(self.cache_dir.rglob("*.jpg"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            
            return {
                "file_count": len(files),
                "total_size_mb": total_size / (1024 * 1024),
                "cache_dir": str(self.cache_dir)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_available_monitors(self) -> list:
        """利用可能なモニタ情報を返すのだ"""
        try:
            with mss.mss() as sct:
                monitors = sct.monitors
                return [
                    {
                        "index": i,
                        "width": monitor["width"],
                        "height": monitor["height"],
                        "left": monitor["left"],
                        "top": monitor["top"]
                    }
                    for i, monitor in enumerate(monitors)
                ]
        except Exception as e:
            return [{"error": str(e)}]
