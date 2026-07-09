"""Walk-forward backtester for Algothon 2026.

Reproduces eval.py's scoring exactly (verified to the cent against the starter
strategy), but generalised so we can score ANY strategy on MANY windows and look
at the distribution of scores rather than a single point estimate.

The governing rule: a strategy is trusted only if it scores well across windows it
never saw, not on the one window we happen to report.

Subtleties of eval.py that must be replicated, all easy to get wrong:
  * commission is charged into cash with a ONE-DAY LAG;
  * the first test-day iteration is a warm-up that sets position but is NOT scored;
  * positions are re-clipped to integer share limits at EACH day's price;
  * the P&L standard deviation is population (ddof=0), not sample.
"""
import numpy as np

# --- competition constants (must match eval.py) ---
DEFAULT_COMM  = 0.0001      # 1bp of dollars traded
INST0_COMM    = 0.00002     # 0.2bp for instrument 0 (ALGO)
DEFAULT_LIMIT = 10_000      # $ position limit per instrument
INST0_LIMIT   = 100_000     # $ limit for ALGO
MIN_DVOL      = 25_000      # below this total dollar volume the score is 0


def _rates(nInst):
    comm = np.full(nInst, DEFAULT_COMM);  comm[0] = INST0_COMM
    lim  = np.full(nInst, DEFAULT_LIMIT); lim[0]  = INST0_LIMIT
    return comm, lim


def score(mu, sigma, param=1.0):
    """eval.py's score: dollar profit, taxed by unreliability.

    sr   = sqrt(250) * mu / sigma          (annualised Sharpe of daily P&L)
    frac = sr^2 / (sr^2 + param^2)         (fraction of profit you keep)
    score = mu * frac  if mu > 0  else  mu (a loss scores its FULL loss)
    """
    if mu <= 0 or sigma < 1e-10:
        return mu
    sr = np.sqrt(250) * mu / sigma
    return mu * sr**2 / (sr**2 + param**2)


def calc_pl(prcHist, strat, numTestDays=250):
    """Faithful re-implementation of eval.py's calcPL, on one window.

    prcHist : (nInst, nt) prices, ALGO in row 0.
    strat   : callable(prcSoFar) -> length-nInst positions (shares).
    """
    nInst, nt = prcHist.shape
    commRate, dlrPosLimit = _rates(nInst)

    cash = 0.0
    curPos = np.zeros(nInst)
    totDVolume = 0.0
    value = 0.0
    comm = 0.0
    pll = []

    startDay = nt - numTestDays
    for t in range(startDay, nt + 1):
        prcSoFar = prcHist[:, :t]
        curPrices = prcSoFar[:, -1]

        if t < nt:
            newPosOrig = strat(prcSoFar)
            posLimits = (dlrPosLimit / curPrices).astype(int)
            newPos = np.clip(newPosOrig, -posLimits, posLimits).astype(int)
        else:
            newPos = np.array(curPos)          # final day: mark only, no trade

        deltaPos = newPos - curPos
        cash -= curPrices.dot(deltaPos) + comm  # NOTE: `comm` here is YESTERDAY's
        dvolumes = curPrices * np.abs(deltaPos)
        totDVolume += np.sum(dvolumes)
        comm = np.sum(dvolumes * commRate)

        curPos = np.array(newPos)
        posValue = curPos.dot(curPrices)
        todayPL = cash + posValue - value
        value = cash + posValue

        if t > startDay:                        # first test day is warm-up, unscored
            pll.append(todayPL)

    pll = np.array(pll)
    mu, sd = pll.mean(), pll.std()              # population std, as eval.py
    sharpe = np.sqrt(250) * mu / sd if sd > 0 else 0.0
    s = score(mu, sd)
    if totDVolume < MIN_DVOL:                   # do-nothing strategies score zero
        s = 0.0
    return {"mu": mu, "std": sd, "sharpe": sharpe, "score": s,
            "dvol": totDVolume, "pll": pll}


def windows(nt, test_len, first_test_day, last_test_day, step):
    """End-indices `e` such that the scored window [e-test_len, e) lies inside
    [first_test_day, last_test_day]. Scoring window = last `test_len` days of prices[:, :e].
    """
    out = []
    e = first_test_day + test_len
    while e <= last_test_day:
        out.append(e)
        e += step
    return out


def walk_forward(prcHist, strat, test_len=125, first_test_day=125,
                 last_test_day=None, step=25):
    """Score `strat` on many windows. Each score is genuinely out-of-sample in
    time: the strategy only ever sees prices up to the current day."""
    nInst, nt = prcHist.shape
    if last_test_day is None:
        last_test_day = nt
    results = []
    for e in windows(nt, test_len, first_test_day, last_test_day, step):
        if hasattr(strat, "reset"):
            strat.reset()                       # clear any smoothing state per window
        r = calc_pl(prcHist[:, :e], strat, numTestDays=test_len)
        r["end"] = e
        results.append(r)
    return results


def summarise(results):
    s  = np.array([r["score"]  for r in results])
    mu = np.array([r["mu"]     for r in results])
    sh = np.array([r["sharpe"] for r in results])
    return {"n": len(results),
            "score_mean": s.mean(), "score_median": float(np.median(s)),
            "score_min": s.min(), "score_max": s.max(),
            "pct_positive": 100.0 * (s > 0).mean(),
            "mu_mean": mu.mean(), "sharpe_mean": sh.mean()}
