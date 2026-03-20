# Performance Log

이 문서는 `run_summary.csv`와 frame CSV를 기준으로 자동 생성되는 성능 기록이다.
표 대신 run별 핵심 변화, 이전 run 대비 증감, continuity/분할/제거 원인을 바로 읽을 수 있게 정리한다.

## Latest Snapshot
- Latest run: `20260319_023912` (2026-03-19)
- Scenario: `live_run`
- Avg FPS: `9.915`
- Parser health: `parse_fail=3, resync=25, dropped=5`
- Tracking continuity: `zero_track=183/595`, `tracks>=2=191/595`
- Dominant issue: `range gate (6.82 avg removed/frame)`

## Change Vs Previous
- Previous run: `20260319_021240`
- Avg FPS: `9.915 (+0.101 vs prev, better)`
- Avg parser ms: `1.34 (+0.17 vs prev, worse)`
- Avg pipeline ms: `10.68 (+0.18 vs prev, worse)`
- Parse failures: `3 (-3 vs prev, better)`
- Resync events: `25 (-40 vs prev, better)`
- Dropped estimate: `5 (-6 vs prev, better)`
- Zero-track frames: `183 (+45 vs prev, worse)`
- 2+ track frames: `191 (+28 vs prev, worse)`
- Avg removed range: `6.82 (+0.14 vs prev, worse)`
- Avg removed ROI: `1.11 (-5.58 vs prev, better)`

## Runs

### 2026-03-19 / 20260319_023912
- Scenario: `live_run`
- Summary: FPS `9.915`, parser/pipe `1.344 / 10.676 ms`, raw->filtered `17.588 -> 8.528`, avg tracks `1.106`
- Parser health: `parse_fail=3, resync=25, dropped=5`
- Continuity: `zero_track=183/595`, `tracks>=2=191/595`
- Filtering: `removed_range=6.824`, `removed_roi=1.111`, `removed_keepout=1.121`
- Longest zero-track streak: `frame 235-276 (42 frames)`
- Dominant issue: `range gate (6.82 avg removed/frame)`
- Change vs prev `20260319_021240`: parser fail `3 (-3 vs prev, better)`, resync `25 (-40 vs prev, better)`, zero-track `183 (+45 vs prev, worse)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260319_023912.csv`
- Artifacts: experiment report `experiment_reports/2026-03-19/20260319_023912.md`

### 2026-03-19 / 20260319_021240
- Scenario: `live_run`
- Summary: FPS `9.814`, parser/pipe `1.17 / 10.493 ms`, raw->filtered `21.767 -> 8.26`, avg tracks `1.102`
- Parser health: `parse_fail=6, resync=65, dropped=11`
- Continuity: `zero_track=138/589`, `tracks>=2=163/589`
- Filtering: `removed_range=6.684`, `removed_roi=6.689`, `removed_keepout=0.134`
- Longest zero-track streak: `frame 468-515 (48 frames)`
- Dominant issue: `ROI gate (6.69 avg removed/frame)`
- Change vs prev `20260319_015812`: parser fail `6 (+4 vs prev, worse)`, resync `65 (+24 vs prev, worse)`, zero-track `138 (+111 vs prev, worse)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260319_021240.csv`
- Artifacts: experiment report `experiment_reports/2026-03-19/20260319_021240.md`

### 2026-03-19 / 20260319_015812
- Scenario: `live_run`
- Summary: FPS `9.874`, parser/pipe `1.669 / 14.204 ms`, raw->filtered `24.038 -> 9.478`, avg tracks `1.623`
- Parser health: `parse_fail=2, resync=41, dropped=5`
- Continuity: `zero_track=27/395`, `tracks>=2=211/395`
- Filtering: `removed_range=8.18`, `removed_roi=6.043`, `removed_keepout=0.337`
- Longest zero-track streak: `frame 3-14 (12 frames)`
- Dominant issue: `range gate (8.18 avg removed/frame)`
- Change vs prev `20260319_002404`: parser fail `2 (-2 vs prev, better)`, resync `41 (-37 vs prev, better)`, zero-track `27 (-20 vs prev, better)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260319_015812.csv`
- Artifacts: experiment report `experiment_reports/2026-03-19/20260319_015812.md`

### 2026-03-19 / 20260319_002404
- Scenario: `live_run`
- Summary: FPS `9.773`, parser/pipe `1.522 / 14.288 ms`, raw->filtered `31.967 -> 11.691`, avg tracks `1.693`
- Parser health: `parse_fail=4, resync=78, dropped=9`
- Continuity: `zero_track=47/391`, `tracks>=2=243/391`
- Filtering: `removed_range=14.483`, `removed_roi=5.609`, `removed_keepout=0.184`
- Longest zero-track streak: `frame 355-374 (20 frames)`
- Dominant issue: `range gate (14.48 avg removed/frame)`
- Change vs prev `20260319_002331`: parser fail `4 (-1 vs prev, better)`, resync `78 (+1 vs prev, worse)`, zero-track `47 (+5 vs prev, worse)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260319_002404.csv`
- Artifacts: experiment report `experiment_reports/2026-03-19/20260319_002404.md`

### 2026-03-19 / 20260319_002331
- Scenario: `live_run`
- Summary: FPS `9.539`, parser/pipe `2.544 / 17.632 ms`, raw->filtered `30.722 -> 8.737`, avg tracks `1.254`
- Parser health: `parse_fail=5, resync=77, dropped=10`
- Continuity: `zero_track=42/209`, `tracks>=2=86/209`
- Filtering: `removed_range=13.737`, `removed_roi=0.196`, `removed_keepout=8.053`
- Longest zero-track streak: `frame 213-219 (7 frames)`
- Dominant issue: `range gate (13.74 avg removed/frame)`
- Change vs prev `20260318_231830`: parser fail `5 (-12 vs prev, better)`, resync `77 (-128 vs prev, better)`, zero-track `42 (-510 vs prev, better)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260319_002331.csv`
- Artifacts: experiment report `experiment_reports/2026-03-19/20260319_002331.md`

### 2026-03-18 / 20260318_231830
- Scenario: `live_run`
- Summary: FPS `9.75`, parser/pipe `0.81 / 10.21 ms`, raw->filtered `22.031 -> 8.942`, avg tracks `0.749`
- Parser health: `parse_fail=17, resync=205, dropped=33`
- Continuity: `zero_track=552/1299`, `tracks>=2=208/1299`
- Filtering: `removed_range=6.05`, `removed_roi=6.851`, `removed_keepout=0.188`
- Longest zero-track streak: `frame 833-906 (74 frames)`
- Dominant issue: `ROI gate (6.85 avg removed/frame)`
- Change vs prev `20260318_225405`: parser fail `17 (+12 vs prev, worse)`, resync `205 (+143 vs prev, worse)`, zero-track `552 (+413 vs prev, worse)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260318_231830.csv`
- Artifacts: experiment report `experiment_reports/2026-03-18/20260318_231830.md`

### 2026-03-18 / 20260318_225405
- Scenario: `baseline`
- Summary: FPS `9.831`, parser/pipe `1.039 / 11.23 ms`, raw->filtered `22.217 -> 9.351`, avg tracks `0.954`
- Parser health: `parse_fail=5, resync=62, dropped=10`
- Continuity: `zero_track=139/590`, `tracks>=2=109/590`
- Filtering: `removed_range=5.925`, `removed_roi=6.544`, `removed_keepout=0.397`
- Longest zero-track streak: `frame 472-507 (36 frames)`
- Dominant issue: `ROI gate (6.54 avg removed/frame)`
- Change vs prev `20260318_215954`: parser fail `5 (+1 vs prev, worse)`, resync `62 (-16 vs prev, better)`, zero-track `139 (+121 vs prev, worse)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260318_225405.csv`
- Artifacts: experiment report `experiment_reports/2026-03-18/20260318_225405.md`

### 2026-03-18 / 20260318_215954
- Scenario: `baseline`
- Summary: FPS `9.247`, parser/pipe `0.853 / 15.563 ms`, raw->filtered `58.486 -> 17.425`, avg tracks `1.387`
- Parser health: `parse_fail=4, resync=78, dropped=45`
- Continuity: `zero_track=18/555`, `tracks>=2=189/555`
- Filtering: `removed_range=36.699`, `removed_roi=4.362`, `removed_keepout=0.0`
- Longest zero-track streak: `frame 195-196 (2 frames)`
- Dominant issue: `range gate (36.70 avg removed/frame)`
- Change vs prev `20260318_024048`: parser fail `4 (-14 vs prev, better)`, resync `78 (+77 vs prev, worse)`, zero-track `18 (-127 vs prev, better)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260318_215954.csv`
- Artifacts: experiment report `experiment_reports/2026-03-18/20260318_215954.md`

### 2026-03-18 / 20260318_024048
- Scenario: `live_run`
- Summary: FPS `9.362`, parser/pipe `2.026 / 12.727 ms`, raw->filtered `15.772 -> 9.217`, avg tracks `0.591`
- Parser health: `parse_fail=18, resync=1, dropped=20`
- Continuity: `zero_track=145/281`, `tracks>=2=30/281`
- Filtering: `removed_range=0.164`, `removed_roi=4.861`, `removed_keepout=1.53`
- Longest zero-track streak: `frame 65-112 (48 frames)`
- Dominant issue: `ROI gate (4.86 avg removed/frame)`
- Change vs prev `20260318_014146`: parser fail `18 (+16 vs prev, worse)`, resync `1 (-31 vs prev, better)`, zero-track `145 (+35 vs prev, worse)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260318_024048.csv`
- Artifacts: experiment report `experiment_reports/2026-03-18/20260318_024048.md`

### 2026-03-18 / 20260318_014146
- Scenario: `live_run`
- Summary: FPS `9.031`, parser/pipe `2.111 / 20.779 ms`, raw->filtered `18.432 -> 8.306`, avg tracks `0.697`
- Parser health: `parse_fail=2, resync=32, dropped=29`
- Continuity: `zero_track=110/271`, `tracks>=2=28/271`
- Filtering: `removed_range=0.0`, `removed_roi=0.0`, `removed_keepout=10.125`
- Longest zero-track streak: `frame 99-112 (14 frames)`
- Dominant issue: `keepout (10.12 avg removed/frame)`
- Change vs prev `20260317_030731`: parser fail `2 (+2 vs prev, worse)`, resync `32 (+31 vs prev, worse)`, zero-track `110 (+102 vs prev, worse)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260318_014146.csv`
- Artifacts: experiment report `experiment_reports/2026-03-18/20260318_014146.md`

### 2026-03-17 / 20260317_030731
- Scenario: `live_run`
- Summary: FPS `9.23`, parser/pipe `2.399 / 20.108 ms`, raw->filtered `18.953 -> 18.953`, avg tracks `1.433`
- Parser health: `parse_fail=0, resync=1, dropped=23`
- Continuity: `zero_track=8/277`, `tracks>=2=110/277`
- Filtering: `removed_range=`, `removed_roi=`, `removed_keepout=`
- Longest zero-track streak: `frame 1-1 (1 frames)`
- Dominant issue: `multi-track split`
- Change vs prev `20260315_165830`: parser fail `0 (+0 vs prev, same)`, resync `1 (+0 vs prev, same)`, zero-track `8 (+7 vs prev, worse)`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260317_030731.csv`
- Artifacts: experiment report `experiment_reports/2026-03-17/20260317_030731.md`

### 2026-03-15 / 20260315_165830
- Scenario: `live_run`
- Summary: FPS `0.158`, parser/pipe `0.351 / 6311.448 ms`, raw->filtered `18.0 -> 18.0`, avg tracks `0.0`
- Parser health: `parse_fail=0, resync=1, dropped=115`
- Continuity: `zero_track=1/2`, `tracks>=2=0/2`
- Filtering: `removed_range=`, `removed_roi=`, `removed_keepout=`
- Longest zero-track streak: `frame 1-1 (1 frames)`
- Dominant issue: `zero-track continuity`
- Artifacts: frame CSV `../evidence/runtime_logs/frames_20260315_165830.csv`
- Artifacts: experiment report `experiment_reports/2026-03-15/20260315_165830.md`

## Reading Guide
- `Parser health`는 UART/parser 연속성 상태를 본다.
- `Continuity`는 사람이 실제로 지속적으로 track로 남는지 본다.
- `Filtering`은 range/ROI/keepout이 사람 점군을 얼마나 자르는지 본다.
- `Dominant issue`는 현재 run에서 가장 먼저 의심할 병목을 자동으로 요약한다.

- Generated at: `2026-03-19T02:48:24`
