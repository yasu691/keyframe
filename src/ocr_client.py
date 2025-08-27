"""Azure OpenAI OCRクライアント：画像からテキストを抽出するのだ"""
import base64
import time
from pathlib import Path
from typing import Optional, Dict, Any
from openai import AzureOpenAI
from src.config import Config


class OcrResult:
    """OCR結果クラスなのだ"""
    
    def __init__(self, success: bool, text: str = "", error: Optional[str] = None, tokens_used: int = 0):
        self.success = success
        self.text = text
        self.error = error
        self.tokens_used = tokens_used
        self.timestamp = time.time()
    
    def is_success(self) -> bool:
        """処理成功かどうかを返すのだ"""
        return self.success
    
    def get_text(self) -> str:
        """抽出されたテキストを返すのだ"""
        return self.text
    
    def get_error(self) -> Optional[str]:
        """エラーメッセージを返すのだ（成功時はNone）"""
        return self.error


class OcrClient:
    """Azure OpenAI Vision OCRクライアントなのだ"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = AzureOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            api_key=config.azure_openai_key,
            api_version="2023-12-01-preview"  # Vision API対応バージョン
        )
        self.model = config.azure_openai_model
    
    def extract_text_from_image(self, image_path: Path, prompt: Optional[str] = None) -> OcrResult:
        """画像ファイルからテキストを抽出するのだ"""
        if not image_path.exists():
            return OcrResult(success=False, error=f"画像ファイルが存在しません: {image_path}")
        
        try:
            # 画像をBase64エンコード
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # OCR実行
            return self._perform_ocr(image_data, prompt)
            
        except Exception as e:
            return OcrResult(success=False, error=f"画像読み込みエラー: {str(e)}")
    
    def extract_text_from_bytes(self, image_bytes: bytes, prompt: Optional[str] = None) -> OcrResult:
        """画像バイト列からテキストを抽出するのだ"""
        try:
            # 画像をBase64エンコード
            image_data = base64.b64encode(image_bytes).decode('utf-8')
            
            # OCR実行
            return self._perform_ocr(image_data, prompt)
            
        except Exception as e:
            return OcrResult(success=False, error=f"画像バイト処理エラー: {str(e)}")
    
    def _perform_ocr(self, image_base64: str, prompt: Optional[str] = None) -> OcrResult:
        """実際のOCR処理を実行するのだ"""
        try:
            # デフォルトプロンプト
            if prompt is None:
                prompt = ("この画像はPCのデスクトップ画面のスクリーンショットです。"
                         "PCのユーザーが作業している内容や状況を目が見えない人に向けて説明するテキストを200文字以内で作成してください")
            
            # Azure OpenAI Vision APIリクエスト
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,  # OCRテキスト用に十分な量
                temperature=0.0,  # 一貫性を重視
                top_p=1.0
            )
            
            # レスポンス解析
            if response.choices and response.choices[0].message:
                extracted_text = response.choices[0].message.content or ""
                tokens_used = response.usage.total_tokens if response.usage else 0
                
                return OcrResult(
                    success=True,
                    text=extracted_text.strip(),
                    tokens_used=tokens_used
                )
            else:
                return OcrResult(success=False, error="OCRレスポンスが空です")
                
        except Exception as e:
            error_message = str(e)
            
            # よくあるエラーパターンの詳細化
            if "429" in error_message:
                error_message = f"API利用制限エラー (Rate Limit): {error_message}"
            elif "401" in error_message:
                error_message = f"認証エラー: {error_message}"
            elif "403" in error_message:
                error_message = f"アクセス権限エラー: {error_message}"
            elif "404" in error_message:
                error_message = f"リソースが見つかりません: {error_message}"
            elif "timeout" in error_message.lower():
                error_message = f"タイムアウトエラー: {error_message}"
            
            return OcrResult(success=False, error=error_message)
    
    def test_connection(self) -> bool:
        """Azure OpenAI接続テストを実行するのだ"""
        try:
            # 小さなテスト画像を作成（1x1ピクセルの白い画像）
            test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "この画像について教えてください。"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{test_image_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=10
            )
            
            return response.choices is not None and len(response.choices) > 0
            
        except Exception as e:
            print(f"⚠️ Azure OpenAI接続テスト失敗: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """使用中のモデル情報を返すのだ"""
        return {
            "model": self.model,
            "endpoint": self.config.azure_openai_endpoint,
            "api_version": "2023-12-01-preview"
        }

