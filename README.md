# 雇用統計再解析プロジェクト (Employment Statistics Re-analysis Project)

米国雇用統計（非農業部門雇用者数/NFP）の信頼性を定量的に評価し、改定誤差を予測するための包括的な分析システムです。

## プロジェクト概要

このプロジェクトは以下の課題に取り組みます:

- **速報値の不確実性**: BLS公表の±85,000人の統計誤差に加え、改定による追加の不確実性
- **季節調整の影響**: X-13-ARIMA-SEATSモデルの選択による調整値の差異
- **予測モデルの構築**: 機械学習による改定誤差の事前予測
- **政策判断支援**: 不確実性を考慮した意思決定フレームワーク

## システム機能

### データ収集・処理
- **FRED API**: PAYEMS系列の自動取得・スナップショット管理
- **BLS PDF解析**: Employment Situation報告書からの速報値抽出
- **改定計算**: 第1次〜第3次速報、年次ベンチマーク改定の追跡
- **品質検証**: データ整合性・異常値の自動検出

### 季節調整再評価
- **X-13-ARIMA-SEATS**: X-11とSEATS両方式による再調整
- **診断統計**: Sliding-span、改定履歴、M統計量の算出
- **方式比較**: 調整方法による差異の定量化

### 分析・予測
- **改定パターン分析**: 時系列での改定傾向の可視化
- **不確実性推定**: 統計的予測区間の算出
- **特徴量エンジニアリング**: 機械学習モデル用特徴量の生成

## プロジェクト構造

```
payrollstats/
├── EMPLOYMENT_STATS_REANALYSIS_GUIDE.md  # 包括的な設計書
├── README.md                              # このファイル
├── requirements.txt                       # Python依存関係
├── 
├── data_raw/                             # 生データ
│   ├── fred_snapshots/                   # PAYEMS_YYYYMMDD.csv
│   ├── bls_pdf/                         # empsit_YYYY_MM_v[1-3].pdf
│   └── benchmark_html/                   # 年次改定データ
│
├── data_processed/                       # 処理済みデータ
│   ├── nfp_revisions.feather            # 統合データセット
│   ├── bls_releases.parquet             # BLS速報値データ
│   └── quality_report.json              # データ品質レポート
│
├── scripts/                             # データ処理スクリプト
│   ├── 01_download_fred.py              # FRED データ取得
│   ├── 02_parse_bls_pdf.py              # BLS PDF解析
│   ├── 03_merge_revisions.py            # 改定テーブル作成
│   └── 04_x13_recalc.R                  # 季節調整再計算
│
└── analysis/                            # 分析・可視化
    ├── data_quality_check.py            # データ品質検証
    ├── revision_analysis.py             # 改定パターン分析
    └── ml_features.py                    # 特徴量エンジニアリング
```

## セットアップ手順

### 1. 環境構築

```bash
# リポジトリクローン
git clone <repository-url>
cd payrollstats

# Python仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt
```

### 2. R環境セットアップ（季節調整用）

```r
# R dependencies
install.packages(c("seasonal", "arrow", "dplyr", "lubridate", "ggplot2", "jsonlite"))
```

### 3. Java環境（tabula-py用）

```bash
# Ubuntu/Debian
sudo apt-get install openjdk-8-jdk

# macOS
brew install openjdk@8

# Windows: Oracle JDK 8をインストール
```

## 使用方法

### データ収集パイプライン

```bash
# 1. FRED データ取得
python scripts/01_download_fred.py

# 2. BLS PDF解析（PDFファイルを data_raw/bls_pdf/ に配置後）
python scripts/02_parse_bls_pdf.py

# 3. 改定テーブル作成
python scripts/03_merge_revisions.py

# 4. 季節調整再計算
Rscript scripts/04_x13_recalc.R

# 5. データ品質検証
python analysis/data_quality_check.py
```

### 定期実行（cron設定例）

```bash
# 毎月第1金曜日（雇用統計発表日）に実行
0 9 1-7 * 5 /path/to/payrollstats/scripts/01_download_fred.py

# 毎日FRED データをチェック（改定検出用）
0 10 * * * /path/to/payrollstats/scripts/01_download_fred.py
```

## データ仕様

### 統合データセット (nfp_revisions.feather)

| カラム名 | 型 | 説明 |
|---------|-----|------|
| date | datetime | 対象月（月初日） |
| release1 | float | 初回発表値（千人） |
| release2 | float | 第2次速報値（千人） |
| release3 | float | 第3次速報値（千人） |
| final | float | 年次ベンチマーク後確報値（千人） |
| rev_2to1 | float | 第2次改定幅（千人） |
| rev_3to2 | float | 第3次改定幅（千人） |
| rev_final | float | 最終改定幅（千人） |
| se | float | BLS公表標準誤差（千人） |
| ci90_lower/upper | float | 90%信頼区間（千人） |
| is_outlier | bool | 外れ値期間フラグ |
| *_x11_adj | float | X-11季節調整値 |
| *_seats_adj | float | SEATS季節調整値 |

## 分析例

### 改定誤差の統計的特性

```python
import pandas as pd
import numpy as np

# データ読み込み
df = pd.read_feather('data_processed/nfp_revisions.feather')

# 改定統計
revision_stats = {
    'mean': df['rev_final'].mean(),
    'std': df['rev_final'].std(),
    'percentiles': df['rev_final'].quantile([0.05, 0.25, 0.5, 0.75, 0.95])
}

print(f"平均改定: {revision_stats['mean']:.1f}千人")
print(f"標準偏差: {revision_stats['std']:.1f}千人")
```

### 予測区間の評価

```python
# 90%信頼区間のカバレッジ評価
within_ci = ((df['final'] >= df['ci90_lower']) & 
             (df['final'] <= df['ci90_upper'])).mean()

print(f"90%信頼区間カバレッジ: {within_ci:.1%}")
```

## 品質保証

### 自動テスト
- データ整合性チェック
- 改定計算の正確性検証
- 季節調整診断統計の閾値監視

### 手動確認ポイント
- BLS公表値との整合性
- 異常な改定幅の原因調査
- 季節調整モデルの適合度

## 制限事項・注意点

### データ取得の制約
- **BLS PDF**: 手動収集が必要（自動化は利用規約要確認）
- **改定履歴**: 2000年以前のデータは限定的
- **リアルタイム制約**: FRED更新タイミングによる遅延

### 統計的制約
- **サンプル調査**: 母集団誤差は避けられない
- **構造変化**: パンデミック等の外生ショック時は予測精度低下
- **季節調整**: モデル選択による主観性

### 技術的依存関係
- **Java**: tabula-py（PDF解析）に必要
- **R**: X-13-ARIMA-SEATS利用に必要
- **メモリ**: 大量時系列データ処理に8GB以上推奨

## トラブルシューティング

### よくある問題

1. **PDF解析エラー**
   ```
   tabula.errors.JavaNotFoundError
   ```
   → Java 8以上をインストール、JAVA_HOME設定確認

2. **FRED API制限**
   ```
   HTTP 429 Too Many Requests
   ```
   → リクエスト間隔を調整、API キー取得検討

3. **季節調整エラー**
   ```
   Error in seas(): SEATS model failed
   ```
   → X-11モードにフォールバック、外れ値処理調整

### ログ確認

```bash
# Python スクリプトのログ
tail -f logs/employment_stats.log

# R スクリプトのログ  
tail -f logs/x13_seasonal.log
```

## 開発・貢献

### コード品質基準
- **Python**: Black フォーマッタ、flake8 リンター
- **R**: lintr パッケージ、styler フォーマッタ
- **テスト**: pytest カバレッジ80%以上

### 提出前チェックリスト
- [ ] 全スクリプトの実行確認
- [ ] データ品質チェック通過
- [ ] 改定計算の手計算検証
- [ ] 季節調整診断統計の確認

## ライセンス・免責事項

- **データソース**: FRED（パブリック）、BLS（パブリック）
- **コード**: MIT License
- **免責**: 投資判断への直接利用は自己責任
- **学術利用**: 適切な引用をお願いします

## 参考文献・関連リンク

### 公式ドキュメント
- [BLS Employment Situation](https://www.bls.gov/news.release/empsit.htm)
- [FRED PAYEMS Series](https://fred.stlouisfed.org/series/PAYEMS)
- [X-13ARIMA-SEATS Reference Manual](https://www.census.gov/ts/x13as/docX13AS.pdf)

### 学術論文
- Aruoba, S. B. (2008). "Data revisions are not well behaved." *Journal of Money, Credit and Banking*
- Croushore, D. (2011). "Frontiers of real-time data analysis." *Journal of Economic Literature*

### 技術資料
- [seasonal package documentation](https://www.seasonal.website/)
- [tabula-py documentation](https://tabula-py.readthedocs.io/)

---

**更新履歴**
- v1.0.0 (2025-08): 初回リリース、基本機能実装
- 今後の予定: ML予測モデル、リアルタイム監視システム# nonfarmpayroll
