"""Algothon 2026 submission (v5) — aggregated lead-lag + MULTI-HORIZON reversal, bang-bang sized.

    getMyPosition(prcSoFar) -> length-51 vector of integer share positions.

v5 = v2 with the reversal sleeve upgraded from a single 20-day lookback to a normalised
[20, 60]-day blend (weight back at 0.25). The ONLY change vs v2. On the general-round (750-day)
data the residual own-reversal IC strengthens at longer lookbacks and is split-half stable, so
the short+long blend carries more signal; it STRICTLY DOMINATES v2 and v4 on both the old
(125-500) and new (500-750) eras and both eval windows. Live anchor to beat: v4 (rev20, w0.15)
scored 841.13 on the hidden 751-1000 window. See CLAUDE.md "GENERAL ROUND" for the full evidence.

------------------------------------------------------------------------------
WHY THIS STRATEGY  (every choice traces to a measured fact; see analysis.ipynb)
------------------------------------------------------------------------------
SIGNAL
  * Returns are Gaussian, thin-tailed, no volatility clustering => linear methods
    are provably sufficient. No ML, no GARCH, no tail hedging.
  * Drift stability -0.03, own-autocorrelation stability +0.07 => momentum, trend
    and own-reversal are dead. There is no market timing to do.
  * Lead-lag L[i,j] = corr(resid_i today, resid_j tomorrow) is the primary alpha:
    21 pairs beyond 3 s.e. vs ~7 under a permutation null; out-of-sample IC 0.048.
    Only ONE pair survives FDR at q=0.05, so the matrix must be AGGREGATED, never
    cherry-picked. It pays through breadth: IR ~ IC * sqrt(breadth).
  * Entries within one standard error are 89% noise; zeroing them is the single
    most valuable filter. A soft (James-Stein) threshold was tested and is worse.
  * Cross-sectional residual reversal is real (Newey-West t = 2.58), ORTHOGONAL to
    lead-lag (signal correlation -0.008), and ~3x weaker (out-of-sample IC 0.017).
    For orthogonal signals the optimal blend weights by IC, giving a reversal
    weight of 0.017/(0.048+0.017) = 0.26. We use 0.25. Theory and the empirical
    optimum agree, which is what makes it not an overfit.

HEDGING
  * ALGO (instrument 0) correlates 0.993 with the equal-weight basket of the other
    50 => it IS the market. We trade alpha on 1..50 and cancel net market exposure
    with ALGO, which has a 10x cap and 5x cheaper commission.
  * Betas average 0.98 but their split-half stability is only 0.780 (volatility's
    is 0.982), because beta is a ratio of two estimates. Shrinking fully to 1.0 --
    i.e. estimating NO betas -- beat every partial shrinkage. Fewer parameters,
    strictly better. So the residual is simply r_i - r_ALGO.
  * ALGO's own return is unpredictable (own autocorrelation inside the noise band;
    a ridge model on the cross-section gives out-of-sample corr -0.03). Its $100k
    cap can therefore only ever be a hedge, never an alpha sleeve.

SIZING  (this is where the 2026 score function bites)
  * score = mu * sr^2/(sr^2+1). At our Sharpe the tax factor is ~0.97, so
    score ~= mu. The objective is DOLLAR PROFIT, not risk-adjusted return.
  * Maximising  mu = sum_i d_i * E[r_i]  subject to  |d_i| <= cap  is a linear
    programme. Its solution is bang-bang: d_i = cap * sign(prediction_i).
    Inverse-vol sizing is mean-variance optimal, which is a DIFFERENT objective.
  * eval.py computes its position limit from `curPrices = prcHistSoFar[:, -1]` --
    the very same last price we size on. There is no price drift between our
    decision and the clip, so no headroom is needed: we take exactly
    floor(CAP / price) shares. (Verified: 0 involuntary trims in 12,750 checks.)
  * TURNOVER: the daily prediction is noisy, and flipping a position on a marginal
    signal pays commission for nothing. A hysteresis band -- keep yesterday's sign
    unless |signal| exceeds 0.30 x mean|signal| -- cut dollar volume from $129M to
    $103M and, more importantly, let profitable positions run. This was the single
    largest improvement found.

------------------------------------------------------------------------------
VALIDATION  (backtester reproduces eval.py to the cent; see documentation.html)
------------------------------------------------------------------------------
  Parameters chosen ONLY on windows scored in days [125,350), across three
  independent evaluation grids. Holdout days [350,500):  mean 463.6, min 371.7,
  100% of windows positive.
  eval.py window (days 251-500):        score 480.65, Sharpe 4.92, mu $500.51
  Frozen fit[1-250] -> trade[251-500], never refit:  score 355.66, Sharpe 3.73
  Placebo, random signal, same machinery:            score -234.25  (loses money)
  Placebo, random L but the REAL reversal sleeve:    score  -32.83  (loses money)
  The placebos are how we know there is no look-ahead leak, and that the lead-lag
  matrix -- not the reversal sleeve -- is carrying the strategy.
"""
import numpy as np

ALGO = 0
CAP = 10_000.0          # $ position limit per instrument
ALGO_CAP = 100_000.0    # $ position limit for ALGO
SIGNIF_SE = 1.0         # zero lead-lag entries within one standard error (noise)
REV_W = 0.25            # reversal weight = IC_rev / (IC_leadlag + IC_rev)
REV_LBS = (20, 60)      # MULTI-HORIZON reversal. General-round (750d) data shows the residual
                        # own-reversal IC strengthens at longer lookbacks (lb20 0.014, lb60 0.017,
                        # lb100 0.022, all split-half stable). A short+long blend [20,60] carries
                        # more signal than v2's single 20d sleeve and is regime-hedged: it strictly
                        # dominates v2/v4 on BOTH the old (125-500) and new (500-750) eras. With the
                        # stronger sleeve the IC-optimal weight returns to 0.25 (v4's 0.15 was an
                        # overcorrection to a 501-750-window artifact).
BAND = 0.30             # hysteresis: only flip a sign when the signal is convincing
MIN_DAYS = 60           # need this much history before trading

_prev_sign = None       # hysteresis state, persists across the single eval run


def reset():
    """Clear hysteresis state. Needed only when backtesting many windows."""
    global _prev_sign
    _prev_sign = None


def getMyPosition(prcSoFar):
    global _prev_sign
    nInst, t = prcSoFar.shape
    r = np.diff(np.log(prcSoFar), axis=1)
    T = r.shape[1]
    if T < MIN_DAYS:
        return np.zeros(nInst, dtype=int)

    # --- market-neutral residuals. Beta is fully shrunk to 1.0, so just subtract ALGO.
    resid = r - r[ALGO]
    R = resid[1:]                                   # alpha universe: instruments 1..50
    sd = R.std(axis=1)
    sd[sd < 1e-12] = 1e-12
    Z = (R - R.mean(axis=1, keepdims=True)) / sd[:, None]

    # --- sleeve 1: aggregated lead-lag ---
    today, tomo = Z[:, :-1], Z[:, 1:]
    n = today.shape[1]
    L = today @ tomo.T / n
    np.fill_diagonal(L, 0.0)                        # own-autocorrelation is dead
    L[np.abs(L) < SIGNIF_SE / np.sqrt(n)] = 0.0     # sub-one-s.e. entries are noise
    sig_ll = L.T @ Z[:, -1]

    # --- sleeve 2: orthogonal residual reversal, multi-horizon (short + long) ---
    # Each horizon's cumulative residual is normalised before averaging, so both
    # contribute equally regardless of window length.
    rev_parts = []
    for lb in REV_LBS:
        c = -Z[:, -lb:].sum(axis=1)
        rev_parts.append(c / (c.std() + 1e-12))
    sig_rev = np.mean(rev_parts, axis=0)

    # --- blend by information coefficient, then make dollar-neutral ---
    sig = ((1 - REV_W) * sig_ll / (sig_ll.std() + 1e-12)
           + REV_W * sig_rev / (sig_rev.std() + 1e-12))
    sig = sig - sig.mean()

    # --- hysteresis: don't pay commission to flip on a marginal signal ---
    sign = np.sign(sig)
    if _prev_sign is not None:
        weak = np.abs(sig) < BAND * np.abs(sig).mean()
        sign = np.where(weak, _prev_sign, sign)
    _prev_sign = sign.copy()

    # --- bang-bang sizing: score ~= mu, so max out every position at its cap ---
    px = prcSoFar[:, -1]
    shares = sign * (CAP / px[1:]).astype(int)      # exactly eval.py's own limit
    dollars = shares * px[1:]

    # --- hedge net market exposure with ALGO ---
    hedge = np.clip(-dollars.sum(), -0.999 * ALGO_CAP, 0.999 * ALGO_CAP)

    out = np.zeros(nInst)
    out[1:] = shares
    out[ALGO] = int(hedge / px[ALGO])
    return out.astype(int)
