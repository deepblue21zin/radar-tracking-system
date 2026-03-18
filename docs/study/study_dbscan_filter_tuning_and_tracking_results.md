# DBSCAN / Filter / Tracking / Control Tuning Study

## 1. Purpose

This note summarizes the tuning work performed between 2026-03-18 and 2026-03-19 for:

- radar point filtering
- adaptive DBSCAN clustering
- tracker continuity
- representative target selection for control
- control-oriented measurement logging

The goal is to record:

- what was changed
- why it was changed
- how the logs changed
- how much the pipeline improved
- what remains to be done

---

## 2. Main Code Changes

### 2.1 `src/cluster/dbscan_cluster.py`

The clustering module was upgraded from a single fixed-`eps` DBSCAN to range-band adaptive DBSCAN.

Main additions:

- `dbscan_adaptive_eps_bands`
- separate `eps` values for near and far range bands
- boundary merge logic to reduce split clusters near band boundaries
- extra cluster metadata:
  - `range_band`
  - `eps_used`
  - `min_samples_used`
  - `boundary_merged`

Current default bands:

```json
[
  { "r_min": 0.0, "r_max": 1.4, "eps": 0.22 },
  { "r_min": 1.4, "r_max": null, "eps": 0.50 }
]
```

### 2.2 `config/runtime_params.json` and `src/runtime_params.py`

Shared runtime defaults were tuned repeatedly to fit the actual logs.

Current baseline values:

```json
{
  "snr_threshold": 110.0,
  "max_range": 3.5,
  "dbscan_min_samples": 2,
  "dbscan_adaptive_eps_bands": [
    { "r_min": 0.0, "r_max": 1.4, "eps": 0.22 },
    { "r_min": 1.4, "r_max": null, "eps": 0.50 }
  ],
  "right_rail_padding": 0.05,
  "report_miss_tolerance": 2,
  "measurement_target_lock_frames": 12,
  "measurement_target_reacquire_gate": 0.9,
  "measurement_target_max_abs_x": 1.25,
  "control_target_lock_frames": 6
}
```

### 2.3 `src/parser/runtime_pipeline.py`

The runtime pipeline was extended with richer target summaries and new representative-target logic.

Added logging groups:

- `primary_cluster_*`
- `primary_track_*`
- `persistent_track_*`
- `measurement_target_*`
- `control_target_*`

Important pipeline change:

```text
tracks
  -> measurement target selection
  -> control input / control target
```

Control is no longer driven only by "nearest track". It now uses a separately selected measurement target.

### 2.4 `src/control/proximity_speed_control.py`

The control module was extended with target lock behavior.

Main additions:

- `target_lock_frames`
- lock persistence across frames
- selected target position fields in `ControlDecision`

---

## 3. Parameter Roles and Observed Effects

### 3.1 `snr_threshold`

Role:

- removes low-SNR points

Observed effect:

- too low: too much noise remains
- too high: valid points are lost

Observed results:

- `120` was too aggressive
- `115` was still too aggressive
- `110` gave the best balance in recent runs

### 3.2 `max_range`

Role:

- upper bound of range filtering

Observed effect:

- too low: far target points are removed before clustering
- higher values help far tracking, but may also admit more clutter

Observed results:

- `3.0` made far-range tracking fragile
- `3.5` improved `measurement_target_y` and `measurement_target_range_m` maxima

### 3.3 `dbscan_min_samples`

Role:

- minimum number of points required to form a cluster

Observed effect:

- larger values break far-range clusters more often
- smaller values allow sparse clusters to survive

Observed results:

- `3` was too strict in far range
- `2` improved continuity and reduced empty-track frames

### 3.4 `dbscan_adaptive_eps_bands`

Role:

- applies different DBSCAN `eps` values to different range bands

Observed effect:

- near band reduces over-merge
- far band helps sparse far-range points stay clustered

Observed results:

- near `0.22` stayed stable
- far `0.45 -> 0.50` improved far-range retention

### 3.5 `right_rail_padding`

Role:

- expands or shrinks right-rail keepout filtering

Observed effect:

- too large: valid points are removed together with clutter

Observed results:

- `0.15` was too aggressive
- `0.05` restored filtered points, clusters, and tracks

### 3.6 `report_miss_tolerance`

Role:

- allows a track to remain visible for a few missed frames

Observed effect:

- short dropouts no longer remove tracks immediately

Observed results:

- `0 -> 2` noticeably improved continuity

### 3.7 `measurement_target_*`

Role:

- chooses a representative measurement target for both analysis and control

Current parameters:

- `measurement_target_lock_frames = 12`
- `measurement_target_reacquire_gate = 0.9`
- `measurement_target_max_abs_x = 1.25`

Intent:

- keep the same target across short gaps
- reacquire near the last known position
- reduce the chance of selecting a target that is too far off the forward axis

---

## 4. Log Trend Summary

### 4.1 2026-03-18

| run | main condition | avg_filtered_points | avg_clusters | avg_tracks | interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| `213244` | early state | 30.013 | 3.488 | 3.430 | one person often split into 3+ clusters |
| `215412` | `snr_threshold=120` | 11.753 | 2.131 | 2.077 | fewer clusters, but too many valid points removed |
| `221238` | near-front keepout disabled | 5.365 | 0.674 | 0.607 | overall detection collapsed |
| `222225` | `snr_threshold=110`, `right_rail_padding=0.05` | 13.435 | 1.820 | 1.737 | best balance on 2026-03-18 |
| `223049` | `snr_threshold=115` | 9.113 | 1.064 | 0.968 | again too aggressive |
| `225536` | `primary_*` logging added | 8.412 | 1.255 | 1.207 | distance trend visible, but `primary_track` not representative enough |

### 4.2 2026-03-19

| run | main change | avg_filtered_points | avg_clusters | avg_tracks | zero_track_frames | interpretation |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `003440` | baseline before new representative target logic | 13.668 | 2.012 | 2.828 | 2 | many tracks available, but representative value was misleading |
| `011052` | compare `persistent_track` vs `control_target` | 11.090 | 1.630 | 2.193 | 2 | `persistent` and `control` were more stable than `primary` |
| `013947` | `measurement_target` introduced | 4.882 | 0.722 | 0.997 | 132 | representative range improved, but detection became sparse |
| `015607` | `max_range = 3.5` | 4.668 | 0.695 | 0.858 | 148 | larger far-range maxima, but many gaps remained |
| `020457` | `dbscan_min_samples = 2` | 4.567 | 0.900 | 1.119 | 66 | continuity improved significantly |
| `021928` | `measurement_target_max_abs_x = 1.25` soft preference | 4.126 | 0.776 | 0.971 | 99 | slight gain in max `y`, but weaker continuity |
| `022853` | far `eps 0.45 -> 0.50` | 4.877 | 0.969 | 1.173 | 38 | best recent balance for far-range retention and continuity |

---

## 5. Representative Target Selection Comparison

### 5.1 `primary_track`

Strength:

- simple

Problem:

- often selects only the nearest target
- frequently under-represented the real `0.5m ~ 3m` walking distance

Conclusion:

- not suitable as the main control input

### 5.2 `persistent_track`

Strength:

- useful for continuity analysis
- often more stable than `primary_track`

Problem:

- may keep an old or less relevant track alive
- not always the best control target

### 5.3 `control_target`

Strength:

- directly reflects what control uses
- more stable due to lock behavior

Problem:

- if measurement selection is wrong, control target also becomes wrong

### 5.4 `measurement_target`

Strength:

- designed to serve both analysis and control
- uses lock, reacquire, and x-bias rules

Current judgment:

- much better than `primary_track`
- the right place to feed the control stage

---

## 6. Current Log Interpretation

The most meaningful recent control-oriented log is:

- [frames_20260319_022853.log](/c:/Users/sy201/U/4-1/C/radar-tracking-system/evidence/runtime_logs/frames_20260319_022853.log)
- [frames_20260319_022853.csv](/c:/Users/sy201/U/4-1/C/radar-tracking-system/evidence/runtime_logs/frames_20260319_022853.csv)

Key values:

- `avg_tracks = 1.173`
- `zero_track_frames = 38`
- `measurement_rows = 549`
- `measurement_y_max = 3.307`
- `measurement_range_max = 3.688`

Far-range retention:

- `filtered_range_max >= 2.0m`: 245 frames, measurement present in 237
- `>= 2.5m`: 161 frames, measurement present in 153
- `>= 3.0m`: 82 frames, measurement present in 74

Meaning:

- the `2m ~ 3m` band is now retained most of the time
- the far range is no longer collapsing as often as before
- the latest setup is the most promising recent state for control-oriented use

Remaining issues:

- `measurement_id_switches = 27`
- `parse_failures = 15`
- `dropped_frames_estimate = 16`
- some selected targets still have large `x` offsets

---

## 7. Current Assessment

### 7.1 Object Estimation

- forward/backward distance change is clearly detectable
- repeated `0.5m ~ 3m` walking trends can be observed in logs
- this is still not a perfect one-person one-track trajectory system

### 7.2 Control Input Readiness

- the system is approaching usable quality for `slow / stop / resume` demos
- measurement/control targets now survive far range much better than before

### 7.3 Limitations

- parse failures and dropped frames still hurt continuity
- track ID switching still exists
- some representative targets are still too far off-axis
- this is not yet safety-grade control

Summary:

- demo / capstone control input: plausible
- robust prototype control: close, but more validation needed
- safety-critical control: not ready

---

## 8. Recommended Baseline

Current recommended baseline:

```json
{
  "snr_threshold": 110.0,
  "max_range": 3.5,
  "dbscan_min_samples": 2,
  "dbscan_adaptive_eps_bands": [
    { "r_min": 0.0, "r_max": 1.4, "eps": 0.22 },
    { "r_min": 1.4, "r_max": null, "eps": 0.50 }
  ],
  "right_rail_padding": 0.05,
  "report_miss_tolerance": 2,
  "measurement_target_lock_frames": 12,
  "measurement_target_reacquire_gate": 0.9,
  "measurement_target_max_abs_x": 1.25,
  "control_target_lock_frames": 6
}
```

---

## 9. Next Work

### 9.1 Priority 1: parse / serial stability

Reason:

- recent logs still show `parse_failures` and dropped frames

Needed work:

- check cable and serial stability
- inspect whether drops cluster around specific periods

### 9.2 Priority 2: stronger x-bias for measurement target

Reason:

- some representative targets still drift too far laterally

Needed work:

- test tighter `measurement_target_max_abs_x`
- consider moving from soft preference toward a harder gate

### 9.3 Priority 3: conveyor control threshold validation

Reason:

- detection quality is now improving, so the next step is actual belt behavior

Needed work:

- validate `slow_distance`, `stop_distance`, and `resume_distance`
- check for over-sensitive slowing or stopping

### 9.4 Priority 4: reporting and presentation summary

Recommended metrics to show:

- `measurement_target_y`
- `measurement_target_range_m`
- `zero_track_frames`
- measurement coverage rate in `2m+` bands

---

## 10. Final Summary

The tuning process followed this sequence:

1. reduce over-filtering and under-filtering
2. add adaptive DBSCAN
3. improve far-range cluster/track survival with `max_range`, `dbscan_min_samples`, and far `eps`
4. replace `primary_track` with `measurement_target` as the main representative value
5. connect control logic to the measurement target path

Current conclusion:

- object estimation quality has improved to a meaningful level
- the system is now reasonably promising for approach-based conveyor control demos
- the main remaining bottlenecks are continuity, parse stability, and off-axis representative target selection

