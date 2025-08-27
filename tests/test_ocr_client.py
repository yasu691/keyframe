"""OcrClient のテストなのだ"""
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from src.config import Config
from src.ocr_client import OcrClient, OcrResult


class TestOcrResult:
    """OcrResult テストクラスなのだ"""
    
    def test_success_result(self):
        """成功結果のテストなのだ"""
        result = OcrResult(success=True, text="Hello World", tokens_used=10)
        
        assert result.is_success() is True
        assert result.get_text() == "Hello World"
        assert result.get_error() is None
        assert result.tokens_used == 10
    
    def test_failure_result(self):
        """失敗結果のテストなのだ"""
        result = OcrResult(success=False, error="API Error", tokens_used=0)
        
        assert result.is_success() is False
        assert result.get_text() == ""
        assert result.get_error() == "API Error"
        assert result.tokens_used == 0


class TestOcrClient:
    """OcrClient テストクラスなのだ"""
    
    def create_test_config(self) -> Config:
        """テスト用設定を作成するのだ"""
        return Config(
            azure_openai_endpoint="https://test.openai.azure.com",
            azure_openai_key="test-key",
            azure_openai_model="gpt-4.1",
            data_dir=Path("/tmp/test"),
            interval_sec=60,
            ocr_enabled=True,
            retry_max_attempts=3,
            retry_base_delay_sec=1.0
        )
    
    @patch('src.ocr_client.AzureOpenAI')
    def test_client_initialization(self, mock_azure_openai):
        """クライアント初期化テストなのだ"""
        config = self.create_test_config()
        client = OcrClient(config)
        
        assert client.config == config
        assert client.model == "gpt-4.1"
        
        # AzureOpenAIクライアントが適切に初期化されることを確認
        mock_azure_openai.assert_called_once_with(
            azure_endpoint="https://test.openai.azure.com",
            api_key="test-key",
            api_version="2023-12-01-preview"
        )
    
    def test_extract_text_from_nonexistent_file(self):
        """存在しないファイルからのテキスト抽出テストなのだ"""
        config = self.create_test_config()
        client = OcrClient(config)
        
        nonexistent_path = Path("/nonexistent/image.jpg")
        result = client.extract_text_from_image(nonexistent_path)
        
        assert result.is_success() is False
        assert "画像ファイルが存在しません" in result.get_error()
    
    @patch('src.ocr_client.AzureOpenAI')
    def test_extract_text_from_image_success(self, mock_azure_openai):
        """画像からのテキスト抽出成功テストなのだ"""
        config = self.create_test_config()
        
        # Azure OpenAIクライアントのモック
        mock_client = Mock()
        mock_azure_openai.return_value = mock_client
        
        # レスポンスのモック
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Extracted text from image"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        
        mock_usage = Mock()
        mock_usage.total_tokens = 150
        mock_response.usage = mock_usage
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # テスト実行
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            tmp_file.write(b"fake image data")
            tmp_file.flush()
            
            client = OcrClient(config)
            result = client.extract_text_from_image(Path(tmp_file.name))
            
            assert result.is_success() is True
            assert result.get_text() == "Extracted text from image"
            assert result.tokens_used == 150
            assert result.get_error() is None
    
    @patch('src.ocr_client.AzureOpenAI')
    def test_extract_text_from_image_api_error(self, mock_azure_openai):
        """API エラー時のテストなのだ"""
        config = self.create_test_config()
        
        # Azure OpenAIクライアントのモック
        mock_client = Mock()
        mock_azure_openai.return_value = mock_client
        
        # API エラーをシミュレート
        mock_client.chat.completions.create.side_effect = Exception("429: Rate limit exceeded")
        
        # テスト実行
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            tmp_file.write(b"fake image data")
            tmp_file.flush()
            
            client = OcrClient(config)
            result = client.extract_text_from_image(Path(tmp_file.name))
            
            assert result.is_success() is False
            assert "API利用制限エラー (Rate Limit)" in result.get_error()
    
    @patch('src.ocr_client.AzureOpenAI')
    def test_extract_text_from_bytes_success(self, mock_azure_openai):
        """バイト列からのテキスト抽出成功テストなのだ"""
        config = self.create_test_config()
        
        # Azure OpenAIクライアントのモック
        mock_client = Mock()
        mock_azure_openai.return_value = mock_client
        
        # レスポンスのモック
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Text from bytes"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        
        mock_usage = Mock()
        mock_usage.total_tokens = 100
        mock_response.usage = mock_usage
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # テスト実行
        client = OcrClient(config)
        image_bytes = b"fake image data"
        result = client.extract_text_from_bytes(image_bytes)
        
        assert result.is_success() is True
        assert result.get_text() == "Text from bytes"
        assert result.tokens_used == 100
    
    @patch('src.ocr_client.AzureOpenAI')
    def test_custom_prompt(self, mock_azure_openai):
        """カスタムプロンプトのテストなのだ"""
        config = self.create_test_config()
        
        mock_client = Mock()
        mock_azure_openai.return_value = mock_client
        
        # レスポンスのモック
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "Custom prompt result"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_response.usage = None  # usage が None の場合
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # テスト実行
        client = OcrClient(config)
        custom_prompt = "この画像から数字だけを抽出してください"
        
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp_file:
            tmp_file.write(b"fake image data")
            tmp_file.flush()
            
            result = client.extract_text_from_image(Path(tmp_file.name), prompt=custom_prompt)
            
            assert result.is_success() is True
            assert result.get_text() == "Custom prompt result"
            assert result.tokens_used == 0  # usage が None の場合
            
            # カスタムプロンプトが使用されたことを確認
            call_args = mock_client.chat.completions.create.call_args[1]
            messages = call_args['messages']
            assert custom_prompt in messages[0]['content'][0]['text']
    
    @patch('src.ocr_client.AzureOpenAI')
    def test_test_connection_success(self, mock_azure_openai):
        """接続テスト成功のテストなのだ"""
        config = self.create_test_config()
        
        mock_client = Mock()
        mock_azure_openai.return_value = mock_client
        
        # 接続テスト成功のモック
        mock_response = Mock()
        mock_choice = Mock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        client = OcrClient(config)
        result = client.test_connection()
        
        assert result is True
    
    @patch('src.ocr_client.AzureOpenAI')
    def test_test_connection_failure(self, mock_azure_openai):
        """接続テスト失敗のテストなのだ"""
        config = self.create_test_config()
        
        mock_client = Mock()
        mock_azure_openai.return_value = mock_client
        
        # 接続テスト失敗のモック
        mock_client.chat.completions.create.side_effect = Exception("Connection failed")
        
        client = OcrClient(config)
        result = client.test_connection()
        
        assert result is False
    
    def test_get_model_info(self):
        """モデル情報取得テストなのだ"""
        config = self.create_test_config()
        
        with patch('src.ocr_client.AzureOpenAI'):
            client = OcrClient(config)
            info = client.get_model_info()
            
            assert info["model"] == "gpt-4.1"
            assert info["endpoint"] == "https://test.openai.azure.com"
            assert info["api_version"] == "2023-12-01-preview"

