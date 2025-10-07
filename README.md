# abestudy
アベノミクス期間の日本個別株データを収集し、年次最適ポートフォリオを算出するプロジェクト。
## ドキュメント
- [アベノミクス基本情報](docs/abenomics_overview.md)
- [プロジェクト構造](docs/architecture.md)
## 実行
```
pip install -r requirements.txt
python -m src.run_pipeline
python -m src.run_visualization  # 主要銘柄のアベノミクス期可視化
```
