# Radar Tracking System Doxygen Overview

이 페이지는 "이 프로젝트가 지금 실제로 어떻게 돌아가고 있는지"를 한눈에 파악하기 위한 시작점이다.

## 1. One-Minute Summary

현재 실시간 파이프라인은 아래 순서로 동작한다.

```text
TI IWR6843 radar
  -> TLV UART stream
  -> runtime entrypoint (tlv_parse_runner.py wrapper)
  -> runtime pipeline (cfg send + packet decode + runtime logging)
  -> filter (ROI / keepout / clutter reject)
  -> DBSCAN cluster
  -> Kalman tracker
  -> control decision / optional STM32 packet
  -> live viewer / runtime CSV, LOG
```

지금 바로 봐야 할 핵심 파일은 8개다.

- `src/parser/tlv_packet_parser.py`
- `src/parser/runtime_pipeline.py`
- `src/parser/tlv_parse_runner.py`
- `src/runtime_params.py`
- `config/runtime_params.json`
- `src/filter/noise_filter.py`
- `src/cluster/dbscan_cluster.py`
- `src/tracking/kalman_tracker.py`
- `src/visualization/live_rail_viewer.py`

## 2. Current System Map

\dot
digraph radar_tracking_pipeline {
  rankdir=LR;
  splines=true;
  graph [fontname="Arial", nodesep=0.45, ranksep=0.65];
  node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11];
  edge [color="#5c6f82", penwidth=1.2];

  subgraph cluster_input {
    label="Input";
    color="#cbd5e1";
    style="rounded";
    radar [label="TI IWR6843\nTLV UART stream", fillcolor="#e0f2fe", color="#468faf"];
  }

  subgraph cluster_online {
    label="Online Runtime Path";
    color="#cbd5e1";
    style="rounded";
    params  [label="Shared Params\nconfig/runtime_params.json\nsrc/runtime_params.py", fillcolor="#eefaf2", color="#4a7c59"];
    entry   [label="Entrypoint\nsrc/parser/\n- tlv_parse_runner.py", fillcolor="#eef4ff", color="#4c6a92"];
    parser  [label="Runtime Pipeline\nsrc/parser/\n- runtime_pipeline.py\n- tlv_packet_parser.py", fillcolor="#eef4ff", color="#4c6a92"];
    filter  [label="Filter\nsrc/filter/\n- noise_filter.py", fillcolor="#eefbf3", color="#4b8b62"];
    cluster [label="Cluster\nsrc/cluster/\n- dbscan_cluster.py", fillcolor="#fff6e8", color="#a26a1c"];
    track   [label="Track\nsrc/tracking/\n- kalman_tracker.py", fillcolor="#fff1f2", color="#a44a5f"];
    control [label="Control\nsrc/control/\n- proximity_speed_control.py", fillcolor="#fef7e7", color="#b7791f"];
  }

  subgraph cluster_output {
    label="Outputs";
    color="#cbd5e1";
    style="rounded";
    viewer [label="Viewer\nsrc/visualization/\n- live_rail_viewer.py", fillcolor="#f3e8ff", color="#7c4d9a"];
    logs   [label="Logs\nruntime CSV / LOG\nrun_summary.csv", fillcolor="#f8fafc", color="#64748b"];
    stmout [label="STM32 Packet\nsrc/communication/\n- control_protocol.py", fillcolor="#eef2ff", color="#5a67d8"];
  }

  subgraph cluster_deferred {
    label="Present in Repo, Not Core Runtime Today";
    color="#d7d7d7";
    style="rounded,dashed";
    stm32 [label="STM32 example side\nsrc/communication/\n- stm32_control_rx_example.c\n- control_packet_protocol.h", fillcolor="#fafafa", color="#888888"];
    tiutil [label="TI tracker utils\nsrc/tracking/\n- tracker_utils.c/h", fillcolor="#fafafa", color="#888888"];
  }

  radar -> entry;
  params -> entry;
  params -> viewer;
  entry -> parser;
  parser -> filter;
  filter -> cluster;
  cluster -> track;
  track -> control;
  parser -> logs;
  filter -> viewer;
  cluster -> viewer;
  track -> viewer;
  control -> logs;
  control -> stmout;
  stmout -> stm32 [style=dashed, color="#999999"];
  tiutil -> track [style=dashed, color="#999999"];
}
\enddot

## 3. What Is Actually Running Now

현재 기준에서 "실제로 이어져 있는 경로"는 아래다.

- `tlv_parse_runner.py`: 기존 실행 명령을 유지하는 호환 래퍼
- `runtime_pipeline.py`: 실제 cfg 전송, UART read, parse, filter, cluster, track, control, logging을 수행하는 메인 구현
- `runtime_params.py` + `config/runtime_params.json`: runner/viewer 공용 기본 파라미터 로더
- `noise_filter.py`: SNR/range/ROI/keepout/static clutter filtering
- `dbscan_cluster.py`: point -> cluster
- `kalman_tracker.py`: cluster -> track
- `proximity_speed_control.py`: track -> control decision
- `live_rail_viewer.py`: raw/filtered/cluster/track 시각화

지금 당장 신경 덜 써도 되는 파일도 있다.

- `src/communication/stm32_control_rx_example.c`: STM32 쪽 수신 예제
- `src/tracking/tracker_utils.c/h`: TI SDK 연동용 유틸, 현재 Python 실시간 경로 핵심은 아님

## 4. Read In This Order

프로젝트를 처음 다시 파악할 때는 아래 순서가 가장 덜 헷갈린다.

1. `README.md`
2. `docs/elevation/runtime_issue_fix_plan.md`
3. `src/parser/tlv_parse_runner.py`
4. `src/parser/runtime_pipeline.py`
5. `src/runtime_params.py`
6. `config/runtime_params.json`
7. `src/filter/noise_filter.py`
8. `src/tracking/kalman_tracker.py`
9. `src/visualization/live_rail_viewer.py`

## 5. Debug By Symptom

증상별로 먼저 볼 파일을 바로 찾고 싶다면 이렇게 보면 된다.

- frame 자체가 깨짐: `src/parser/tlv_packet_parser.py`, `src/parser/runtime_pipeline.py`
- 시작 직후 프레임이 뒤틀림: `src/parser/runtime_pipeline.py`
- 점은 많은데 사람이 안 보임: `src/filter/noise_filter.py`
- cluster가 이상함: `src/cluster/dbscan_cluster.py`
- track가 끊김 / ghost가 많음: `src/tracking/kalman_tracker.py`
- 제어 명령이 이상함: `src/control/proximity_speed_control.py`, `src/communication/control_protocol.py`
- 파라미터가 runner/viewer에서 다르게 보임: `src/runtime_params.py`, `config/runtime_params.json`
- 화면이 헷갈림: `src/visualization/live_rail_viewer.py`

## 6. Best Pages To Open In HTML

Doxygen HTML에서 처음 클릭하기 좋은 페이지는 아래다.

- Main Page: 전체 구조와 읽는 순서
- Files: 실제 코드 파일 목록
- `src/parser/tlv_parse_runner.py`: 호환 entrypoint
- `src/parser/runtime_pipeline.py`: end-to-end runtime implementation
- `src/runtime_params.py`: shared parameter loader
- `docs/elevation/runtime_issue_fix_plan.md`: 현재 남은 문제와 튜닝 계획

## 7. Scope Of This Documentation

- Included: `src/` 아래 프로젝트 코드, `config/runtime_params.json`, `docs/elevation` 계획 문서, 핵심 운영 문서
- Excluded: generated Doxygen output, runtime evidence, experiments, vendored `filterpy-master`, dated error/correction logs
