from __future__ import annotations

import json

from .constants import ROLE_LABEL, ROLE_MODEL, ROLE_ORDER

def _build_html() -> str:
    # pipeline pills
    pills = []
    for i, r in enumerate(ROLE_ORDER):
        if i:
            pills.append(f'<span class="arrow" id="arrow-{i-1}">→</span>')
        pills.append(f'''
        <div class="pill" id="pill-{r}">
          <span class="pill-name">{ROLE_LABEL[r]}</span>
          <span class="pill-model">{ROLE_MODEL[r]}</span>
        </div>''')

    roles_json = json.dumps(ROLE_ORDER, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>보고서 자동화 하네스</title>
<style>
:root {{
  --blue:#3182F6; --blue-d:#1B64DA;
  --green:#00B493; --red:#F04452;
  --violet:#7C3AED;
  --text:#191F28; --sub:#4E5968; --muted:#8B95A1;
  --border:#E5E8EB; --card:#F9FAFB; --log:#F2F4F6;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#fff;color:var(--text);min-height:100vh;padding-bottom:60px}}
.wrap{{max-width:740px;margin:0 auto;padding:44px 24px}}
h1{{font-size:26px;font-weight:800;letter-spacing:-.5px}}
.sub{{font-size:14px;color:var(--muted);margin-top:6px}}
.sec{{margin-top:36px}}
.sec-title{{font-size:16px;font-weight:700;margin-bottom:14px;color:var(--text)}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:22px}}
.field-label{{font-size:12px;font-weight:700;color:var(--sub);
              text-transform:uppercase;letter-spacing:.4px;margin-bottom:8px}}
.field-desc{{font-size:12px;color:var(--muted);margin-top:4px;margin-bottom:12px}}
select{{appearance:none;background:white;border:1.5px solid var(--border);
        border-radius:10px;padding:10px 16px;font-size:14px;color:var(--text);
        cursor:pointer;font-family:inherit;width:200px;outline:none}}
select:focus{{border-color:var(--blue)}}
.range-row{{display:flex;align-items:center;gap:10px}}
.arrow{{font-size:15px;color:var(--muted);font-weight:600;padding:0 2px}}
hr{{border:none;border-top:1px solid var(--border);margin:20px 0}}
.opts-row{{display:flex;align-items:center;gap:14px;flex-wrap:wrap}}
.mode-row{{display:flex;gap:10px;margin-bottom:14px}}
.mode-btn{{flex:1;border:2px solid var(--border);border-radius:11px;
           padding:13px 0;font-size:15px;font-weight:700;cursor:pointer;
           font-family:inherit;background:#fff;color:var(--sub);transition:all .15s}}
.mode-btn.selected{{border-color:var(--blue);background:#EEF4FF;color:var(--blue)}}
.mode-btn.notion-selected{{border-color:var(--violet);background:#F5F3FF;color:var(--violet)}}
.text-input{{border:1.5px solid var(--border);border-radius:10px;padding:10px 16px;
             font-size:14px;font-family:inherit;color:var(--text);outline:none;
             width:100%;box-sizing:border-box;margin-top:6px}}
.text-input:focus{{border-color:var(--violet)}}
.report-list{{display:flex;flex-direction:column;gap:8px;margin-top:8px}}
.report-card{{border:1.5px solid var(--border);border-radius:10px;padding:12px 16px;
              cursor:pointer;transition:all .15s;background:#fff}}
.report-card:hover{{border-color:var(--violet);background:#F5F3FF}}
.report-card.selected{{border-color:var(--violet);background:#F5F3FF;color:var(--violet)}}
.state-card{{margin-top:12px;border-radius:10px;padding:12px 16px;
             font-size:13px;font-weight:600;min-height:38px;
             background:var(--log);color:var(--sub);display:none}}
.state-card.visible{{display:block}}
.state-card.done{{background:#E6FAF6;color:var(--green)}}
.state-card.error{{background:#FEE8EA;color:var(--red)}}
.num-wrap{{display:flex;align-items:center;gap:8px}}
.num-wrap label{{font-size:13px;font-weight:700;color:var(--sub)}}
input[type=number]{{width:62px;border:1.5px solid var(--border);border-radius:9px;
                   padding:8px 10px;font-size:14px;text-align:center;outline:none;
                   font-family:inherit}}
input[type=number]:focus{{border-color:var(--blue)}}
.actions{{display:flex;gap:10px;margin-top:24px}}
.btn{{border:none;border-radius:11px;padding:13px 26px;font-size:15px;
      font-weight:700;cursor:pointer;font-family:inherit;transition:background .15s}}
.btn-p{{background:var(--blue);color:#fff}}
.btn-p:hover{{background:var(--blue-d)}}
.btn-p:disabled{{background:#D0E4FF;color:var(--blue);cursor:default}}
.btn-d{{background:var(--red);color:#fff}}
.btn-d:hover{{background:#C03040}}
.btn-d:disabled{{background:var(--log);color:var(--muted);cursor:default}}
.btn-d.stopping{{background:#C03040;color:#fff;cursor:default;
                 animation:stop-pulse .9s ease-in-out infinite}}
@keyframes stop-pulse{{0%,100%{{opacity:1}}50%{{opacity:.45}}}}
.btn-s{{background:var(--log);color:var(--sub)}}
.btn-s:hover{{background:var(--border)}}
.btn-sm{{padding:8px 16px;font-size:13px}}
.pipeline{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.pill{{background:var(--log);border-radius:10px;padding:11px 16px;
       text-align:center;min-width:100px;transition:all .2s}}
.pill-name{{display:block;font-size:13px;font-weight:700;color:var(--muted)}}
.pill-model{{display:block;font-size:11px;color:var(--muted);margin-top:2px}}
.pill.active{{background:var(--blue)}}
.pill.active .pill-name,.pill.active .pill-model{{color:#fff}}
.pill.done{{background:var(--green)}}
.pill.done .pill-name,.pill.done .pill-model{{color:#fff}}
.pill.failed{{background:var(--red)}}
.pill.failed .pill-name,.pill.failed .pill-model{{color:#fff}}
.log-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}}
.phase-track{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:14px;min-height:0}}
.phase-pill{{position:relative;overflow:hidden;background:var(--log);border-radius:10px;
             padding:11px 16px;text-align:center;min-width:110px;transition:background .2s}}
.phase-pill-name{{display:block;font-size:13px;font-weight:700;color:var(--muted)}}
.phase-pill-round{{display:block;font-size:11px;color:var(--muted);margin-top:2px;min-height:14px}}
.phase-pill.done{{background:var(--green)}}
.phase-pill.done .phase-pill-name,.phase-pill.done .phase-pill-round{{color:#fff}}
.phase-pill.active{{background:#1a1a1a}}
.phase-pill.active .phase-pill-name,.phase-pill.active .phase-pill-round{{color:#fff}}
.phase-pill.active::after{{content:'';position:absolute;top:0;left:-60%;width:50%;height:100%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);
  animation:wave-sweep 1.8s ease-in-out infinite}}
@keyframes wave-sweep{{0%{{left:-60%}}100%{{left:120%}}}}
.phase-sep{{font-size:15px;color:var(--muted);font-weight:600;padding:0 2px}}
.log-card{{border:1px solid var(--border);border-radius:12px;margin-bottom:10px;overflow:hidden}}
.log-card-hdr{{background:var(--card);padding:10px 16px;font-size:13px;font-weight:700;
               color:var(--sub);display:flex;justify-content:space-between;
               align-items:center;cursor:pointer;user-select:none}}
.log-card-hdr.active{{color:var(--blue)}}
.log-card-hdr.done{{color:var(--green)}}
.log-card-body{{background:var(--log);padding:12px 16px;
                font-family:'Menlo','Consolas',monospace;font-size:12px;line-height:1.7;
                color:#333D4B;max-height:300px;overflow-y:auto;
                white-space:pre-wrap;word-break:break-word}}
.round-sep{{color:var(--muted);font-size:11px;font-weight:700;
            border-top:1px solid var(--border);margin:6px 0;padding-top:6px;display:block}}
.li{{color:#3182F6}} .le{{color:#F04452}} .lg{{color:#00B493}}
.ld{{color:#8B95A1}}
</style>
</head>
<body>
<div class="wrap">
  <h1>보고서 자동화 하네스</h1>
  <p class="sub">교재·강의노트로 예비/결과보고서를 자동 생성합니다</p>

  <div class="sec">
    <div class="sec-title">실행 설정</div>
    <div class="card">
      <div class="field-label">모드 선택</div>
      <div class="mode-row">
        <button class="mode-btn" id="mode-pre" onclick="selectMode('pre')">예비보고서 모드</button>
        <button class="mode-btn" id="mode-result" onclick="selectMode('result')">결과보고서 모드</button>
        <button class="mode-btn" id="mode-notion" onclick="selectMode('notion')">Notion에 배포</button>
      </div>
      <div id="state-card" class="state-card"></div>
      <hr>
      <div id="pipeline-opts">
        <div class="field-label">옵션</div>
        <div class="opts-row" style="margin-top:10px">
          <div class="num-wrap">
            <label>GAN 최대</label>
            <input type="number" id="rounds" value="3" min="1" max="10">
          </div>
        </div>
      </div>
      <div id="notion-ui" style="display:none">
        <div class="field-label">배포할 보고서</div>
        <div id="report-list" class="report-list"><span style="color:var(--muted)">로딩 중...</span></div>
        <div class="field-label" style="margin-top:16px">Notion 상위 페이지 URL</div>
        <input type="text" id="notion-parent-url" class="text-input"
               placeholder="https://www.notion.so/..." oninput="saveNotionPrefs()">
        <div class="field-label" style="margin-top:12px">Notion 통합 토큰</div>
        <input type="password" id="notion-token" class="text-input"
               placeholder="secret_..." oninput="saveNotionPrefs()">
        <div class="field-desc" style="margin-top:4px">Notion → 설정 → 통합 → Internal Integration Token</div>
      </div>
    </div>
  </div>

  <div class="actions">
    <button class="btn btn-p" id="start-btn" onclick="doStart()">실행하기</button>
    <button class="btn btn-d" id="stop-btn" onclick="doStop()" disabled>중단</button>
    <button class="btn btn-s" onclick="doPreview()">미리보기</button>
  </div>

  <div class="sec">
    <div class="sec-title">진행 상황</div>
    <div class="pipeline">{''.join(pills)}</div>
    <div id="phase-track" class="phase-track"></div>
  </div>

  <div class="sec">
    <div class="log-hdr">
      <div class="sec-title" style="margin:0">실행 로그</div>
      <button class="btn btn-s btn-sm" onclick="clearLog()">지우기</button>
    </div>
    <div id="log-container"></div>
  </div>

</div>

<script>
const ROLES   = {roles_json};
let es = null;
let selectedReport = null;
let lastExitCode   = 0;
let currentCardBody = null;
let phaseCardCount  = 0;
let activePhasePill = null;
let isStopping      = false;
let selectedMode    = 'pre';

function setRunning(v) {{
  const stopBtn = document.getElementById('stop-btn');
  document.getElementById('start-btn').disabled = v;
  stopBtn.disabled = !v;
  stopBtn.textContent = '중단';
  stopBtn.classList.remove('stopping');
  if (!v) {{
    if (isStopping) {{
      clearLog();
      resetStages();
      isStopping = false;
    }} else if (activePhasePill) {{
      activePhasePill.className = 'phase-pill' + (lastExitCode === 0 ? ' done' : ' failed');
      activePhasePill = null;
    }}
    if (selectedMode === 'notion') {{
      const card = document.getElementById('state-card');
      if (lastExitCode === 0) {{
        card.className   = 'state-card visible done';
        card.textContent = '✓ Notion에 성공적으로 배포되었습니다.';
        document.getElementById('start-btn').disabled = true;
      }} else {{
        card.className   = 'state-card visible error';
        card.textContent = '✗ 배포 실패 — 아래 로그를 확인하세요.';
      }}
    }} else {{
      setTimeout(() => fetchState(selectedMode), 500);
    }}
  }}
}}

function setStage(role, state) {{
  const el = document.getElementById('pill-' + role);
  if (!el) return;
  el.className = 'pill' + (state !== 'idle' ? ' ' + state : '');
}}

function resetStages() {{ ROLES.forEach(r => setStage(r, 'idle')); }}

const TAG_CLASS = {{info:'li', error:'le', gan:'lg', dim:'ld'}};

/* ── 모드 선택 ── */
function updatePipelineDisplay(mode) {{
  const preRoles    = ['pre-generator', 'pre-reviewer'];
  const resultRoles = ['result-generator', 'result-reviewer'];
  const active = mode === 'pre' ? preRoles : resultRoles;
  ROLES.forEach((r, i) => {{
    const pill  = document.getElementById('pill-' + r);
    const arrow = document.getElementById('arrow-' + i);
    if (pill)  pill.style.display  = active.includes(r) ? '' : 'none';
    if (arrow) arrow.style.display = (active.includes(r) && i < ROLES.length - 1
                                      && active.includes(ROLES[i + 1])) ? '' : 'none';
  }});
}}

async function fetchState(mode) {{
  const card     = document.getElementById('state-card');
  const startBtn = document.getElementById('start-btn');
  card.className = 'state-card visible';
  card.textContent = '상태 확인 중...';
  try {{
    const r    = await fetch('/check-state?mode=' + mode);
    const data = await r.json();
    if (data.error) {{
      card.className   = 'state-card visible error';
      card.textContent = data.error;
      startBtn.disabled = true;
    }} else if (data.step === 'done') {{
      card.className   = 'state-card visible done';
      card.textContent = data.label;
      startBtn.disabled = true;
    }} else {{
      card.className   = 'state-card visible';
      card.textContent = data.label;
      startBtn.disabled = false;
    }}
  }} catch(e) {{
    card.className   = 'state-card visible error';
    card.textContent = '상태 확인 실패: ' + e.message;
    startBtn.disabled = true;
  }}
}}

function selectMode(mode) {{
  selectedMode = mode;
  document.getElementById('mode-pre').classList.toggle('selected',         mode === 'pre');
  document.getElementById('mode-result').classList.toggle('selected',      mode === 'result');
  document.getElementById('mode-notion').classList.toggle('notion-selected', mode === 'notion');

  const isNotion = mode === 'notion';
  document.getElementById('pipeline-opts').style.display  = isNotion ? 'none' : '';
  document.getElementById('notion-ui').style.display      = isNotion ? ''     : 'none';
  document.querySelector('.pipeline').style.display       = isNotion ? 'none' : '';
  document.getElementById('start-btn').textContent        = isNotion ? '배포하기' : '실행하기';

  if (isNotion) {{
    fetchReportList();
    loadNotionPrefs();
    document.getElementById('state-card').className = 'state-card';
    document.getElementById('start-btn').disabled = true;
  }} else {{
    document.getElementById('start-btn').disabled = false;
    updatePipelineDisplay(mode);
    fetchState(mode);
  }}
}}

/* ── Notion 모드 함수 ── */
async function fetchReportList() {{
  const list = document.getElementById('report-list');
  list.innerHTML = '<span style="color:var(--muted)">로딩 중...</span>';
  selectedReport = null;
  try {{
    const r    = await fetch('/list-reports');
    const data = await r.json();
    if (!data.files || data.files.length === 0) {{
      list.innerHTML = '<span style="color:var(--muted)">output/ 폴더에 보고서 파일이 없습니다.</span>';
      return;
    }}
    list.innerHTML = '';
    data.files.forEach(f => {{
      const card = document.createElement('div');
      card.className = 'report-card';
      card.innerHTML =
        `<div class="report-card-name">${{f.name}}</div>` +
        `<div class="field-desc">${{(f.size / 1024).toFixed(1)}} KB</div>`;
      card.onclick = () => {{
        list.querySelectorAll('.report-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedReport = f.path;
        document.getElementById('start-btn').disabled = false;
        document.getElementById('state-card').className = 'state-card';
      }};
      list.appendChild(card);
    }});
  }} catch(e) {{
    list.innerHTML = `<span style="color:var(--red)">보고서 목록 로드 실패: ${{e.message}}</span>`;
  }}
}}

function loadNotionPrefs() {{
  document.getElementById('notion-parent-url').value =
    localStorage.getItem('notion_parent_url') || '';
  document.getElementById('notion-token').value =
    localStorage.getItem('notion_token') || '';
}}

function saveNotionPrefs() {{
  localStorage.setItem('notion_parent_url',
    document.getElementById('notion-parent-url').value);
  localStorage.setItem('notion_token',
    document.getElementById('notion-token').value);
}}

async function doDeployNotion() {{
  const parentUrl = document.getElementById('notion-parent-url').value.trim();
  const token     = document.getElementById('notion-token').value.trim();
  if (!selectedReport) {{ alert('배포할 보고서를 선택해주세요.'); return; }}
  if (!parentUrl)      {{ alert('Notion 상위 페이지 URL을 입력해주세요.'); return; }}
  if (!token)          {{ alert('Notion 통합 토큰을 입력해주세요.'); return; }}
  await post('/deploy-notion', {{ file: selectedReport, parentUrl, token }});
}}

/* ── Phase 트랙 ── */
function addPhaseCard(title) {{
  const track = document.getElementById('phase-track');
  if (activePhasePill) activePhasePill.className = 'phase-pill done';
  if (phaseCardCount > 0) {{
    const sep = document.createElement('span');
    sep.className = 'phase-sep';
    sep.textContent = '→';
    track.appendChild(sep);
  }}
  const pill = document.createElement('div');
  pill.className = 'phase-pill active';
  const nameEl = document.createElement('span');
  nameEl.className = 'phase-pill-name';
  nameEl.textContent = title;
  const roundEl = document.createElement('span');
  roundEl.className = 'phase-pill-round';
  pill.appendChild(nameEl);
  pill.appendChild(roundEl);
  track.appendChild(pill);
  activePhasePill = pill;
  phaseCardCount++;
}}

function updatePhaseRound(round, maxRounds) {{
  if (activePhasePill) {{
    activePhasePill.querySelector('.phase-pill-round').textContent =
      '라운드 ' + round + ' / ' + maxRounds;
  }}
}}

/* ── 로그 카드 ── */
function createLogCard(title) {{
  const container = document.getElementById('log-container');
  container.querySelectorAll('.log-card-hdr.active').forEach(h => {{
    h.className = 'log-card-hdr done';
  }});
  const card = document.createElement('div');
  card.className = 'log-card';
  const hdr = document.createElement('div');
  hdr.className = 'log-card-hdr active';
  hdr.textContent = title;
  const body = document.createElement('div');
  body.className = 'log-card-body';
  hdr.onclick = () => {{ body.style.display = body.style.display === 'none' ? '' : 'none'; }};
  card.appendChild(hdr);
  card.appendChild(body);
  container.appendChild(card);
  currentCardBody = body;
  return body;
}}

function ensureDefaultCard() {{
  if (!currentCardBody) createLogCard('일반');
  return currentCardBody;
}}

function appendLog(text, tag) {{
  const target = ensureDefaultCard();
  const s = document.createElement('span');
  if (tag && TAG_CLASS[tag]) s.className = TAG_CLASS[tag];
  s.textContent = text;
  target.appendChild(s);
  target.scrollTop = target.scrollHeight;
}}

function clearLog() {{
  document.getElementById('log-container').innerHTML = '';
  document.getElementById('phase-track').innerHTML   = '';
  currentCardBody = null;
  phaseCardCount  = 0;
  activePhasePill = null;
}}

function connectSSE() {{
  if (es) {{ es.close(); }}
  es = new EventSource('/events');
  es.onmessage = e => {{
    const m = JSON.parse(e.data);
    if      (m.type === 'log')     appendLog(m.text, m.tag);
    else if (m.type === 'stage')   setStage(m.role, m.state);
    else if (m.type === 'running') setRunning(m.value);
    else if (m.type === 'clear')   {{ clearLog(); resetStages(); }}
    else if (m.type === 'done')    {{ lastExitCode = m.code; setRunning(false); }}
    else if (m.type === 'phase_start') {{
      addPhaseCard(m.title);
      createLogCard(m.title);
    }}
    else if (m.type === 'notion_upload') {{
      if (activePhasePill) {{
        activePhasePill.querySelector('.phase-pill-round').textContent =
          m.uploaded + ' / ' + m.total + ' 블록';
      }}
    }}
    else if (m.type === 'phase_round') {{
      updatePhaseRound(m.round, m.maxRounds);
      if (currentCardBody) {{
        const sep = document.createElement('span');
        sep.className = 'round-sep';
        sep.textContent = '─── 라운드 ' + m.round + ' / ' + m.maxRounds + ' ───';
        currentCardBody.appendChild(sep);
        currentCardBody.scrollTop = currentCardBody.scrollHeight;
      }}
    }}
  }};
  es.onerror = () => setTimeout(connectSSE, 2000);
}}

async function post(path, body={{}}) {{
  return fetch(path, {{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify(body)}});
}}

async function doStart() {{
  if (selectedMode === 'notion') {{
    await doDeployNotion();
  }} else {{
    await post('/start', {{
      mode: selectedMode,
      maxRounds: +document.getElementById('rounds').value,
    }});
  }}
}}

async function doStop() {{
  isStopping = true;
  const btn = document.getElementById('stop-btn');
  btn.textContent = '중단 중...';
  btn.classList.add('stopping');
  btn.disabled = true;
  await post('/stop');
}}

async function doPreview() {{
  clearLog(); resetStages();
  const r = await fetch('/preview?mode=' + selectedMode
    + '&rounds=' + document.getElementById('rounds').value);
  createLogCard('미리보기');
  appendLog(await r.text(), 'dim');
}}

connectSSE();
document.addEventListener('DOMContentLoaded', () => selectMode('pre'));
</script>
</body>
</html>"""
