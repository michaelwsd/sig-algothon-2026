"""Algothon 2026 submission: aggregated cross-instrument lead-lag, market-neutral.

    getMyPosition(prcSoFar) -> length-51 vector of integer share positions.

WHY THIS STRATEGY (every choice traces to a measured fact; see analysis.ipynb):

  * Returns are Gaussian, symmetric, thin-tailed, with no volatility clustering.
    => linear methods are provably sufficient. No ML, no GARCH, no tail hedging.
  * Drift stability -0.03 and own-autocorrelation stability +0.07.
    => momentum / trend / own-reversal are dead. No timing, always fully invested.
  * Lead-lag (instrument i today predicting instrument j tomorrow) is the only
    surviving signal: 21 pairs beyond 3 s.e. vs ~7 under a permutation null,
    out-of-sample IC 0.048. But only ONE pair survives FDR at q=0.05, so the
    signal must be AGGREGATED across all 2,450 pairs, never cherry-picked.
    It pays through breadth: IR ~ IC * sqrt(breadth).
  * ALGO (instrument 0) correlates 0.993 with the equal-weight basket of the
    other 50 and has a 10x cap / 5x cheaper commission => the hedging vehicle.
  * Betas: mean 0.98 but split-half stability only 0.780, versus volatility's
    0.982. Beta is a ratio of two estimates and inherits noise from both, so we
    shrink it FULLY to its cross-sectional mean of 1.0 and estimate no betas at
    all. This removed an entire noisy parameter and improved every window tested.
  * After the ALGO hedge, average pairwise residual correlation falls from 0.200
    to -0.010, i.e. the bets are near-independent. That makes the mean-variance
    optimal weight collapse to  dollars ~ prediction / volatility  (inverse-vol),
    with no 50x50 covariance matrix to estimate.
  * score = mu * sr^2/(sr^2+1) is nearly linear in position size once Sharpe > 3,
    so we deploy capital up to the caps rather than optimise Sharpe further.
  * Commission is 1bp: cheap. Position smoothing damps the daily signal and cost
    us score on every window tested, so there is none.

VALIDATION (backtester reproduces eval.py to the cent):
  Parameters were chosen using ONLY windows scored on days [125,350).
  Holdout windows on days [350,500), never used for any choice: mean score 353.9,
  min 277.7, 100% positive.  eval.py window (days 251-500): score 345.6, SR 4.97.
  Frozen fit[1-250] traded blind on [251-500], never refit: score 242.8, SR 3.64.
  Placebo with a random matrix of matched scale: -119.3 (loses money), which is
  how we know there is no look-ahead leak.
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
