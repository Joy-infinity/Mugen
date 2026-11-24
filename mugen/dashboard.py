"""
Mugen dashboard: watch the maze work.

Reads the JSON log that the Mugen server writes (`python -m mugen --log-file
mugen.log`) and serves a live, self-contained dashboard: how many bots were
trapped, the worst offenders, which AI agents showed up, a timeline, and a
live feed of the most recent decisions.

Zero dependencies -- pure Python standard library, like the rest of Mugen.

    python -m mugen.dashboard --log mugen.log --port 8090

The page polls a small JSON API (`/api/stats`) every few seconds, so it stays
live while Mugen keeps trapping.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def aggregate(log_path: str, timeline_minutes: int = 30, recent: int = 15) -> dict:
    """
    Parse the JSON-lines log into a summary the dashboard renders.

    Malformed lines are skipped, so a half-written final line never crashes it.
    """
    total = passed = trapped = 0
    ip_counts: dict[str, int] = {}
    agent_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    events: list[dict] = []

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ev = rec.get("event")
                if ev == "pass":
                    total += 1
                    passed += 1
                    events.append(rec)
                elif ev == "trapped":
                    total += 1
                    trapped += 1
                    ip = rec.get("ip", "unknown")
                    ip_counts[ip] = ip_counts.get(ip, 0) + 1
                    agent = rec.get("ai_agent")
                    if agent:
                        agent_counts[agent] = agent_counts.get(agent, 0) + 1
                    for reason in rec.get("reasons", []):
                        reason_counts[reason] = reason_counts.get(reason, 0) + 1
                    events.append(rec)
    except FileNotFoundError:
        pass

    # Timeline: trapped vs passed per minute over the recent window.
    now = time.time()
    start = now - timeline_minutes * 60
    buckets = [{"t": i, "trapped": 0, "passed": 0} for i in range(timeline_minutes)]
    for rec in events:
        ts = rec.get("ts", 0)
        if ts < start:
            continue
        idx = int((ts - start) // 60)
        if 0 <= idx < timeline_minutes:
            key = "trapped" if rec.get("event") == "trapped" else "passed"
            buckets[idx][key] += 1

    def top(counts: dict[str, int], n: int) -> list[dict]:
        items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:n]
        return [{"label": k, "count": v} for k, v in items]

    recent_events = [
        {
            "ts": r.get("ts"),
            "event": r.get("event"),
            "ip": r.get("ip", "unknown"),
            "path": r.get("path", ""),
            "ai_agent": r.get("ai_agent"),
            "score": r.get("score"),
            "reasons": r.get("reasons", []),
        }
        for r in events[-recent:][::-1]
    ]

    rate = round(100 * trapped / total, 1) if total else 0.0
    return {
        "total": total,
        "passed": passed,
        "trapped": trapped,
        "trap_rate": rate,
        "top_ips": top(ip_counts, 8),
        "ai_agents": top(agent_counts, 8),
        "reasons": top(reason_counts, 6),
        "timeline": buckets,
        "recent": recent_events,
        "generated": now,
    }


# The dashboard page. Self-contained: inline CSS + vanilla JS, no external libs.
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mugen Dashboard</title>
<style>
  :root{
    --bg:#0b0f1a; --panel:#131a2b; --panel2:#0f1524; --line:#223049;
    --text:#dfe4ee; --muted:#8793ab; --blue:#5aaaff; --cyan:#7bd5ff;
    --green:#50dc96; --red:#ff6e78; --yellow:#f0d278;
  }
  *{box-sizing:border-box}
  body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#16223b 0%,var(--bg) 60%);
    color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
  header{display:flex;align-items:center;gap:14px;padding:22px 28px;border-bottom:1px solid var(--line)}
  header .mark{font-size:26px}
  header h1{font-size:19px;margin:0;font-weight:650;letter-spacing:.2px}
  header .sub{color:var(--muted);font-size:13px;margin-left:2px}
  header .live{margin-left:auto;display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--green);box-shadow:0 0 10px var(--green);animation:pulse 1.6s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  .wrap{padding:24px 28px;max-width:1200px;margin:0 auto}
  .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
  .card .k{color:var(--muted);font-size:13px;margin-bottom:6px}
  .card .v{font-size:30px;font-weight:680;letter-spacing:.3px}
  .v.blue{color:var(--cyan)} .v.green{color:var(--green)} .v.red{color:var(--red)}
  .grid{display:grid;grid-template-columns:2fr 1fr;gap:16px}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:16px}
  .panel h2{font-size:14px;margin:0 0 14px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.6px}
  svg{width:100%;height:170px;display:block}
  .row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--panel2)}
  .row:last-child{border-bottom:0}
  .row .lbl{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .row .cnt{color:var(--cyan);font-weight:600;margin-left:12px}
  .tag{display:inline-block;background:#10203a;color:var(--cyan);border:1px solid #1d3a5c;border-radius:20px;padding:2px 10px;font-size:12px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{text-align:left;color:var(--muted);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--line);font-size:12px;text-transform:uppercase;letter-spacing:.4px}
  td{padding:7px 8px;border-bottom:1px solid var(--panel2);font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  .pill{font-family:inherit;font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600}
  .pill.trapped{background:#2a1419;color:var(--red)}
  .pill.pass{background:#122a1e;color:var(--green)}
  .muted{color:var(--muted)}
  .empty{color:var(--muted);text-align:center;padding:26px 0}
  @media(max-width:860px){.cards{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <span class="mark">&#8734;</span>
  <div><h1>Mugen Dashboard</h1></div>
  <span class="sub">watching the maze</span>
  <span class="live"><span class="dot"></span><span id="updated">connecting…</span></span>
</header>
<div class="wrap">
  <div class="cards">
    <div class="card"><div class="k">Total requests</div><div class="v" id="c-total">–</div></div>
    <div class="card"><div class="k">Bots trapped</div><div class="v red" id="c-trapped">–</div></div>
    <div class="card"><div class="k">Humans passed</div><div class="v green" id="c-passed">–</div></div>
    <div class="card"><div class="k">Trap rate</div><div class="v blue" id="c-rate">–</div></div>
  </div>
  <div class="panel">
    <h2>Last 30 minutes &middot; <span style="color:var(--red)">trapped</span> vs <span style="color:var(--green)">passed</span></h2>
    <svg id="chart" viewBox="0 0 600 170" preserveAspectRatio="none"></svg>
  </div>
  <div class="grid">
    <div>
      <div class="panel">
        <h2>Live feed</h2>
        <table id="feed"><thead><tr><th>Time</th><th>Verdict</th><th>IP</th><th>Path</th><th>Why</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">Waiting for traffic…</td></tr></tbody></table>
      </div>
    </div>
    <div>
      <div class="panel"><h2>Top trapped IPs</h2><div id="ips"><div class="empty">—</div></div></div>
      <div class="panel"><h2>AI agents caught</h2><div id="agents"><div class="empty">None yet</div></div></div>
      <div class="panel"><h2>Top trip reasons</h2><div id="reasons"><div class="empty">—</div></div></div>
    </div>
  </div>
</div>
<script>
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function fmtTime(ts){if(!ts)return"";var d=new Date(ts*1000);return d.toLocaleTimeString()}
function rows(el,items,empty){
  if(!items.length){el.innerHTML='<div class="empty">'+empty+'</div>';return}
  el.innerHTML=items.map(function(i){return '<div class="row"><span class="lbl">'+esc(i.label)+'</span><span class="cnt">'+i.count+'</span></div>'}).join("")
}
function drawChart(buckets){
  var W=600,H=170,pad=8,n=buckets.length,bw=(W-pad*2)/n;
  var max=1;buckets.forEach(function(b){max=Math.max(max,b.trapped+b.passed)});
  var bars=buckets.map(function(b,i){
    var x=pad+i*bw, th=(b.trapped/max)*(H-20), ph=(b.passed/max)*(H-20);
    var y1=H-th, y2=y1-ph;
    var w=Math.max(1,bw-2);
    var s='<rect x="'+x+'" y="'+y1+'" width="'+w+'" height="'+th+'" fill="#ff6e78" rx="1"/>';
    s+='<rect x="'+x+'" y="'+y2+'" width="'+w+'" height="'+ph+'" fill="#50dc96" opacity="0.8" rx="1"/>';
    return s;
  }).join("");
  document.getElementById("chart").innerHTML=bars;
}
function refresh(){
  fetch("/api/stats").then(function(r){return r.json()}).then(function(d){
    document.getElementById("c-total").textContent=d.total;
    document.getElementById("c-trapped").textContent=d.trapped;
    document.getElementById("c-passed").textContent=d.passed;
    document.getElementById("c-rate").textContent=d.trap_rate+"%";
    document.getElementById("updated").textContent="updated "+new Date().toLocaleTimeString();
    drawChart(d.timeline);
    rows(document.getElementById("ips"),d.top_ips,"None yet");
    rows(document.getElementById("agents"),d.ai_agents,"None yet");
    rows(document.getElementById("reasons"),d.reasons,"—");
    var fb=document.querySelector("#feed tbody");
    if(!d.recent.length){fb.innerHTML='<tr><td colspan="5" class="empty">Waiting for traffic…</td></tr>';return}
    fb.innerHTML=d.recent.map(function(e){
      var verdict=e.event==="trapped"?'<span class="pill trapped">trapped</span>':'<span class="pill pass">passed</span>';
      var why=e.ai_agent?("AI: "+e.ai_agent):(e.reasons&&e.reasons.length?e.reasons[0]:"—");
      return '<tr><td class="muted">'+fmtTime(e.ts)+'</td><td>'+verdict+'</td><td>'+esc(e.ip)+'</td><td class="muted">'+esc(e.path)+'</td><td class="muted">'+esc(why)+'</td></tr>';
    }).join("");
  }).catch(function(){document.getElementById("updated").textContent="offline"});
}
refresh();setInterval(refresh,4000);
</script>
</body>
</html>"""


def make_handler(log_path: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MugenDashboard"
        sys_version = ""

        def log_message(self, *a):
            pass

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/api/stats"):
                body = json.dumps(aggregate(log_path)).encode("utf-8")
                ctype = "application/json; charset=utf-8"
            else:
                body = PAGE.encode("utf-8")
                ctype = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="mugen.dashboard",
        description="Live dashboard for Mugen's trap logs.",
    )
    p.add_argument("--log", default="mugen.log", help="path to Mugen's --log-file")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8090)
    args = p.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(args.log))
    httpd.daemon_threads = True
    print(f"Mugen dashboard on http://{args.host}:{args.port}  (reading {args.log})",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
