# BLS Total nonfarm level API

このAPIは U.S. Bureau of Labor Statistics (BLS) の Current Employment Statistics (CES) 公式flat fileから `CES0000000001` (Total nonfarm employment) を抽出して配布します。

## 重要な境界

このデータは各観測月について取得時点でBLSが公開している**最新利用可能な水準系列**です。初回公表値、第2回、第3回公表値などのrelease vintage履歴ではありません。したがって、改定幅、改定分布、revision uncertaintyの計算には使用できません。

## 配布物

GitHub Pages deploy後:

- `/api/v1/manifest.json`
- `/api/v1/total-nonfarm.json`
- `/api/v1/total-nonfarm.csv`
- `/status.json`

`manifest.json`はレコード数、対象期間、取得日時、BLS sourceのSHA-256、およびJSON/CSVのbyte数とSHA-256を持ちます。キャッシュ利用者はmanifestを先に取得し、checksumが変化した場合だけ本体を再取得できます。

## データ辞書

| field | meaning |
|---|---|
| `series_id` | BLS series ID。現在は `CES0000000001` |
| `observation_date` | 観測月。各月1日をISO dateで表現 |
| `value_thousands` | 雇用者数、単位は千人 |
| `preliminary` | BLS flat fileの `P` footnoteの有無 |
| `retrieved_at_utc` | BLSから取得したUTC時刻 |
| `source_sha256` | 取得したBLS flat file全体のSHA-256 |

## 更新

`.github/workflows/update-dashboard.yml` は月次のEmployment Situation公表後に起動するスケジュールを持ち、BLS公式sourceを1回取得してAPIを再生成します。取得処理には30秒timeoutを設定し、HTTP 200以外をfail-closedで拒否します。取得失敗時に古いデータを新しいデータとして偽装して公開する処理はありません。

## 出典・利用条件

- Source: U.S. Bureau of Labor Statistics, Current Employment Statistics
- Source file: https://download.bls.gov/pub/time.series/ce/ce.data.00a.TotalNonfarm.Employment
- CES published series: https://www.bls.gov/web/empsit/cesseriespub.htm
- BLS copyright policy: https://www.bls.gov/opub/copyright-information.htm
- BLS Terms of Service: https://www.bls.gov/developers/termsOfService.htm

BLSは公開物を原則public domainとしており、出典としてBLSを明記するよう求めています。また、取得後の派生データや分析の品質・適時性をBLSが保証するものではありません。
