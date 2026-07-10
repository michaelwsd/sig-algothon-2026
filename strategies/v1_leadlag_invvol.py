"""v1 — aggregated lead-lag, inverse-vol sized, ALGO-hedged.

  LIVE LEADERBOARD SCORE: 469.12   (mu 479.60, sigma 1133.21, Sharpe 6.69, 9th)
  eval.py window (days 251-500):   345.57

WHAT IT GOT RIGHT
  * Aggregating the whole lead-lag matrix rather than cherry-picking pairs.
  * Zeroing entries within one standard error.
  * Shrinking beta fully to 1.0 (estimating no betas at all).
  * Hedging net market exposure with ALGO.

WHAT IT GOT WRONG (all fixed in v2)
  1. `TARGET_FRAC = 0.95` -- "headroom against the daily re-clip". A BUG: eval.py
     clips using `curPrices = prcHistSoFar[:, -1]`, the same price we size on, so
     there is no drift and no headroom is needed. This threw away 5% of the book.
  2. Inverse-vol sizing. Mean-variance optimal, but the score function pays for
     DOLLAR PROFIT (frac is saturated above Sharpe ~5), so the right objective is
     a linear programme whose solution is bang-bang at the cap.
  3. No reversal sleeve, and no hysteresis on the position signs.

It produced the highest Sharpe and the lowest volatility on the leaderboard.
Neither was worth anything. See documentation.html, "Leaderboard: score ~= mu".
"""
import numpy as np

ALGO = 0
CAP = 10_000            # $ position limit per instrument
ALGO_CAP = 100_000      # $ position limit for ALGO
TARGET_FRAC = 0.95      # leave headroom: eval.py re-clips daily at that day's price
GROSS_FRAC = 1.2        # deploy capital: scale gross exposure, then clip per name
SIGNIF_SE = 1.0         # zero lead-lag entries within one standard error (noise)
MIN_DAYS = 60           # need this much history before trading


def getMyPosition(prcSoFar):
    nInst, t = prcSoFar.shape
    r = np.diff(np.log(prcSoFar), axis=1)        # log returns, (nInst, T)
    T = r.shape[1]
    if T < MIN_DAYS:
        return np.zeros(nInst, dtype=int)

    # --- market-neutral residuals. Beta is fully shrunk to 1.0, so we simply
    #     subtract ALGO. Estimating 51 noisy betas made results strictly worse.
    algo = r[ALGO]
    resid = r - algo                              # broadcast over instruments
    R = resid[1:]                                 # alpha universe: instruments 1..50

    sd = R.std(axis=1)
    sd[sd < 1e-12] = 1e-12
    Z = (R - R.mean(axis=1, keepdims=True)) / sd[:, None]   # standardised residuals

    # --- lead-lag matrix: L[i,j] = corr(z_i today, z_j tomorrow) ---
    today, tomo = Z[:, :-1], Z[:, 1:]
    n = today.shape[1]
    L = today @ tomo.T / n
    np.fill_diagonal(L, 0.0)                      # own-autocorrelation is dead
    L[np.abs(L) < SIGNIF_SE / np.sqrt(n)] = 0.0   # drop sub-one-s.e. entries as noise

    # --- prediction for tomorrow, made dollar-neutral ---
    sig = L.T @ Z[:, -1]
    sig = sig - sig.mean()

    # --- sizing: mean-variance optimal reduces to prediction / vol ---
    dollars = sig / sd
    gross = np.abs(dollars).sum()
    if gross > 0:
        dollars *= (GROSS_FRAC * 50 * TARGET_FRAC * CAP) / gross
    dollars = np.clip(dollars, -TARGET_FRAC * CAP, TARGET_FRAC * CAP)

    # --- hedge net market exposure with ALGO (beta = 1 for all) ---
    hedge = np.clip(-dollars.sum(), -TARGET_FRAC * ALGO_CAP, TARGET_FRAC * ALGO_CAP)

    dvec = np.zeros(nInst)
    dvec[1:] = dollars
    dvec[ALGO] = hedge
    return (dvec / prcSoFar[:, -1]).astype(int)
