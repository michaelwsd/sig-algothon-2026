# Strategy development progression

Each file is a complete, self-contained `getMyPosition(prcSoFar)`. They are numbered in the order they were
developed, and each one exists because the previous one taught us something. **The live submission is
`test_round/too_much_alpha.py`**, which is a byte-identical copy of the newest version here (`eval.py` imports
that module by name, so it must live in the round folder).

| Version | File | eval.py score (days 251-500) | Live leaderboard | What changed |
|---|---|---|---|---|
| v0 | `v0_naive_momentum.py` | 0.10 | — | The organisers' starter. Buys yesterday's winners. |
| v1 | `v1_leadlag_invvol.py` | 345.57 | 469.12 | Aggregated lead-lag on beta-hedged residuals, inverse-vol sized, ALGO hedge. |
| v2 | `v2_leadlag_reversal_bangbang.py` | 480.65 | 526.61 | Hysteresis band, bang-bang sizing at the exact cap, orthogonal reversal sleeve. Test-round best. |
| v3 | *(deleted)* | 495.26 | **503.38 — worse** | Dollar-weighted ridge. Beat v2 on every offline test, **lost live**. Reverted and removed. |
| v4 | `v4_leadlag_reversal_rev015.py` | 489.92 | **841.13 (751-1000)** | v2 with reversal weight 0.25 → 0.15. First general-round submission (SUB-BFF1CA1C). Live 841.13 revealed the 751-1000 window is *more predictable* than 501-750 (same strategy: 554 → 841). |
| v5 | `v5_leadlag_multirev.py` | 518.11 | **671.85 (751-1000)** | Multi-horizon reversal [20,60] at weight 0.25. Dominated v2/v4 on EVERY offline window (eval[501-750] 606 vs 554) but **LOST live (671.85 vs v4's 841.13)**. Third offline-validated change to lose live. The reversal sleeve is anti-predictive between adjacent windows. |
| **v6** | **`v6_leadlag_pure.py`** | 457.29 | *staged (general round)* | **STAGED.** v2 with the reversal sleeve REMOVED (rev_w=0) — pure lead-lag. Two live results (v4 rev0.15→841, v5 rev0.25→672) show *less reversal → higher live*; a linearly-blended anti-predictive sleeve is optimised at weight 0. eval[501-750] 556.78 (offline is anti-predictive for reversal, so ignore it). Bet: live > v4's 841. |

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

**v2 → v3: a validated offline gain that FAILED live (the key lesson).**
v2 scored 526.61 live. Chasing the leader, v3 changed the estimator to target dollars rather than IC: a ridge
predictor `B = (X'X/n + lam I)^-1 (X'Y/n)` with a *raw* (dollar-weighted) target instead of the standardised
one, so the fit focuses on high-volatility, high-dollar-impact names. It beat v2 on **every** offline test
(frozen 389.4 vs 355.7, dense holdout 484.2 vs 460.8, eval 495.3 vs 480.65).

Then it scored **503.38 live — worse than v2's 526.61.** So we reverted to v2 and deleted the v3 files. The
lesson, which now governs the whole project: our offline validation is drawn from the same 500 days we hold, so
it is a *proxy* for out-of-sample, not the real thing. A ~5-10% offline improvement is not enough to ship over a
strategy with a proven live score. The dead-end verdicts (dollar-ridge, pairs, sector-neutralisation, dual
reversal) are recorded in the "Things that FAILED" table in `CLAUDE.md`; the engines themselves were removed in
the cleanup.

## Layout

```
strategies/
  v0_naive_momentum.py             the starter (recovered from git 937a1ac); eval 0.10
  v1_leadlag_invvol.py             scored 469.12 live
  v2_leadlag_reversal_bangbang.py  scored 526.61 live  <- LIVE (best); mirrored into test_round/
  engines/
    leadlag_invvol_engine.py             v1 research engine (beta_shrink, sector_k, rank, est_window, scale_mode)
    leadlag_reversal_bangbang_engine.py  v2 research engine (exact_cap, band, rev_w, util, lag2_w, algo_lead)
```

The **engines** are research tools, not submissions. Only the v1 and v2 engines are kept (they map to live
strategies). The v3-round experiments (dollar-ridge, pairs, sector-neutralisation, dual-reversal) were tried,
failed, and deleted in a cleanup; their verdicts are preserved in the "Things that FAILED" table in `CLAUDE.md`
so they are not rebuilt from scratch.

## Keeping the live submission in sync

`test_round/too_much_alpha.py` must stay byte-identical to the live strategy here. Check it:

```bash
diff strategies/v2_leadlag_reversal_bangbang.py test_round/too_much_alpha.py && echo "in sync"
```

## Starting a new round

Copy the LIVE strategy (`v2_leadlag_reversal_bangbang.py`) into the new round folder as `too_much_alpha.py`,
score it **once** on the new data before touching anything, and record that number. It is the honest
out-of-sample test the whole project has been building toward. Only then iterate, and add the result as a new
`v3_*.py` here — **and only promote it over v2 if a live/data-drop result confirms it, given what happened with
the first v3.**
