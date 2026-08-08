# Verified BLS payroll vintage API

このAPIは、BLS Employment Situation の公表文に明記された Total nonfarm payroll employment の前月差について、公表時点ごとの値だけを保存・配布します。

## 配布物

- `api/v1/vintage-manifest.json`: 件数、coverage、出典、SHA-256
- `api/v1/payroll-vintages.json`: observation month × release stage の正準レコード
- `api/v1/payroll-revisions.json`: 連続するrelease間の改定差
- `api/v1/payroll-revisions.csv`: 改定差のCSV

## 現在のcoverage

- observation month: 2026-05 ～ 2026-07
- verified vintage records: 6
- derived adjacent-release revisions: 3
- 2026-05: release1 / release2 / release3
- 2026-06: release1 / release2
- 2026-07: release1

このcoverageは改定分布や長期不確実性を推定するには不足しています。そのため `analysis_available` は `false` のままです。

## stable key

`(observation_month, revision_stage)` を一意キーとして扱います。`release1` は初回、`release2` は翌月の改定、`release3` は翌々月の改定です。

## 欠損の意味

後続releaseがまだ存在しない月について、`release2` / `release3` を `0` や初回値で補完しません。存在しないstageは未観測です。

## provenance

各レコードは `release_date`、`source_document_id`、`source_url` を持ちます。BLS資料は米国連邦政府著作物としてpublic domainです。BLSは出典表記を求めています。

## 更新

新しいEmployment Situationが公表されたら、既存レコードを上書きせず新しいrelease stageを追加します。通常CIはBLSへアクセスせず、保存済みsnapshotから決定的に配布物を再生成します。

## 利用例

```python
import json
from urllib.request import urlopen

url = "https://kafka2306.github.io/nonfarmpayroll/api/v1/payroll-vintages.json"
with urlopen(url) as response:
    payload = json.load(response)

may = [r for r in payload["records"] if r["observation_month"] == "2026-05"]
print([(r["revision_stage"], r["value_thousands"]) for r in may])
```

## 制約

旧synthetic artifactは入力に使用しません。このAPIの部分coverageだけから平均改定幅、標準偏差、不確実性score等を公開しません。
