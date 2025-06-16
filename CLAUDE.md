# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 開発コマンド

### 環境構築
```bash
# 仮想環境作成
uv venv

# 依存関係をインストール（pyproject.tomlベース）
uv sync
```

### 実行
```bash
# メインアプリケーション実行
uv run main.py

# Pythonファイルの実行
uv run <ファイル名>.py
```

### 依存関係管理
```bash
# パッケージ追加
uv add <パッケージ名>

# 開発用パッケージ追加
uv add --dev <パッケージ名>

# 現在の設計書で予定されているライブラリ
uv add pydantic python-dotenv httpx google-generativeai tenacity
uv add --dev pytest
```

## **1\. プロジェクト概要**

天候の変化を予測し、ユーザーの状況に応じた最もインテリジェントな帰宅出発時刻を提案する、個人用のCLIアプリケーション。厳密な計算ロジックとLLMの表現力を融合させ、単なる情報提供を超えた、パーソナルアシスタントのような体験を目指す。

## **2\. コア機能**

* **動的な天候パターン分析**: 天気の変化を4つの主要パターンに分類し、状況に最適化された判断ロジックを実行する。  
* **ハイブリッド最適化エンジン**: 正確性が求められる計算（時刻、待ち時間）はPythonロジックが担当し、ファジーな解釈や表現生成はLLMが担当する、信頼性と柔軟性を両立したアーキテクチャ。  
* **非同期処理による高速応答**: ネットワークI/O（API呼び出し）を非同期で実行し、アプリケーションの応答性を最大化する。  
* **堅牢なエラーハンドリング**: APIの一時的なエラーや予期せぬデータ形式に対応する、リトライ機構とデータバリデーションを備える。  
* **構造化されたLLMレスポンス**: LLMの出力をJSON形式で受け取ることで、アプリケーション側での動的な表示制御を可能にする。

## **3\. アーキテクチャと設計思想**

* **形式**: コマンドラインアプリケーション (CLI)  
* **設計思想**:  
  * **クラスベース**: 機能ごとに責務を分離したサービスクラス（WeatherService, TimetableServiceなど）で構成する。  
  * **依存性の注入 (Dependency Injection)**: 各クラスの依存関係を外部から注入することで、コンポーネントの疎結合と高いテスト容易性を実現する。  
* **データ構造**:  
  * **Pydantic**: アプリケーション内で扱う全てのデータ（APIレスポンス、計算結果など）を型安全なデータモデルとして定義し、バリデーションと可読性を確保する。  
* **非同期処理**:  
  * **asyncio / httpx.AsyncClient**: I/Oバウンドな処理（API呼び出し）を非同期で実行する。  
* **設定管理**:  
  * **.env ファイル**: python-dotenvを使用し、APIキーなどの秘匿情報を環境変数として安全に管理する。  
* **ロギング**:  
  * **logging**: printの代わりに標準のloggingモジュールを使用し、デバッグやエラー追跡を容易にする。

## **4\. データソース**

* **天気予報**: Yahoo\!天気API  
* **時刻表**: data/timetable.csv

## **5\. LLM連携**

* **API**: Google Gemini API  
* **役割**:  
  1. Pythonロジックによる計算結果と天気データを受け取る。  
  2. 状況を解釈し、ユーザーに寄り添った自然な推奨文を生成する。  
  3. 出力を構造化されたJSON形式（例: { "summary": "...", "warning": "..." }）で返す。

## **6\. プロジェクト構造**

\- recommend-app/  
  \- main.py               \# アプリケーションのエントリーポイント (async)  
  \- src/  
    \- \_\_init\_\_.py  
    \- services/             \# 各機能サービスクラス  
      \- \_\_init\_\_.py  
      \- weather\_service.py  
      \- timetable\_service.py  
      \- recommendation\_engine.py  
      \- llm\_formatter.py  
    \- models/               \# Pydanticデータモデル  
      \- \_\_init\_\_.py  
      \- data\_models.py  
    \- core/                 \# コア機能、設定  
      \- \_\_init\_\_.py  
      \- config.py           \# .envを読み込み設定をグローバルに提供  
      \- exceptions.py       \# カスタム例外クラス  
  \- data/  
    \- timetable.csv         \# 時刻表データ  
  \- tests/                  \# テストコード  
    \- ...  
  \- .env                    \# APIキー等を記述 (Git管理外)  
  \- .gitignore  
  \- README.md               \# (このファイル)

## **7\. 開発ガイド**

### **環境構築**

Bash

\# 仮想環境作成・有効化  
uv venv

\# .envファイルを作成し、APIキーを記述  
\# 例: GEMINI\_API\_KEY="AI..."  
\#     YAHOO\_CLIENT\_ID="dj..."  
cp .env.example .env  
\# (エディタで.envファイルを編集)

### **依存関係のインストール**

Bash

\# アプリケーションライブラリ  
uv pip install pydantic python-dotenv httpx "google-generativeai" tenacity

\# 開発用ライブラリ  
uv pip install \-d pytest

### テスト実行
```bash
# テスト実行（pytestを使用）
uv run pytest

# 特定のテストファイル実行
uv run pytest tests/<テストファイル名>.py
```

### 設定ファイル
```bash
# .envファイルを作成してAPIキーを設定
cp .env.example .env
# GEMINI_API_KEY="AI..."
# YAHOO_CLIENT_ID="dj..."
```
