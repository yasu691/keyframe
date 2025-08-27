"""アクティブウィンドウ情報取得サービスなのだ"""
import sys
from typing import Dict, Optional


class ActiveWindowService:
    """アクティブウィンドウ情報取得サービス（OS別実装）なのだ"""
    
    def __init__(self):
        self.platform = sys.platform
        self._init_platform_specific()
    
    def _init_platform_specific(self) -> None:
        """プラットフォーム固有の初期化なのだ"""
        if self.platform == "darwin":
            # macOS用インポート
            try:
                from AppKit import NSWorkspace
                self.workspace = NSWorkspace.sharedWorkspace()
                self.available = True
            except ImportError as e:
                print(f"⚠️ macOS NSWorkspace インポートエラー: {e}")
                self.available = False
                
        elif self.platform == "win32":
            # Windows用インポート
            try:
                import win32gui
                import win32process
                import psutil
                self.win32gui = win32gui
                self.win32process = win32process
                self.psutil = psutil
                self.available = True
            except ImportError as e:
                print(f"⚠️ Windows pywin32/psutil インポートエラー: {e}")
                self.available = False
        else:
            print(f"⚠️ 未対応プラットフォーム: {self.platform}")
            self.available = False
    
    def get_active_window_info(self) -> Dict[str, str]:
        """アクティブウィンドウの情報を取得するのだ"""
        if not self.available:
            return {"active_app": "", "active_title": ""}
        
        try:
            if self.platform == "darwin":
                return self._get_macos_active_window()
            elif self.platform == "win32":
                return self._get_windows_active_window()
            else:
                return {"active_app": "", "active_title": ""}
                
        except Exception as e:
            print(f"⚠️ アクティブウィンドウ情報取得エラー: {e}")
            return {"active_app": "", "active_title": ""}
    
    def _get_macos_active_window(self) -> Dict[str, str]:
        """macOSでアクティブウィンドウ情報を取得するのだ"""
        try:
            # NSWorkspaceでアクティブアプリケーションを取得
            active_app = self.workspace.activeApplication()
            
            if active_app:
                app_name = active_app.get("NSApplicationName", "")
                # macOSでウィンドウタイトル取得は複雑なのでアプリ名のみ
                # 必要に応じてAXUIElementやCoreGraphicsを使用
                return {
                    "active_app": app_name,
                    "active_title": ""  # macOSでは取得困難（権限必要）
                }
            else:
                return {"active_app": "", "active_title": ""}
                
        except Exception as e:
            print(f"⚠️ macOSアクティブウィンドウ取得エラー: {e}")
            return {"active_app": "", "active_title": ""}
    
    def _get_windows_active_window(self) -> Dict[str, str]:
        """Windowsでアクティブウィンドウ情報を取得するのだ"""
        try:
            # フォアグラウンドウィンドウハンドルを取得
            hwnd = self.win32gui.GetForegroundWindow()
            
            if hwnd:
                # ウィンドウタイトルを取得
                window_title = self.win32gui.GetWindowText(hwnd)
                
                # プロセスIDを取得
                _, process_id = self.win32process.GetWindowThreadProcessId(hwnd)
                
                # プロセス名を取得
                try:
                    process = self.psutil.Process(process_id)
                    app_name = process.name()
                except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                    app_name = ""
                
                return {
                    "active_app": app_name,
                    "active_title": window_title
                }
            else:
                return {"active_app": "", "active_title": ""}
                
        except Exception as e:
            print(f"⚠️ Windowsアクティブウィンドウ取得エラー: {e}")
            return {"active_app": "", "active_title": ""}
    
    def is_available(self) -> bool:
        """サービスが利用可能かどうかを返すのだ"""
        return self.available
    
    def get_platform_info(self) -> Dict[str, str]:
        """プラットフォーム情報を返すのだ（デバッグ用）"""
        return {
            "platform": self.platform,
            "available": str(self.available),
            "supported_features": self._get_supported_features()
        }
    
    def _get_supported_features(self) -> str:
        """サポートされている機能を返すのだ"""
        if not self.available:
            return "none"
        
        if self.platform == "darwin":
            return "app_name_only"  # macOSはアプリ名のみ
        elif self.platform == "win32":
            return "app_name_and_title"  # Windowsはアプリ名+タイトル
        else:
            return "none"

