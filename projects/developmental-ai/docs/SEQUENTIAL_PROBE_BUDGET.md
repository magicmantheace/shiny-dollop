# Sequential offline calibration with harmful-probe accounting

**Post-hoc synthetic experiment; NOT deployment or safe real-world probing.**

The earlier [public-outcome reversal calibration](OBSERVABLE_REVERSAL_CALIBRATION.md)
used 12 disposable one-step calibration episodes for each world and seed,
correctly selected between two *already trained* numeric outcome models,
and completed 360/360 normal/reversed test tasks on each rule. But 56/144
calibration probes caused damage; wrong calibration failed 720/720 tasks.

The separate frozen-before-code
[sequential budget protocol](../benchmarks/sequential_probe_protocol.json)
keeps the original models and seed groups and asks whether stopping
as soon as the **original confidence threshold** is met reduces
damaging calibration interventions without losing test accuracy.

- Models: normal source collect `train/0..79`; reversed rule
  `train/300..379`. No new test exposure when fitting.
- Calibrations: `train/900..911`. Original fixed12, adaptive
  stopping after at least 4 and original log margin >=2, and
  forced four-probe control. Each action harm counts against the
  actual method.
- Negative stale-calibration controls: first four calibration
  episodes use normal physics, later ones use reversed physics,
  with reversed physics at held-out evaluation. The runtime
  selector sees only public numeric action features and outcomes,
  never the hidden domain.
- Test `test/15000..15059` in normal/reversed target worlds,
  60 episodes per seed and group (71001/71013/71031 and
  81001/81013/81031, **all previously inspected**).
- Equal-input learning models and replay/immutability safeguards;
  compare abstention and unequal privileged oracle.
- Outcomes: task success, tested damage, probes used, harms during
  disposable calibration, stale-interval errors and selection decisions.

An early-stop method might reduce probe harms but can select a stale
model before a real change. Calibration cannot be assumed valid
forever; the observed synthetic examples are not permission to
experiment on people, files, OS settings or external applications.

```sh
python -m unittest tests.test_sequential_probe -v
python -m benchmarks.sequential_probe_benchmark --cohort development
python -m benchmarks.sequential_probe_benchmark --cohort inspected-additional
```
