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
- [x] **フェーズ1**: タイピング計測 + JSONL出力
- [x] **フェーズ2**: スクリーンショット + アクティブウィンドウ
- [x] **フェーズ3**: Azure OpenAI OCR
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
export DATA_DIR="~/.keystats"        # デフォルト: ~/.keystats  
export INTERVAL_SEC="60"             # デフォルト: 60秒
export AZURE_OPENAI_MODEL="gpt-4.1"  # デフォルト: gpt-4.1
export OCR_ENABLED="true"             # デフォルト: true
export RETRY_MAX_ATTEMPTS="3"         # デフォルト: 3
export RETRY_BASE_DELAY_SEC="1.0"    # デフォルト: 1.0秒
```

### 設定ファイル（代替手段）

`~/.keystats/config.ini`:

```ini
[azure]
endpoint = https://your-resource.openai.azure.com
key = your-api-key
model = gpt-4.1

[paths]
data_dir = ~/.keystats

[timing]
interval_sec = 60

[ocr]
enabled = true
retry_max_attempts = 3
retry_base_delay_sec = 1.0
```

**優先度**: 環境変数 > INIファイル > デフォルト値

## インストール・実行

### 開発環境セットアップ

```bash
# パッケージインストール
uv install

# 開発依存関係も含む
uv add --dev pytest pytest-cov
```

### フェーズ1: タイピング計測

```bash
# 必須環境変数設定
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_KEY="your-api-key"

# オプション環境変数
export DATA_DIR="~/.keystats"     # デフォルト: ~/.keystats  
export INTERVAL_SEC="60"          # デフォルト: 60秒

# 実行
uv run python main.py
```

**macOS権限設定**: システム設定 > プライバシーとセキュリティ > アクセシビリティで許可が必要なのだ。権限なしでも実行は継続されるが、キー数は0になるのだ。

### テスト実行

```bash
# 全テスト実行
uv run pytest

# カバレッジ付き
uv run pytest --cov=src

# 特定テストのみ
uv run pytest tests/test_integration.py -v
```

### コード品質チェック

```bash
# Ruffでリント（自動修正付き）
uv run ruff check --fix .

# Ruffでフォーマット
uv run ruff format .

# Tyで型チェック
uv run ty

# 一括実行
uv run ruff check --fix . && uv run ruff format . && uv run ty
```

**設定**: `pyproject.toml` に Ruff (リンタ・フォーマッタ) と Ty (型チェッカ) の設定を記載済みなのだ。

## アーキテクチャ

```
src/
├── config.py         # ConfigLoader: env > ini > default
├── scheduler.py      # TimeSlicer: 60秒定期実行
├── keylogger.py      # KeyLogger: pynputでタイピング統計
├── jsonl_writer.py   # JsonlWriter: 日別JSONL出力
├── (future phases)   # ocr.py, alerts.py, notifications.py...
└── main.py          # エントリーポイント
```

## データ出力例

フェーズ1では以下のJSONL形式でタイピング統計を記録するのだ:

```json
{
  "ts_utc": "2025-08-27T10:00:00Z",
  "interval_sec": 60,
  "typing": {
    "kpm": 132,           # Keys Per Minute
    "kps15": 2.3,         # Keys Per Second (直近15秒)
    "median_latency_ms": 95.0,  # キー間隔中央値
    "backspace_pct": 4.1,       # Backspace比率 (%)
    "idle": false,              # アイドル状態（30秒キーなし）
    "total_keys_cum": 12345     # 累積キー数
  },
  "screen": {
    "screenshot_path": null,    # フェーズ1では常にnull
    "ocr_text": "",            # フェーズ1では空
    "active_app": "",          # フェーズ1では空
    "active_title": ""         # フェーズ1では空
  },
  "alerts": []                 # フェーズ1では空配列
}
```

ファイルパス: `DATA_DIR/yyyy-mm-dd.jsonl` （日別）

## ライセンス

詳細は [LICENSE](LICENSE) を参照なのだ
