"""Generate a self-contained HTML code browser for core runtime files."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "docs" / "runtime_code_browser.html"


@dataclass(frozen=True)
class CodeFile:
    group: str
    path: str
    label: str
    description: str


FILES = [
    CodeFile("Runtime", "src/parser/tlv_parse_runner.py", "tlv_parse_runner.py", "기본 실행 진입점 호환 래퍼"),
    CodeFile("Runtime", "src/parser/runtime_pipeline.py", "runtime_pipeline.py", "실제 serial read / processing / logging / report 메인 루프"),
    CodeFile("Runtime", "src/parser/tlv_packet_parser.py", "tlv_packet_parser.py", "TLV packet을 frame과 point 배열로 해석"),
    CodeFile("Runtime", "src/runtime_params.py", "runtime_params.py", "공용 파라미터 기본값과 JSON override 로더"),
    CodeFile("Filter/Cluster/Track", "src/filter/noise_filter.py", "noise_filter.py", "SNR/range/ROI/keepout/static clutter 전처리"),
    CodeFile("Filter/Cluster/Track", "src/cluster/dbscan_cluster.py", "dbscan_cluster.py", "DBSCAN clustering 및 adaptive eps 처리"),
    CodeFile("Filter/Cluster/Track", "src/tracking/kalman_tracker.py", "kalman_tracker.py", "greedy association 기반 Kalman tracker"),
    CodeFile("Control", "src/control/proximity_speed_control.py", "proximity_speed_control.py", "belt axis 기준 motion state와 speed command 결정"),
    CodeFile("Control", "src/communication/control_protocol.py", "control_protocol.py", "STM32 제어 packet 인코딩/송신"),
    CodeFile("Viewer", "src/visualization/live_rail_viewer.py", "live_rail_viewer.py", "runtime snapshot 기반 실시간 시각화"),
    CodeFile("Reporting", "src/reporting/runtime_experiment_report.py", "runtime_experiment_report.py", "run별 markdown experiment report 생성"),
    CodeFile("Reporting", "src/reporting/performance_log_report.py", "performance_log_report.py", "run_summary/frame CSV 기반 performance log 생성"),
    CodeFile("Config", "config/runtime_params.json", "runtime_params.json", "공용 실험/시연 파라미터 기본값"),
    CodeFile("Config", "config/profile_3d.cfg", "profile_3d.cfg", "레이더 demo firmware의 CFAR/beamforming/AoA 설정"),
]


def slugify(path: str) -> str:
    return path.replace("/", "-").replace(".", "-")


def render_code_table(file_path: str) -> str:
    abs_path = PROJECT_ROOT / file_path
    text = abs_path.read_text(encoding="utf-8")
    rows: list[str] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        content = escape(raw_line)
        if content == "":
            content = "&#8203;"
        anchor = f"{slugify(file_path)}-L{line_no}"
        rows.append(
            "<tr>"
            f'<td class="line-no"><a href="#{anchor}" id="{anchor}">{line_no}</a></td>'
            f'<td class="code-line"><code>{content}</code></td>'
            "</tr>"
        )
    if not rows:
        rows.append(
            '<tr><td class="line-no">1</td><td class="code-line"><code>&#8203;</code></td></tr>'
        )
    return "\n".join(rows)


def build_html() -> str:
    grouped: dict[str, list[CodeFile]] = {}
    for item in FILES:
        grouped.setdefault(item.group, []).append(item)

    nav_sections: list[str] = []
    panels: list[str] = []
    first_slug = slugify(FILES[0].path)

    for group, items in grouped.items():
        buttons: list[str] = []
        for item in items:
            slug = slugify(item.path)
            abs_path = PROJECT_ROOT / item.path
            line_count = len(abs_path.read_text(encoding="utf-8").splitlines())
            buttons.append(
                "<button "
                f'class="file-button{" active" if slug == first_slug else ""}" '
                f'data-target="{slug}" type="button">'
                f'<span class="file-label">{escape(item.label)}</span>'
                f'<span class="file-meta">{escape(item.path)} · {line_count} lines</span>'
                "</button>"
            )
            panels.append(
                "<section "
                f'class="code-panel{" active" if slug == first_slug else ""}" '
                f'id="panel-{slug}">'
                '<div class="panel-head">'
                f'<div><p class="eyebrow">{escape(group)}</p><h2>{escape(item.label)}</h2>'
                f'<p>{escape(item.description)}</p></div>'
                '<div class="panel-actions">'
                f'<a class="panel-link" href="../{escape(item.path)}">원본 파일 열기</a>'
                f'<a class="panel-link secondary" href="./runtime_system_onepage.html">구조 설명 보기</a>'
                "</div>"
                "</div>"
                f'<div class="path-chip">{escape(item.path)}</div>'
                '<div class="code-shell">'
                '<table class="code-table"><tbody>'
                f"{render_code_table(item.path)}"
                "</tbody></table>"
                "</div>"
                "</section>"
            )
        nav_sections.append(
            "<section class=\"nav-group\">"
            f"<h3>{escape(group)}</h3>"
            f"{''.join(buttons)}"
            "</section>"
        )

    files_payload = [
        {"path": item.path, "slug": slugify(item.path), "label": item.label}
        for item in FILES
    ]

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Runtime Code Browser</title>
  <style>
    :root {{
      --bg: #f3f5f8;
      --paper: #ffffff;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #d7dee8;
      --accent: #0f6cbd;
      --accent-soft: #e7f1fb;
      --accent-2: #b45309;
      --sidebar: #0f172a;
      --sidebar-line: #253146;
      --sidebar-ink: #dbe7ff;
      --shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
      --code-bg: #0d1117;
      --code-line: #161b22;
      --code-ink: #e6edf3;
      --line-no: #7d8590;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Pretendard", "Noto Sans KR", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(15,108,189,0.08), transparent 26%),
        linear-gradient(180deg, #f5f7fa 0%, #eff3f8 100%);
    }}

    a {{ color: inherit; }}

    .layout {{
      display: grid;
      grid-template-columns: 340px minmax(0, 1fr);
      min-height: 100vh;
    }}

    .sidebar {{
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
      padding: 24px 18px 28px;
      background:
        linear-gradient(180deg, rgba(15,23,42,0.98), rgba(18,30,52,0.98));
      color: var(--sidebar-ink);
      border-right: 1px solid var(--sidebar-line);
    }}

    .sidebar h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      line-height: 1.08;
      letter-spacing: -0.03em;
    }}

    .sidebar p {{
      margin: 0 0 18px;
      color: rgba(219,231,255,0.8);
      font-size: 14px;
      line-height: 1.55;
    }}

    .quick-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 18px;
    }}

    .quick-links a {{
      text-decoration: none;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.06);
      font-size: 12px;
      color: #fff;
    }}

    .search {{
      width: 100%;
      margin-bottom: 18px;
      padding: 11px 12px;
      border-radius: 14px;
      border: 1px solid rgba(255,255,255,0.14);
      background: rgba(255,255,255,0.08);
      color: #fff;
      outline: none;
    }}

    .search::placeholder {{
      color: rgba(219,231,255,0.56);
    }}

    .nav-group {{
      margin-top: 18px;
      padding-top: 18px;
      border-top: 1px solid rgba(255,255,255,0.08);
    }}

    .nav-group h3 {{
      margin: 0 0 10px;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: rgba(219,231,255,0.72);
    }}

    .file-button {{
      width: 100%;
      text-align: left;
      margin: 0 0 8px;
      padding: 12px 12px;
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.04);
      color: inherit;
      cursor: pointer;
    }}

    .file-button.active {{
      background: linear-gradient(180deg, rgba(15,108,189,0.32), rgba(15,108,189,0.18));
      border-color: rgba(135,185,240,0.45);
      box-shadow: 0 10px 24px rgba(15,108,189,0.18);
    }}

    .file-button.hidden {{
      display: none;
    }}

    .file-label {{
      display: block;
      font-weight: 700;
      font-size: 14px;
      margin-bottom: 4px;
    }}

    .file-meta {{
      display: block;
      font-size: 12px;
      color: rgba(219,231,255,0.72);
      word-break: break-word;
    }}

    .main {{
      padding: 24px;
    }}

    .main-head {{
      background: linear-gradient(135deg, rgba(15,108,189,0.95), rgba(33,81,164,0.92));
      color: #fff;
      padding: 24px 26px;
      border-radius: 24px;
      box-shadow: var(--shadow);
      margin-bottom: 20px;
    }}

    .main-head h2 {{
      margin: 0 0 8px;
      font-size: 34px;
      line-height: 1.1;
      letter-spacing: -0.03em;
    }}

    .main-head p {{
      margin: 0;
      max-width: 900px;
      color: rgba(255,255,255,0.9);
    }}

    .code-panel {{
      display: none;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .code-panel.active {{
      display: block;
    }}

    .panel-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      padding: 22px 24px 14px;
      border-bottom: 1px solid #e7edf4;
      background: linear-gradient(180deg, #fff, #fbfcfe);
    }}

    .eyebrow {{
      margin: 0 0 8px;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
      font-weight: 700;
    }}

    .panel-head h2 {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: -0.03em;
    }}

    .panel-head p {{
      margin: 0;
      color: var(--muted);
      max-width: 860px;
    }}

    .panel-actions {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 10px;
      min-width: 230px;
    }}

    .panel-link {{
      text-decoration: none;
      padding: 9px 12px;
      border-radius: 999px;
      border: 1px solid #c9d7ea;
      background: #f0f6ff;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }}

    .panel-link.secondary {{
      border-color: #e3d4c3;
      background: #fff5ec;
      color: var(--accent-2);
    }}

    .path-chip {{
      margin: 14px 24px 0;
      display: inline-block;
      padding: 7px 11px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
    }}

    .code-shell {{
      margin: 18px 0 0;
      background: var(--code-bg);
      overflow: auto;
      border-top: 1px solid #10161f;
    }}

    .code-table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}

    .code-table tr:nth-child(even) {{
      background: rgba(255,255,255,0.015);
    }}

    .line-no {{
      width: 72px;
      vertical-align: top;
      text-align: right;
      padding: 0 10px 0 0;
      background: var(--code-line);
      border-right: 1px solid rgba(255,255,255,0.08);
      user-select: none;
    }}

    .line-no a {{
      display: block;
      padding: 0 0 0 10px;
      color: var(--line-no);
      text-decoration: none;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      line-height: 1.72;
    }}

    .line-no a:hover {{
      color: #c9d1d9;
    }}

    .code-line {{
      padding: 0 18px;
      color: var(--code-ink);
    }}

    .code-line code {{
      display: block;
      white-space: pre;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      line-height: 1.72;
    }}

    @media (max-width: 1080px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        position: static;
        height: auto;
      }}
      .panel-head {{
        flex-direction: column;
      }}
      .panel-actions {{
        justify-content: flex-start;
      }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <h1>Runtime Code Browser</h1>
      <p>핵심 파일 전체를 GitHub처럼 왼쪽에서 고르고, 오른쪽에서 line number와 함께 읽는 정적 코드 브라우저다.</p>
      <div class="quick-links">
        <a href="./runtime_system_onepage.html">구조 설명</a>
        <a href="./performance_log.md">성능 로그</a>
        <a href="./experiment_journal.md">실험 저널</a>
        <a href="../README.md">README</a>
      </div>
      <input class="search" id="file-search" type="search" placeholder="파일 이름 검색" />
      {''.join(nav_sections)}
    </aside>

    <main class="main">
      <section class="main-head">
        <h2>Full Code View</h2>
        <p>
          이 페이지는 요약이 아니라 전체 코드를 읽는 용도다. 먼저 왼쪽에서 파일을 고르고,
          오른쪽에서 전체 코드와 line number를 보면서 필요한 줄로 바로 이동하면 된다.
        </p>
      </section>
      {''.join(panels)}
    </main>
  </div>

  <script>
    const FILES = {json.dumps(files_payload, ensure_ascii=False)};
    const buttons = Array.from(document.querySelectorAll('.file-button'));
    const panels = Array.from(document.querySelectorAll('.code-panel'));
    const searchInput = document.getElementById('file-search');

    function activateFile(slug) {{
      buttons.forEach((button) => {{
        button.classList.toggle('active', button.dataset.target === slug);
      }});
      panels.forEach((panel) => {{
        panel.classList.toggle('active', panel.id === `panel-${{slug}}`);
      }});
      if (window.location.hash !== `#${{slug}}`) {{
        history.replaceState(null, '', `#${{slug}}`);
      }}
    }}

    buttons.forEach((button) => {{
      button.addEventListener('click', () => activateFile(button.dataset.target));
    }});

    searchInput.addEventListener('input', () => {{
      const query = searchInput.value.trim().toLowerCase();
      buttons.forEach((button) => {{
        const text = button.textContent.toLowerCase();
        button.classList.toggle('hidden', query !== '' && !text.includes(query));
      }});
    }});

    const hash = window.location.hash.replace(/^#/, '');
    const known = FILES.some((item) => item.slug === hash);
    activateFile(known ? hash : FILES[0].slug);
  </script>
</body>
</html>
"""


def main() -> None:
    OUTPUT_PATH.write_text(build_html(), encoding="utf-8")
    print(f"[generated] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
