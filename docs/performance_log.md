# Performance Log

이 문서는 "무엇을 바꿨고, 어떤 근거에서, 값이 어떻게 변했는지"를 계속 누적하는 운영 기록이다.

| Date | Run ID | Scenario | Avg FPS | Avg Filter Ratio | Avg Raw -> Filtered | Parser / Pipe (ms) | Parser Health | Notes |
|---|---|---|---:|---:|---|---|---|---|
| 2026-03-02 | baseline-replay | parser-only replay | 31.20 | - | - | 27.8 / - | replay | Initial project scaffold |
| 2026-03-18 | 20260318_024048 | `live_run` | 9.36 | 0.480 | `15.77 -> 9.22` | `2.03 / 12.73` | `parse_fail=18, resync=1, dropped=20` | Near-field tuning run. `avg_removed_range=0.16`, `avg_removed_axis_roi=4.86`. Filter는 작동했지만 `avg_tracks=0.59`라 continuity는 아직 약함. Evidence: `evidence/runtime_logs/frames_20260318_024048.csv` |
| 2026-03-18 | 20260318_215954 | `baseline / full_frame` | 9.25 | 0.294 | `58.49 -> 17.43` | `0.85 / 15.56` | `parse_fail=4, resync=78, dropped=45` | `avg_removed_range=36.70`가 가장 커서 `max_range=3.0m`가 사람 점군을 과하게 제거. 영상 샘플에서도 `filtered=4~6`, `clusters=0`, `tracks=0` 구간 반복 확인. 이 run을 근거로 viewer에 `motion cloud / trail / velocity arrow / status overlay / sensor_yaw_deg`를 추가했고, reader buffer를 `128KB`로 키움. Improvement 확인은 재측정 필요. Evidence: `evidence/runtime_logs/frames_20260318_215954.csv`, `C:\\Users\\JSjeong\\Videos\\화면 녹화\\화면 녹화 중 2026-03-18 221638.mp4` |
| 2026-03-18 | 20260318_225405 | `baseline / full_frame` | 9.83 | 0.410 | `22.22 -> 9.35` | `1.04 / 11.23` | `parse_fail=5, resync=62, dropped=10` | `215954`보다 parser health는 좋아졌지만 continuity는 아직 약하다. `zero_tracks=139/590`, 최장 zero-track streak는 `frame 68-94`의 `27 frame`이고 이 구간에서 `raw 520 -> filtered 41`, `removed_range=427`, `removed_roi=52`였다. 후반 `frame 472-507`도 `raw 615 -> filtered 29`, `removed_range=460`, `removed_roi=126`로 다시 크게 잘렸다. 즉, 앞뒤 이동 실험에서 주된 끊김 원인은 parser보다 `max_range=3.0m + z/ROI gate` 쪽이다. 이 run 이후 viewer의 raw/filter/cluster/track 계산을 `runtime_pipeline.process_runtime_frame()` 공용 경로로 통합했다. Evidence: `evidence/runtime_logs/frames_20260318_225405.csv`, `evidence/runtime_logs/frames_20260318_225405.log` |
| 2026-03-18 | 20260318_231830 | `longer front/back walk` | 9.75 | 0.388 | `22.03 -> 8.94` | `0.81 / 10.21` | `parse_fail=17, resync=205, dropped=33` | 앞뒤 왕복 자체는 더 길게 잡혔지만 continuity는 오히려 악화됐다. `zero_tracks=552/1299`, 최장 zero-track streak는 `frame 833-906`의 `74 frame`이고 이 구간에서 `raw 1062 -> filtered 88`, `removed_range=760`, `removed_roi=211`이었다. preview 좌표 기준 `y=1.74 -> 0.60 -> 1.31`, `y=1.30 -> 0.32 -> 1.12` 같은 왕복 패턴은 보이지만, `x` 변화폭도 커서 축이 아직 완전히 맞진 않았다. 핵심 원인은 여전히 `range + ROI gate`이며, far 구간에서 `avg_tracks`가 `0.749`까지 떨어진다. Evidence: `evidence/runtime_logs/frames_20260318_231830.csv`, `evidence/runtime_logs/frames_20260318_231830.log` |

## Change Tracking Rule
- 코드 수정이 실행 흐름, 파라미터, 시각화, parser 안정성에 영향을 주면 같은 날 바로 이 문서에 추가한다.
- 개선이 확인되면 반드시 `무엇을 수정했는지`, `어떤 로그/영상으로 확인했는지`, `전/후 수치가 어떻게 바뀌었는지`를 함께 남긴다.
- 개선이 아니라 회귀나 미해결 진단이어도 삭제하지 않고 그대로 남긴다.

## Measurement Notes
- `Avg FPS`: `run_summary.csv` 기준 실효 처리 FPS.
- `Avg Filter Ratio`: `avg_filtered_points / avg_raw_points`에 해당하는 frame 평균값.
- `Avg Raw -> Filtered`: run 전체 평균 raw point 수와 filtered point 수.
- `Parser / Pipe (ms)`: run 평균 `parser_latency_ms` / `pipeline_latency_ms`.
- `Parser Health`: `parse_failures`, `resync_events`, `dropped_frames_estimate`.
