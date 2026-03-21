"""Generate a Doxygen-style runtime portal with links and run visualizations."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .runtime_experiment_report import analyze_frame_csv
except ImportError:
    from runtime_experiment_report import analyze_frame_csv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOXYGEN_HTML_DIR = PROJECT_ROOT / "docs" / "doxygen" / "html"
RUN_SUMMARY_PATH = PROJECT_ROOT / "evidence" / "runtime_logs" / "run_summary.csv"
OUTPUT_PATH = DOXYGEN_HTML_DIR / "runtime_portal.html"


def _to_float(value: Any, default: float = 0.0) -> float:
    if value in ("", None):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    if value in ("", None):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _relpath(target: str | Path | None, base_dir: Path) -> str:
    if target in ("", None):
        return ""
    return os.path.relpath(Path(target).resolve(), start=base_dir).replace("\\", "/")


def _load_runs() -> list[dict[str, Any]]:
    if not RUN_SUMMARY_PATH.exists():
        return []

    rows = list(csv.DictReader(RUN_SUMMARY_PATH.open("r", encoding="utf-8", newline="")))
    entries: list[dict[str, Any]] = []
    for row in rows:
        frame_csv = row.get("frame_log_path", "")
        analysis = {
            "zero_track_frames": 0,
            "tracks_ge_2_frames": 0,
            "longest_zero_track_streak": None,
        }
        if frame_csv and Path(frame_csv).exists():
            analysis = analyze_frame_csv(frame_csv)

        frames_processed = max(1, _to_int(row.get("frames_processed")))
        run_id = str(row.get("run_id", ""))
        started_at = str(row.get("started_at", ""))
        run_date = started_at[:10] if started_at else ""
        report_path = PROJECT_ROOT / "docs" / "experiment_reports" / run_date / f"{run_id}.md"

        entries.append(
            {
                "run_id": run_id,
                "started_at": started_at,
                "scenario": str(row.get("scenario", "")),
                "frames_processed": frames_processed,
                "avg_fps": _to_float(row.get("avg_fps")),
                "avg_filtered_points": _to_float(row.get("avg_filtered_points")),
                "avg_tracks": _to_float(row.get("avg_tracks")),
                "avg_clusters": _to_float(row.get("avg_clusters")),
                "avg_removed_range": _to_float(row.get("avg_removed_range")),
                "avg_removed_axis_roi": _to_float(row.get("avg_removed_axis_roi")),
                "avg_pipeline_latency_ms": _to_float(row.get("avg_pipeline_latency_ms")),
                "parse_failures": _to_int(row.get("parse_failures")),
                "resync_events": _to_int(row.get("resync_events")),
                "dropped_frames_estimate": _to_int(row.get("dropped_frames_estimate")),
                "snr_threshold": _to_float(row.get("snr_threshold")),
                "max_range": _to_float(row.get("max_range")),
                "dbscan_eps": _to_float(row.get("dbscan_eps")),
                "dbscan_min_samples": _to_int(row.get("dbscan_min_samples")),
                "association_gate": _to_float(row.get("association_gate")),
                "zero_track_frames": _to_int(analysis.get("zero_track_frames")),
                "tracks_ge_2_frames": _to_int(analysis.get("tracks_ge_2_frames")),
                "zero_track_ratio": _to_int(analysis.get("zero_track_frames")) / frames_processed,
                "longest_zero_track_streak": analysis.get("longest_zero_track_streak"),
                "frame_csv_rel": _relpath(frame_csv, DOXYGEN_HTML_DIR),
                "report_rel": _relpath(report_path, DOXYGEN_HTML_DIR) if report_path.exists() else "",
            }
        )
    return entries


def _code_cards_html() -> str:
    items = [
        ("Runtime", "runtime_pipeline.py", "runtime__pipeline_8py.html", "runtime__pipeline_8py_source.html", "namespaceruntime__pipeline.html"),
        ("Viewer", "live_rail_viewer.py", "live__rail__viewer_8py.html", "live__rail__viewer_8py_source.html", "namespacelive__rail__viewer.html"),
        ("Filter", "noise_filter.py", "noise__filter_8py.html", "noise__filter_8py_source.html", "namespacenoise__filter.html"),
        ("Cluster", "dbscan_cluster.py", "dbscan__cluster_8py.html", "dbscan__cluster_8py_source.html", "namespacedbscan__cluster.html"),
        ("Tracker", "kalman_tracker.py", "kalman__tracker_8py.html", "kalman__tracker_8py_source.html", "namespacekalman__tracker.html"),
        ("Control", "proximity_speed_control.py", "proximity__speed__control_8py.html", "proximity__speed__control_8py_source.html", "namespaceproximity__speed__control.html"),
        ("Params", "runtime_params.py", "runtime__params_8py.html", "runtime__params_8py_source.html", "namespaceruntime__params.html"),
        ("Reports", "runtime_experiment_report.py", "runtime__experiment__report_8py.html", "runtime__experiment__report_8py_source.html", "namespaceruntime__experiment__report.html"),
        ("Reports", "performance_log_report.py", "performance__log__report_8py.html", "performance__log__report_8py_source.html", "namespaceperformance__log__report.html"),
    ]
    cards: list[str] = []
    for group, label, api, source, ns in items:
        cards.append(
            "<div class='code-card'>"
            f"<div class='code-group'>{group}</div>"
            f"<div class='code-title'>{label}</div>"
            f"<div class='code-links'><a href='{api}'>API</a><a href='{source}'>Source</a><a href='{ns}'>Namespace</a></div>"
            "</div>"
        )
    return "".join(cards)


def _runs_table_html(entries: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for entry in reversed(entries[-12:]):
        streak = entry.get("longest_zero_track_streak")
        streak_text = "-"
        if streak:
            streak_text = f"{streak[0]}-{streak[1]} ({streak[2]})"
        report_link = f"<a href='{entry['report_rel']}'>report</a>" if entry.get("report_rel") else "-"
        csv_link = f"<a href='{entry['frame_csv_rel']}'>frame csv</a>" if entry.get("frame_csv_rel") else "-"
        rows.append(
            "<tr>"
            f"<td>{entry['run_id']}</td>"
            f"<td>{entry['scenario'] or '-'}</td>"
            f"<td>{entry['avg_tracks']:.2f}</td>"
            f"<td>{entry['zero_track_ratio']*100:.1f}%</td>"
            f"<td>{entry['resync_events']}</td>"
            f"<td>{entry['avg_removed_range']:.2f}</td>"
            f"<td>{entry['snr_threshold']:.0f}</td>"
            f"<td>{entry['dbscan_min_samples']}</td>"
            f"<td>{streak_text}</td>"
            f"<td>{report_link} / {csv_link}</td>"
            "</tr>"
        )
    return "".join(rows)


def build_html(entries: list[dict[str, Any]]) -> str:
    latest = entries[-1] if entries else None
    prev = entries[-2] if len(entries) >= 2 else None
    latest_cards = (
        "<div class='summary-grid'>"
        f"<div class='summary-card'><div class='summary-label'>Latest Run</div><div class='summary-value'>{latest['run_id']}</div><div class='summary-sub'>{latest['started_at']}</div></div>"
        f"<div class='summary-card'><div class='summary-label'>Avg Tracks</div><div class='summary-value'>{latest['avg_tracks']:.2f}</div><div class='summary-sub'>prev {prev['avg_tracks']:.2f}</div></div>"
        f"<div class='summary-card'><div class='summary-label'>Zero-Track Ratio</div><div class='summary-value'>{latest['zero_track_ratio']*100:.1f}%</div><div class='summary-sub'>{latest['zero_track_frames']}/{latest['frames_processed']}</div></div>"
        f"<div class='summary-card'><div class='summary-label'>Parser Health</div><div class='summary-value'>resync {latest['resync_events']}</div><div class='summary-sub'>parse_fail {latest['parse_failures']}, dropped {latest['dropped_frames_estimate']}</div></div>"
        "</div>"
        if latest and prev
        else "<p>No runtime runs found yet.</p>"
    )
    runs_json = json.dumps(entries[-16:], ensure_ascii=False)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "https://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en-US">
<head>
<meta http-equiv="Content-Type" content="text/xhtml;charset=UTF-8"/>
<meta http-equiv="X-UA-Compatible" content="IE=11"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>radar-tracking-system: Runtime Portal</title>
<link href="tabs.css" rel="stylesheet" type="text/css"/>
<link href="doxygen.css" rel="stylesheet" type="text/css" />
<style type="text/css">
  .portal-nav {{ display:flex; flex-wrap:wrap; gap:10px; margin:16px 0 20px; }}
  .portal-nav a {{ padding:8px 14px; border:1px solid #cfd8e6; border-radius:999px; text-decoration:none; background:#fff; color:#205081; font-weight:600; }}
  .hero-box {{ background:linear-gradient(135deg,#2151a4,#0f6cbd); color:#fff; border-radius:14px; padding:22px 24px; margin:20px 0; }}
  .hero-box h1 {{ margin:0 0 10px; font-size:30px; }}
  .hero-box p {{ margin:0; line-height:1.6; max-width:980px; }}
  .small {{ font-size:13px; color:#6b7280; }}
  .summary-grid,.chart-grid,.impact-grid,.code-grid {{ display:grid; gap:14px; }}
  .summary-grid {{ grid-template-columns:repeat(4,minmax(0,1fr)); margin-top:18px; }}
  .summary-card,.code-card,.chart-box,.impact-col,.note {{ background:#fff; border:1px solid #d8e1ee; border-radius:12px; }}
  .summary-card {{ padding:16px; color:#1f2937; }}
  .summary-label {{ font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:#64748b; margin-bottom:8px; }}
  .summary-value {{ font-size:24px; font-weight:700; letter-spacing:-.03em; }}
  .summary-sub {{ margin-top:6px; font-size:13px; color:#6b7280; }}
  .section-block {{ margin:24px 0 28px; }}
  .code-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
  .code-card {{ padding:16px; }}
  .code-group {{ font-size:12px; text-transform:uppercase; color:#7c8796; margin-bottom:6px; }}
  .code-title {{ font-size:18px; font-weight:700; margin-bottom:10px; }}
  .code-links {{ display:flex; gap:8px; flex-wrap:wrap; }}
  .code-links a {{ padding:7px 10px; border-radius:999px; background:#edf4ff; border:1px solid #c8d8f2; text-decoration:none; }}
  .chart-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
  .chart-box {{ padding:14px; }}
  .impact-controls {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }}
  .impact-controls button {{ padding:8px 12px; border-radius:999px; border:1px solid #c8d8f2; background:#edf4ff; color:#205081; cursor:pointer; font-weight:600; }}
  .impact-controls button.active {{ background:#205081; color:#fff; border-color:#205081; }}
  .impact-grid {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
  .impact-col {{ padding:14px; }}
  .impact-col h3 {{ margin-top:0; font-size:15px; }}
  .impact-item {{ margin:8px 0; padding:8px 10px; border-radius:10px; background:#f7faff; border:1px solid #dbe6f5; transition:all .15s ease; }}
  .impact-item.dim {{ opacity:.28; filter:grayscale(.25); }}
  .impact-item.hot {{ background:#fff1e8; border-color:#efc6ad; }}
  .runs-table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid #d8e1ee; border-radius:12px; overflow:hidden; }}
  .runs-table th,.runs-table td {{ padding:10px 12px; border-bottom:1px solid #e7edf5; text-align:left; vertical-align:top; }}
  .runs-table th {{ background:#f5f8fc; font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:#6b7280; }}
  .flow-svg,.chart-box svg {{ width:100%; }}
  .note {{ padding:14px 16px; margin-top:14px; }}
  @media (max-width: 1100px) {{ .summary-grid,.chart-grid,.impact-grid,.code-grid {{ grid-template-columns:1fr 1fr; }} }}
  @media (max-width: 800px) {{ .summary-grid,.chart-grid,.impact-grid,.code-grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div id="top">
<div id="titlearea"><table cellspacing="0" cellpadding="0"><tbody><tr id="projectrow"><td id="projectalign"><div id="projectname">radar-tracking-system</div><div id="projectbrief">Runtime portal with doxygen links and experiment visualizations</div></td></tr></tbody></table></div>
<div id="main-nav"></div>
</div>
<div id="container"><div id="doc-content" class="contents">
  <div class="hero-box">
    <h1>Runtime Portal</h1>
    <p>이 페이지는 Doxygen 코드 문서로 바로 들어가면서, 실제 run 데이터 기준으로 파라미터와 결과값의 연계성을 시각적으로 보여주는 포털이다.</p>
    <div class="small" style="color:rgba(255,255,255,0.82); margin-top:10px;">Updated: {updated_at}</div>
    {latest_cards}
  </div>
  <div class="portal-nav">
    <a href="index.html">Doxygen Home</a>
    <a href="runtime__pipeline_8py_source.html">runtime_pipeline Source</a>
    <a href="live__rail__viewer_8py_source.html">viewer Source</a>
    <a href="../../runtime_system_onepage.html">구조 설명</a>
    <a href="../../runtime_code_browser.html">전체 코드 브라우저</a>
    <a href="../../performance_log.md">performance_log.md</a>
  </div>
  <div class="section-block">
    <h2>1. Open Code In Doxygen</h2>
    <p>Doxygen source/API 페이지로 바로 들어가는 진입점이다.</p>
    <div class="code-grid">{_code_cards_html()}</div>
  </div>
  <div class="section-block">
    <h2>2. Runtime Flow Visual</h2>
    <svg class="flow-svg" viewBox="0 0 1180 240" xmlns="http://www.w3.org/2000/svg">
      <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#2151a4"/></marker></defs>
      <rect x="18" y="60" width="130" height="78" rx="14" fill="#f8fbff" stroke="#b8cbe6"/><text x="83" y="89" text-anchor="middle" font-size="14" font-weight="700">cfg / sensor</text><text x="83" y="111" text-anchor="middle" font-size="12" fill="#56657a">CFAR / beamforming</text>
      <rect x="180" y="60" width="130" height="78" rx="14" fill="#fff" stroke="#cfd8e6"/><text x="245" y="89" text-anchor="middle" font-size="14" font-weight="700">TLV parse</text><text x="245" y="111" text-anchor="middle" font-size="12" fill="#56657a">ParsedFrame</text>
      <rect x="342" y="60" width="140" height="78" rx="14" fill="#fff" stroke="#cfd8e6"/><text x="412" y="89" text-anchor="middle" font-size="14" font-weight="700">World transform</text><text x="412" y="111" text-anchor="middle" font-size="12" fill="#56657a">yaw / pitch / height</text>
      <rect x="514" y="60" width="130" height="78" rx="14" fill="#fff" stroke="#cfd8e6"/><text x="579" y="89" text-anchor="middle" font-size="14" font-weight="700">Preprocess</text><text x="579" y="111" text-anchor="middle" font-size="12" fill="#56657a">range / ROI / keepout</text>
      <rect x="676" y="60" width="130" height="78" rx="14" fill="#fff" stroke="#cfd8e6"/><text x="741" y="89" text-anchor="middle" font-size="14" font-weight="700">DBSCAN</text><text x="741" y="111" text-anchor="middle" font-size="12" fill="#56657a">clusters</text>
      <rect x="838" y="60" width="130" height="78" rx="14" fill="#fff" stroke="#cfd8e6"/><text x="903" y="89" text-anchor="middle" font-size="14" font-weight="700">Tracker</text><text x="903" y="111" text-anchor="middle" font-size="12" fill="#56657a">track continuity</text>
      <rect x="1000" y="32" width="150" height="58" rx="14" fill="#fff" stroke="#cfd8e6"/><text x="1075" y="58" text-anchor="middle" font-size="14" font-weight="700">Viewer</text><text x="1075" y="76" text-anchor="middle" font-size="12" fill="#56657a">latest snapshot</text>
      <rect x="1000" y="106" width="150" height="58" rx="14" fill="#fff" stroke="#cfd8e6"/><text x="1075" y="132" text-anchor="middle" font-size="14" font-weight="700">Reports</text><text x="1075" y="150" text-anchor="middle" font-size="12" fill="#56657a">CSV / md / PNG</text>
      <path d="M148 99 H180" stroke="#2151a4" stroke-width="3" fill="none" marker-end="url(#arrow)"/><path d="M310 99 H342" stroke="#2151a4" stroke-width="3" fill="none" marker-end="url(#arrow)"/><path d="M482 99 H514" stroke="#2151a4" stroke-width="3" fill="none" marker-end="url(#arrow)"/><path d="M644 99 H676" stroke="#2151a4" stroke-width="3" fill="none" marker-end="url(#arrow)"/><path d="M806 99 H838" stroke="#2151a4" stroke-width="3" fill="none" marker-end="url(#arrow)"/><path d="M968 78 H1000" stroke="#2151a4" stroke-width="3" fill="none" marker-end="url(#arrow)"/><path d="M968 120 H1000" stroke="#b45309" stroke-width="3" fill="none" marker-end="url(#arrow)"/>
      <text x="104" y="188" font-size="13" fill="#56657a">Sensor-side result</text><text x="475" y="188" font-size="13" fill="#56657a">Host-side interpretation and tracking</text><text x="961" y="188" font-size="13" fill="#56657a">Output surfaces</text>
    </svg>
  </div>
  <div class="section-block">
    <h2>3. Parameter To Result Link Map</h2>
    <p>버튼을 누르면 어떤 파라미터가 어떤 모듈, 메트릭, 화면 현상으로 이어지는지 강조된다.</p>
    <div class="impact-controls">
      <button class="impact-button active" data-topic="all" type="button">전체</button>
      <button class="impact-button" data-topic="sensor" type="button">sensor pose</button>
      <button class="impact-button" data-topic="range" type="button">max_range / ROI</button>
      <button class="impact-button" data-topic="dbscan" type="button">DBSCAN</button>
      <button class="impact-button" data-topic="tracker" type="button">tracker</button>
      <button class="impact-button" data-topic="viewer" type="button">viewer / logging</button>
    </div>
    <div class="impact-grid">
      <div class="impact-col"><h3>Parameter</h3><div class="impact-item" data-topics="sensor">sensor_yaw_deg / sensor_pitch_deg / sensor_height_m</div><div class="impact-item" data-topics="range">max_range / filter_x_y_z / keepout</div><div class="impact-item" data-topics="dbscan">dbscan_eps / dbscan_min_samples / velocity_weight</div><div class="impact-item" data-topics="tracker">association_gate / max_misses / report_miss_tolerance</div><div class="impact-item" data-topics="viewer">max_vis_fps / disable_text_log / disable_overview_png</div></div>
      <div class="impact-col"><h3>Touched Module</h3><div class="impact-item" data-topics="sensor">transform_points_to_world()</div><div class="impact-item" data-topics="range">preprocess_points()</div><div class="impact-item" data-topics="dbscan">cluster_points()</div><div class="impact-item" data-topics="tracker">MultiObjectKalmanTracker.update()</div><div class="impact-item" data-topics="viewer">run_viewer() / run_realtime()</div></div>
      <div class="impact-col"><h3>Observed Metric</h3><div class="impact-item" data-topics="sensor">avg_removed_axis_roi / path angle</div><div class="impact-item" data-topics="range">avg_removed_range / avg_filtered_points</div><div class="impact-item" data-topics="dbscan">avg_clusters / avg_tracks / tracks_ge_2_frames</div><div class="impact-item" data-topics="tracker">zero_track_frames / longest_zero_track_streak</div><div class="impact-item" data-topics="viewer">avg_pipeline_latency_ms / resync_events</div></div>
      <div class="impact-col"><h3>Visible Symptom</h3><div class="impact-item" data-topics="sensor">앞뒤 이동이 대각선처럼 보임</div><div class="impact-item" data-topics="range">멀어지면 사람이 사라짐</div><div class="impact-item" data-topics="dbscan">한 사람을 여러 track으로 봄</div><div class="impact-item" data-topics="tracker">zero-track 깜빡임이 김</div><div class="impact-item" data-topics="viewer">시연 화면이 늦고 끊겨 보임</div></div>
    </div>
    <div class="note">코드를 볼 때도 <strong>파라미터 → 모듈 → 메트릭 → 화면 현상</strong> 순서로 따라가면 가장 빠르다.</div>
  </div>
  <div class="section-block">
    <h2>4. Run Visualizations From Real Logs</h2>
    <p>아래 차트는 실제 <code>run_summary.csv</code>와 frame CSV 분석값을 사용한다.</p>
    <div class="chart-grid">
      <div class="chart-box"><h3>Avg Tracks by Run</h3><div id="chart-tracks"></div></div>
      <div class="chart-box"><h3>Zero-Track Ratio by Run</h3><div id="chart-zero"></div></div>
      <div class="chart-box"><h3>Parser Continuity by Run</h3><div id="chart-parser"></div></div>
      <div class="chart-box"><h3>Avg Removed Range by Run</h3><div id="chart-range"></div></div>
      <div class="chart-box"><h3>SNR Threshold vs Avg Filtered Points</h3><div id="chart-snr"></div></div>
      <div class="chart-box"><h3>DBSCAN Min Samples vs Avg Tracks</h3><div id="chart-dbscan-min"></div></div>
    </div>
  </div>
  <div class="section-block">
    <h2>5. Recent Runs Table</h2>
    <table class="runs-table"><thead><tr><th>Run</th><th>Scenario</th><th>Avg Tracks</th><th>Zero-Track</th><th>Resync</th><th>Removed Range</th><th>SNR</th><th>DBSCAN Min</th><th>Longest Zero Streak</th><th>Artifacts</th></tr></thead><tbody>{_runs_table_html(entries)}</tbody></table>
  </div>
  <div class="section-block">
    <h2>6. How To Use This Portal</h2>
    <ol>
      <li>코드는 위 <strong>Open Code In Doxygen</strong>에서 source/API 페이지로 본다.</li>
      <li>파라미터가 어떤 결과로 이어지는지는 <strong>Link Map</strong>을 먼저 본다.</li>
      <li>실제 이전 run 비교는 <strong>Run Visualizations</strong>와 표를 본다.</li>
      <li>구조 설명이 필요하면 <a href="../../runtime_system_onepage.html">runtime_system_onepage.html</a>로 돌아간다.</li>
    </ol>
  </div>
</div></div>
<script type="text/javascript">
const RUNS = {runs_json};
function svgEl(name, attrs={{}}){{const el=document.createElementNS('http://www.w3.org/2000/svg',name);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));return el;}}
function renderLineChart(containerId, runs, key, color, digits){{const c=document.getElementById(containerId);if(!c||!runs.length)return;const w=520,h=230,pL=44,pR=16,pT=12,pB=34;const values=runs.map(r=>Number(r[key]||0));const labels=runs.map(r=>String(r.run_id).slice(-6));const min=Math.min(...values),max=Math.max(...values),span=max-min||1;const svg=svgEl('svg',{{viewBox:`0 0 ${{w}} ${{h}}`,width:'100%',height:'220'}});for(let i=0;i<4;i++){{const y=pT+((h-pT-pB)/3)*i;svg.appendChild(svgEl('line',{{x1:pL,y1:y,x2:w-pR,y2:y,stroke:'#e7edf5'}}));}}let pts='';values.forEach((v,i)=>{{const x=pL+i*(w-pL-pR)/Math.max(1,values.length-1);const y=pT+(h-pT-pB)-((v-min)/span)*(h-pT-pB);pts+=`${{x}},${{y}} `;svg.appendChild(svgEl('circle',{{cx:x,cy:y,r:3.5,fill:color}}));const lab=svgEl('text',{{x,y:h-10,'text-anchor':'middle','font-size':'11',fill:'#64748b'}});lab.textContent=labels[i];svg.appendChild(lab);}});svg.appendChild(svgEl('polyline',{{points:pts.trim(),fill:'none',stroke:color,'stroke-width':3}}));const minT=svgEl('text',{{x:8,y:h-pB,'font-size':'11',fill:'#64748b'}});minT.textContent=min.toFixed(digits);svg.appendChild(minT);const maxT=svgEl('text',{{x:8,y:pT+4,'font-size':'11',fill:'#64748b'}});maxT.textContent=max.toFixed(digits);svg.appendChild(maxT);c.appendChild(svg);}}
function renderParserChart(containerId,runs){{const c=document.getElementById(containerId);if(!c||!runs.length)return;const w=520,h=230,pL=44,pR=18,pT=16,pB=38,maxVal=Math.max(...runs.flatMap(r=>[r.parse_failures,r.resync_events,r.dropped_frames_estimate]),1);const svg=svgEl('svg',{{viewBox:`0 0 ${{w}} ${{h}}`,width:'100%',height:'220'}});for(let i=0;i<4;i++){{const y=pT+((h-pT-pB)/3)*i;svg.appendChild(svgEl('line',{{x1:pL,y1:y,x2:w-pR,y2:y,stroke:'#e7edf5'}}));}}const colors=[['parse_failures','#d9485f','parse'],['resync_events','#0f6cbd','resync'],['dropped_frames_estimate','#b45309','dropped']];runs.forEach((run,idx)=>{{const groupX=pL+idx*(w-pL-pR)/runs.length;colors.forEach(([key,color],cidx)=>{{const val=Number(run[key]||0),barW=10,x=groupX+cidx*12,hv=((h-pT-pB)*val/maxVal),y=(h-pB)-hv;svg.appendChild(svgEl('rect',{{x,y,width:barW,height:hv,fill:color,rx:2}}));}});const lab=svgEl('text',{{x:groupX+12,y:h-12,'text-anchor':'middle','font-size':'11',fill:'#64748b'}});lab.textContent=String(run.run_id).slice(-6);svg.appendChild(lab);}});colors.forEach((item,idx)=>{{svg.appendChild(svgEl('rect',{{x:pL+idx*110,y:6,width:12,height:12,fill:item[1],rx:2}}));const t=svgEl('text',{{x:pL+18+idx*110,y:16,'font-size':'11',fill:'#475569'}});t.textContent=item[2];svg.appendChild(t);}});c.appendChild(svg);}}
function renderScatterChart(containerId,runs,xKey,yKey,xLabel,yLabel,color){{const c=document.getElementById(containerId);if(!c||!runs.length)return;const w=520,h=230,pL=52,pR=18,pT=18,pB=42;const pts=runs.map(r=>({{x:Number(r[xKey]||0),y:Number(r[yKey]||0),label:String(r.run_id).slice(-6)}})).filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));if(!pts.length)return;const minX=Math.min(...pts.map(p=>p.x)),maxX=Math.max(...pts.map(p=>p.x)),minY=Math.min(...pts.map(p=>p.y)),maxY=Math.max(...pts.map(p=>p.y)),spanX=maxX-minX||1,spanY=maxY-minY||1;const svg=svgEl('svg',{{viewBox:`0 0 ${{w}} ${{h}}`,width:'100%',height:'220'}});svg.appendChild(svgEl('line',{{x1:pL,y1:h-pB,x2:w-pR,y2:h-pB,stroke:'#94a3b8'}}));svg.appendChild(svgEl('line',{{x1:pL,y1:pT,x2:pL,y2:h-pB,stroke:'#94a3b8'}}));pts.forEach(p=>{{const x=pL+((p.x-minX)/spanX)*(w-pL-pR),y=pT+(h-pT-pB)-((p.y-minY)/spanY)*(h-pT-pB);svg.appendChild(svgEl('circle',{{cx:x,cy:y,r:5,fill:color,opacity:0.9}}));const lab=svgEl('text',{{x:x+7,y:y-7,'font-size':'11',fill:'#475569'}});lab.textContent=p.label;svg.appendChild(lab);}});const xT=svgEl('text',{{x:w/2,y:h-8,'text-anchor':'middle','font-size':'11',fill:'#64748b'}});xT.textContent=`${{xLabel}} (${{minX.toFixed(2)}} ~ ${{maxX.toFixed(2)}})`;svg.appendChild(xT);const yT=svgEl('text',{{x:14,y:pT+6,'font-size':'11',fill:'#64748b'}});yT.textContent=`${{yLabel}} (${{maxY.toFixed(2)}})`;svg.appendChild(yT);c.appendChild(svg);}}
function setImpact(topic){{document.querySelectorAll('.impact-button').forEach(b=>b.classList.toggle('active',b.dataset.topic===topic));document.querySelectorAll('.impact-item').forEach(item=>{{if(topic==='all'){{item.classList.remove('dim','hot');return;}}const topics=(item.dataset.topics||'').split(' ');const match=topics.includes(topic);item.classList.toggle('dim',!match);item.classList.toggle('hot',match);}});}}
document.addEventListener('DOMContentLoaded',()=>{{renderLineChart('chart-tracks',RUNS,'avg_tracks','#0f6cbd',2);renderLineChart('chart-zero',RUNS.map(r=>({{...r,zero_track_ratio_pct:r.zero_track_ratio*100}})),'zero_track_ratio_pct','#c2410c',1);renderParserChart('chart-parser',RUNS);renderLineChart('chart-range',RUNS,'avg_removed_range','#7c3aed',2);renderScatterChart('chart-snr',RUNS,'snr_threshold','avg_filtered_points','snr_threshold','avg_filtered_points','#0f766e');renderScatterChart('chart-dbscan-min',RUNS,'dbscan_min_samples','avg_tracks','dbscan_min_samples','avg_tracks','#c2410c');document.querySelectorAll('.impact-button').forEach(b=>b.addEventListener('click',()=>setImpact(b.dataset.topic)));setImpact('all');}});
</script>
</body></html>"""


def main() -> None:
    DOXYGEN_HTML_DIR.mkdir(parents=True, exist_ok=True)
    entries = _load_runs()
    OUTPUT_PATH.write_text(build_html(entries), encoding="utf-8")
    print(f"[generated] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
