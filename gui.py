#!/usr/bin/env python3
"""기초전기실험 보고서 자동화 하네스 GUI.

로컬 웹서버를 띄운 후 브라우저를 자동으로 엽니다.
추가 설치 없이 Python 표준 라이브러리만 사용합니다.

Usage:
    python gui.py          # 기본 포트 7788
    python gui.py --port 9000
"""
from __future__ import annotations

import argparse
import json
import re
import socketserver
import subprocess
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

PROJECT_DIR   = Path(__file__).parent.resolve()
HARNESS       = PROJECT_DIR / "harness.py"
NOTION_DEPLOY = PROJECT_DIR / "harness_core" / "notion_deploy.py"
PYTHON        = sys.executable
DEFAULT_PORT  = 7788

ROLE_ORDER = ["pre-generator", "pre-reviewer", "result-generator", "result-reviewer"]
ROLE_LABEL = {
    "pre-generator":    "예비 생성",
    "pre-reviewer":     "예비 검토",
    "result-generator": "결과 생성",
    "result-reviewer":  "결과 검토",
}
ROLE_MODEL = {
    "pre-generator":    "Opus",
    "pre-reviewer":     "Sonnet",
    "result-generator": "Opus",
    "result-reviewer":  "Sonnet",
}
ANSI             = re.compile(r"\033\[[0-9;]*m")
PHASE_START_RE   = re.compile(r'── ((?:결과보고서 )?Phase \d+): (.+?) ──')
PHASE_ROUND_RE   = re.compile(r'── Phase (\d+) 라운드 (\d+)/(\d+) ──')
NOTION_STEP_RE   = re.compile(r'\[deploy:step\] (.+)')
NOTION_UPLOAD_RE = re.compile(r'\[deploy\] 블록 업로드 (\d+)/(\d+)')

# ---------------------------------------------------------------------------
# 상태 감지 (harness_core.io_state 활용)
# ---------------------------------------------------------------------------

try:
    from harness_core.io_state import detect_pre_report_state, detect_result_report_state
    from harness_core.config import OUTPUT_DIR as _OUTPUT_DIR, MEASURED_DIR as _MEASURED_DIR
    _STATE_DETECTION_AVAILABLE = True
except ImportError:
    _STATE_DETECTION_AVAILABLE = False
    _OUTPUT_DIR   = PROJECT_DIR / "output"
    _MEASURED_DIR = PROJECT_DIR / "input" / "measured"

# 모드별 --from / --to 고정 매핑
_STEP_CLI_ARGS = {
    "pre":    {"from": "pre-generator",    "to": "pre-reviewer"},
    "result": {"from": "result-generator", "to": "result-reviewer"},
}

def _get_state(mode: str) -> dict:
    """파일 상태를 감지하여 step/label/error 딕셔너리를 반환한다."""
    if not _STATE_DETECTION_AVAILABLE:
        return {"step": "p1g", "label": "상태 감지 불가 (harness_core 없음)", "error": None}
    try:
        if mode == "pre":
            return detect_pre_report_state(output_dir=_OUTPUT_DIR)
        else:
            return detect_result_report_state(output_dir=_OUTPUT_DIR, measured_dir=_MEASURED_DIR)
    except Exception as exc:
        return {"step": "p1g", "label": "상태 감지 오류", "error": str(exc)}

# ---------------------------------------------------------------------------
# 앱 상태 (전역 싱글톤)
# ---------------------------------------------------------------------------

class _AppState:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self._listeners: list[list] = []   # SSE 클라이언트별 이벤트 버퍼
        self._lock = threading.Lock()
        self._stream_done = 0

    def broadcast(self, event: dict) -> None:
        data = json.dumps(event, ensure_ascii=False)
        with self._lock:
            for buf in self._listeners:
                buf.append(data)

    def add_listener(self, buf: list) -> None:
        with self._lock:
            self._listeners.append(buf)

    def remove_listener(self, buf: list) -> None:
        with self._lock:
            if buf in self._listeners:
                self._listeners.remove(buf)

    def on_stream_done(self) -> None:
        should_notify = False
        proc = None
        with self._lock:
            self._stream_done += 1
            if self._stream_done >= 2:
                self._stream_done = 0
                proc = self.proc
                should_notify = True
        if should_notify:
            code = -1
            if proc is not None:
                try:
                    # poll() 대신 wait() 사용: Windows에서 파이프 EOF 직후
                    # 프로세스가 아직 완전히 종료되지 않아 poll()이 None을
                    # 반환하는 경쟁 조건을 방지한다.
                    code = proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    code = proc.poll() if proc.poll() is not None else -1
            self.broadcast({"type": "done", "code": code})
            self.broadcast({"type": "running", "value": False})

state = _AppState()

# ---------------------------------------------------------------------------
# HTML 템플릿
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# HTTP 핸들러
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html()
        elif parsed.path == "/events":
            self._sse()
        elif parsed.path == "/preview":
            self._preview(parse_qs(parsed.query))
        elif parsed.path == "/check-state":
            self._check_state(parse_qs(parsed.query))
        elif parsed.path == "/list-reports":
            self._list_reports()
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._read_json()
        if path == "/start":
            self._start(body)
        elif path == "/stop":
            self._stop()
        elif path == "/deploy-notion":
            self._deploy_notion(body)
        else:
            self.send_error(404)

    # ── GET 핸들러 ──────────────────────────────────────────────────────────

    def _html(self) -> None:
        data = _build_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        buf: list[str] = []
        state.add_listener(buf)
        try:
            while True:
                if buf:
                    items = buf.copy()
                    buf.clear()
                    for item in items:
                        self.wfile.write(f"data: {item}\n\n".encode("utf-8"))
                    self.wfile.flush()
                else:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            state.remove_listener(buf)

    def _preview(self, qs: dict) -> None:
        mode       = qs.get("mode",   ["pre"])[0]
        max_rounds = qs.get("rounds", ["3"])[0]
        detected   = _get_state(mode)
        step       = detected.get("step") or "p1g"
        cli_roles  = _STEP_CLI_ARGS.get(mode, _STEP_CLI_ARGS["pre"])
        cmd = [PYTHON, str(HARNESS),
               "--from", cli_roles["from"], "--to", cli_roles["to"],
               "--max-rounds", max_rounds,
               "--start-step", step,
               "--dry-run"]
        res = subprocess.run(cmd, capture_output=True, text=True,
                             cwd=str(PROJECT_DIR))
        data = (res.stdout or res.stderr or "결과 없음").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _check_state(self, qs: dict) -> None:
        mode = qs.get("mode", ["pre"])[0]
        if mode not in ("pre", "result"):
            self._json({"error": "mode must be pre or result"}, 400)
            return
        result = _get_state(mode)
        self._json(result)

    def _list_reports(self) -> None:
        files = []
        if _OUTPUT_DIR.exists():
            for f in sorted(_OUTPUT_DIR.glob("*.md")):
                if re.search(r"\d+주차.*(예비|결과)보고서\.md$", f.name):
                    files.append({
                        "name": f.name,
                        "path": str(f),
                        "size": f.stat().st_size,
                    })
        self._json({"files": files})

    # ── POST 핸들러 ─────────────────────────────────────────────────────────

    def _start(self, body: dict) -> None:
        if state.proc and state.proc.poll() is None:
            self._json({"error": "이미 실행 중"}, 400)
            return

        mode       = body.get("mode",      "pre")
        max_rounds = body.get("maxRounds", 3)

        # 최신 파일 상태 재감지
        detected = _get_state(mode)
        if detected.get("error"):
            self._json({"error": detected["error"]}, 400)
            return
        step = detected.get("step", "p1g")
        if step == "done":
            self._json({"error": "이미 완성됨 — 실행할 단계가 없습니다."}, 400)
            return

        cli_roles = _STEP_CLI_ARGS.get(mode, _STEP_CLI_ARGS["pre"])
        cmd = [PYTHON, str(HARNESS),
               "--from", cli_roles["from"], "--to", cli_roles["to"],
               "--max-rounds", str(max_rounds),
               "--start-step", step]

        state.broadcast({"type": "clear"})
        state.broadcast({"type": "log", "text": f"$ {' '.join(cmd[2:])}\n\n", "tag": "dim"})

        state._stream_done = 0
        state.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=str(PROJECT_DIR),
        )
        state.broadcast({"type": "running", "value": True})

        threading.Thread(target=_reader, args=(state.proc.stdout, "out"),
                         daemon=True).start()
        threading.Thread(target=_reader, args=(state.proc.stderr, "err"),
                         daemon=True).start()

        self._json({"ok": True})

    def _stop(self) -> None:
        if state.proc and state.proc.poll() is None:
            state.proc.terminate()
        self._json({"ok": True})

    def _deploy_notion(self, body: dict) -> None:
        if state.proc and state.proc.poll() is None:
            self._json({"error": "이미 실행 중"}, 400)
            return

        file_path  = body.get("file", "")
        parent_url = body.get("parentUrl", "")
        token      = body.get("token", "")

        if not file_path or not parent_url or not token:
            self._json({"error": "file, parentUrl, token 모두 필요합니다."}, 400)
            return

        if not Path(file_path).exists():
            self._json({"error": f"파일을 찾을 수 없습니다: {file_path}"}, 400)
            return

        cmd = [PYTHON, str(NOTION_DEPLOY),
               "--file", file_path,
               "--parent-url", parent_url,
               "--token", token]

        state.broadcast({"type": "clear"})
        state.broadcast({"type": "log",
                          "text": f"$ notion_deploy --file {Path(file_path).name}\n\n",
                          "tag": "dim"})

        state._stream_done = 0
        state.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, cwd=str(PROJECT_DIR),
        )
        state.broadcast({"type": "running", "value": True})

        threading.Thread(target=_reader, args=(state.proc.stdout, "out"),
                         daemon=True).start()
        threading.Thread(target=_reader, args=(state.proc.stderr, "err"),
                         daemon=True).start()

        self._json({"ok": True})

    # ── 공통 ────────────────────────────────────────────────────────────────

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _json(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args) -> None:
        pass  # 서버 로그 억제


# ---------------------------------------------------------------------------
# 스트림 리더 스레드
# ---------------------------------------------------------------------------

def _reader(stream, name: str) -> None:
    try:
        for line in stream:
            clean = ANSI.sub("", line.rstrip("\n"))
            if not clean:
                continue

            # Notion 배포 단계 마커 → phase_start 이벤트만 emit, 로그에는 출력 안 함
            ms = NOTION_STEP_RE.search(clean)
            if ms:
                state.broadcast({"type": "phase_start", "title": ms.group(1)})
                continue

            is_err = (name == "err")
            if is_err or ("✗" in clean or ("FAIL" in clean and "[harness]" in clean)):
                tag = "error"
            elif "── Phase" in clean and "라운드" in clean:
                tag = "gan"
            elif "[harness]" in clean or "[deploy]" in clean:
                tag = "info"
            else:
                tag = "default"

            state.broadcast({"type": "log", "text": clean + "\n", "tag": tag})

            # Notion 블록 업로드 진행률 → notion_upload 이벤트
            mu = NOTION_UPLOAD_RE.search(clean)
            if mu:
                state.broadcast({"type": "notion_upload",
                                  "uploaded": int(mu.group(1)),
                                  "total":    int(mu.group(2))})

            for role in ROLE_ORDER:
                if f"▶ {role} 시작" in clean:
                    state.broadcast({"type": "stage", "role": role, "state": "active"})
                elif f"✓ {role} 완료" in clean:
                    state.broadcast({"type": "stage", "role": role, "state": "done"})
                elif f"✗ {role} 실패" in clean:
                    state.broadcast({"type": "stage", "role": role, "state": "failed"})

            m = PHASE_START_RE.search(clean)
            if m:
                state.broadcast({"type": "phase_start",
                                  "title": f"{m.group(1)}: {m.group(2)}"})

            m = PHASE_ROUND_RE.search(clean)
            if m:
                state.broadcast({"type": "phase_round",
                                  "phase": int(m.group(1)),
                                  "round": int(m.group(2)),
                                  "maxRounds": int(m.group(3))})
    finally:
        state.on_stream_done()


# ---------------------------------------------------------------------------
# 서버 실행
# ---------------------------------------------------------------------------

class _ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:  # type: ignore[override]
        """클라이언트 연결 중단 등 무해한 소켓 오류는 조용히 무시한다."""
        import sys
        exc = sys.exc_info()[1]
        _IGNORED_CONN_ERRORS = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)
        if isinstance(exc, _IGNORED_CONN_ERRORS):
            return
        super().handle_error(request, client_address)


def _free_port(port: int) -> None:
    """해당 포트를 점유 중인 프로세스를 종료한다."""
    import signal
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ProcessLookupError, ValueError):
                pass
        if pids:
            time.sleep(0.3)
    except FileNotFoundError:
        pass  # lsof 없는 환경(Windows)은 건너뜀


def main() -> None:
    parser = argparse.ArgumentParser(description="보고서 자동화 하네스 GUI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    _free_port(args.port)

    url = f"http://localhost:{args.port}"
    server = _ThreadingHTTPServer(("", args.port), Handler)

    print(f"GUI 서버 시작: {url}")
    print("브라우저가 자동으로 열립니다. 종료하려면 Ctrl+C 를 누르세요.")

    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료.")


if __name__ == "__main__":
    main()
