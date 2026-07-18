# Algothon 2026 — Project Guide

Working repo for the **Susquehanna x UNSW FinTech Society Algothon 2026** (7th year). Rules source of
truth: <https://wiki.algothon.au/>. This file captures what we've established so future sessions continue
smoothly.

## How to work with me (IMPORTANT — read first)

**I am learning by building this myself. Teach me; do not build it for me.**
- Explain every decision and the *why* behind it, in the context of this specific competition.
- When code is needed, tell me what to write and let me write it — walk me through it, don't hand me a
  finished file. (A prior session drafted a full notebook; that was reverted at my request.)
- Go step by step and pause for me to run things and report back.
- Render math in plain text / code blocks, NOT LaTeX (`$$...$$` doesn't render in my terminal).
  *(Exception: LaTeX is fine inside `analysis.ipynb`, since Jupyter renders it.)*
- Prefer logical derivations over asserted facts — when I don't get something, prove it from first
  principles.
- Don't make any assumptions — always ask for clarification.

> Note: some recent sessions were explicitly run in "build it, but explain as you go" mode at my request.
> That was a temporary override, not a change to the rule above.

## The competition in one paragraph

Implement `getMyPosition(prcSoFar)` in `too_much_alpha.py` (our submission file; `eval.py` imports it).
Each day it receives price history as a NumPy array shaped **(51 instruments, days-so-far)** and must return
a length-51 vector of **integer share positions** (the total desired holding, long or short, per instrument).
The organizers replay this over a hidden window and rank you on a score. There are **2,000 days of simulated
data total**, released in stages; you always get an earlier slice and are graded on the *next, unseen*
250-day window. Right now: we have days 1-500; the leaderboard scores hidden days 501-750.

**The governing fact:** you are always scored on days you have never seen. A result that looks good on the
500 days we have is worthless unless it reflects a *stable property of the data generator* rather than a
fluke of this sample. Every idea must pass a stability test (does the first half of the data predict the
second half?) before we trust it.

## Timeline (2026)

- Jul 8 — launch, test dataset (500 days) released
- Jul 16 — General Round dataset (likely reveals days 501-750)
- Jul 30 — General Round closes
- Aug 3 — finalists announced + finalist dataset
- Aug 10 — Finalist Round closes
- Aug 13 — Finals at SIG Sydney. **Judged 50% quantitative score / 50% technical presentation** — so
  document the research process as we go; half the grade is the story.

## Current status (as of the latest session)

**LIVE SUBMISSION = v2** (`too_much_alpha.py`). It has the best live score, 526.61. v3 was tried and
reverted (it beat v2 offline but lost live — see "v3 tried and reverted" below). Official `eval.py` on
days 251-500:

| Measure | v1 (scored 469.12 live) | **v2 (LIVE, 526.61)** |
|---|---|---|
| Score | 345.57 | **480.65** |
| Mean daily P&L | $359.58 | **$500.51** |
| Annualised Sharpe | 4.97 | 4.92 |
| Dollar volume | $111.9M | $103.2M |
| Runtime, 250 calls | 0.05s | 0.04s (limit 600s) |

Honest out-of-sample evidence for v2 (see "Validation protocol"):

- **Holdout** (days 350-500, never used to choose anything): mean 463.6, min 371.7, 100% of windows positive.
- **Frozen** (lead-lag matrix fit on days 1-250, trade 251-500, never refit): score 355.7, SR 3.73.
  **Quote this one** as the conservative expectation, not 480.7.
- **Placebo, random signal + identical machinery:** -234.3. **Placebo, random `L` but the REAL reversal
  sleeve:** -32.8. Both *lose money* ⇒ no look-ahead leak, and the lead-lag matrix (not reversal) is what
  carries the strategy.

## GENERAL ROUND (Jul 16 data drop, days 1-750) — the honest OOS test, and a strategic reframe

The Jul 16 drop appended **days 501-750** (the exact window we were scored on live). Days 1-500 are
byte-identical to the test-round file (verified, max abs diff 0.0). `eval.py`/rules **unchanged** (only the
import name differs). Now scored on hidden **751-1000**. Repo: `general_round/` mirrors `test_round/`.

**v2 reproduces live to the cent.** `cd general_round && python eval.py` (v2, unmodified, days 501-750):
**Score 526.61, mu 542.6, sigma 1492.85, Sharpe 5.75** — byte-for-byte our test-round LIVE number. So the
backtester = live reality, and 501-750 is now a real, fresh, never-tuned-on validation block.

**THE STRATEGIC FACT: the field roughly DOUBLED between rounds; v2 stood still.** Test-round leader 810 →
general-round leader 1274. Ivan&Haowen (test leader, 810) → 1187. The whole board is clustered mu ~1160-1282.
v2's mu is **flat ~540** on every rolling 250-day window through 1-750 (251-500: 500, 351-600: 551, 451-700:
592, 501-750: 543) — **no upward trend**. So on 751-1000 v2 will likely score ~540-600, i.e. **near the
bottom** of the current board unless the hidden window is special.

**Why the field jumped — the load-bearing new insight: the lead-lag screen is strongly DATA-HUNGRY.**
Marginal-screen OOS IC on the fresh 501-750 block, vs fit-window length: 99d → 0.037, 249d → 0.052, 399d →
0.073, 499d → **0.076** (in-sample ceiling at 750d is 0.25). In the test round everyone fit on ~250 days (IC
~0.052 ⇒ mu ~500); in the general round everyone fits on ~750 days (higher IC ⇒ higher mu). Much of the
field-wide doubling is **everyone getting 3× the training data and converging near the same data-limited
ceiling** (fits the tight clustering). v2 uses an expanding window, so it captures this **for free** — its
751-1000 fit (750-999 days) is richer than any window we can test locally.

**The scoring theorem that makes IC the objective.** For this Gaussian generator under bang-bang,
`capture = mu / perfect-foresight-ceiling = daily cross-sectional IC` (because `E[move·sign(pred)] =
ρ·σ·√(2/π)` and perfect foresight is the same with ρ=1). Perfect-foresight ceiling is **flat ~$8,000/day**
in every block. So we capture 542/8000 = **6.8%** (≈ IC 0.076); the leader captures 1282/8000 = **~16%**
(≈ IC 0.16). **BUT the theorem is in z-space; SCORE is in dollars, and the two diverge** — see the IC-vs-
score trap below. Always confirm a signal by ground-truth bang-bang SCORE, never by IC alone.

**Are we behind (H1), or is 751-1000 just richer (H2)?** Evidence for **H1 (field found better signal, we're
behind):** the generator is provably constant-parameter over 750 days (flat vol ~35%, flat ceiling, flat
block stats); the board shows the **same dollar-vol (~1500) but 2.4× the mu** ⇒ same book size, better
predictor, not more leverage. Evidence for **H2 (richer hidden window):** uniform-ish field scaling + tight
clustering. **Cannot be resolved from our data.** THE fastest resolver is to **submit and read the live
751-1000 score**: v2 unchanged scored 526 on 501-750, so a live number near ~540 ⇒ H1 (crisis); near ~1000 ⇒
H2 (fine). This one submission is the highest-value action available.

**Re-examined generator on 750 days — assumptions HOLD.** Gaussian (excess kurtosis -0.033, skew -0.004, in
noise bands), **no vol clustering** (ACF r² ≈ 0 at all lags), **no nonlinear lead-lag** (|z|→z matrix 0.1%
significant, below null). Confirmed: linear methods are sufficient; lag-1 is the only structure.

**Lag-1 linear predictability caps at IC ~0.076 OOS.** Full VAR ridge: in-sample IC 0.35 but OOS **0.067**
(2,500 params, massive overfit) — the marginal screen (0.076) BEATS the full ridge VAR OOS. Lag-2/3/5 are
noise or negative; cumulative sums hurt; raw-return prediction (0.066) < market-neutral (0.076); multi-lag
ridge VAR scores a **disaster** (164 vs 556 bang-bang). So a better *version of the same lead-lag* is not
the answer.

**NEW dead ends (this round), all ground-truth SCORE-tested — the "IC-vs-score trap" strikes again:**
- **Reduced-rank regression (RRR) & PLS.** These DO raise OOS z-IC above the marginal screen (RRR-12 0.083,
  PLS-5 0.082 vs 0.076) AND are **data-hungrier** (their IC edge over marginal grows with fit length — the
  one genuinely interesting lead for the finalist round). **But on ground-truth bang-bang SCORE they LOSE:**
  RRR/PLS win only on the 501-750 window used to pick their rank (RRR-r8 683) and lose badly on 251-500
  (448) and on worst-windows; a "marginal-when-thin / PLS-when-thick" hybrid scored 437-516 vs marginal's
  554 on 501-750 and 379-455 vs 490 on 251-500. Reason: rank reduction keeps the *systematic* lead-lag
  (high z-IC) and discards the *idiosyncratic* lead-lag that carries the tradeable dollars — identical
  failure to SVD-truncation / sector-neutralisation. **This is the 4th+ confirmation of "breadth beats
  denoising / never regularise L", now extended to RRR and PLS.** The marginal screen at full magnitude is
  the robust SCORE-optimum. (Engines kept for the finalist round: RRR/PLS are the only estimators whose IC
  edge *grows* with data — worth re-testing when 1000+ days exist, but only against ground-truth score.)

**The one robust, shippable improvement found: reversal weight 0.25 → ~0.15.** The reversal sleeve has
**decayed to ~0 IC on the newer data** (fit-half/test-half of 750d: reversal OOS IC **-0.005, t -0.6**;
lead-lag 0.066, t 8.6). The IC-optimal blend weight is now `w_rev = IC_rev/(IC_ll+IC_rev) ≈ 0` (was 0.257).
A `rev_w` sweep across selection/holdout/fresh/both-eval-windows is **uniformly better at 0.15-0.20 than at
0.25** (e.g. eval501-750 554 vs 527; eval251-500 490 vs 481; holdout 655 vs 581; fresh WF 571 vs 514).
`rev_w=0.15` keeps some diversification/tail-protection while upweighting the now-stronger lead-lag; pure LL
(rev_w=0) is best on 501-750 but has a slightly worse selection worst-window. **This is low-risk (a minor
reweight of a validated sleeve, not a structural change like v3) and principled (reversal IC genuinely
decayed).**

**LIVE SUBMISSION = v4** (`strategies/v4_leadlag_reversal_rev015.py`, byte-identical to v2 except
`REV_W 0.25 → 0.15`; copied to `general_round/too_much_alpha.py`). eval[501-750] 554.16 (mu 568.5, SR 6.21);
eval[251-500] 489.92.

**LIVE GENERAL-ROUND SCORE (751-1000), submission SUB-BFF1CA1C: 841.13** (mu 851.76, sigma 1514.31, 4792
trades). **This resolves H1 vs H2 — BOTH are partly true:**
- **H2 confirmed (window is richer).** The *same* v4 strategy scored 554 on 501-750 but **841 on 751-1000**,
  at essentially the *same* dollar-vol (1448 → 1514). Same book size, +50% mu ⇒ 751-1000 is a genuinely
  more *predictable* stretch (higher IC, not higher vol). So the generator is **NOT perfectly
  constant-parameter in predictability** across the 1000 days — 751-1000 is a high-signal regime. Our
  1-750 backtests therefore *understate* achievable live score.
- **H1 also real (field is ahead).** Leader 1274 on the same 751-1000 window ⇒ they capture ~16% of the
  ~8000/day ceiling vs our ~10.6% (841/8000). Gap is now **~1.5×, not 2.4×.** We are at **~66% of the
  leader**, materially better than the 41% the raw 526-vs-1282 comparison implied.
- **Consequence for research:** a more-predictable window means more extractable signal, and it is exactly
  the regime where a better estimator (or a data-hungry one like RRR/PLS) could pay where it didn't on the
  quieter 501-750. But live submissions are the only window into 751-1000, so validate on ALL of 1-750
  robustly first, then spend a submission. The live 841 is the anchor to beat.

**Post-841 research (this session) — what moved the score and what didn't:**
- **STAGED = v5** (`strategies/v5_leadlag_multirev.py`): v2 with a **multi-horizon reversal sleeve [20,60]**
  at weight 0.25 (only change vs v2). eval[251-500] 518.11, eval[501-750] **606.21** (+9.4% vs v4's 554).
  Rationale that makes it robust, not overfit: the residual own-reversal IC **strengthens at longer
  lookbacks and is split-half stable** (lb20 0.014, lb60 0.017, lb100 0.022, each stable across halves —
  independent, non-score evidence), and the [20,60] blend **strictly dominates v2 and v4 on BOTH the old
  (125-500) and new (500-750) eras** and both eval windows (unlike v3, which was better on one dataset).
  v4's cut to rev_w=0.15 was an overcorrection to a 501-750-window artifact; with the stronger multi-horizon
  sleeve the IC-optimal weight returns to v2's original 0.25. **Recommend submitting v5** (live-feedback
  safety: v4=841 is the anchor; if v5 underperforms we will see it). Expected live ~900-920 if the
  ev501/live ratio holds — still far short of the leader (1274); v5 is an increment, not the gap-closer.
- **No estimator beats the marginal screen on SCORE — confirmed across 43 windows spanning all 1-750**
  (fixed hyperparams, not per-window cherry-picked): marginal mean 496.9/worst 233.7; ridge-VAR 464/201;
  RRR-15 425/115; RRR-20 449/135; PLS-12 483/253; marginal+RRR ensemble 488/200. The marginal lead-lag
  screen is the robust score-optimum, full stop. **This buries the RRR/PLS lead** from the pre-841 note:
  they raise OOS z-IC and are data-hungrier, but they LOSE on dollar-score even on the full data — the
  IC-vs-score gap, now confirmed on 43 windows, not one. Do not revisit multivariate estimators unless a
  future round provides a *fundamentally* different regularization; ridge/RRR/PLS are all dead on score.
- **Orthogonal-signal hunt (blend-and-score across all 1-750): only reversal helps.** Tested rev{5..60},
  momentum-20, 1-day acceleration, cross-sectional rank-reversal, short/long vol-ratio. Momentum, accel,
  vol-ratio all HURT (confirms no vol clustering, no own-momentum). Reversal helps, and *longer* horizons
  help more on recent data (rev60 NEW-era 617 vs rev20 571) — the basis for v5's [20,60].
- **Still-open gap to the leader (~1.5×).** We could not find the signal that lifts capture from ~0.11 to
  ~0.16 on 751-1000. Lag-1 linear is exhausted (marginal screen optimal, data Gaussian/lag-1-only). The
  leader's edge is most likely a signal OUTSIDE the lead-lag+reversal family — but every classical stat-arb
  family is now tested and dead. Highest-value next probes if pushing further: market/regime-conditional
  lead-lag (does the sign structure change with market state?), and re-testing v5's own reversal horizon
  once the finalist data lands. Otherwise the increments are on a plateau.

**Bottom line for the general round.** We likely fell behind (H1 more probable than H2). No lag-1 linear
estimator we can build closes the 0.076→0.16 IC gap on SCORE — the multivariate VAR structure (in-sample
0.35) is real but not robustly extractable OOS (RRR/PLS raise IC, lose score). If the live submission
confirms H1, the gap needs a signal **outside the entire classical stat-arb / lead-lag family** (all of
which are now exhaustively tested and dead) — or it needs the RRR/PLS data-hunger to pay once 1000+ days
exist. The immediate move is: **submit, read the number, resolve H1 vs H2**, then decide.

## Leaderboard history (test round, days 501-750 hidden) — LIVE scores

| Our version | live score | mu | sigma | note |
|---|---|---|---|---|
| v1 lead-lag + inverse-vol | 469.12 | 479.60 | 1133 | highest Sharpe on the board — a mistake |
| **v2 + reversal + bang-bang** | **526.61** | 542.56 | 1493 | **BEST — this is LIVE** |
| v3 dollar-weighted ridge | 503.38 | 519.99 | 1493 | won every offline test, **LOST live**. Reverted. See below. |

**The v2 leaderboard read (leader "Ivan & Haowen" scored 810.91, mu 823, sigma 1608, Sharpe 8.09).**
The leader makes **52% more dollar profit than us at HIGHER Sharpe and similar vol** ⇒ they are not
leveraging, they have a materially better predictor (higher directional hit rate). `frac` is still ~0.98 for
everyone, so **score ≈ mu still holds**; the hunt is purely for more mean P&L.

**The hit-rate ceiling (why small edges matter enormously).** Under bang-bang everyone sits at the caps, so
mu is set by directional sign accuracy weighted by realised move size. Our hit rate on the 50 instruments is
**52.1%**. Perfect foresight would earn **$9,683/day**; we earn $543, i.e. **5.4% of the ceiling**. The leader
needs only ~**53.2%** accuracy to earn their 823. So ~1 percentage point of hit rate ≈ 50% more score. The
lever is a better SIGN predictor, and it must be judged by SCORE, not by IC (see the v3 dead-ends below).

## v3 TRIED AND REVERTED — the single most important lesson

**v3 (dollar-weighted ridge) beat v2 on EVERY offline test, then scored WORSE live.**
Offline (all drawn from our days 1-500): frozen 389.4 vs v2 355.7; dense holdout 484.2 vs 460.8;
eval.py window 495.26 vs 480.65. Live on the hidden days 501-750: **v3 = 503.38, v2 = 526.61.**
So we **reverted to v2** and deleted the v3 files.

Why it matters: our whole validation protocol (selection/holdout/frozen/placebo) is drawn from the SAME
500-day sample. It is our best available proxy for out-of-sample, but it is NOT the real thing. The Jul 16
live result is the first truly independent test, and it disagreed with the offline holdout. **Do not trust a
~5-10% offline improvement enough to ship it over a strategy with a proven LIVE score.** Only change the live
submission for a large, robust offline gain, or after a new live/data-drop confirms it.

What v3 changed (recorded so the idea isn't rebuilt from scratch): a ridge predictor
`B = (X'X/n + lam I)^-1 (X'Y/n)` with a RAW (dollar-weighted) target instead of the standardised one, to make
the estimator chase dollar profit rather than IC. Good theory, better offline, worse live. The dollar-weighting
insight is still probably correct in principle; the specific parameterisation did not generalise.

### Canonical literature applied (systematic pass), and verdicts
- **Avellaneda-Lee (2010) OU s-score stat-arb:** fit AR(1)/OU to each instrument's trailing cumulative residual,
  trade the normalised s-score instead of a raw sum. Applied: eval 344-418 vs v2's raw-sum reversal 480. **Worse.**
  The residual cumulative is near-random-walk (AR(1)≈1), so the OU normalisation adds estimation noise. The simple
  20-day sum already captures the same reversion.
- **Gatev pairs / cointegration** → dead (see pairs entries). **Jegadeesh-Titman / Moskowitz momentum** → dead
  (drift stability -0.03). **Lo-MacKinlay / Lehmann / Khandani-Lo contrarian** → this IS our reversal sleeve.
  **Lead-lag (2024 winner)** → our primary signal. **PCA/factor residuals (Avellaneda-Lee)** → we hedge the market
  factor. So the classical stat-arb / momentum / mean-reversion literature is now systematically covered; nothing
  outside v2 survives the frozen test.

### Directions tried while chasing the leader (810), and their verdicts
- price-level mean reversion: **dead** (AR(1) 0.977 ≈ random walk, speed stability 0.083, IC ~0.018 t<2).
- factor-level lead-lag (do the 3 PCs lead each other): **weak** (OOS IC 0.013). Lead-lag is idiosyncratic.
- ridge / dollar-weighted ridge (v3): better offline, **worse live**. Reverted (see above).
- sector-neutralise then lead-lag: IC 0.047 but SCORE 445→272. **dead** (IC-vs-score gap).
- dual reversal horizon (20+60): great on selection, **overfit** on holdout. **dead**.
- **pairs trading / cointegration (tested TWICE, both dead):** in-sample cointegration is real (27/30
  shortest-half-life pairs cointegrate at 5%, half-lives 3-5d) but only ~46% stable OOS (half-life corr 0.245).
  (a) stat-arb signal across all 50: eval 93-242, blending into the main strategy HURTS. (b) FOCUSED top-k pairs
  (trade only the best few): eval 5-87 vs v2's 480, and crucially Sharpe stayed LOW (0.6-1.8), so it's not even a
  high-Sharpe/low-mu case — the selected spreads don't reliably revert OOS. Two compounding failures: little
  capital deployed (score ≈ mu, so idle book = low score) AND an unstable signal. The cross-sectional reversal
  sleeve already captures the ROBUST version (revert against the whole basket, using all 50 names). Do not retry.
- **formulaic-alpha factor zoo (Alpha101 / QuantGPT operator vocabulary, price-only subset):** systematic sweep of
  rank/delta/ts_rank/decay_linear/ts_std/cross-corr factors. Only lead-lag (OOS IC 0.039) and reversal (0.025-0.030)
  survive — both already in v2. decay-weighting is WORSE than a flat sum; rank transforms collapse to ~0 (Gaussian
  data, so ranks lose the info z-scores keep). **No third factor exists.** No external alpha tool can extract signal
  that isn't in the data; the score ceiling is set by the generator, not our tooling.

## THE LEADERBOARD LESSON (read before optimising anything)

v1 scored **469.12** live (mu 479.60, sigma 1133.21), ranking 9th. Decomposing the board:

| Team | mu | sigma | Sharpe | frac | score |
|---|---|---|---|---|---|
| Disciples of Claude | 575.48 | 1724.95 | 5.28 | 0.9653 | 555.5 |
| I'm going to quit | 566.64 | 1619.25 | 5.53 | 0.9684 | 548.7 |
| **2much alpha (us, v1)** | 479.60 | 1133.21 | **6.69** | **0.9782** | 469.1 |

**We had the highest Sharpe and the lowest volatility on the board.** That is not a virtue here.
`frac = sr^2/(sr^2+1)` is **saturated** above SR≈5: we keep 97.8% of profit, the leader keeps 96.5%.
So an extra point of Sharpe is worth <2% of score, while an extra dollar of profit is worth ~98 cents.

> **score ≈ mu. The objective is DOLLAR PROFIT, not risk-adjusted return.**

Everything in v2 follows from that one realisation.

## How eval.py scores you (the referee)

- Replays the **last 250 days** of `prices.txt`. Each day: hands you only the past, calls your function,
  clips your positions to the limit, charges commission on shares traded, records daily P&L.
- **Score** = `mu * frac`, where `mu` = mean daily P&L in **dollars**, `frac = sr^2/(sr^2+1)`, and
  `sr = sqrt(250)*mu/sigma` is the annualized Sharpe. **If `mu <= 0`, score = `mu` (raw loss).**
  - Read as: *dollar profit, taxed by unreliability.* `frac` = fraction of profit you keep: SR 1→50%,
    2→80%, 3→90%. Curve flattens past SR≈2.
  - Asymmetry: profitable strategies can't score negative (vol only shrinks toward 0); bad signals score
    their full loss. → **signal quality first, size second.**
  - **Score is ~linear in position size once SR > 3**, because doubling positions doubles both `mu` and
    `sigma`, leaving `frac` unchanged. → **get the signal right, then deploy capital to the caps.** This
    turned out to be the single largest lever we found (see "gross scaling").
- **Position limit** $10k/instrument, re-clipped daily. **CORRECTION to an earlier note here:** the clip uses
  `curPrices = prcHistSoFar[:, -1]`, the *same* last price your function sizes on, so there is **no price
  drift and no need for headroom.** Take exactly `floor(10_000 / price)` shares. (v1 held back 5% for
  nothing; verified 0 involuntary trims in 12,750 checks.)
- **Instrument 0 ("ALGO")** is special: **$100k cap (10x), 0.2bp commission (5x cheaper)**.
- **Commission** 1bp (0.0001) of dollars traded; instrument 0 is 0.2bp.
  **MEASURED: turnover is NOT a headwind at 1bp.** Position smoothing lost score on every window tested.
  (The old note in this file said "smooth position changes"; that was wrong. Don't.)
- **Min $25k total dollar volume** over the 250 days or score = 0 (kills do-nothing). We trade $111.9M.
- No look-ahead possible (you only ever get `prcHist[:, :t]`). Positions are whole shares. No starting
  capital — only the per-instrument limits constrain you.
- Sandbox: 10-min total runtime, **network-disabled**. Allowed without declaration: numpy, pandas, scipy,
  scikit-learn, statsmodels, matplotlib. Extra packages need `requirements.txt`; undeclared ones →
  disqualification. **Our submission uses numpy only.**

### Four subtleties of eval.py that the backtester must replicate

1. Commission is charged into cash with a **one-day lag** (the `comm` subtracted on day `t` is day `t-1`'s).
2. The first test-day iteration is a **warm-up**: it sets position but is **not scored**.
3. Positions are re-clipped to **integer share limits at each day's price**, even if you don't trade.
4. The P&L standard deviation is **population** (`ddof=0`), not sample.

### Sharpe, derived (so we don't re-explain)

Variance of a sum of independent days adds: `Var(year) = 250 * Var(day)`. Std is its sqrt, so
`std(year) = sqrt(250) * std(day)`. But `mean(year) = 250 * mean(day)`. Ratio → `Sharpe(year) =
sqrt(250) * Sharpe(day)`. Mean grows by 250, risk only by sqrt(250) — that gap is why aggregating a tiny
daily edge over many days produces a usable annual Sharpe, and where the `sqrt(250)` comes from.

## What we've learned about the data (all reproduced in `analysis.ipynb`)

- **Simulated, Gaussian, constant-parameter.** Excess kurtosis mean -0.026 (2-SE band ±0.438), skew mean
  +0.002, Jarque-Bera rejects at the chance rate, pooled QQ-plot straight into both corners.
  ⇒ No tail-hedging. **No nonlinear ML**: for Gaussians all dependence is linear, so there is nothing for it
  to find, and only 499 obs to overfit.
- **No volatility clustering.** Mean autocorrelation of `r^2` is -0.006 at lag 1 and ~0 at lags 2,3,5,10
  (2-SE band ±0.090); same on `|r|`. Real markets show ~+0.2. ⇒ **No GARCH, no vol timing.** Risk is one
  fixed number per instrument.
- **Volatility magnitude:** annual 15.7% to 64.7%, a **4.1x spread** ⇒ equal-dollar sizing would let wild
  names dominate. Use inverse-vol.
- **Instrument 0 = the market index.** Correlates **0.9930** with the equal-weight basket of the other 50;
  regression slope 1.006; starts at exactly 100.00; lowest vol of all 51 (0.0099 vs basket 0.0098).
  Combined with its special limits, it's the **designed hedging vehicle**.
- **Factor structure (correlation-matrix eigenvalues):** 11.55 (market, 22.7% of all variance), 2.84 and
  1.97 (two sectors), then 1.27 which is **noise**. Marchenko-Pastur ceiling `(1+sqrt(N/T))^2 = 1.74`;
  market-adjusted ceiling `(1 - lambda_1/N) * 1.74 = 1.35`. Three factors survive **both** bars.
  - The naive Kaiser rule ("keep eigenvalues > 1") would have manufactured a phantom 4th factor. This is
    exactly how overfit models are born.
  - Independent cross-check: equicorrelation identity `lambda_1 = 1 + (N-1)*rho` predicts `1 + 50*0.200 =
    10.98` against the observed 11.55. Two unrelated calculations agreeing ⇒ neither is a coding error.
- **Average pairwise correlation 0.200** before hedging, **-0.010** after. Removing ONE factor destroyed
  nearly all co-movement. The slight negative is mechanical, not a bug: the hedge approximately demeans each
  day cross-sectionally, and exactly-demeaned data has average pairwise correlation `-1/(N-1) = -0.0204`.
  ⇒ After the hedge the 50 bets are **uncorrelated ON AVERAGE**, so the mean-variance optimal weight
  collapses to `dollars ~ prediction / sigma`. (That is why v1's inverse-vol sizing was principled. It is
  moot under v2's bang-bang, which optimises a different objective and ignores sigma entirely.)
- **CORRECTION — this file used to infer from the above that "the residual covariance is ~diagonal". That
  inference is FALSE, and it matters.** *Average* pairwise correlation ≈ 0 does **not** imply the correlation
  matrix ≈ I: two sector factors with mixed-sign loadings produce positive correlation within sectors and
  negative across, averaging to ~0. Measured on the residuals: average pairwise corr **-0.009** but average
  **|corr| 0.069**, and the residual correlation matrix has **eigenvalues 4.03 and 2.75 above its own
  Marchenko-Pastur ceiling of 1.73**. Two real factors survive the market hedge.
  ⇒ Consequence: `sig = L' z` is a **marginal (univariate-screen) estimator, not the regression**. The
  VAR(1) coefficient is `A = L' C0^-1`, so v2 is strictly mis-specified. **We built and tested the
  correction; it does not reliably pay — see "GLS whitening" in the FAILED table.** The reasoning error was
  real; the resulting strategy error is not worth fixing.
- **Stability audit (split-half correlation of per-instrument parameters, across instruments):**
  - volatility ≈ **0.982** (trust it — use for inverse-vol sizing)
  - market beta ≈ **0.780** (persistent, but noisier because beta is a *ratio* of two estimates)
  - drift ≈ **-0.034** (NOISE — **momentum/trend-following is dead here**)
  - own-autocorrelation ≈ **+0.072** (NOISE — own momentum/reversal is dead; the old starter traded this)

### Signals: the full hunt

- **Own-autocorrelation / drift / momentum: dead.** Inside the noise band and doesn't repeat across halves.
- **Lead-lag `L[i,j] = corr(resid_i[t], resid_j[t+1])`: the primary alpha.**
  - 21 of 2,450 off-diagonal pairs beyond 3 s.e., vs 6.6 under the analytic null and **6.8 under a 300-run
    permutation null** (we generated the null rather than assuming it; permutation p < 0.0001).
  - Benjamini-Hochberg: only **1 pair** survives at q=0.05, 4 at q=0.10, 13 at q=0.20.
    ⇒ **No single pair is a goldmine. AGGREGATE the whole matrix; never cherry-pick pairs.**
  - Whole-matrix split-half stability **+0.110** (so ~11% of each entry is signal, 89% noise).
  - **Out-of-sample IC 0.048** (matrix fitted on first half, scored on second; t≈4.96; positive 61% of days).
  - **Why a weak signal pays: breadth.** Grinold: `IR ≈ IC * sqrt(breadth)`. With 50 names × 250 days,
    `IR <= 0.048 * sqrt(12500) ≈ 5.4`. Our realised SR of 4.97 sits just under that bound.
  - **A tempting story we TESTED AND REFUTED:** aggregation does *not* stabilise the predictor.
    Entry stability +0.110 vs prediction stability +0.096. They're the same. The edge comes from breadth,
    not from any hidden robustness in the matrix. Don't repeat this mistake.
- **Cross-sectional reversal (residual, 20-day lookback): real, orthogonal, ~3x weaker.**
  - **CORRECTION to an earlier note in this file.** It does NOT "flip sign" and it is NOT positive only 22%
    of the time. With the signal defined as *minus* the past 20-day residual return: full-sample IC +0.0218,
    naive t 2.66, **Newey-West t 2.58** (corrects for overlapping windows), same sign in both halves
    (+0.0271 / +0.0166), positive in **78%** of rolling 60-day windows. The old "22%" was the same fact under
    the opposite sign convention.
  - Out-of-sample IC **0.0166** vs lead-lag's 0.0484, and cross-sectional correlation between the two signals
    is -0.008 ⇒ genuinely **orthogonal**, a legitimate candidate diversifier.
  - Still unresolved whether it earns a slot. See "Open questions".

## The v2 strategy (in `test_round/too_much_alpha.py`)

Each day, causally from history only:

```
1. log returns
2. residuals = returns - ALGO returns          # beta fully shrunk to 1.0 (see below)
3. standardise residuals -> Z
4. L = Z[:, :-1] @ Z[:, 1:].T / n ; zero the diagonal
   zero every entry with |L| < 1.0 / sqrt(n)   # sub-one-standard-error entries are noise
5. sig_ll  = L.T @ Z[:, -1]                    # aggregated lead-lag
   sig_rev = -Z[:, -20:].sum(axis=1)           # orthogonal residual reversal
   sig = 0.75*norm(sig_ll) + 0.25*norm(sig_rev) ; sig -= sig.mean()
6. HYSTERESIS: keep yesterday's sign where |sig| < 0.30 * mean|sig|
7. shares = sign(sig) * (10_000 / price).astype(int)     # BANG-BANG at the exact cap
8. ALGO position = -sum(dollars), clipped                # hedge net market exposure
```

### The four v2 changes, in order of value

1. **Hysteresis band (biggest win).** Only flip a position's sign when the signal is convincing. The daily
   prediction is noisy; flipping on a marginal signal pays commission for nothing and whipsaws out of
   positions that were about to work. `band` sweep (mean selection score, 3 grids): 0→365, 0.15→404,
   **0.20→448, 0.25→445, 0.30→445**, 0.35→426, 0.50→396. Broad hump; we chose 0.30 by the pre-registered
   rule (best worst-window among configs within 2% of the best mean). Dollar volume fell $129M → $103M, but
   the gain is far larger than the commission saved: it lets winners run.
2. **Bang-bang sizing.** Because `score ≈ mu`, maximising `mu = sum d_i E[r_i]` s.t. `|d_i| <= cap` is a
   *linear programme*, whose solution is `d_i = cap * sign(pred_i)`. Inverse-vol sizing is mean-variance
   optimal — a **different objective**. Under bang-bang, `sd` and any conviction exponent drop out entirely;
   only the SIGN matters. Bonus: net exposure grows, so ALGO's $100k cap is finally used (up to $99.6k).
3. **Exact cap (this was a BUG in v1).** v1 used `TARGET_FRAC = 0.95` "for headroom against the daily
   re-clip". **There is no drift to defend against:** `eval.py` builds `posLimits` from
   `curPrices = prcHistSoFar[:, -1]`, the *same* last price we size on. Verified 0 involuntary trims in
   12,750 checks. Taking exactly `floor(CAP/price)` shares recovered 5% of the book for free.
4. **Reversal sleeve at the IC-optimal weight.** For *orthogonal* signals the optimal blend weights by IC:
   `w_rev = IC_rev/(IC_ll + IC_rev) = 0.0166/(0.0484+0.0166) = 0.257`. We use 0.25. Theory and the empirical
   plateau (0.25-0.30) agree, which is what makes it principled rather than fitted. Selection mean rose
   292→319 at `rev_w=0.10` while the *worst* window also improved, i.e. it strictly dominates.

**Why beta is fully shrunk to 1.0 (we estimate no betas at all).** Betas average 0.98 but their split-half
stability is only 0.780, versus volatility's 0.982, because beta is a ratio of two estimated quantities and
inherits noise from both. Shrinking `beta_i -> beta_i + k*(1 - beta_i)` improved the score monotonically all
the way to `k = 1.0`, i.e. deleting the parameter entirely. Fewer estimated parameters, strictly better.

**ALGO cannot carry alpha.** Its own autocorrelation is inside the noise band at every lag, and a ridge model
predicting `r_ALGO[t+1]` from today's 50 residuals scores an out-of-sample correlation of **-0.031** (and
-0.070 on the reverse split). The market return is unpredictable, so ALGO's $100k cap can only ever hedge.

## Validation protocol (do not violate this)

- **SELECTION set:** windows whose *scored* days lie in `[125, 350)`. Every parameter choice was made here,
  and every sharp optimum was re-confirmed on **three different evaluation grids** (test_len 100/125/75).
- **HOLDOUT set:** windows whose scored days lie in `[350, 500)`.
- **Pre-registered decision rule:** among configs within 2% of the best selection mean, take the one with the
  best *worst* window. Write the config down before running the holdout.
- v2 holdout: mean **463.6**, min 371.7, 100% positive — again *higher* than selection (445.3). The opposite
  of what overfitting produces.
- Also run, on the final config: **frozen fit** (355.7), and **two placebos** (random signal: -234.3; random
  `L` with the real reversal sleeve: -32.8). Both must lose money.
- Prefer flat parameter plateaus over sharp peaks. Treat the Jul 16 data drop as a **one-shot** honest
  out-of-sample test — validate on it, don't re-tune on it until validated.

## Things that sounded good and FAILED (don't retry blindly)

| Idea | Rationale | Result (mean selection score) |
|---|---|---|
| SVD rank truncation of `L` | entries are 89% noise, so denoise | rank 3→62, rank 10→55, rank 35→105, none→99. **Hurts.** Signal is spread across the full spectrum. |
| Sector neutralisation | two real sector factors exist, remove them too | k=0→296, k=1→288, k=2→227, k=3→155. **Hurts.** Strips real lead-lag that travels *through* sectors. |
| Position smoothing | cut turnover/commission | 1.0→293, 0.8→269, 0.6→223. **Hurts.** At 1bp, commission isn't the bottleneck. |
| Rolling estimation window | adapt to changing structure | expanding→296, 250d→282, 125d→240. **Hurts.** Constant-parameter generator ⇒ more data is strictly better. |
| Keep only "significant" pairs (2.5 s.e.) | trade the strong pairs | ~45 vs ~140 for keep-all. **Hurts badly.** Only 1 pair survives FDR; cherry-picking = one bet. |
| Multi-lag (add lag-2 matrix) | if i leads j by 2 days we're missing it | lag2_w 0→292, 0.15→275, 0.3→256, 0.5→236. **Hurts.** The structure is lag-1 only. |
| ALGO as a 51st predictor row | maybe the market leads residuals | 293.7 alone (noise-level gain), and **313.9 vs 349.3 once the reversal sleeve is on. Hurts.** |
| Soft / James-Stein shrinkage of `L` | principled middle ground vs hard cut | soft-only λ=0.5→231, λ=1→236; hard+soft→239. **Hurts** vs hard threshold's 292. (`CLAUDE.md` used to list this as the top next step. It is now tested and dead. NB a *global multiplicative* shrink is a **no-op** once gross is renormalised — shrinkage must be nonlinear.) |
| Signal EWMA (blend with yesterday's signal) | smooth the noisy prediction | on top of hysteresis: 448→376→354→338 as ewma goes 0→0.1→0.2→0.3. **Hurts.** Hysteresis already does this, better. |
| Raising gross utilisation (without reversal) | 31% of the book was idle | util 0.7→285, 0.8→292, 0.9→263, 1.0→258. **Hurts.** The idle capital was idle *because there was no conviction there*; the marginal dollar bought noise. (With the reversal sleeve on, conviction spreads and full utilisation becomes optimal.) |
| Multi-horizon lead-lag `L_k`, k=2..8 | maybe the signal persists multi-day (the hysteresis-gain hypothesis) | **The lead-lag signal is lag-1 ONLY.** OOS IC: k=1 → 0.044 (t 4.9), k≥2 all inside the noise band (t<2). Holding longer dilutes: cumulative-k-day IC decays 0.040→0.017. So hysteresis does NOT work via horizon persistence, and a multi-day predictor is dead. |
| Sector-neutralise residuals before lead-lag | raises the predictor's OOS IC (0.039→0.047, t 5.6) | **IC up, SCORE DOWN (445→272).** The single most important negative result of the v2→v3 round: under bang-bang, dollar profit is sign-accuracy weighted by realised move size, NOT cross-sectional IC. **Never optimise IC once the Sharpe tax is saturated.** |
| Second (long) reversal horizon, 20d + 60d | reversal 60d has higher OOS IC (0.030) than 20d (0.025) | **OVERFIT.** Selection mean 486.6 (vs v2 445.3), worst window 342 — but HOLDOUT 369.9 (vs v2 463.6) and eval 454 (vs 480.65). A selection-set artefact. The selection surface was bumpy (spike at lb2=80), not a plateau — the warning sign. the deleted engines documented these; verdicts kept in this table. |
| **Bagged hard threshold on `L`** | the 1-s.e. keep/drop is a discontinuous, high-variance decision (matrix stability is only 0.110); bootstrap the (z[t],z[t+1]) pairs and average the thresholded estimates to smooth it | **Hurts.** B=20 → 414.9, B=50 → 374.6, vs 443.5. |
| **Stability selection on `L`** | keep `L[i,j]` weighted by the fraction of bootstraps in which it clears the bar with the same sign (Meinshausen-Bühlmann) | **Hurts.** B=20 → 388.4, B=50 → 391.5, vs 443.5. |
| **GLS / whitened predictor** (`strategies/engines/gls_whiten_engine.py`) | `sig = L'z` is a MARGINAL estimator; the VAR(1) regression is `A = L' C0^-1`, and `C0` is provably **not** diagonal (2 sector eigenvalues above MP). So whiten today's cross-section: `C0_a = (1-a)C0 + aI`, `a=1` is v2. | **SHELVED — real but too weak to ship.** Paired over days 125-499: best `a`≈0.85 gives d_mu **+44/day (t = 1.39)** and d_hit **+0.003 (t = 1.71)** — right sign, smooth plateau over a ∈ [0.75,0.9] in two independent sub-samples, but **not significant**. Holdout 476.2 vs v2 463.6 (+2.7%); eval 485.6 vs 480.65. **A rank-2 correction — which targets exactly the two real factors and should therefore be CLEANER — is WEAKER and bumpy (all t < 1.6).** That kills the mechanism story. Gain is far below the bar set by the v3 disaster (v3 had ~+9% frozen and still lost live). **Do not ship without new-data confirmation.** |
| Antisymmetric decomposition of `L` | true "i leads j" flow should live in the antisymmetric part; splitting might denoise | **Hurts.** Symmetric part alone → 29.6, antisymmetric alone → 259.8, full `L` → 443.5. (`antisym=0.5` reproduces v2 exactly — it is algebraically `0.5·L`, a no-op under bang-bang. Good sanity check.) **Useful structural confirmation though: A >> S proves the lead-lag is genuinely DIRECTIONAL, not a contemporaneous-correlation artefact.** |
| **GLS whitening of the predictor** (`strategies/engines/gls_whiten_engine.py`, `Engine6`) | `sig=L'z` is a MARGINAL estimator; the true VAR(1) coefficient is `A=L'C0^-1`, and the residual `C0` still has 2 sector factors (eigenvalues 4.03, 2.75 > MP 1.73), so `C0≠I`. Whiten today's cross-section: `Ca=(1-a)C0+aI`, `a=1`=v2. | **Walk-forward gain, FROZEN loss — do NOT ship.** Selection/holdout peak at a≈0.92 (eval 500.6 vs 480.65, better holdout). But the FROZEN test (fit C0 on 1-250, trade 251-500 blind — the best live proxy) gives a=0.9 → **345.5 vs v2's 355.7**. `C0^-1` amplifies the noisiest small-eigenvalue directions, so a stale frozen `C0` hurts. Sound theory, real offline gain, rejected by the one test that mimics live. The v3 trap again. |
| Median-demean (exact 25/25 long/short) | dollar-neutrality is a constraint; the LP optimum under it is a top-25/bottom-25 split | **Hurts badly.** 358.0 vs 443.5. The unbalanced long/short tilt is genuinely informative, and ALGO already absorbs it — the neutrality constraint just throws information away. |
| `sd_scale`: scale the prediction by `sd_j` | predict the DOLLAR move rather than the z-move (v3's dollar-weighting insight, moved to the PREDICTION stage where it is a much smaller change) | **Hurts.** 387.7 vs 443.5. v3's dollar-weighting is now dead from both directions — estimation stage (lost live) and prediction stage (loses offline). |
| Alternative hysteresis fallbacks | if "carry yesterday's sign" is what pays, maybe a better fallback exists for weak names | **Nothing beats plain carry (443.5).** reversal-sign → 368.9; sign of k-day mean signal → best 437.9 (k=10), bumpy; sign of EWMA → best 413.2. Unbounded memory of the last conviction is the right rule. |

Parameter sensitivities that DO matter: `signif_se` (1.0 is a sharp-ish hump, but it is the canonical
one-standard-error cut and survived three different evaluation grids), `band` (broad hump 0.20-0.30),
`rev_w` (plateau 0.25-0.30, and 0.257 is the theory value), and `beta_shrink` (monotone to 1.0).
Re-verified: `rev_lb` is a **flat, noisy surface** (selection would pick 15, holdout picks 20 — no signal
there); `rev_w` has a clean plateau 0.25-0.35 in **both** the selection and holdout regions, and dropping
the sleeve entirely costs holdout hit rate 0.5223 → 0.5192. Both live values are correct; no free gain.

### THE UNIFYING PRINCIPLE: breadth beats denoising. Never reweight `L` by reliability.

Six separate attempts to "clean up" the lead-lag matrix have now failed — SVD rank truncation, soft /
James-Stein shrinkage, keeping only 2.5-s.e. pairs, sector neutralisation, **bagging**, and **stability
selection**. They fail for one reason, and it is worth internalising:

`sig_j = sum_i L[i,j] * z_i` is a sum of **50 terms**. Noise in the individual `L[i,j]` is therefore
*already averaged down by breadth* before it ever reaches the position. Any scheme that reweights entries
by how large or how reliable they looked **in-sample** re-introduces selection bias, and that bias does not
average away. The unbiased-but-noisy estimator beats the "denoised" one.

So the 1-s.e. hard threshold is **not** doing denoising. It is doing something narrower and cheaper:
deleting entries whose *sign* is a coin flip, which contribute variance with no mean. Keep every surviving
entry at its **full, unshrunk magnitude**. This principle now predicts the outcome of the whole FAILED
table above — treat any new "let's regularise `L`" idea as dead on arrival unless it clears this argument.

## Repo layout (one folder per round; shared core at the root)

```
sig-algothon-2026/
  CLAUDE.md              this file — project-wide guide
  backtester.py          SHARED. walk-forward backtester, reused by every round
  documentation.html     SHARED. cumulative write-up across rounds
  requirements-dev.txt   exact grading-sandbox package set
  strategies/            SHARED. every strategy version, in development order
    README.md            the progression, and why each step happened
    v0_naive_momentum.py             organisers' starter.       eval 0.10
    v1_leadlag_invvol.py             lead-lag + inverse-vol.    eval 345.57, LIVE 469.12
    v2_leadlag_reversal_bangbang.py  + reversal + bang-bang.    eval 480.65, LIVE 526.61  <- LIVE (best)
    engines/
      leadlag_invvol_engine.py              v1 research engine (beta_shrink, sector_k, rank, est_window, scale_mode)
      leadlag_reversal_bangbang_engine.py   v2 research engine (exact_cap, band, rev_w, util, lag2_w, algo_lead)
      gls_whiten_engine.py                  SHELVED candidate: v2 + GLS whitening of the predictor (whiten=a;
                                            a=1.0 reproduces v2 exactly). Real theory, +2.7% holdout, t=1.4.
                                            Below the ship bar — re-test on the Jul 16 data before trusting.
    (v3 dollar-ridge, pairs, sector-neut and dual-reversal engines were tried and DELETED;
     their verdicts live in the "Things that FAILED" table so they aren't rebuilt.)
  test_round/            days 1-500 (released Jul 8)
    prices.txt           500 days x 51, header row of fake tickers, ALGO first
    eval.py              official scorer for this round. Never modified
    too_much_alpha.py    THE LIVE SUBMISSION — byte-identical copy of the newest strategy
    analysis.ipynb       the research notebook for this round's data
  general_round/         create when the Jul 16 data lands (see below)
```

**Why the submission is duplicated.** `eval.py` does `from too_much_alpha import getMyPosition`, so the live
file must sit next to it in the round folder. `strategies/` is the versioned record. Keep them in sync:

```bash
diff strategies/v2_leadlag_reversal_bangbang.py test_round/too_much_alpha.py && echo "in sync"
```

The **engines** are research tools, not submissions. They expose every knob we tested — *including the ones
that failed* — so a future session can re-verify a dead end rather than rediscover it.

**Why this split.** `prices.txt`, `eval.py`, the submission and the analysis notebook are all *about one
dataset*, so they live together. `backtester.py` and the `strategies/` engines are dataset-agnostic tools, so
they are shared. Nothing needed a code change to move: `eval.py` reads `./prices.txt` and imports
`too_much_alpha` from its own directory, and the notebook reads `prices.txt` relatively.

- `test_round/too_much_alpha.py` — **the live submission** (a byte-identical copy of
  `strategies/v2_leadlag_reversal_bangbang.py`); numpy only; no dependency on the other files. `eval.py` already
  imports it, so `cd test_round && python eval.py` scores us directly. Rename to `<TeamName>.py` at submission.
- `backtester.py` — `calc_pl` reproduces `eval.py` to the cent (verified on the old starter: mu 10.3597,
  std 1640.1991, dvol 5,919,621, score 0.1023). `walk_forward` + `summarise` give a score *distribution*
  across many unseen windows. Don't submit.
- `strategies/` — every version in development order, plus configurable research `engines/`. Research only.
- `test_round/analysis.ipynb` — 90 cells. Builds every concept from first principles with worked examples,
  explains each code cell line by line, and enforces structural claims with `assert`. Half the final grade.

### Starting a new round

1. `mkdir general_round` and drop in the organisers' new `prices.txt` and `eval.py`.
2. Copy `test_round/too_much_alpha.py` across as the starting submission.
3. Seed `general_round/analysis.ipynb` from the test-round notebook; re-run it on the new data and check the
   structural findings still hold (they should, if the generator is unchanged).
4. **Score the frozen config on the new data ONCE before touching anything.** That is the honest
   out-of-sample test the whole project has been building toward. Do not re-tune until you've recorded it.

## How to use the backtester

Run research from the **repo root**, adding the round folder to the path so `import too_much_alpha` resolves:

```python
import sys, pandas as pd
sys.path.insert(0, "test_round")          # so the round's submission is importable
from backtester import calc_pl, walk_forward, summarise
import too_much_alpha as strat

prc = pd.read_csv("test_round/prices.txt", sep=r"\s+").values.T   # (51, 500) — note the transpose

# 1. Score one window exactly as eval.py would (last 250 days)
r = calc_pl(prc, strat.getMyPosition, numTestDays=250)
print(r["score"], r["sharpe"], r["mu"], r["dvol"])       # 345.57  4.97  359.58  111932293

# 2. Score MANY windows and look at the distribution, not one lucky number
HOLD = dict(test_len=100, first_test_day=350, last_test_day=500, step=25)
print(summarise(walk_forward(prc, strat.getMyPosition, **HOLD)))
# -> {'n':3, 'score_mean':353.9, 'score_min':277.7, 'pct_positive':100.0, ...}

# 3. Compare variants with the research engine instead of the frozen submission
from strategies.engines.leadlag_reversal_bangbang_engine import Engine
Engine(signif_se=1.0, rev_w=0.25, exact_cap=True, band=0.30)   # the v2 config

# NOTE: v2 keeps hysteresis STATE between days. walk_forward calls .reset() on any
# object that has it, so pass the Engine object (not a bare function) or wrap the
# submission module:  class A: reset=lambda s: tma.reset(); __call__=lambda s,p: tma.getMyPosition(p)
```

To run the official scorer: `cd test_round && python eval.py`.

`walk_forward` slices `prc[:, :e]` for each window end `e` and scores the last `test_len` days of it, so the
strategy only ever sees the past. `first_test_day` / `last_test_day` bound which days get *scored*, which is
how the selection/holdout split is enforced. If your strategy object has a `.reset()` method (state, e.g.
position smoothing), `walk_forward` calls it before each window.

**The judgement it encodes:** never trust a single score. Read `score_min` and `pct_positive`, not just
`score_mean`. A strategy with a great mean and one catastrophic window is not a strategy.

## ANSWERED questions (were 1-3 on this list; kept because the answers are load-bearing)

**1. WHY hysteresis pays — SOLVED. It is a GATE, not a smoother.**
Instrumented the eval window, splitting every (day, name) slot by whether the band fired:

| on the 19% of slots where hysteresis fires | hit rate | mu/day |
|---|---|---|
| if we had used today's FRESH sign | **50.5%** (a coin flip) | **$5.7** |
| using the HELD (carried) sign | **52.4%** | **$95.5** |

Fresh and held disagree ~50% of the time on those slots, and **100% of hysteresis's +$90/day comes from
them** (non-overridden slots are untouched at $429.6). So: *when today's evidence on a name is weak, today's
sign is worthless — but the last **confident** opinion we held about that name still hits at 52.4%, as well
as a fresh strong signal does.* Hysteresis refuses to take a coin-flip bet.
- This is why **signal-EWMA HURTS while hysteresis helps**: EWMA smears *every* name and dilutes the strong
  signals; hysteresis touches *only* the weak ones. **The value is in the gating, not the smoothing.**
- It is **not** horizon persistence — consistent with `L_k` (k≥2) being pure noise.
- The persistence comes from the **reversal sleeve**: hysteresis is worth **+79** with `rev_w=0.25` but only
  **+36** with `rev_w=0` (interaction table: (0,0)→277.6, (0,0.30)→313.8, (0.25,0)→364.5, (0.25,0.30)→443.5).

**2. Is the band a crude proxy for a holding-period model? — NO. Carry is optimal.**
Tested explicit fallbacks for the weak names: reversal-sign → 368.9, sign-of-k-day-mean → best 437.9,
sign-of-EWMA → best 413.2, **plain carry → 443.5**. Unbounded memory of the last conviction wins. There is
no better holding-period model hiding here; stop looking for one.

**3. Are we over-hedging? — NO. Keep `hedge = 1.0`.**
`hedge_w` sweep (selection mean / worst): 0.00 → 445.6 / **199.0**; 0.50 → 445.0 / 221.5;
**1.00 → 443.5 / 242.8**. Dropping the hedge gains +0.5% of mean (noise) and costs 18% of the worst window.
Under the pre-registered rule (within 2% of best mean → take best worst-window), full hedging wins outright.
The hedge is nearly free in mean and buys real tail protection.

## Open questions / next steps (in order of expected value)

1. **Jul 16 drop:** score v2 once, without re-tuning, and record it before touching anything. This is the
   single highest-value action available and it is not a research task.
2. **Re-test the shelved GLS whitening candidate on the new data** (`strategies/engines/gls_whiten_engine.py`,
   `whiten=0.85`). It is the only surviving candidate with a correct theory behind it: +2.7% holdout,
   d_hit t=1.71, smooth plateau — but below the ship bar. A new 250-day sample is an independent test. If it
   confirms, that is real evidence; if not, delete it.
3. **The hit-rate ceiling is still the whole game.** We convert 52.1% sign accuracy into $543/day against a
   perfect-foresight ceiling of $9,683. The leader needs only ~53.2%. Every lever inside the current model
   class is now measured and on a plateau — **a further gain must come from a genuinely new signal, not from
   tuning.** Do not spend more time regularising `L` (see "the unifying principle").
4. **Selection worst-window regressed** (v1 250.3 → v2 242.8) even as the mean and the holdout improved.
   Worth understanding rather than ignoring.

## Past years (context)

- 2024 winner (~600 teams; now at SIG) used **cross-instrument lead-lag**. Heavy ML consistently abandoned
  by past participants (regime shifts break it; 10-min runtime limits retraining).
- Commission history: 10bp (2024) → 5bp (2025) → 1bp (2026). Turnover is much cheaper now — cheap enough that
  smoothing is counterproductive, as we measured.
- Prior score formula was `mean - 0.1*std`; the Sharpe-tax formula is new for 2026.
