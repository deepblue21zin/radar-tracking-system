# Radar Tracking System Doxygen Overview

이 페이지는 Doxygen 문서를 열었을 때 가장 먼저 보는 상위 구조 요약이다.

## 1. Pipeline Map

\dot
digraph radar_tracking_pipeline {
  rankdir=LR;
  splines=true;
  node [shape=box, style="rounded,filled", fillcolor="#eef4ff", color="#4c6a92", fontname="Arial"];
  edge [color="#617a99"];

  radar   [label="TI IWR6843\nTLV UART stream"];
  parser  [label="src/parser\n- tlv_packet_parser.py\n- tlv_parse_runner.py"];
  filter  [label="src/filter\n- noise_filter.py"];
  cluster [label="src/cluster\n- dbscan_cluster.py"];
  track   [label="src/tracking\n- kalman_tracker.py\n- tracker_utils.c/h"];
  viewer  [label="src/visualization\n- live_rail_viewer.py"];
  stm32   [label="src/communication\n- stm32_uart_tx.c"];
  logs    [label="evidence/runtime_logs\nframe/summary CSV"];
  docs    [label="docs/\narchitecture + specs"];

  radar -> parser;
  parser -> filter;
  filter -> cluster;
  cluster -> track;
  track -> stm32;
  parser -> logs;
  filter -> viewer;
  cluster -> viewer;
  track -> viewer;
  docs -> parser [style=dashed];
  docs -> track [style=dashed];
}
\enddot

## 2. Recommended Reading Order

1. Main Page: start here for the pipeline overview and navigation hints.
2. README: runtime goal, command examples, and experiment workflow.
3. Files: inspect the actual source layout under `src/`.
4. `src/parser/tlv_parse_runner.py`: end-to-end runtime entrypoint.
5. `src/tracking/kalman_tracker.py`: track lifecycle and association policy.
6. `src/visualization/live_rail_viewer.py`: live debug viewer wiring.

## 3. What Each View Is Good For

- Main Page: one-page mental model of the whole system.
- Files: see which modules exist and jump into source files.
- Function/Class pages: inspect local logic and caller/callee relations.
- Source Browser: compare documentation and implementation side by side.

## 4. Scope of This Documentation

- Included: project-owned source files in `src/`, high-level docs, and architecture notes.
- Excluded: generated Doxygen output, runtime evidence, experiments, and vendored `filterpy-master`.

## 5. Related Project Docs

- `README.md`: operational overview and run commands.
- `docs/architecture.md`: concise architecture description.
- `docs/capstone_pipeline_spec.md`: pipeline spec for the capstone workflow.
- `docs/architecture_analysis_spec.md`: analysis-focused architecture notes.
