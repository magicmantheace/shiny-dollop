# Local learning experiment — 13 October 2026

Run with Python standard library, random seed 7, 3,000 episodes, a 6×6 grid, two visible food locations and three hazardous cells, 50-step maximum per episode.

The policy starts with **zero** manually entered routes or action values. The agent has a small set of hard-coded sensor and action types, food and safety rewards, plus a curiosity reward. It does not learn from unrestricted natural-language interaction.

## Measured results

| Metric | Untrained (greedy, 200 evaluation episodes) | Trained (greedy, 200 evaluation episodes) |
| --- | ---: | ---: |
| Food retrieval success | 4% | 100% |
| Mean steps per episode | 49.3 | 8.5 |
| Mean external return | -16.83 | +9.66 |
| Site 0 success | 4% | 100% |
| Site 1 success | 4% | 100% |

- The learned path reaches food in the theoretical minimum number of actions for both sites (8 and 9 respectively).
- Persistent SQLite memory logged 3,000 episodes, 2,912 training successes, discovered food locations and hazards, visitation counts, and 360 learned state/action values.
- The model was reopened from the SQLite file and a separate evaluation confirmed the same greedy success rate.
- Five unit tests cover outcomes, learned improvement, persistence, and read-only inspection.

## Limitations

These are **in-sample** results from a deliberately small, fixed world with a visible goal signal. They do **not** demonstrate general intelligence, lifelong skill transfer, invention of new primitive actions, conversational understanding, or biological brain emulation. To test genuine adaptation, the next experiment should randomize obstacle patterns, food locations, and sensory signals and measure held-out transfer across environments.
