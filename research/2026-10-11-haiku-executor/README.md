# Haiku 5.5 vs Jev as the pilot's executor (offline, judged)

`python3 research/executor_ab.py --n 70 --judge 90 --out research/2026-10-11-haiku-executor`

- 210 logged decisions (70 from each Obeka validation run: Many Mornings r1, Long Morning r3, Twice-Told r4),
  423 answered questions. Both executors answered through the same sidecar (board, memo, plan tags and gates).
  Only the provider differed. Haiku ran at effort medium through `claude -p`.
- Agreement: 316/423 final answers (75%), 309/422 raw picks.
- Blind Opus judge (memo hidden, random A/B order) on 90 of the 107 disagreements: **Haiku better 52, Jev better
  20, same 18** (72% of decided, sign test p = 0.0002).
  - When both play something but different things (target, which spell, which bounce): Haiku 46, Jev 16, same 18.
  - When Haiku acts and Jev passes: Haiku 6, Jev 4. That's no clear signal; Jev's wins there were held
    counters and saved Rifts.
- Latency: median 10.3 s per decision for Haiku via the CLI vs 0.3 s for Jev. Most of that is starting the
  CLI process; the direct API with prompt caching would be much faster, but that hasn't been measured.

Caveats: the judge is a Claude model, like Haiku, so a family bias toward Claude-style reasoning can't be ruled
out. Jev is a different model. These are single decisions, not games, and Haiku's self-reported probabilities
pass through gates tuned on Jev's calibrated ones.
