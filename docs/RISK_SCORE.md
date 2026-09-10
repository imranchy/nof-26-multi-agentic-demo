# Failure-prone risk in NoF v1

The dashboard's **Failure-prone risk** is not a manually assigned confidence score.

The SLA-state surrogate was trained from simulator-derived network-state labels. In `scripts/train_classifier.py`, the simulator's fresh-traffic blocking ratio is calculated for each training interval:

- blocking ratio = 0 -> `normal`
- blocking ratio > 0 and <= the learned positive-blocking threshold -> `degraded`
- blocking ratio > the threshold -> `failure_prone`

For the frozen model shipped in this repository, `models/sla_random_forest.metadata.json` records the learned failure threshold. The displayed Failure-prone risk is the trained classifier's probability for the `failure_prone` class at the queried timestamp.

This means the risk score is **learned from the simulator scenario and its assumptions**. It is not a calibrated production failure probability and must not be interpreted as physical-layer fault probability. The v1 UI therefore shows only:

- predicted SLA state
- Failure-prone risk

A separate generic classifier-confidence score is intentionally not displayed.
