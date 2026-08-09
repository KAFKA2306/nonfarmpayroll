# nonfarmpayroll — 検証済みBLSデータのみ公開

> **状態: 長期の改定分析は利用不可 / 一次確認済みrelease vintageは部分公開**  
> 旧dashboardで公開していた平均改定、不確実性、品質score、稼働率などの固定値は、検証済みBLS公表vintageから再現できないため撤回しています。

## 現在の公開契約

GitHub Pagesは `.github/workflows/update-dashboard.yml` だけがdeployできるfail-closed構成です。

- `analysis_available: false`
- `legacy_synthetic_artifacts_trusted: false`
- 最新利用可能なBLS CES Total nonfarm level seriesをJSON/CSVで配布
- BLS Employment Situation公表資料から一次確認したrelease vintageを部分配布
- coverageが不十分なため、長期の平均改定幅・不確実性・品質score等は公開しない
- 旧`dashboard.html` / `dashboard.js` / synthetic CSVをPages artifactへ含めない

公開先:

```text
https://kafka2306.github.io/nonfarmpayroll/
```

公開URLがHTTP 200であることだけでは正常判定しません。`status.json`で`analysis_available=false`かつ`legacy_synthetic_artifacts_trusted=false`であることを確認してください。

## 検証済みデータ

### 最新利用可能な水準系列

BLS Current Employment StatisticsのTotal nonfarm employment (`CES0000000001`) を公式BLS sourceから取得し、canonical workflowで再生成します。

公開artifact:

- `api/v1/manifest.json`
- `api/v1/total-nonfarm.json`
- `api/v1/total-nonfarm.csv`

この系列は各観測月の最新利用可能値であり、当時の初回・第2回・第3回公表値を単独では復元しません。

### release vintage — partial coverage

`data_verified/vintages/bls-payroll-change-2026-08-07.json`には、BLS Employment Situationの公表資料をsourceとして、2026年5月〜7月について一次確認できた公表値を保存しています。

現在の収録は6 recordsです。

- 2026-05: release1 `+172K` / release2 `+129K` / release3 `+63K`
- 2026-06: release1 `+57K` / release2 `+20K`
- 2026-07: release1 `-23K`

source document:

- 2026-06-05 Employment Situation — `USDL-26-0786`
- 2026-07-02 Employment Situation — `USDL-26-1125`
- 2026-08-07 Employment Situation — `USDL-26-1291`

公開artifact:

- `api/v1/vintage-manifest.json`
- `api/v1/payroll-vintages.json`
- `api/v1/payroll-revisions.json`
- `api/v1/payroll-revisions.csv`

このcoverageは部分的です。数か月のverified recordsを、1939年以降の長期revision分布や不確実性推定へ外挿しません。

## 撤回した旧主張

旧README/dashboardには、検証済みvintageから再現できない次の主張がありました。

- 平均改定: 約`+17K`
- 改定の標準偏差: 約`73.4K`
- 合成不確実性: 約`112.3K`
- 品質score: `95/100`
- uptime: `99.9%`
- monthly workflow成功率: `95%+`

これらは**撤回済みの旧表示**であり、現在の分析結果ではありません。

## legacy artifact

次のfileはIncidentの調査証拠としてrepositoryに残っていますが、正準分析結果ではありません。

```text
data_processed/nfp_revisions.csv
data_processed/nfp_revisions.feather
data_processed/nfp_revisions.parquet
data_processed/summary_report.json
dashboard.js
```

これらをproduction Pagesへ再公開したり、verified analysisの入力へ昇格したりしてはいけません。

## CI / publication safety

canonical workflowは次を検証します。

1. BLS level API builderとrelease-vintage API builderのunit test
2. deterministic API rebuild
3. manifest checksum
4. public pageに`改定分析は利用不可`が含まれること
5. `analysis_available=false`
6. legacy synthetic artifactを信頼しないこと
7. 撤回済み固定値や`fully automated`等の旧運用保証をpublic pageへ再混入させないこと
8. canonical workflow以外が`deploy-pages` / `upload-pages-artifact`を使用していないこと

`.github/workflows/deploy-static.yml`と`.github/workflows/initial-setup.yml`はretiredで、Pages deploy権限を持ちません。health checkもHTTP 200だけではなく公開status contractを検証します。

## 本復旧の残条件

長期の改定分析を再開するには、十分な期間についてBLS/一次公表資料からrelease vintageを拡充し、observation date / release date / revision stage / source documentを保持した上で、raw vintageからsummaryを再計算する必要があります。

本repositoryは、coverage不足を数値で埋めず、検証できない場合はfail closedにします。

## 関連

- Incident: https://github.com/KAFKA2306/nonfarmpayroll/issues/1
- BLS Employment Situation archive: https://www.bls.gov/bls/news-release/empsit.htm
- BLS current Employment Situation: https://www.bls.gov/news.release/empsit.nr0.htm

**公開訂正:** 2026-08-05  
**partial verified vintages更新:** 2026-08-08
