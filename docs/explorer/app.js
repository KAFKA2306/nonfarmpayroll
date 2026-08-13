const form = document.querySelector('form');
const output = document.querySelector('#output');
const status = document.querySelector('#status');
const worker = new Worker('./worker.mjs', {type:'module'});
worker.onmessage = ({data}) => {
  if (!data.ok) { status.textContent = `FAIL CLOSED: ${data.error}`; output.textContent = ''; return; }
  const r = data.result;
  status.textContent = `verified ${r.series.series_id} / ${r.mode} / ${r.records.length} observations`;
  output.textContent = r.records.map(x => `${x.observation_date}\t${x.transformed_value ?? 'N/A'}${x.preliminary ? '\tpreliminary' : ''}`).join('\n');
  document.querySelector('#meta').textContent = `${r.source.publisher} | retrieved ${r.source.retrieved_at_utc} | sha256 ${r.verified_artifact_sha256}`;
};
form.addEventListener('submit', e => {
  e.preventDefault();
  status.textContent = 'Python runtime loading…';
  worker.postMessage({start:form.start.value,end:form.end.value,mode:form.mode.value});
});
