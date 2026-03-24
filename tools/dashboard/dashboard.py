#!/usr/bin/env python3
"""
SEC 15c3-5 Market Access Controls — Live Demo Dashboard

Single-file web dashboard for demonstrating the kill switch lifecycle.
Serves a real-time HTML dashboard on localhost:8080 and proxies to AWS.

Usage:
    python3 tools/dashboard.py [--port 8080] [--region us-east-1]

Prerequisites:
    - AWS credentials configured (same as AWS CLI)
    - boto3 installed (comes with AWS CLI)
    - Infrastructure deployed via Terraform
"""

import argparse
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NAME_PREFIX = "sec-15c3-5"
ENVIRONMENT = "dev"
API_URL = "https://zjawxgdsth.execute-api.us-east-1.amazonaws.com"

TABLE_STATE = f"{NAME_PREFIX}-{ENVIRONMENT}-state-cache"
TABLE_AUDIT = f"{NAME_PREFIX}-{ENVIRONMENT}-audit-index"
FN_ORDER_GEN = f"{NAME_PREFIX}-{ENVIRONMENT}-order-generator"
FN_AGGREGATOR = f"{NAME_PREFIX}-{ENVIRONMENT}-killswitch-aggregator"
FN_ROUTER = f"{NAME_PREFIX}-{ENVIRONMENT}-order-router"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("dashboard")

# ---------------------------------------------------------------------------
# AWS helpers
# ---------------------------------------------------------------------------

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def json_dumps(obj):
    return json.dumps(obj, cls=DecimalEncoder)


def get_clients(region):
    return {
        "dynamodb": boto3.resource("dynamodb", region_name=region),
        "lambda": boto3.client("lambda", region_name=region),
    }


def read_state(ddb):
    table = ddb.Table(TABLE_STATE)
    try:
        resp = table.scan()
        items = resp.get("Items", [])
        return items
    except ClientError as e:
        log.error("DynamoDB state read failed: %s", e)
        return []


def read_audit(ddb, limit=50):
    table = ddb.Table(TABLE_AUDIT)
    try:
        resp = table.scan(Limit=limit)
        items = resp.get("Items", [])
        items.sort(key=lambda x: x.get("ts", 0), reverse=True)
        return items
    except ClientError as e:
        log.error("DynamoDB audit read failed: %s", e)
        return []


def invoke_lambda_async(lam, fn_name, payload):
    try:
        resp = lam.invoke(
            FunctionName=fn_name,
            InvocationType="Event",
            Payload=json.dumps(payload).encode(),
        )
        return {"success": True, "status": resp["StatusCode"]}
    except ClientError as e:
        return {"success": False, "error": str(e)}


def proxy_api(method, path, body=None):
    url = f"{API_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode()}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# HTML Dashboard (embedded)
# ---------------------------------------------------------------------------

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SEC 15c3-5 — Live Demo</title>
<style>
/* ── Reset & Base ─────────────────────────────────────────────── */
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0a0e17;--surface:#111827;--border:#1e293b;
  --text:#e2e8f0;--muted:#64748b;
  --green:#22c55e;--red:#ef4444;--amber:#f59e0b;--cyan:#06b6d4;
  --green-bg:rgba(34,197,94,.12);--red-bg:rgba(239,68,68,.12);
}
body{font-family:'SF Mono','Fira Code','Cascadia Code',monospace;
     background:var(--bg);color:var(--text);font-size:13px;overflow:hidden;height:100vh}
button{font-family:inherit;cursor:pointer;border:none;border-radius:6px;
       padding:8px 16px;font-size:12px;font-weight:600;transition:all .15s}
button:active{transform:scale(.96)}

/* ── Header ───────────────────────────────────────────────────── */
.header{display:flex;align-items:center;justify-content:space-between;
        padding:12px 24px;border-bottom:1px solid var(--border);background:var(--surface)}
.header h1{font-size:15px;font-weight:700;letter-spacing:-.3px}
.header h1 span{color:var(--cyan)}
.status-pill{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted)}
.status-dot{width:8px;height:8px;border-radius:50%;background:var(--green);
            animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* ── Grid Layout ──────────────────────────────────────────────── */
.grid{display:grid;grid-template-columns:280px 1fr 300px;grid-template-rows:1fr auto;
      gap:1px;background:var(--border);height:calc(100vh - 49px)}
.grid>div{background:var(--bg);padding:16px;overflow-y:auto}

/* ── Panel Headers ────────────────────────────────────────────── */
.panel-title{font-size:11px;font-weight:700;text-transform:uppercase;
             letter-spacing:1px;color:var(--muted);margin-bottom:12px}

/* ── Kill Switch Panel (left) ─────────────────────────────────── */
.scope-card{background:var(--surface);border-radius:8px;padding:12px;
            margin-bottom:8px;border:1px solid var(--border);transition:all .3s}
.scope-card.killed{border-color:var(--red);background:var(--red-bg)}
.scope-card.active{border-color:var(--green);background:var(--green-bg)}
.scope-header{display:flex;justify-content:space-between;align-items:center}
.scope-name{font-weight:700;font-size:13px}
.scope-badge{font-size:10px;font-weight:700;padding:3px 8px;border-radius:4px;text-transform:uppercase}
.scope-badge.killed{background:var(--red);color:#fff}
.scope-badge.active{background:var(--green);color:#fff}
.scope-badge.unknown{background:var(--muted);color:#fff}
.scope-meta{font-size:10px;color:var(--muted);margin-top:6px}
.scope-actions{margin-top:8px;display:flex;gap:4px}
.scope-actions button{font-size:10px;padding:4px 10px}
.btn-kill{background:var(--red);color:#fff}
.btn-kill:hover{background:#dc2626}
.btn-unkill{background:var(--green);color:#fff}
.btn-unkill:hover{background:#16a34a}

/* ── Order Feed (center) ──────────────────────────────────────── */
.feed-table{width:100%;border-collapse:collapse}
.feed-table th{position:sticky;top:0;background:var(--surface);text-align:left;
               font-size:10px;text-transform:uppercase;letter-spacing:.8px;
               color:var(--muted);padding:6px 8px;border-bottom:1px solid var(--border)}
.feed-table td{padding:5px 8px;border-bottom:1px solid var(--border);font-size:12px;
               white-space:nowrap}
.feed-table tr{transition:background .3s}
.feed-table tr.new-row{animation:flashRow .6s}
@keyframes flashRow{0%{background:rgba(6,182,212,.15)}100%{background:transparent}}
.decision-allow{color:var(--green);font-weight:700}
.decision-drop{color:var(--red);font-weight:700}

/* ── Controls (right) ─────────────────────────────────────────── */
.ctrl-section{margin-bottom:16px}
.ctrl-section h3{font-size:11px;color:var(--muted);text-transform:uppercase;
                 letter-spacing:.8px;margin-bottom:8px}
.ctrl-btn{width:100%;margin-bottom:6px;display:flex;align-items:center;gap:8px;
          justify-content:center;padding:10px 16px}
.btn-primary{background:var(--cyan);color:#000}
.btn-primary:hover{background:#22d3ee}
.btn-danger{background:var(--red);color:#fff}
.btn-danger:hover{background:#dc2626}
.btn-success{background:var(--green);color:#fff}
.btn-success:hover{background:#16a34a}
.btn-amber{background:var(--amber);color:#000}
.btn-amber:hover{background:#fbbf24}
.btn-secondary{background:var(--surface);color:var(--text);border:1px solid var(--border)}
.btn-secondary:hover{background:var(--border)}

/* spinner on buttons */
.btn-loading{opacity:.6;pointer-events:none}
.btn-loading::after{content:" ..."}

/* ── Stats Bar (bottom) ───────────────────────────────────────── */
.stats-bar{grid-column:1/-1;display:flex;gap:32px;align-items:center;
           padding:10px 24px !important;border-top:1px solid var(--border);
           background:var(--surface) !important;overflow:visible}
.stat{display:flex;flex-direction:column;align-items:center}
.stat-value{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
.stat-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.stat-value.green{color:var(--green)}
.stat-value.red{color:var(--red)}
.stat-value.amber{color:var(--amber)}

/* ── Log Toast ────────────────────────────────────────────────── */
.toast-area{position:fixed;bottom:60px;right:24px;display:flex;flex-direction:column;
            gap:6px;z-index:100;pointer-events:none}
.toast{background:var(--surface);border:1px solid var(--border);border-radius:8px;
       padding:8px 14px;font-size:11px;animation:toastIn .3s,toastOut .3s 3s forwards}
.toast.error{border-color:var(--red)}
.toast.success{border-color:var(--green)}
@keyframes toastIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes toastOut{to{opacity:0;transform:translateY(-10px)}}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <h1><span>SEC 15c3-5</span> Market Access Controls — Live Demo</h1>
  <div class="status-pill">
    <div class="status-dot" id="connDot"></div>
    <span id="connText">Connecting...</span>
  </div>
</div>

<!-- Main Grid -->
<div class="grid">

  <!-- Left: Kill Switch State -->
  <div id="statePanel">
    <div class="panel-title">Kill Switch Status</div>
    <div id="scopeCards">
      <div style="color:var(--muted);font-size:12px">Loading state...</div>
    </div>
  </div>

  <!-- Center: Order Feed -->
  <div>
    <div class="panel-title">Live Order Feed</div>
    <table class="feed-table">
      <thead><tr>
        <th>Time</th><th>Order ID</th><th>Account</th><th>Symbol</th>
        <th>Side</th><th>Qty</th><th>Decision</th><th>Reason</th>
      </tr></thead>
      <tbody id="feedBody"></tbody>
    </table>
  </div>

  <!-- Right: Controls -->
  <div>
    <div class="panel-title">Controls</div>

    <div class="ctrl-section">
      <h3>Services</h3>
      <button class="ctrl-btn btn-primary" onclick="startServices()">
        &#9654; Start Services
      </button>
    </div>

    <div class="ctrl-section">
      <h3>Order Generation</h3>
      <button class="ctrl-btn btn-success" onclick="generateOrders('normal')">
        Generate Normal Orders
      </button>
      <button class="ctrl-btn btn-danger" onclick="generateOrders('panic')">
        &#9888; Trigger Panic Mode
      </button>
    </div>

    <div class="ctrl-section">
      <h3>Manual Kill Switch</h3>
      <button class="ctrl-btn btn-danger" onclick="killScope('GLOBAL')">
        KILL GLOBAL
      </button>
      <button class="ctrl-btn btn-danger" onclick="killScope('SYMBOL:AAPL')">
        KILL SYMBOL:AAPL
      </button>
      <button class="ctrl-btn btn-danger" onclick="killScope('ACCOUNT:99999')">
        KILL ACCOUNT:99999
      </button>
    </div>

    <div class="ctrl-section">
      <h3>Recovery</h3>
      <button class="ctrl-btn btn-success" onclick="unkillScope('GLOBAL')">
        UNKILL GLOBAL
      </button>
      <button class="ctrl-btn btn-success" onclick="unkillScope('SYMBOL:AAPL')">
        UNKILL SYMBOL:AAPL
      </button>
      <button class="ctrl-btn btn-success" onclick="unkillScope('ACCOUNT:99999')">
        UNKILL ACCOUNT:99999
      </button>
    </div>

    <div class="ctrl-section">
      <h3>Cleanup</h3>
      <button class="ctrl-btn btn-secondary" onclick="resetAll()">
        Reset All Kill Switches
      </button>
    </div>
  </div>

  <!-- Bottom: Stats -->
  <div class="stats-bar">
    <div class="stat"><span class="stat-value" id="statTotal">0</span><span class="stat-label">Total Orders</span></div>
    <div class="stat"><span class="stat-value green" id="statAllowed">0</span><span class="stat-label">Allowed</span></div>
    <div class="stat"><span class="stat-value red" id="statDropped">0</span><span class="stat-label">Dropped</span></div>
    <div class="stat"><span class="stat-value amber" id="statKills">0</span><span class="stat-label">Active Kills</span></div>
    <div class="stat"><span class="stat-value" id="statLastUpdate" style="font-size:12px">—</span><span class="stat-label">Last Update</span></div>
  </div>
</div>

<!-- Toast container -->
<div class="toast-area" id="toastArea"></div>

<script>
// ── State ──────────────────────────────────────────────────────
let seenOrderIds = new Set();
let feedRows = [];
const MAX_FEED = 200;
let prevState = {};

// ── Helpers ────────────────────────────────────────────────────
function toast(msg, type='info') {
  const d = document.createElement('div');
  d.className = 'toast ' + type;
  d.textContent = msg;
  document.getElementById('toastArea').appendChild(d);
  setTimeout(() => d.remove(), 3300);
}

async function api(method, path, body) {
  const opts = {method, headers:{'Content-Type':'application/json'}};
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  return r.json();
}

function fmtTime(ts) {
  if (!ts) return '—';
  const d = new Date(typeof ts === 'number' ? (ts > 1e12 ? ts : ts*1000) : ts);
  return d.toLocaleTimeString();
}

function shortId(id) {
  return id ? id.substring(0,8) : '—';
}

function setLoading(btn, loading) {
  if (loading) btn.classList.add('btn-loading');
  else btn.classList.remove('btn-loading');
}

// ── Render State Panel ─────────────────────────────────────────
const WATCHED_SCOPES = ['GLOBAL','SYMBOL:AAPL','SYMBOL:GOOGL','SYMBOL:MSFT',
                        'SYMBOL:TSLA','ACCOUNT:99999'];

function renderState(items) {
  const map = {};
  items.forEach(i => { map[i.scope] = i; });

  // add any scopes from API that aren't in our watch list
  const allScopes = [...WATCHED_SCOPES];
  items.forEach(i => {
    if (!allScopes.includes(i.scope)) allScopes.push(i.scope);
  });

  let html = '';
  let activeKills = 0;
  allScopes.forEach(scope => {
    const item = map[scope];
    const status = item ? item.status : 'UNKNOWN';
    const killed = status === 'KILLED';
    if (killed) activeKills++;
    const cls = killed ? 'killed' : (status === 'ACTIVE' ? 'active' : '');
    const badgeCls = killed ? 'killed' : (status === 'ACTIVE' ? 'active' : 'unknown');

    // flash if state changed
    const prevStatus = prevState[scope];
    const changed = prevStatus && prevStatus !== status;

    html += `<div class="scope-card ${cls}" ${changed ? 'style="animation:flashRow .6s"' : ''}>
      <div class="scope-header">
        <span class="scope-name">${scope}</span>
        <span class="scope-badge ${badgeCls}">${status}</span>
      </div>
      ${item ? `<div class="scope-meta">${item.reason || ''}<br>Updated: ${fmtTime(item.updated_ts)} by ${item.updated_by || '—'}</div>` : ''}
    </div>`;

    prevState[scope] = status;
  });

  document.getElementById('scopeCards').innerHTML = html;
  document.getElementById('statKills').textContent = activeKills;
}

// ── Render Audit Feed ──────────────────────────────────────────
function renderAudit(items) {
  const tbody = document.getElementById('feedBody');
  let newCount = 0;
  let allowed = 0, dropped = 0;

  items.forEach(item => {
    if (item.decision === 'ALLOW') allowed++;
    else if (item.decision === 'DROP') dropped++;

    if (seenOrderIds.has(item.order_id)) return;
    seenOrderIds.add(item.order_id);
    newCount++;

    const isAllow = item.decision === 'ALLOW';
    const row = document.createElement('tr');
    row.className = 'new-row';
    row.innerHTML = `
      <td>${fmtTime(item.ts)}</td>
      <td>${shortId(item.order_id)}</td>
      <td>${item.account_id || '—'}</td>
      <td>${item.symbol || '—'}</td>
      <td>${item.side || '—'}</td>
      <td>${item.qty || '—'}</td>
      <td class="${isAllow ? 'decision-allow' : 'decision-drop'}">${item.decision}</td>
      <td style="color:var(--muted);max-width:120px;overflow:hidden;text-overflow:ellipsis">${item.reason || ''}</td>`;
    feedRows.unshift(row);
  });

  // trim old rows
  while (feedRows.length > MAX_FEED) {
    const old = feedRows.pop();
    old.remove();
  }

  // prepend new rows
  if (newCount > 0) {
    feedRows.slice(0, newCount).reverse().forEach(r => {
      tbody.insertBefore(r, tbody.firstChild);
    });
  }

  // update stats
  document.getElementById('statTotal').textContent = seenOrderIds.size;
  document.getElementById('statAllowed').textContent = allowed;
  document.getElementById('statDropped').textContent = dropped;
}

// ── Polling ────────────────────────────────────────────────────
let pollOk = false;
async function poll() {
  try {
    const [stateResp, auditResp] = await Promise.all([
      fetch('/api/state').then(r=>r.json()),
      fetch('/api/audit').then(r=>r.json())
    ]);
    renderState(stateResp);
    renderAudit(auditResp);
    document.getElementById('statLastUpdate').textContent = new Date().toLocaleTimeString();
    if (!pollOk) {
      pollOk = true;
      document.getElementById('connDot').style.background = 'var(--green)';
      document.getElementById('connText').textContent = 'Connected to AWS';
    }
  } catch(e) {
    pollOk = false;
    document.getElementById('connDot').style.background = 'var(--red)';
    document.getElementById('connText').textContent = 'Connection error';
  }
}
setInterval(poll, 2000);
poll();

// ── Actions ────────────────────────────────────────────────────
async function startServices() {
  const btn = event.target;
  setLoading(btn, true);
  toast('Starting aggregator + router...', 'info');
  const r = await api('POST', '/api/services/start');
  setLoading(btn, false);
  if (r.success) toast('Services started!', 'success');
  else toast('Error: ' + (r.error||'unknown'), 'error');
}

async function generateOrders(mode) {
  const btn = event.target;
  setLoading(btn, true);
  const label = mode === 'panic' ? 'Panic mode (account 99999, 10/sec)' : 'Normal orders (5/sec, 10s)';
  toast('Generating: ' + label, 'info');
  const r = await api('POST', '/api/generate', {mode});
  setLoading(btn, false);
  if (r.success) toast('Order generation triggered!', 'success');
  else toast('Error: ' + (r.error||'unknown'), 'error');
}

async function killScope(scope) {
  const btn = event.target;
  setLoading(btn, true);
  toast('Sending KILL ' + scope + '...', 'info');
  const r = await api('POST', '/api/kill', {scope, reason:'Manual kill via dashboard', operator:'dashboard'});
  setLoading(btn, false);
  if (r.success) toast('KILL sent for ' + scope, 'success');
  else toast('Error: ' + (r.error||'unknown'), 'error');
  setTimeout(poll, 500);
}

async function unkillScope(scope) {
  const btn = event.target;
  setLoading(btn, true);
  toast('Sending UNKILL ' + scope + '...', 'info');
  const r = await api('POST', '/api/unkill', {scope, reason:'Manual unkill via dashboard', operator:'dashboard'});
  setLoading(btn, false);
  if (r.success) toast('UNKILL sent for ' + scope, 'success');
  else toast('Error: ' + (r.error||'unknown'), 'error');
  setTimeout(poll, 500);
}

async function resetAll() {
  const btn = event.target;
  setLoading(btn, true);
  toast('Resetting all kill switches...', 'info');
  const scopes = Object.keys(prevState).filter(s => prevState[s] === 'KILLED');
  if (scopes.length === 0) scopes.push('GLOBAL','SYMBOL:AAPL','ACCOUNT:99999');
  for (const s of scopes) {
    await api('POST', '/api/unkill', {scope:s, reason:'Dashboard cleanup', operator:'dashboard'});
  }
  setLoading(btn, false);
  toast('All kill switches reset', 'success');
  setTimeout(poll, 500);
}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------

class DashboardHandler(BaseHTTPRequestHandler):
    clients = None  # set by serve()

    def log_message(self, fmt, *args):
        # quieter logging
        log.debug(fmt, *args)

    def _json(self, data, status=200):
        body = json_dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    # ── GET routes ─────────────────────────────────────────────

    def do_GET(self):
        if self.path == "/":
            self._html(DASHBOARD_HTML)
        elif self.path == "/api/state":
            items = read_state(self.clients["dynamodb"])
            self._json(items)
        elif self.path == "/api/audit":
            items = read_audit(self.clients["dynamodb"])
            self._json(items)
        elif self.path == "/api/health":
            self._json({"status": "ok", "service": "dashboard"})
        else:
            self.send_error(404)

    # ── POST routes ────────────────────────────────────────────

    def do_POST(self):
        if self.path == "/api/generate":
            body = self._read_body()
            mode = body.get("mode", "normal")
            if mode == "panic":
                payload = {
                    "mode": "panic",
                    "duration_seconds": 90,
                    "rate_per_second": 10,
                    "account_id": "99999",
                }
            else:
                payload = {
                    "mode": "normal",
                    "duration_seconds": 10,
                    "rate_per_second": 5,
                }
            result = invoke_lambda_async(self.clients["lambda"], FN_ORDER_GEN, payload)
            self._json(result)

        elif self.path == "/api/kill":
            body = self._read_body()
            result = proxy_api("POST", "/kill", body)
            self._json(result)

        elif self.path == "/api/unkill":
            body = self._read_body()
            result = proxy_api("POST", "/unkill", body)
            self._json(result)

        elif self.path == "/api/services/start":
            r1 = invoke_lambda_async(self.clients["lambda"], FN_AGGREGATOR, {})
            r2 = invoke_lambda_async(self.clients["lambda"], FN_ROUTER, {})
            self._json({
                "success": r1.get("success") and r2.get("success"),
                "aggregator": r1,
                "router": r2,
            })

        else:
            self.send_error(404)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def serve(port, region):
    clients = get_clients(region)
    DashboardHandler.clients = clients

    # quick connectivity check
    log.info("Checking AWS connectivity...")
    try:
        table = clients["dynamodb"].Table(TABLE_STATE)
        table.table_status  # triggers describe_table
        log.info("  DynamoDB table %s: OK", TABLE_STATE)
    except Exception as e:
        log.warning("  DynamoDB check failed (will retry on requests): %s", e)

    httpd = HTTPServer(("0.0.0.0", port), DashboardHandler)
    log.info("━" * 60)
    log.info("  SEC 15c3-5 Live Demo Dashboard")
    log.info("  http://localhost:%d", port)
    log.info("━" * 60)
    log.info("Press Ctrl+C to stop\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("\nShutting down.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEC 15c3-5 Live Demo Dashboard")
    parser.add_argument("--port", type=int, default=8080, help="Port (default 8080)")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    args = parser.parse_args()
    serve(args.port, args.region)
