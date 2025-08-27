"""ActiveWindowService のテストなのだ"""
import sys
from unittest.mock import Mock, patch
import pytest

from src.active_window import ActiveWindowService


class TestActiveWindowService:
    """ActiveWindowService テストクラスなのだ"""
    
    def test_service_initialization_real_macos(self):
        """実際のmacOS環境での初期化テストなのだ"""
        if sys.platform != "darwin":
            pytest.skip("macOS環境でのみ実行")
        
        service = ActiveWindowService()
        assert service.platform == "darwin"
        # macOS環境では実際のNSWorkspaceが利用可能なはず
        assert service.is_available() in [True, False]  # 権限次第
    
    def test_service_initialization_unsupported_platform(self):
        """未対応プラットフォームでの初期化テストなのだ"""
        with patch('sys.platform', 'linux'):
            service = ActiveWindowService()
            
            assert service.platform == 'linux'
            assert service.available is False
    
    def test_get_active_window_info_service_unavailable(self):
        """サービス利用不可の場合のテストなのだ"""
        with patch('sys.platform', 'linux'):
            service = ActiveWindowService()
            
            result = service.get_active_window_info()
            
            assert result["active_app"] == ""
            assert result["active_title"] == ""
    
    def test_is_available(self):
        """利用可能性チェックテストなのだ"""
        with patch('sys.platform', 'linux'):
            service = ActiveWindowService()
            assert service.is_available() is False
    
    def test_get_platform_info(self):
        """プラットフォーム情報取得テストなのだ"""
        service = ActiveWindowService()
        info = service.get_platform_info()
        
        assert "platform" in info
        assert "available" in info  
        assert "supported_features" in info
        
        # 実際のプラットフォームに応じた検証
        if sys.platform == "darwin":
            assert info["platform"] == "darwin"
        elif sys.platform == "win32":
            assert info["platform"] == "win32"
        else:
            assert info["supported_features"] == "none"
    
    def test_get_active_window_info_real_environment(self):
        """実環境でのアクティブウィンドウ情報取得テストなのだ"""
        service = ActiveWindowService()
        result = service.get_active_window_info()
        
        # 結果の構造が正しいことを確認（値は環境依存）
        assert "active_app" in result
        assert "active_title" in result
        assert isinstance(result["active_app"], str)
        assert isinstance(result["active_title"], str)
