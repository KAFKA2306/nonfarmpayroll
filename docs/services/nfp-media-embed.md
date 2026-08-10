# 検証済みNFPチャート埋め込み

経済メディア、ニュースレター、調査・教育サイト向けに、U.S. Bureau of Labor Statistics (BLS) の Current Employment Statistics `CES0000000001`（Total nonfarm employment）を記事へ埋め込むためのMVPです。

## 無料で提供するもの

- 検証済みlevel snapshotのJSON/CSV
- `range=1y|5y|all`、`locale=ja|en`、`partner=<opaque id>` に対応するiframe表示
- BLS、CES、series ID、単位、季節調整、最新観測日、preliminary、取得時刻、sourceへの導線
- manifestのfile byte count / SHA-256不一致時のfail-close
- `analysis_available=false` / `revision_vintage_available=false` の境界表示

デモ:

`/docs/embed/nfp/index.html?range=5y&locale=ja&partner=public`

## 有料PoCで検証する価値

原データ自体の販売ではなく、媒体ブランドに合わせた表示、CMS組み込み、更新状態の運用、provenance/checksum監査パネル、複数記事用の設定管理、障害時のfallback手順と導入支援を候補とします。

料金、SLA、導入実績、顧客名は契約・証拠がない段階では表示しません。

## データ境界

このembedが読む数値データは `docs/api/v1/total-nonfarm.json` のlevel seriesだけです。release-vintage history、revision stage、改定幅、不確実性をlevel seriesから生成しません。

2026-08-10T20:06:33ZにBLS公式flat fileを再取得して確認した公開snapshotは、直近5年分として2021-07〜2026-07の61観測を保持します。`all`はこの公開snapshot内の全期間を意味し、1939年以降の全履歴を意味しません。最新の2026-07観測はBLS source上でpreliminaryです。

Source: https://download.bls.gov/pub/time.series/ce/ce.data.00a.TotalNonfarm.Employment

BLSは、BLSが公開する素材は一部の既存著作権付き写真・図版を除きpublic domainであり、BLSをsourceとして示すよう求めています。

Copyright information: https://www.bls.gov/opub/copyright-information.htm

## partner計測

embedは親windowへ `postMessage` で、`partner` と次のイベント名だけを通知します。

- `embed_loaded`
- `source_opened`
- `full_chart_opened`
- `business_inquiry_started`

氏名、メールアドレス、IP、検索語、閲覧履歴、level値は計測payloadへ含めません。repository側には現時点で外部analytics collectorを設置していません。

## 問い合わせ

技術MVPに関する相談・PoC検討は Issue #5 で受け付けます。

https://github.com/KAFKA2306/nonfarmpayroll/issues/5
