# Keras → TFLite parity report

| Check | Value |
| --- | --- |
| Keras source | `ml/artifacts_v3/agrishield_model.keras` |
| TFLite file | `mobile/assets/model/agrishield_model.tflite` |
| TFLite size | 4,611,780 bytes (4.61 MB) |
| Input | [1, 128, 128, 3] float32 |
| Output | [1, 38] float32 |
| Output classes vs labels | 38 vs 38 |
| Parity images | 400 |
| Top-1 agreement | **0.9975** (required ≥ 0.99) |
| Max probability difference | 0.02074 |
| Input sensitivity | 0.28116 |
| Single-image CPU latency | 2.3 ms |
| Result | **PASS** |

Mismatches on 1 image(s).

| Image | Keras | TFLite |
| --- | --- | --- |
| /tmp/agrishield_v3/test/potato_late_blight/plantvillage_08fc6763cb65.jpg | `potato_late_blight` | `soybean_healthy` |
