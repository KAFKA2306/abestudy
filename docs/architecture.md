# プロジェクト構造

```
abestudy/
├── README.md
├── docs/
│   ├── abenomics_overview.md
│   └── architecture.md
├── data/
│   ├── raw/
│   └── interim/
├── src/
│   ├── data_io/
│   ├── ingestion/
│   ├── analytics/
│   ├── reporting/
│   └── common/
└── reports/
    └── portfolio/
```

## ディレクトリ方針
- `docs`: 調査内容と設計仕様
- `data/raw`: yfinance 取得データ (`.yaml`)
- `data/interim`: 前処理や特徴量生成中間データ
- `src/data_io`: `.yaml` 読み書き機能
- `src/ingestion`: yfinance からの取得ロジック
- `src/analytics`: ポートフォリオ最適化ロジック
- `src/reporting`: YAML レポート生成
- `src/common`: 共有定数やユーティリティ
- `reports/portfolio`: 年次レポート出力

## ネーミング規約
- モジュール名はスネークケース
- クラス名はパスカルケース
- 関数名はスネークケース
- ファイル名は役割が一意になるようにする

## データ規約
- 取得データのカラム: `close`, `volume`, `timestamp`
- インデックス: `timestamp` (DatetimeIndex)
- タイムゾーン: `Asia/Tokyo`
- 欠損値処理: 当日データ欠損の場合はドロップ

## レポート規約
- ルートキー: `period`, `universe`, `portfolio`
- `portfolio` 配下に `weights`, `risk_metrics`, `classification`
- 全ての数値は小数点以下 6 桁まで

## 実装ステップ
1. ディレクトリを初期化
2. 銘柄ユニバースリストを作成
3. データ取得スクリプトを実装
4. データ I/O ライブラリを実装
5. 最適化アルゴリズムを実装
6. レポートモジュールを実装
7. 実行スクリプトを作成し年次レポートを生成
