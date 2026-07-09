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
- Prefer logical derivations over asserted facts — when I don't get something, prove it from first
  principles.

## The competition in one paragraph

Implement `getMyPosition(prcSoFar)` in `teamName.py`. Each day it receives price history as a NumPy array
shaped **(51 instruments, days-so-far)** and must return a length-51 vector of **integer share positions**
(the total desired holding, long or short, per instrument). The organizers replay this over a hidden window
and rank you on a score. There are **2,000 days of simulated data total**, released in stages; you always
get an earlier slice and are graded on the *next, unseen* 250-day window. Right now: we have days 1-500;
the leaderboard scores hidden days 501-750.

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

## How eval.py scores you (the referee)

- Replays the **last 250 days** of `prices.txt`. Each day: hands you only the past, calls your function,
  clips your positions to the limit, charges commission on shares traded, records daily P&L.
- **Score** = `mu * frac`, where `mu` = mean daily P&L in **dollars**, `frac = sr^2/(sr^2+1)`, and
  `sr = sqrt(250)*mu/sigma` is the annualized Sharpe. **If `mu <= 0`, score = `mu` (raw loss).**
  - Read as: *dollar profit, taxed by unreliability.* `frac` = fraction of profit you keep: SR 1→50%,
    2→80%, 3→90%. Curve flattens past SR≈2.
  - Asymmetry: profitable strategies can't score negative (vol only shrinks toward 0); bad signals score
    their full loss. → **signal quality first, size second.** Target SR≈2, then scale `mu`.
- **Position limit** $10k/instrument, **re-clipped daily at that day's price** even if you don't trade →
  size to ~95% of cap so rising prices don't force involuntary (commission-charged) trims.
- **Commission** 1bp (0.0001) of dollars traded; instrument 0 is **0.2bp** (5x cheaper). Turnover is a real
  headwind — smooth position changes.
- **Instrument 0 ("ALGO")** is special: **$100k cap (10x), 0.2bp commission (5x cheaper)**.
- **Min $25k total dollar volume** over the 250 days or score = 0 (kills do-nothing).
- No look-ahead possible (you only ever get `prcHist[:, :t]`). Positions are whole shares. No starting
  capital — only the per-instrument limits constrain you.
- Sandbox: 10-min total runtime, **network-disabled**. Allowed without declaration: numpy, pandas, scipy,
  scikit-learn, statsmodels, matplotlib. Extra packages need `requirements.txt`; undeclared ones →
  disqualification.

### Sharpe, derived (so we don't re-explain)

Variance of a sum of independent days adds: `Var(year) = 250 * Var(day)`. Std is its sqrt, so
`std(year) = sqrt(250) * std(day)`. But `mean(year) = 250 * mean(day)`. Ratio → `Sharpe(year) =
sqrt(250) * Sharpe(day)`. Mean grows by 250, risk only by sqrt(250) — that gap is why longer horizons
improve risk-adjusted return, and where the `sqrt(250)` comes from.

## What we've learned about the data (from day-1 analysis of prices.txt, 500 days x 51)

- **Simulated, Gaussian, constant-parameter.** ~0 excess kurtosis, no volatility clustering, vol stable
  across halves. ⇒ No tail-hedging / GARCH / vol-timing edge. Linear statistics (means, covariances,
  regressions) are sufficient; deep ML has nothing extra to find and 499 obs to overfit.
- **Instrument 0 = the market index.** Return correlates **0.993** with the equal-weight basket of the
  other 50; starts at exactly 100; lowest vol. Combined with its special limits, it's the **designed
  hedging vehicle**: run alpha on instruments 1-50, neutralize net market exposure with ALGO.
- **Factor structure:** 1 dominant market factor (eigenvalue 10.6) + 2 clear sector factors (2.8, 2.0)
  above the Marchenko-Pastur noise ceiling (~1.73); a 4th (1.27) is indistinguishable from noise.
  ⇒ compute alpha on **beta-hedged residual returns**.
- **Stability audit (split-half correlation of per-instrument parameters):**
  - volatility ≈ **0.98** (trust it — use for inverse-vol sizing)
  - market beta ≈ **0.78** (trust it — hedging with estimated betas works)
  - drift ≈ **0.00** (NOISE — **momentum/trend-following is dead here**; ignore backtests that rely on it)
- **Signals hunted so far:**
  - Own-autocorrelation (per-instrument momentum/reversal): dead, inside noise band. (The starter
    `too_much_alpha.py` trades exactly this — that's the joke.)
  - **Lead-lag (corr(r_i[t], r_j[t+1])): the primary alpha candidate.** ~20 pairs beyond 3 s.e. (noise
    predicts ~7); 3 pairs survive Benjamini-Hochberg FDR (4→40, 9→5, 9→15) and replicate in both data
    halves; whole-matrix split-half corr ≈ 0.15 (weak but real, aggregatable across 2,450 pairs).
    This is the structure the confirmed 2024 winner used.
  - Cross-sectional reversal (residual, ~20-day lookback): full-sample IC ≈ -0.019 (t≈2.5) looks
    tradeable but the rolling IC is **positive only ~22% of the time** and flips sign across sub-windows.
    Demoted to a *diversifier at best* — a live example of the overfitting trap (backtests ~18 on last 250
    days, but -0.9 Sharpe on days 126-375).

## Strategy direction (not yet built)

Architecture: **alpha sleeves on instruments 1-50 → beta-hedge net market exposure via ALGO →
inverse-vol size → smooth position changes to control commission → target SR≈2, then scale into the
limits.** Primary sleeve = shrunken lead-lag predictor (keep only entries beyond ~2.5 s.e., shrink the
rest to 0). Add reversal only if walk-forward shows it improves the score distribution.

**Anti-overfitting protocol:** never tune on the window you report; prefer flat parameter plateaus over
sharp peaks; validate by fit-on-first-half / test-on-second-half (and vice versa); treat the Jul 16 data
drop as a one-shot honest out-of-sample test — validate on it, don't re-tune on it until validated.

## Repo files

- `teamName.py` — implement `getMyPosition(prcSoFar)` here (renamed to `<TeamName>.py` only at submission).
- `eval.py` — official scorer (scores last 250 days of `prices.txt`). Don't submit it.
- `prices.txt` — current stage's price data (500 days x 51, header row of fake tickers, ALGO first).
- `too_much_alpha.py` — starter example (naive 1-day momentum; scores negative — it's a strawman).
- `analysis.ipynb` — our research notebook (being built by me, step by step).
- `requirements-dev.txt` — exact grading-sandbox package set. Don't submit it.

## Planned notebooks / modules (roadmap)

1. `analysis.ipynb` — understand the market (scoring, simulated-vs-real, index, factors, stability audit,
   signal hunt). **In progress.**
2. A reusable **walk-forward backtester** replicating eval.py exactly, scoring any strategy across *many*
   sub-windows (score distribution, not one point estimate).
3. Lead-lag predictor notebook (estimation window, shrinkage, position smoothing, ALGO hedge, inverse-vol).
4. Ensemble + final sizing against the score curve.

## Past years (context)

- 2024 winner (~600 teams; now at SIG) used **cross-instrument lead-lag**. Heavy ML consistently abandoned
  by past participants (regime shifts break it; 10-min runtime limits retraining).
- Commission history: 10bp (2024) → 5bp (2025) → 1bp (2026). Turnover is much cheaper now.
- Prior score formula was `mean - 0.1*std`; the Sharpe-tax formula is new for 2026.
