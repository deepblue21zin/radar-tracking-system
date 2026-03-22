# Experiment Journal

이 문서는 런타임/시각화 튜닝을 `문제 확인 -> 가설 -> 수정 -> 로그 검증 -> 다음 액션` 흐름으로 정리한 운영 기록이다.

## 목적
- 실험을 단순 로그 모음이 아니라, "왜 이걸 바꿨는지"가 보이는 형태로 남긴다.
- 이후 취업용 포트폴리오나 발표 자료에서 디버깅/개선 과정을 설명할 수 있게 한다.
- 같은 문제를 반복할 때 이전 가설과 수정 결과를 바로 재사용할 수 있게 한다.

## Iteration 1: 근거리 필터링은 되는데 tracking continuity가 약함
- Problem:
  - `20260318_024048`에서 filter는 작동했지만 `avg_tracks=0.59`로 연속 추적이 약했다.
- Hypothesis:
  - ROI/keepout 기준은 어느 정도 맞지만, near-field 조건에서 사람 점군이 충분히 유지되지 않는다.
- Change:
  - runtime 파이프라인과 파라미터 관리를 정리하고, filter/DBSCAN/tracker 흐름을 로그로 추적하기 시작했다.
- Verification:
  - [docs/performance_log.md](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/docs/performance_log.md)에 `20260318_024048` 기준 `avg_removed_range=0.16`, `avg_removed_axis_roi=4.86`를 기록했다.
- Next issue:
  - 사람 점군이 실제로 어디서 많이 잘리는지와 viewer에서 사람이 왜 잘 안 보이는지 확인이 필요했다.

## Iteration 2: viewer에서 사람이 거의 안 보이고 range gate 영향이 큼
- Problem:
  - `20260318_215954`에서 `avg_removed_range=36.70`이 가장 컸고, 영상에서도 `filtered=4~6`, `tracks=0` 구간이 반복됐다.
- Hypothesis:
  - `max_range=3.0m`가 사람 점군을 과하게 자르고 있고, viewer도 디버그용 scatter라 움직임 가독성이 낮다.
- Change:
  - viewer에 `motion cloud`, `trail`, `velocity arrow`, `status overlay`, `sensor_yaw_deg`를 추가했다.
  - reader buffer를 키워 parser 복구 여유를 늘렸다.
- Verification:
  - [docs/performance_log.md](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/docs/performance_log.md)의 `20260318_215954` 항목에 원인과 수정 방향을 기록했다.
- Next issue:
  - viewer 계산과 runtime 계산이 어긋나면 튜닝 근거가 흔들리므로 공용 처리 경로 통합이 필요했다.

## Iteration 3: viewer와 runtime 결과를 같은 처리 경로로 맞춤
- Problem:
  - viewer에서 보이는 raw/filter/cluster/track와 runtime 로그가 완전히 같다고 보장할 수 없었다.
- Hypothesis:
  - 같은 함수가 아니라 같은 처리 경로를 타야 튜닝 결과를 믿을 수 있다.
- Change:
  - viewer가 `runtime_pipeline.process_runtime_frame()` 공용 경로를 사용하도록 정리했다.
  - 이후에는 `run_realtime()` loop callback 방식으로 붙여 runtime 결과를 직접 렌더링하게 바꿨다.
- Verification:
  - `20260318_225405` 분석에서 parser health는 좋아졌지만 continuity는 여전히 range/ROI 영향이 크다는 점을 분리해서 볼 수 있게 됐다.
- Next issue:
  - 왕복 실험에서 앞뒤 이동은 보이는데 축이 비틀어져 보이는 현상이 남았다.

## Iteration 4: 앞뒤 왕복은 잡히지만 축이 틀어지고 far 구간이 자주 끊김
- Problem:
  - `20260318_231830`에서는 왕복 패턴은 읽히지만 `x` 변화폭도 커서 순수 앞뒤 이동처럼 보이지 않았다.
  - `zero_tracks=552/1299`, 최장 streak `74 frame`으로 continuity도 약했다.
- Hypothesis:
  - `sensor_yaw_deg`만으로는 실제 설치 자세를 다 설명할 수 없고, `range + ROI gate`가 far 구간을 다시 자른다.
- Change:
  - `sensor_yaw_deg`를 노출하고, status overlay에 제거 원인과 parser health를 같이 표시했다.
- Verification:
  - [docs/performance_log.md](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/docs/performance_log.md)의 `20260318_231830` 항목에 왕복 패턴과 continuity 저하를 함께 정리했다.
- Next issue:
  - 대각선 이동처럼 보이는 근본 원인이 `yaw`만이 아니라 사람 분할과 설치 각도까지 포함하는지 확인이 필요했다.

## Iteration 5: 사람 1명을 여러 track으로 나눠 잡고 대각선처럼 보임
- Problem:
  - `20260319_002404`에서 `tracks>=2` 프레임이 많았고, dominant track 방향도 Y축에서 약 `23도` 틀어져 있었다.
  - 영상과 로그를 같이 보면 사람 1명이 좌/우 반사점으로 분할되어 보였고, viewer에서는 그게 대각선 이동처럼 과장됐다.
- Hypothesis:
  - 사람 분할, `yaw` 미보정, 그리고 설치 pitch/height 미보정이 동시에 작동하고 있다.
- Change:
  - `sensor_yaw_deg`만으로 설명되지 않는 현상을 분리해서 분석했고, 이후 `sensor_pitch_deg`, `sensor_height_m`, world 좌표 보정이 필요하다는 결론을 냈다.
- Verification:
  - `20260319_002404`에서 `avg_tracks=1.69`, `zero_tracks=47`, `parse_fail=4`, `resync=78`, `dropped=9`를 근거로 viewer 문제만이 아니라 좌표/연속성 문제도 함께 있음을 정리했다.
- Next issue:
  - 시연 시 체감 끊김과 딜레이의 주원인이 logging인지 draw stall인지 분리해서 확인할 필요가 있었다.

## Iteration 6: logging 부담을 줄였지만 draw stall과 UART continuity가 더 큼
- Problem:
  - `20260319_015812`에서 parser health는 좋아졌지만 `max_pipe_ms=2516.66`이 남아 체감 끊김이 컸다.
- Hypothesis:
  - text log flush와 overview PNG는 일부 부담이지만, 더 큰 병목은 viewer draw와 UART continuity다.
- Change:
  - `--disable-text-log`, `--disable-overview-png`를 추가해 logging 부하를 따로 끌 수 있게 했다.
- Verification:
  - `20260319_021240`에서는 `avg_pipe_ms 14.20 -> 10.49`로 내려갔지만, `parse_fail/resync/dropped`는 오히려 다시 증가했다.
- Next issue:
  - 즉, logging은 보조 병목이고 핵심은 draw 구조와 좌표 보정 문제다. 다음 단계는 `pitch/height` 보정과 viewer read/draw 분리다.

## Current Direction
- Problem:
  - 실시간 시연에서 대각선/값 튐/딜레이가 동시에 보인다.
- Active hypothesis:
  - `sensor_pitch_deg=30`, `sensor_height_m=1.74` 설치를 world 좌표로 보정하지 않은 상태에서, single-thread draw가 지연을 키우고 있다.
- In progress:
  - `sensor_pitch_deg`, `sensor_height_m`, world-coordinate 보정을 공용 runtime 경로에 추가
  - viewer를 `read/process`와 `draw`로 분리해 최신 상태만 렌더링하도록 구조 개선
  - run 종료 시 structured experiment report를 자동 생성해 다음 실험 기록을 표준화

## Related Docs
- 성능 수치 요약: [docs/performance_log.md](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/docs/performance_log.md)
- 수정 이력: [docs/correction report/2026-03-18.md](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/docs/correction%20report/2026-03-18.md)
- 런타임 이슈/튜닝 계획: [docs/elevation/runtime_issue_fix_plan.md](/d:/capstone_radar/ti_toolbox/radar-tracking-system/radar-tracking-system/docs/elevation/runtime_issue_fix_plan.md)
- 자동 생성 run 리포트 인덱스: `docs/experiment_reports/README.md`
