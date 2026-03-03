# FMEA (Failure Mode and Effects Analysis)

| Component | Failure Mode | Effect | Detection | Mitigation |
|---|---|---|---|---|
| TLV parser | Packet header sync loss | Frame drop / parse error | Magic-word scan fail count | Resync window + discard corrupted frame |
| Noise filter | Over-filtering | Missed target | Recall drop in labeled replay | Adaptive threshold by range/SNR |
| DBSCAN | Under/over clustering | ID switch / split-merge errors | Cluster count anomaly | Tune `eps/min_samples` by scenario |
| Kalman tracker | Divergence after occlusion | Position jump | Innovation residual spike | Gating + track state reset |
| STM32 communication | UART congestion | Control latency increase | Tx queue depth, CRC fail rate | Rate limit + compact packet format |
