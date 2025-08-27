"""ConfigLoader のテストなのだ"""
import os
import tempfile
from pathlib import Path
import pytest

from src.config import ConfigLoader, Config


class TestConfigLoader:
    """ConfigLoader テストクラスなのだ"""
    
    def test_load_from_env_only(self, monkeypatch):
        """環境変数のみから設定を読み込むテストなのだ"""
        # 環境変数をセットなのだ
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test-env.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_KEY", "env-test-key")
        monkeypatch.setenv("DATA_DIR", "/tmp/env-test")
        monkeypatch.setenv("INTERVAL_SEC", "120")
        
        # 存在しないINIパスで初期化なのだ
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "nonexistent.ini"
            loader = ConfigLoader(config_path)
            config = loader.load()
        
        assert config.azure_openai_endpoint == "https://test-env.openai.azure.com"
        assert config.azure_openai_key == "env-test-key"
        assert config.data_dir == Path("/tmp/env-test")
        assert config.interval_sec == 120
    
    def test_load_from_ini_only(self, monkeypatch):
        """INIファイルのみから設定を読み込むテストなのだ"""
        # 環境変数をクリアなのだ
        for env_key in ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY", "DATA_DIR", "INTERVAL_SEC"]:
            monkeypatch.delenv(env_key, raising=False)
        
        # テスト用INIファイルを作成なのだ
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "test.ini"
            config_path.write_text("""
[azure]
endpoint = https://test-ini.openai.azure.com
key = ini-test-key

[paths]
data_dir = /tmp/ini-test

[timing]
interval_sec = 90
""")
            
            loader = ConfigLoader(config_path)
            config = loader.load()
        
        assert config.azure_openai_endpoint == "https://test-ini.openai.azure.com"
        assert config.azure_openai_key == "ini-test-key"
        assert config.data_dir == Path("/tmp/ini-test")
        assert config.interval_sec == 90
    
    def test_env_overrides_ini(self, monkeypatch):
        """環境変数がINIファイルを上書きすることを確認するテストなのだ"""
        # INIファイルを作成なのだ
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "test.ini"
            config_path.write_text("""
[azure]
endpoint = https://ini-value.openai.azure.com
key = ini-key

[paths]
data_dir = /tmp/ini-dir
""")
            
            # 環境変数で一部を上書きなのだ
            monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://env-override.openai.azure.com")
            monkeypatch.setenv("DATA_DIR", "/tmp/env-override")
            # AZURE_OPENAI_KEY は環境変数なし（INI値を使う）
            monkeypatch.delenv("AZURE_OPENAI_KEY", raising=False)
            
            loader = ConfigLoader(config_path)
            config = loader.load()
        
        assert config.azure_openai_endpoint == "https://env-override.openai.azure.com"  # 環境変数
        assert config.azure_openai_key == "ini-key"  # INI値
        assert config.data_dir == Path("/tmp/env-override")  # 環境変数
    
    def test_missing_required_fields_raises_error(self, monkeypatch):
        """必須フィールドが不足している場合にエラーを発生させるテストなのだ"""
        # 必須環境変数をクリアなのだ
        for env_key in ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_KEY"]:
            monkeypatch.delenv(env_key, raising=False)
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "empty.ini"
            loader = ConfigLoader(config_path)
            
            with pytest.raises(ValueError, match="必須設定.*が設定されていない"):
                loader.load()
    
    def test_default_values_used(self, monkeypatch):
        """デフォルト値が使用されることを確認するテストなのだ"""
        # 最低限の必須フィールドのみ設定なのだ
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://required.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_KEY", "required-key")
        monkeypatch.delenv("DATA_DIR", raising=False)
        monkeypatch.delenv("INTERVAL_SEC", raising=False)
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "nonexistent.ini"
            loader = ConfigLoader(config_path)
            config = loader.load()
        
        assert config.azure_openai_endpoint == "https://required.openai.azure.com"
        assert config.azure_openai_key == "required-key"
        assert config.data_dir == Path.home() / ".keystats"  # デフォルト
        assert config.interval_sec == 60  # デフォルト
