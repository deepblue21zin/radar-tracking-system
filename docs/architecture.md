# Radar Tracking System Architecture

## Pipeline
1. `tlv_parse_runner.py` keeps the legacy runtime entrypoint for commands and imports.
2. `runtime_pipeline.py` performs cfg send, UART buffering, TLV frame parsing, filtering, DBSCAN, tracking, control, and runtime logging.
3. `live_rail_viewer.py` reuses the same reader/filter/cluster defaults for 3D inspection.
4. Shared defaults are loaded from `config/runtime_params.json` through `src/runtime_params.py`.

## Modules
- `src/parser`
  - `tlv_packet_parser.py`: low-level TLV header and payload decode
  - `runtime_pipeline.py`: real runtime implementation
  - `tlv_parse_runner.py`: compatibility wrapper
- `src/runtime_params.py`: JSON runtime param loading and validation
- `config/runtime_params.json`: shared filter/DBSCAN/tracking/control/viewer defaults
- `src/filter`: point-level and frame-level denoising
- `src/cluster`: DBSCAN clustering
- `src/tracking`: Kalman tracking lifecycle
- `src/control`: proximity-based speed control decision
- `src/communication`: Python-to-STM32 control packet encoding / examples
- `src/visualization`: 3D inspection viewer

## Data Contracts
- Input frame: timestamp + point cloud (x, y, z, doppler, snr).
- Parsed frame: `frame_number`, `num_obj`, `points`, `packet_bytes`, `num_tlv`, `parser_latency_ms`.
- Cluster: `x`, `y`, `z`, `v`, `size`, `confidence`, `spread_xy`, `mean_snr`.
- Output track: `track_id`, position, velocity, confidence, lifecycle counters.
- Optional control output: command, speed ratio, event, zone distance, closing speed.
