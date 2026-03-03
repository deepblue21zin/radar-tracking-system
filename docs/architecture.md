# Radar Tracking System Architecture

## Pipeline
1. TLV parser ingests UART binary stream from radar in real time.
2. Noise filter removes static clutter and outliers.
3. Tracking stage clusters points (DBSCAN) and estimates states (Kalman).
4. Communication stage sends tracked targets to STM32.

## Modules
- `src/parser`: real-time UART reader (`tlv_parse_runner.py`) + packet decoder (`tlv_packet_parser.py`).
- `src/filter`: point-level and frame-level denoising.
- `src/tracking`: clustering and tracking lifecycle.
- `src/communication`: UART protocol and packet sender.

## Data Contracts
- Input frame: timestamp + point cloud (x, y, z, doppler, snr).
- Output track: track_id, position, velocity, confidence.
