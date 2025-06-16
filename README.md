# Kitaku - 天候を考慮した帰宅推奨システム

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

天候の変化を予測し、ユーザーの状況に応じた最もインテリジェントな帰宅出発時刻を提案する、個人用のCLIアプリケーションです。

## 🌟 特徴

- **動的な天候パターン分析**: 天気の変化を4つの主要パターンに分類し、状況に最適化された判断ロジックを実行
- **ハイブリッド最適化エンジン**: 正確性が求められる計算（時刻、待ち時間）はPythonロジックが担当し、ファジーな解釈や表現生成はLLMが担当
- **非同期処理による高速応答**: ネットワークI/O（API呼び出し）を非同期で実行し、アプリケーションの応答性を最大化
- **堅牢なエラーハンドリング**: APIの一時的なエラーや予期せぬデータ形式に対応する、リトライ機構とデータバリデーション
- **構造化されたLLMレスポンス**: LLMの出力をJSON形式で受け取ることで、動的な表示制御を実現
- **カスタマイズ可能なLLMモデル**: 環境変数でGeminiモデルを自由に選択可能

## 📱 使用例

```bash
$ uv run main.py

Kitaku - 天候を考慮した帰宅推奨システム
現在地の天候情報を取得し、最適な帰宅時刻を提案します...

============================================================
🚶 Kitaku - 帰宅推奨システム（複数オプション）
============================================================

🌤️  天候情報:
   パターン: clear
   現在の降水量: 0.0mm/h
   1時間以内最大降水量: 0.0mm/h
   リスクレベル: low

📋 推奨オプション一覧:
------------------------------------------------------------

【オプション 1】
🕐 推奨出発時刻（大学）: 19:07
🚃 電車発車時刻（駅）: 19:17 (準急 淀屋橋行き)
📊 信頼度: 100.0%
💭 分析: 現在の天候は良好で、安心してご帰宅いただけます。
```

## 🚀 セットアップ

### 前提条件

- Python 3.11以上
- [uv](https://docs.astral.sh/uv/) パッケージマネージャー

### インストール手順

1. **リポジトリをクローン**
   ```bash
   git clone https://github.com/takehirohotta/kitaku.git
   cd kitaku
   ```

2. **仮想環境を作成**
   ```bash
   uv venv
   ```

3. **依存関係をインストール**
   ```bash
   uv sync
   ```

4. **環境変数を設定**
   ```bash
   cp .env.example .env
   ```
   
   `.env`ファイルを編集して以下の設定を行う：
   ```env
   # Yahoo天気API設定
   YAHOO_CLIENT_ID=your_yahoo_client_id_here
   
   # Google Gemini API設定
   GEMINI_API_KEY=your_gemini_api_key_here
   
   # 使用するGeminiモデル（オプション、デフォルト: gemini-2.0-flash-lite）
   GEMINI_MODEL=gemini-2.0-flash-lite
   ```

### APIキーの取得方法

#### Yahoo天気API
1. [Yahoo!デベロッパーネットワーク](https://developer.yahoo.co.jp/)にアクセス
2. アプリケーションを作成してClient IDを取得

#### Google Gemini API
1. [Google AI Studio](https://makersuite.google.com/app/apikey)にアクセス
2. APIキーを生成

### 利用可能なGeminiモデル

環境変数 `GEMINI_MODEL` でモデルを選択できます：
- `gemini-2.0-flash-lite` (デフォルト、軽量版)

## 🏃 実行方法

```bash
# メインアプリケーション実行
uv run main.py
```

## 🏗️ アーキテクチャ

### プロジェクト構造
```
kitaku/
├── main.py                     # エントリーポイント
├── src/
│   ├── services/               # 各機能サービスクラス
│   │   ├── weather_service.py
│   │   ├── timetable_service.py
│   │   ├── recommendation_engine.py
│   │   └── llm_formatter.py
│   ├── models/                 # Pydanticデータモデル
│   │   └── data_models.py
│   └── core/                   # コア機能、設定
│       ├── config.py
│       └── exceptions.py
├── data/
│   └── keihan_neyagawa.csv    # 時刻表データ
├── .env.example               # 環境変数テンプレート
└── pyproject.toml            # プロジェクト設定
```

### 技術スタック

- **言語**: Python 3.11+
- **パッケージ管理**: uv
- **データバリデーション**: Pydantic
- **HTTP クライアント**: httpx (非同期)
- **環境変数管理**: python-dotenv
- **LLM**: Google Gemini API
- **天気データ**: Yahoo!天気API

### 設計思想

- **クラスベース**: 機能ごとに責務を分離したサービスクラス構成
- **依存性の注入**: コンポーネントの疎結合と高いテスト容易性を実現
- **型安全**: Pydanticによる厳密なデータバリデーション
- **非同期処理**: I/Oバウンドな処理の高速化

## 🛠️ 開発

### 開発用パッケージの追加
```bash
uv add --dev pytest
```

### テスト実行
```bash
uv run pytest
```

### 新しい依存関係の追加
```bash
uv add package_name
```

## 📊 データソース

- **天気予報**: Yahoo!天気API
- **時刻表**: 京阪電車寝屋川市駅の時刻表データ（CSV形式）

## 🤖 LLM連携

Google Gemini APIを使用して：
1. Pythonロジックによる計算結果と天気データを受け取り
2. 状況を解釈し、ユーザーに寄り添った自然な推奨文を生成
3. 構造化されたJSON形式で出力を返す

## ⚙️ 設定

### 環境変数一覧

| 変数名 | 必須 | デフォルト値 | 説明 |
|--------|------|-------------|------|
| `YAHOO_CLIENT_ID` | ✅ | - | Yahoo天気APIのクライアントID |
| `GEMINI_API_KEY` | ✅ | - | Google Gemini APIキー |
| `GEMINI_MODEL` | ❌ | `gemini-2.0-flash-lite` | 使用するGeminiモデル名 |

## 📝 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) ファイルを参照してください。

## 🤝 コントリビューション

プルリクエストやイシューの報告を歓迎します！

## 📞 サポート

問題や質問がある場合は、[Issues](https://github.com/takehirohotta/kitaku/issues)で報告してください。
