# nonfarmpayroll — BLS雇用統計を、記事・分析・プロダクトですぐ使える形に

**U.S. Bureau of Labor Statistics (BLS) の Total nonfarm employment を、出典・取得時刻・検証情報付きの JSON / CSV / 埋め込みチャートとして再利用できます。**

毎月の雇用統計を使うたびに、一次資料を探し直し、系列を整形し、出典表記を確認し、チャートを作り直す。その手間を減らすための公開データレイヤーです。

- **見る**: https://kafka2306.github.io/nonfarmpayroll/
- **埋め込む**: https://kafka2306.github.io/nonfarmpayroll/docs/embed/nfp/?range=5y&locale=ja&partner=public
- **JSON**: https://kafka2306.github.io/nonfarmpayroll/docs/api/v1/total-nonfarm.json
- **CSV**: https://kafka2306.github.io/nonfarmpayroll/docs/api/v1/total-nonfarm.csv
- **Manifest**: https://kafka2306.github.io/nonfarmpayroll/docs/api/v1/manifest.json

## このrepositoryが提供する顧客価値

### 1. 雇用統計を、そのまま記事やダッシュボードへ使える

BLS Current Employment Statistics の `CES0000000001`（Total nonfarm employment）を、Web表示だけでなく JSON / CSV として配布しています。

現在の公開snapshotは **2021-07〜2026-07の61観測**です。2026-07はBLS source上でpreliminaryです。

「データを探す → 整形する → 出典を確認する」から始めず、分析・可視化・記事制作へ進めます。

### 2. 経済メディアやニュースレターへ、チャートをiframeで埋め込める

埋め込みMVPは次のURL parameterに対応しています。

- `range=1y|5y|all`
- `locale=ja|en`
- `partner=<opaque id>`

例:

```html
<iframe
  src="https://kafka2306.github.io/nonfarmpayroll/docs/embed/nfp/?range=5y&locale=ja&partner=public"
  loading="lazy"
  width="100%"
  height="520"
></iframe>
```

チャート内には BLS / CES / series ID / 単位 / 季節調整 / 最新観測日 / preliminary / 取得時刻 / source への導線を表示します。

### 3. 数値だけでなく「どこから来たデータか」を一緒に使える

`manifest.json`には、公開artifactの byte count と SHA-256、取得時刻、coverage、series ID を保持しています。

埋め込み側はmanifestと配布ファイルの整合性が確認できない場合、壊れた数値を表示する代わりに fail closed します。

つまりこのrepositoryが提供したいのは、単なるNFPの数字ではなく、**再利用時に出典とデータ境界を失いにくい配布形態**です。

### 4. 「最新水準」と「当時の公表値」を混同しない

雇用統計では、現在取得できるlevel seriesと、各release時点で公表された値は同じものではありません。

このrepositoryでは両者を分けています。

- **level snapshot**: `CES0000000001` の最新利用可能な水準系列
- **release vintage**: BLS Employment Situation公表資料から一次確認した当時の公表値

release vintageは現在、2026年5月〜7月の **6 records** を部分収録しています。

これにより、利用者が「現在の系列から過去の初回公表値を逆算した」と誤認しない構造にしています。

## こんな用途に向いています

| 利用者 | 使い方 | 得られるもの |
|---|---|---|
| 経済メディア / ニュースレター | iframeを記事へ埋め込む | BLS出典付きNFPチャート |
| アナリスト | JSON / CSVを取得 | 検証済みlevel snapshot |
| データエンジニア | Manifestとartifactを読む | provenance / checksum付きの入力 |
| 教育・研究用途 | sourceと観測期間を併記 | 数値の由来を追跡できる教材 |
| サービス運営者 | status / manifestを機械判定 | 利用可能範囲をコードから確認 |

## すぐ使う

### JSON

```bash
curl -L https://kafka2306.github.io/nonfarmpayroll/docs/api/v1/total-nonfarm.json
```

### CSV

```bash
curl -L https://kafka2306.github.io/nonfarmpayroll/docs/api/v1/total-nonfarm.csv
```

### 配布状態を確認

```bash
curl -L https://kafka2306.github.io/nonfarmpayroll/status.json
curl -L https://kafka2306.github.io/nonfarmpayroll/docs/api/v1/manifest.json
```

## 公開しているデータ

### Total nonfarm employment level series

Series:

```text
BLS Current Employment Statistics
CES0000000001 — Total nonfarm employment
```

Artifacts:

- `docs/api/v1/total-nonfarm.json`
- `docs/api/v1/total-nonfarm.csv`
- `docs/api/v1/manifest.json`

現在のcommitted snapshot:

- coverage: `2021-07-01` → `2026-07-01`
- records: `61`
- retrieved: `2026-08-10T20:06:33Z`
- latest observation: `2026-07`, preliminary

一次source:

https://download.bls.gov/pub/time.series/ce/ce.data.00a.TotalNonfarm.Employment

### Verified release vintages

2026年5月〜7月について、BLS Employment Situationの公表資料から確認したrelease vintageを保持しています。

- 2026-05: release1 `+172K` / release2 `+129K` / release3 `+63K`
- 2026-06: release1 `+57K` / release2 `+20K`
- 2026-07: release1 `-23K`

Artifacts:

- `docs/api/v1/vintage-manifest.json`
- `docs/api/v1/payroll-vintages.json`
- `docs/api/v1/payroll-revisions.json`
- `docs/api/v1/payroll-revisions.csv`

BLS source documents:

- 2026-06-05 Employment Situation — `USDL-26-0786`
- 2026-07-02 Employment Situation — `USDL-26-1125`
- 2026-08-07 Employment Situation — `USDL-26-1291`

Archive:

https://www.bls.gov/bls/news-release/empsit.htm

## 信頼性を支える設計

このrepositoryは、値を増やすことよりも「確認できる値を壊さず届けること」を優先します。

CIでは主に次を検証します。

1. level API builder / release-vintage API builderのunit test
2. media embed contract test / JavaScript syntax
3. manifestと配布ファイルのbyte count / SHA-256整合性
4. release-vintage APIのdeterministic rebuild
5. `status.json`で公開可能範囲を機械判定できること
6. legacy synthetic artifactをproduction入力へ再混入させないこと
7. embedがlevel seriesからrevision historyを生成しないこと
8. CI終了後のworking treeがcleanであること

Machine-readable status:

```json
{
  "status": "partial",
  "analysis_available": false,
  "revision_vintage_available": true,
  "revision_vintage_coverage": "partial",
  "verified_level_series_available": true,
  "legacy_synthetic_artifacts_trusted": false
}
```

## 現在のデータ境界

利用できるのは、**検証済みlevel snapshot**と**部分収録されたrelease vintage**です。

現在は十分な長期release-vintage coverageがないため、長期の平均改定幅・改定分布・不確実性scoreなどは公開していません。level seriesからそれらを推定して補完することもしません。

旧dashboardに存在したsynthetic / demo / placeholder由来の固定値はproduction Pagesへ公開せず、正準分析結果として扱いません。事故経緯と撤回内容は Issue #1 に残しています。

- Incident: https://github.com/KAFKA2306/nonfarmpayroll/issues/1
- Media embed / PoC: https://github.com/KAFKA2306/nonfarmpayroll/issues/5

## Media embedの次の価値検証

技術MVPは公開済みですが、外部導入実績や有料PoCを実績として主張できる段階ではありません。

今後検証する候補は、原データの販売ではなく次の導入価値です。

- 媒体ブランドに合わせた表示
- CMS組み込み
- provenance / checksum監査パネル
- 複数記事向け設定管理
- 更新状態の監視とfallback手順
- 導入支援

顧客・利用・売上のKPIは、観測できた事実だけを `metrics/nfp-media-embed-kpi.json` に記録します。

## Source

- U.S. Bureau of Labor Statistics — Current Employment Statistics: https://www.bls.gov/ces/
- Employment Situation archive: https://www.bls.gov/bls/news-release/empsit.htm
- BLS Copyright Information: https://www.bls.gov/opub/copyright-information.htm

**README updated: 2026-08-16**
