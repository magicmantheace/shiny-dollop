# Developmental Agent: learning and memory prototype

A small, *real, runnable* proof of concept of a persistent, self-improving artificial organism. Python standard library only, so it runs on Windows 11, WSL, Linux, and ordinary CPUs. It is **not** a fruit-fly brain emulator, general AI, or evidence of consciousness.

## What it does

- **Senses:** its own (x, y) location and a signal identifying one of two available food sites.
- **Acts:** moves north/south/east/west, or attempts to eat. No route is programmed into its policy.
- **Has drives:** externally defined food reward, avoidance of dangerous tiles, and an internal novelty bonus that encourages exploration of unfamiliar states.
- **Learns:** Q-learning updates its action values based on experience, reward, and predicted future return. It chooses increasingly reliable behaviors through practice.
- **Remembers:** SQLite database stores episodic significant events, generalized semantic landmarks (discovered hazards/food sites), procedural Q values, and visitation counts. All persist across restarts.
- **Evaluates:** deterministic, non-learning testing makes improvement measurable. Both food destinations must be learned.

The environment's geometry, goals, penalties, and available actions are deliberately constrained. The behaviors are **learned within those rules**, not spontaneously invented out of nothing. This is a foundation for more capable agents, not humanlike independence.

## Run

From this directory, Python 3.10+:

```bash
python organism.py evaluate --episodes 200 --db brain.db
python organism.py train --episodes 3000 --db brain.db
python organism.py remember --last 12 --db brain.db
python organism.py watch --goal 0 --db brain.db
python organism.py watch --goal 1 --db brain.db
python organism.py evaluate --episodes 200 --db brain.db
python -m unittest -v test_organism.py
```

A bundled `demo_brain.db` contains a **synthetically trained** example for immediate inspection (use `--db demo_brain.db`). Start with `brain.db` to see an untrained mind learn from scratch. Train again using the same `brain.db` to continue from prior experiences. For a fresh learner, choose a new `--db` filename. `evaluate` does not change the persistent skills or memories.

## Learning systems

| System | Prototype | Expansion |
| --- | --- | --- |
| Sensory | Location + food signal | Vision/audio/computer signals |
| Reinforcement | Q-table | RL policy with recurrent network |
| Curiosity | Novelty bonus | Prediction error / learning progress |
| Episodic memory | SQLite events + episodes | Context-rich retrieval and causal summaries |
| Semantic memory | Learned risk/food landmarks | Provenance-scored knowledge graph |
| Procedural memory | Saved Q-values | Reusable skills and learned policies |
| Consolidation | Persistent atomic checkpoints | Offline replay and regression evaluation |
| Safety boundaries | Simulation-only actions | Approval-gated real-world tool execution |

## What to measure

Success rate before/after training; steps to food; penalty avoidance; retention after process restart; training transfer to unseen environments. The first four are directly measurable in this prototype; **transfer to unseen environments is not yet implemented**.

## Design note

For a larger project such as AthenZ, this could become a separately tested development sandbox: experiments and learning updates earn promotion into production only after passing repeatable evaluations. Do **not** add an unrestricted action executor or write private experiences to a public repository. Keep any `.db` file out of Git.
