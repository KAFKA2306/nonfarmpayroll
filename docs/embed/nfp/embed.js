(() => {
  'use strict';

  const MANIFEST_URL = '../../api/v1/manifest.json';
  const DATA_URL = '../../api/v1/total-nonfarm.json';
  const ALLOWED_RANGES = new Set(['1y', '5y', 'all']);
  const ALLOWED_LOCALES = new Set(['ja', 'en']);
  const METRICS = new Set(['embed_loaded', 'source_opened', 'full_chart_opened', 'business_inquiry_started']);
  const params = new URLSearchParams(location.search);
  const range = ALLOWED_RANGES.has(params.get('range')) ? params.get('range') : '5y';
  const locale = ALLOWED_LOCALES.has(params.get('locale')) ? params.get('locale') : 'ja';
  const rawPartner = params.get('partner') || 'public';
  const partner = /^[a-z0-9][a-z0-9_-]{0,39}$/i.test(rawPartner) ? rawPartner : 'invalid';

  const copy = {
    ja: {
      title: '米国 Total nonfarm employment',
      unavailable: '検証に失敗したためチャートを表示できません。',
      preliminary: '暫定値',
      final: '確定扱い',
      source: 'BLS原典',
      full: '全体ページ',
      inquiry: '媒体導入を相談する',
      boundary: '水準系列のみ。release-vintage history・改定幅・不確実性の分析には使用できません。',
      subset: '公開スナップショット収録期間',
      retrieved: '取得時刻',
    },
    en: {
      title: 'U.S. Total nonfarm employment',
      unavailable: 'Chart unavailable because verification failed.',
      preliminary: 'Preliminary',
      final: 'Not preliminary',
      source: 'BLS source',
      full: 'Full page',
      inquiry: 'Discuss media integration',
      boundary: 'Level series only. Not release-vintage history and not valid for revision-size or uncertainty analysis.',
      subset: 'Published snapshot coverage',
      retrieved: 'Retrieved',
    },
  }[locale];

  function emit(metric) {
    if (!METRICS.has(metric)) return;
    if (window.parent !== window) {
      window.parent.postMessage({ type: 'nfp_media_embed_metric', schema_version: 1, partner, metric }, '*');
    }
  }

  async function getText(url) {
    const response = await fetch(url, { cache: 'no-store', credentials: 'omit' });
    if (!response.ok) throw new Error(`HTTP_${response.status}`);
    return response.text();
  }

  async function sha256(text) {
    const bytes = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
  }

  function filterRange(records) {
    if (range === 'all' || range === '5y') return records;
    const latest = new Date(`${records.at(-1).observation_date}T00:00:00Z`);
    const cutoff = new Date(latest);
    cutoff.setUTCFullYear(cutoff.getUTCFullYear() - 1);
    return records.filter((r) => new Date(`${r.observation_date}T00:00:00Z`) >= cutoff);
  }

  function draw(records) {
    const svg = document.getElementById('chart');
    const values = records.map((r) => r.value_thousands);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const span = Math.max(1, hi - lo);
    const width = 760;
    const height = 260;
    const pad = 24;
    const points = records.map((r, i) => {
      const x = pad + ((width - pad * 2) * i) / Math.max(1, records.length - 1);
      const y = height - pad - ((r.value_thousands - lo) / span) * (height - pad * 2);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(' ');
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.innerHTML = `<polyline class="series" fill="none" points="${points}" vector-effect="non-scaling-stroke" />`;
  }

  function bindMetric(id, metric) {
    document.getElementById(id).addEventListener('click', () => emit(metric));
  }

  function failClosed(error) {
    document.documentElement.dataset.state = 'unavailable';
    document.getElementById('loading').hidden = true;
    const failure = document.getElementById('failure');
    failure.hidden = false;
    failure.textContent = `${copy.unavailable} (${String(error.message || error)})`;
  }

  async function main() {
    try {
      const [manifestText, dataText] = await Promise.all([getText(MANIFEST_URL), getText(DATA_URL)]);
      const manifest = JSON.parse(manifestText);
      if (manifest.level_series_available !== true || manifest.analysis_available !== false || manifest.revision_vintage_available !== false) {
        throw new Error('MANIFEST_BOUNDARY');
      }
      const expected = manifest.files?.['total-nonfarm.json'];
      if (!expected || expected.bytes !== new TextEncoder().encode(dataText).length || expected.sha256 !== await sha256(dataText)) {
        throw new Error('CHECKSUM_MISMATCH');
      }
      const data = JSON.parse(dataText);
      if (data.series?.series_id !== 'CES0000000001' || !Array.isArray(data.records) || data.records.length === 0) {
        throw new Error('DATA_CONTRACT');
      }
      const records = filterRange(data.records);
      const latest = data.records.at(-1);
      if (!records.length || latest.observation_date !== manifest.last_observation) throw new Error('COVERAGE_CONTRACT');

      document.documentElement.lang = locale;
      document.getElementById('title').textContent = copy.title;
      document.getElementById('latest-value').textContent = `${latest.value_thousands.toLocaleString(locale === 'ja' ? 'ja-JP' : 'en-US')} thousand`;
      document.getElementById('latest-date').textContent = latest.observation_date;
      const preliminary = document.getElementById('preliminary');
      preliminary.textContent = latest.preliminary ? copy.preliminary : copy.final;
      preliminary.dataset.preliminary = String(latest.preliminary);
      document.getElementById('unit').textContent = data.series.unit;
      document.getElementById('seasonal').textContent = data.series.seasonal_adjustment;
      document.getElementById('retrieved').textContent = `${copy.retrieved}: ${data.source.retrieved_at_utc}`;
      document.getElementById('coverage').textContent = `${copy.subset}: ${data.first_observation} – ${data.last_observation}`;
      document.getElementById('boundary').textContent = copy.boundary;
      document.getElementById('source-link').textContent = copy.source;
      document.getElementById('source-link').href = data.source.url;
      document.getElementById('full-link').textContent = copy.full;
      document.getElementById('inquiry-link').textContent = copy.inquiry;
      document.getElementById('range-label').textContent = range.toUpperCase();
      draw(records);
      document.getElementById('loading').hidden = true;
      document.getElementById('content').hidden = false;
      document.documentElement.dataset.state = 'verified';
      bindMetric('source-link', 'source_opened');
      bindMetric('full-link', 'full_chart_opened');
      bindMetric('inquiry-link', 'business_inquiry_started');
      emit('embed_loaded');
    } catch (error) {
      failClosed(error);
    }
  }

  main();
})();
