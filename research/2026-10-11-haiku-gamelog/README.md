# Haiku 5.5 executor with vs without the game log (offline, judged)

`python3 research/executor_ab.py --a haiku --b haiku+log --n 70 --judge 90 --transport api --out research/2026-10-11-haiku-gamelog`

- 210 logged decisions (411 answered questions) from the three Obeka validation runs. Each decision's
  round-by-round digest (edhkit/gamelog.py) was rebuilt from the earlier logged states of its game.
- Agreement 351/411 (85%). That is about Haiku's own run-to-run variation (effort low vs medium agreed
  59/66, 89%), so most of the 60 disagreements are probably noise rather than the log.
- Blind Opus judge (memo hidden, digest shown for both answers): **with log 25, without 26, same 9** (p = 1.0).
  No measurable effect on single decisions.
- Cost: 420 API calls, $0.49 in total (1.78M of 4.3M input tokens were cache reads). The log added ~0.9 s
  median latency (4.6 -> 5.5 s).

Decision: the paired games test Jev vs Haiku without the log, one variable at a time. The log stays available
(`--game-log`) for a later whole-game test, where politics and long plans could matter more than single choices.
