# Corpus sources

| File | Source | Licence |
|---|---|---|
| `manuals/RA-3_Service_Manual_EN.pdf` | Synthetic, written for this repo. Rendered from `src/RA-3_Service_Manual_EN.md` by `tools/build_manuals.py` | CC BY 4.0 |

The RA-3 robot arm and its manufacturer are fictional. Sensor baselines, alarm limits and fault
signatures are written to match `iiot-smart-factory-sim` (`simulator/config.py`,
`simulator/degradation.py`) so live-diagnosis answers can be checked against ground truth.

`private/` is git-ignored: drop your own PDFs there for local testing.
