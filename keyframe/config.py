"""設定ローダ: 環境変数 > INI > デフォルト値の優先順位で設定を読み込むのだ"""
import os
import configparser
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """アプリケーション設定なのだ"""
    azure_openai_endpoint: str
    azure_openai_key: str
    data_dir: Path
    interval_sec: int = 60


class ConfigLoader:
    """設定読み込みクラス: env > ini > default の優先順位なのだ"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".keystats" / "config.ini"
    
    def load(self) -> Config:
        """設定を読み込んで Config オブジェクトを返すのだ"""
        # デフォルト値なのだ
        defaults = {
            "azure_openai_endpoint": "",
            "azure_openai_key": "",
            "data_dir": str(Path.home() / ".keystats"),
            "interval_sec": "60"
        }
        
        # INI ファイルから読み込みなのだ
        config_values = defaults.copy()
        if self.config_path.exists():
            config_values.update(self._load_from_ini())
        
        # 環境変数で上書きなのだ
        config_values.update(self._load_from_env())
        
        # バリデーションなのだ
        self._validate_required_fields(config_values)
        
        return Config(
            azure_openai_endpoint=config_values["azure_openai_endpoint"],
            azure_openai_key=config_values["azure_openai_key"],
            data_dir=Path(config_values["data_dir"]).expanduser(),
            interval_sec=int(config_values["interval_sec"])
        )
    
    def _load_from_ini(self) -> dict:
        """INI ファイルから設定を読み込むのだ"""
        parser = configparser.ConfigParser()
        parser.read(self.config_path, encoding='utf-8')
        
        values = {}
        
        # [azure] セクションなのだ
        if parser.has_section('azure'):
            azure = parser['azure']
            if 'endpoint' in azure:
                values['azure_openai_endpoint'] = azure['endpoint']
            if 'key' in azure:
                values['azure_openai_key'] = azure['key']
        
        # [paths] セクションなのだ  
        if parser.has_section('paths'):
            paths = parser['paths']
            if 'data_dir' in paths:
                values['data_dir'] = paths['data_dir']
        
        # [timing] セクションなのだ
        if parser.has_section('timing'):
            timing = parser['timing']
            if 'interval_sec' in timing:
                values['interval_sec'] = timing['interval_sec']
        
        return values
    
    def _load_from_env(self) -> dict:
        """環境変数から設定を読み込むのだ"""
        values = {}
        
        env_mapping = {
            "AZURE_OPENAI_ENDPOINT": "azure_openai_endpoint",
            "AZURE_OPENAI_KEY": "azure_openai_key", 
            "DATA_DIR": "data_dir",
            "INTERVAL_SEC": "interval_sec"
        }
        
        for env_key, config_key in env_mapping.items():
            if env_key in os.environ:
                values[config_key] = os.environ[env_key]
        
        return values
    
    def _validate_required_fields(self, config_values: dict) -> None:
        """必須フィールドの検証なのだ"""
        required_fields = ["azure_openai_endpoint", "azure_openai_key"]
        
        for field in required_fields:
            if not config_values.get(field):
                raise ValueError(f"必須設定 {field} が設定されていないのだ")
