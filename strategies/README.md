# Strategy development progression

Each file is a complete, self-contained `getMyPosition(prcSoFar)`. They are numbered in the order they were
developed, and each one exists because the previous one taught us something. **The live submission is
`test_round/too_much_alpha.py`**, which is a byte-identical copy of the newest version here (`eval.py` imports
that module by name, so it must live in the round folder).

| Version | File | eval.py score (days 251-500) | Live leaderboard | What changed |
|---|---|---|---|---|
| v0 | `v0_naive_momentum.py` | 0.10 | — | The organisers' starter. Buys yesterday's winners. |
| v1 | `v1_leadlag_invvol.py` | 345.57 | **469.12** (9th) | Aggregated lead-lag on beta-hedged residuals, inverse-vol sized, ALGO hedge. |
| v2 | `v2_leadlag_reversal_bangbang.py` | **480.65** | not yet scored | Hysteresis band, bang-bang sizing at the exact cap, orthogonal reversal sleeve. |

## The progression, and why each step happened

**v0 → v1: the obvious idea is a strawman.**
The starter trades an instrument's own momentum. The stability audit kills it: own-return lag-1 autocorrelation
has a split-half stability of **+0.072**, and drift **-0.034**. The instruments that *look* like they trend do
not do it again in the other half of the data. If an instrument's own past cannot predict it, the only place
left to look is *other instruments' pasts*. That is the lead-lag matrix
`L[i,j] = corr(resid_i[t], resid_j[t+1])`, whose whole-matrix split-half stability is **+0.110** — weak per
entry, but real, and it pays through breadth (`IR ≈ IC · sqrt(breadth)`).

**v1 → v2: the leaderboard taught us the objective.**
v1 scored 469.12 live with the **highest Sharpe (6.69) and the lowest volatility (1133) on the board**. That is
not a virtue here. The score's tax factor `frac = sr²/(sr²+1)` is saturated above Sharpe ≈ 5: we kept 97.8% of
our profit, the leader kept 96.5%. So an extra point of Sharpe was worth under 2% of score, while an extra
dollar of profit was worth ~98 cents.

> **score ≈ mu.** We had optimised risk-adjusted return in a competition that pays for dollar profit.

Everything in v2 follows:

1. **Hysteresis band (biggest gain).** Only flip a position's sign when the signal is convincing. Eval-window
   mean P&L: $397 → $500. Far more than the ~$10/day of commission it saves, so the mechanism is not cost —
   the sticky position appears to capture multi-day persistence. *This is the least-understood part of the
   strategy; see the open questions in `CLAUDE.md`.*
2. **Bang-bang sizing.** Maximising `mu = Σ dᵢ·E[rᵢ]` subject to `|dᵢ| ≤ cap` is a linear programme, solved by
   `dᵢ = cap · sign(predᵢ)`. Inverse-vol sizing is mean-variance optimal — a *different* objective. Only the
   sign of the prediction now matters.
3. **The exact cap.** v1's `TARGET_FRAC = 0.95` was a bug: `eval.py` clips at the same price we size on, so no
   headroom is needed. Verified 0 involuntary trims in 12,750 checks. Free 5% of the book.
4. **Reversal sleeve at weight 0.25**, which is the IC-optimal blend `IC_rev/(IC_ll + IC_rev) = 0.257` for
   orthogonal signals. Theory and the empirical plateau agree.

## Layout

```
strategies/
  v0_naive_momentum.py             the starter (recovered from git 937a1ac)
  v1_leadlag_invvol.py             scored 469.12 live
  v2_leadlag_reversal_bangbang.py  current; mirrored into test_round/
  engines/
    v1_engine.py    configurable LeadLag: beta_shrink, sector_k, rank, est_window, scale_mode
    v2_engine.py    configurable Engine:  exact_cap, band, rev_w, util, lag2_w, algo_lead, shrink
```

The **engines** are research tools, not submissions. They expose every knob we tested — including the ones
that failed — so a future session can re-verify a dead end rather than rediscover it. The failure table lives
in `CLAUDE.md`.

## Keeping the live submission in sync

`test_round/too_much_alpha.py` must stay byte-identical to the newest strategy here. Check it:

```bash
diff strategies/v2_leadlag_reversal_bangbang.py test_round/too_much_alpha.py && echo "in sync"
```

## Starting a new round

Copy the newest strategy into the new round folder as `too_much_alpha.py`, score it **once** on the new data
before touching anything, and record that number. It is the honest out-of-sample test the whole project has
been building toward. Only then start iterating, and add the result as a new `v3_*.py` here.
