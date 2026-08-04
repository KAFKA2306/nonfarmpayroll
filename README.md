# nonfarmpayroll — 米国雇用統計改定分析の停止状態

> **状態: 分析利用不可 / 公開訂正中**  
> このリポジトリで従来公開していた雇用統計の改定幅、不確実性、品質scoreは、検証済みのBLS公表vintageに基づく結果として確認できませんでした。現在は数値分析を停止し、GitHub Pagesにはstatusだけを公開します。

## 重要な訂正

旧READMEとdashboardでは、次の値を実測結果として表示していました。

- 平均改定: 約`+17K`
- 改定の標準偏差: 約`73.4K`
- 合成不確実性: 約`112.3K`
- 品質score: `95/100`
- uptime: `99.9%`
- monthly workflow成功率: `95%+`

これらの主張を撤回します。

default branchの監査で、次を確認しました。

1. `data_processed/nfp_revisions.csv`の`release1`、`release2`、`release3`には、1939年から小数を含む人工的な値が保存されている。
2. `dashboard.js`はdata fileの読込に失敗すると、`Math.random()`でdemo revisionを生成する。
3. 同じdemo処理が、平均改定、改定標準偏差、合成不確実性を固定値として作る。
4. `scripts/03_merge_revisions.py`はBLS release dataがない場合、`release1 = final`というplaceholderを作る。
5. repositoryには`data_processed/bls_releases.csv`または対応するparquetを確認できない。
6. monthly workflowはFRED PAYEMSを取得するが、BLS初回・第2回・第3回公表値のvintageを取得しない。

したがって、既存の`nfp_revisions.csv`と`summary_report.json`は、実測BLS改定履歴の正準dataではありません。研究、投資判断、政策評価、統計的主張に使用しないでください。

## 現在公開する内容

`.github/workflows/update-dashboard.yml`はfail-closedへ変更しました。

- pull requestではstatus page contractを検証する
- mainへのmerge後はstatus-only Pagesをdeployする
- 旧`dashboard.html`、`dashboard.js`、synthetic CSVを公開artifactへ含めない
- 公開statusは`analysis_available: false`を返す
- 検証済みvintageがない限り、改定統計を表示しない

公開先:

```text
https://kafka2306.github.io/nonfarmpayroll/
```

公開URLがHTTP 200でも、分析が利用可能であることを意味しません。`status.json`の状態を確認してください。

## 現在確認できる実装

| 項目 | 状態 |
|---|---|
| FRED PAYEMS取得script | 存在する |
| latest-vintageの雇用者数系列 | 取得可能 |
| BLS初回公表値の履歴 | 正準入力なし |
| 第2回・第3回公表値の履歴 | 正準入力なし |
| 改定幅の実測集計 | 利用不可 |
| 不確実性の実測推定 | 利用不可 |
| 公開dashboard | status-onlyへ停止 |

## FRED PAYEMSだけでは不足する理由

現在取得しているPAYEMS系列は、各観測月について現在利用できる系列値です。これだけでは、当時の初回公表値、第2回公表値、第3回公表値、その後のbenchmark revisionを区別できません。

改定分析には、少なくとも次の列を持つvintage dataが必要です。

```text
series_id
observation_date
release_date
revision_stage
value
unit
seasonal_adjustment
source_url
retrieved_at
source_document_id
```

## 本復旧の条件

1. BLSまたはALFRED等の一次sourceから公表vintageを取得する
2. observation dateとrelease dateを分離する
3. 初回、第2回、第3回、benchmark revisionを機械的に識別する
4. raw vintageを改変せず保存し、derived metricsと分離する
5. source URL、取得日時、document ID、checksumを保存する
6. synthetic・demo・placeholder dataをproduction artifactから除外する
7. revision計算、単位、欠損、重複、期間整合のtestを追加する
8. READMEとdashboardの数値をraw vintageから再生成する
9. 公開Pagesのcommit SHAとdata checksumを表示する

## 旧artifactの扱い

次のfileはIncidentの調査証拠として残っていますが、正準分析結果ではありません。

```text
data_processed/nfp_revisions.csv
data_processed/nfp_revisions.feather
data_processed/nfp_revisions.parquet
data_processed/summary_report.json
dashboard.js
```

これらを削除せず残す場合も、再公開・再計算・比較の入力に使用してはいけません。

## 検証

status-only workflowは次を検査します。

- 公開HTMLに「分析利用不可」が含まれる
- `analysis_available`が`false`
- legacy synthetic artifactを信頼しない状態である
- 撤回済みの固定数値や稼働保証が公開HTMLへ再混入していない

## 関連Issue

- Incident: https://github.com/KAFKA2306/nonfarmpayroll/issues/1
- 全repository README監査: https://github.com/KAFKA2306/com/issues/3

本リポジトリの出力は投資助言、売買推奨、政策判断の根拠ではありません。

**README監査・公開訂正日:** 2026年8月5日
