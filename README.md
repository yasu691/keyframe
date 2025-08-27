# keyframe 🎵

調子とリズムを記録するタイピング・画面モニタリングツールなのだ

## 概要

自分の「調子（リズム）」と「その時に見ていたもの」を定量記録し、集中度・成果モニタリングの土台を作るツールなのだ。

- **タイピング指標**: KPM/KPS15/インターバル中央値/Backspace比を60秒ごとに記録
- **画面OCR**: スクリーンショット → Azure OpenAI でテキスト化  
- **注意散漫検知**: ブラックリスト語（YouTube/TikTok等）を検出してアラート
- **JSONL形式**: 日別ファイルで構造化データとして保存

## 実装状況（段階的開発中）

- [x] **フェーズ0**: 設定ローダ + 60秒スケジューラ
- [ ] **フェーズ1**: タイピング計測 (OCR無し)
- [ ] **フェーズ2**: スクリーンショット + アクティブウィンドウ
- [ ] **フェーズ3**: Azure OpenAI OCR
- [ ] **フェーズ4**: リトライキャッシュ
- [ ] **フェーズ5**: アラートエンジン
- [ ] **フェーズ6**: Tkinter通知
- [ ] **フェーズ7**: 運用・掃除機能

## 環境設定

### 必須環境変数

```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_KEY="your-api-key"
```

### オプション環境変数

```bash
export DATA_DIR="~/.keystats"     # デフォルト: ~/.keystats  
export INTERVAL_SEC="60"          # デフォルト: 60秒
```

### 設定ファイル（代替手段）

`~/.keystats/config.ini`:

```ini
[azure]
endpoint = https://your-resource.openai.azure.com
key = your-api-key

[paths]
data_dir = ~/.keystats

[timing]
interval_sec = 60
```

**優先度**: 環境変数 > INIファイル > デフォルト値

## インストール・実行

### フェーズ0 プロトタイプ

```bash
# 開発環境セットアップ
pip install -e ".[dev]"

# 設定例（必須）
export AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com"
export AZURE_OPENAI_KEY="dummy-key-for-prototype"

# 実行
python main.py
```

### テスト実行

```bash
# 全テスト実行
pytest

# カバレッジ付き
pytest --cov=src
```

## アーキテクチャ

```
src/
├── config.py         # ConfigLoader: env > ini > default
├── scheduler.py      # TimeSlicer: 60秒定期実行
├── (future phases)   # typing.py, ocr.py, alerts.py...
└── main.py          # エントリーポイント
```

## ライセンス

詳細は [LICENSE](LICENSE) を参照なのだ
