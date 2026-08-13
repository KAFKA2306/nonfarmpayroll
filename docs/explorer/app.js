const app = document.querySelector('#app');
app.innerHTML = `
  <h1>検証済みNFP level explorer</h1>
  <p><strong>改定分析は利用不可。</strong> manifestで検証されたCES0000000001のlevel snapshotだけを扱います。coverage外を補間せず、release-vintage historyや長期revision統計を生成しません。</p>
  <form>
    <label>開始 <input name="start" type="date" value="2025-01-01" required></label>
    <label>終了 <input name="end" type="date" value="2026-07-01" required></label>
    <label>表示 <select name="mode"><option value="level">level</option><option value="mom">前月差</option><option value="yoy">前年差</option></select></label>
    <button type="submit">Pythonで計算</button>
  </form>
  <p id="status">実行するとPyodideを読み込みます。</p>
  <p id="meta"></p>
  <pre id="output"></pre>
  <p><a href="../../index.html">戻る</a></p>
`;
const form = app.querySelector('form');
const output = app.querySelector('#output');
const status = app.querySelector('#status');
const meta = app.querySelector('#meta');
const worker = new Worker('./worker.mjs', {type:'module'});
worker.onmessage = ({data}) => {
  if (!data.ok) { status.textContent = `FAIL CLOSED: ${data.error}`; output.textContent = ''; meta.textContent = ''; return; }
  const r = data.result;
  status.textContent = `verified ${r.series.series_id} / ${r.mode} / ${r.records.length} observations`;
  output.textContent = r.records.map(x => `${x.observation_date}\t${x.transformed_value ?? 'N/A'}${x.preliminary ? '\tpreliminary' : ''}`).join('\n');
  meta.textContent = `${r.source.publisher} | ${r.series.unit} | ${r.series.seasonal_adjustment} | retrieved ${r.source.retrieved_at_utc} | sha256 ${r.verified_artifact_sha256}`;
};
form.addEventListener('submit', e => {
  e.preventDefault();
  status.textContent = 'Python runtime loading…';
  worker.postMessage({start:form.start.value,end:form.end.value,mode:form.mode.value});
});
