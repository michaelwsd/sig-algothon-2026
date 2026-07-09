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

**Strategy is built, validated and scoring.** Official `eval.py` on days 251-500:

| Measure | Value |
|---|---|
| Score | **345.57** |
| Annualised Sharpe | 4.97 |
| Mean daily P&L | $359.58 |
| Dollar volume | $111.9M |
| Runtime, 250 calls | 0.05s (limit 600s) |

Honest out-of-sample evidence (see "Validation protocol" below):

- **Holdout** (days 350-500, never used to choose anything): mean 353.9, min 277.7, 100% of windows positive.
- **Frozen** (fit on days 1-250, trade 251-500, never refit): score 242.8, SR 3.64. **Quote this one** as the
  conservative expectation, not 345.6.
- **Placebo** (identical machinery, random matrix of matched scale): -119.3, i.e. it *loses money*. This is
  how we know there is no look-ahead leak.

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
- **Position limit** $10k/instrument, **re-clipped daily at that day's price** even if you don't trade →
  size to ~95% of cap so rising prices don't force involuntary (commission-charged) trims.
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
  ⇒ **After the hedge, the 50 bets are near-independent**, so the residual covariance is ~diagonal and the
  mean-variance optimal weight collapses to `dollars ~ prediction / sigma`. **Inverse-vol sizing is optimal
  here, not a heuristic.**
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

## The strategy (in `too_much_alpha.py`)

Each day, causally from history only:

```
1. log returns
2. residuals = returns - ALGO returns          # beta fully shrunk to 1.0 (see below)
3. standardise residuals -> Z
4. L = Z[:, :-1] @ Z[:, 1:].T / n ; zero the diagonal
   zero every entry with |L| < 1.0 / sqrt(n)   # sub-one-standard-error entries are noise
5. sig = L.T @ Z[:, -1] ; sig -= sig.mean()    # aggregate, make dollar-neutral
6. dollars = sig / resid_vol                   # mean-variance optimal (covariance is ~diagonal)
   scale so sum|dollars| = 1.2 * 50 * 0.95 * 10_000, then clip each to +/- 9500
7. ALGO position = -sum(dollars), clipped      # hedge net market exposure
8. shares = (dollars / price).astype(int)
```

**Why beta is fully shrunk to 1.0 (we estimate no betas at all).** Betas average 0.98 but their split-half
stability is only 0.780, versus volatility's 0.982, because beta is a ratio of two estimated quantities and
inherits noise from both. Shrinking `beta_i -> beta_i + k*(1 - beta_i)` improved the score monotonically all
the way to `k = 1.0`, i.e. deleting the parameter entirely. Fewer estimated parameters, strictly better
results. This was counter-intuitive and is one of the two biggest wins.

**Why gross scaling (the other big win).** Scaling so the *largest* position hits the cap leaves most of the
book tiny and wastes capital. Scaling *gross exposure* past the caps and clipping per name deploys far more.
Since score is ~linear in size, this roughly tripled the score. The `gross_frac` sweep is a broad hump:
0.6→232, 1.0→280, **1.2→293**, 1.5→296, 2.0→285, 3.0→264. We chose 1.2, on the plateau, maximising the
*worst* window rather than the mean.

## Validation protocol (do not violate this)

- **SELECTION set:** windows whose *scored* days lie in `[125, 350)`. Every parameter choice was made here.
- **HOLDOUT set:** windows whose scored days lie in `[350, 500)`. Touched exactly once, after the config was
  frozen and written down.
- The holdout scored **higher** than the selection set (353.9 vs 293.2). That is the opposite of what
  overfitting produces, and is the strongest single piece of evidence we have.
- Also run, on the final config: **frozen fit** (242.8), **placebo** (-119.3), and a **plateau check** (any
  sharp optimum must be re-confirmed under several different evaluation grids).
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

Parameter sensitivities that DO matter: `signif_se` (1.0 is a sharp-ish hump, but it is the canonical
one-standard-error cut and survived three different evaluation grids), `gross_frac` (broad hump), and
`beta_shrink` (monotone to 1.0).

## Repo layout (one folder per round; shared core at the root)

```
sig-algothon-2026/
  CLAUDE.md              this file — project-wide guide
  backtester.py          SHARED. walk-forward backtester, reused by every round
  strategy.py            SHARED. configurable LeadLag research engine
  documentation.html     SHARED. cumulative write-up across rounds
  requirements-dev.txt   exact grading-sandbox package set
  test_round/            days 1-500 (released Jul 8)
    prices.txt           500 days x 51, header row of fake tickers, ALGO first
    eval.py              official scorer for this round. Never modified
    too_much_alpha.py    THE SUBMISSION for this round
    analysis.ipynb       the research notebook for this round's data
  general_round/         create when the Jul 16 data lands (see below)
```

**Why this split.** `prices.txt`, `eval.py`, the submission and the analysis notebook are all *about one
dataset*, so they live together. `backtester.py` and `strategy.py` are dataset-agnostic tools, so they sit at
the root and are shared. Nothing needed a code change to move: `eval.py` reads `./prices.txt` and imports
`too_much_alpha` from its own directory, and the notebook reads `prices.txt` relatively.

- `too_much_alpha.py` — **the submission.** Self-contained `getMyPosition(prcSoFar)`; numpy only; no
  dependency on the other files. `eval.py` already imports it, so `cd test_round && python eval.py` scores us
  directly. Rename to `<TeamName>.py` only at submission. (This file *used to be* the naive-momentum starter;
  that version is still in git history.)
- `backtester.py` — `calc_pl` reproduces `eval.py` to the cent (verified on the old starter: mu 10.3597,
  std 1640.1991, dvol 5,919,621, score 0.1023). `walk_forward` + `summarise` give a score *distribution*
  across many unseen windows. Don't submit.
- `strategy.py` — configurable `LeadLag` engine exposing every knob we tested. Research only. Don't submit.
- `analysis.ipynb` — 90 cells. Builds every concept from first principles with worked examples, explains each
  code cell line by line, and enforces structural claims with `assert`. Evidence base; half the final grade.

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
from strategy import LeadLag
LeadLag(signif_se=1.0, beta_shrink=1.0, scale_mode="gross", gross_frac=1.2)
```

To run the official scorer: `cd test_round && python eval.py`.

`walk_forward` slices `prc[:, :e]` for each window end `e` and scores the last `test_len` days of it, so the
strategy only ever sees the past. `first_test_day` / `last_test_day` bound which days get *scored*, which is
how the selection/holdout split is enforced. If your strategy object has a `.reset()` method (state, e.g.
position smoothing), `walk_forward` calls it before each window.

**The judgement it encodes:** never trust a single score. Read `score_min` and `pct_positive`, not just
`score_mean`. A strategy with a great mean and one catastrophic window is not a strategy.

## Open questions / next steps (in order of expected value)

1. **Jul 16 drop:** score the primary config AND the `+reversal` variant once each, without re-tuning, then
   pick. On our holdout the reversal variant scored 369.7 mean / 308.2 min vs the primary's 353.9 / 277.7 —
   it won on both — but we did **not** switch, because choosing it after seeing the holdout would consume the
   holdout and invalidate the number that makes it look good. The drop settles it cleanly.
2. **Shrink `L` smoothly instead of thresholding it.** We tried a hard 1-s.e. cut and a hard SVD truncation.
   A James-Stein style entrywise shrinkage toward zero is the principled middle ground we never tested.
3. **Multi-lag structure.** We only ever tested lag 1. If `i` leads `j` by two days, we're leaving it on the
   table.
4. **Cost of the daily re-clip.** Quantify how much score the involuntary trims cost, and whether a lower
   `TARGET_FRAC` pays for itself.

## Past years (context)

- 2024 winner (~600 teams; now at SIG) used **cross-instrument lead-lag**. Heavy ML consistently abandoned
  by past participants (regime shifts break it; 10-min runtime limits retraining).
- Commission history: 10bp (2024) → 5bp (2025) → 1bp (2026). Turnover is much cheaper now — cheap enough that
  smoothing is counterproductive, as we measured.
- Prior score formula was `mean - 0.1*std`; the Sharpe-tax formula is new for 2026.
