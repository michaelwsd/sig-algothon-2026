"""Improved lead-lag engine: exact control of gross utilisation + conviction exponent."""
import numpy as np

ALGO = 0
CAP = 10_000.0
ALGO_CAP = 100_000.0


def waterfill(b, cap, target_gross):
    """Find k>0 so that sum_i min(k*|b_i|, cap) == target_gross, then apply.

    Scaling-then-clipping lets the clip decide our gross exposure. This instead
    hits a chosen gross exactly, which is what we actually want to control.
    """
    a = np.abs(b)
    if a.sum() == 0:
        return np.zeros_like(b)
    hi = target_gross / a[a > 0].min() if (a > 0).any() else 1.0
    lo, hi = 0.0, max(hi, 1.0)
    for _ in range(60):
        k = 0.5 * (lo + hi)
        g = np.minimum(k * a, cap).sum()
        if g < target_gross:
            lo = k
        else:
            hi = k
    k = 0.5 * (lo + hi)
    return np.sign(b) * np.minimum(k * a, cap)


class Engine:
    def __init__(self, signif_se=1.0, lag2_w=0.0, algo_lead=False, shrink=None,
                 power=1.0, util=0.95, rev_w=0.0, rev_lb=20, min_days=60,
                 hedge=True, cap_frac=0.999, exact_cap=False, band=0.0, sig_ewma=0.0):
        self.signif_se = signif_se   # hard threshold on L, in standard errors
        self.lag2_w = lag2_w         # weight on the lag-2 lead-lag matrix
        self.algo_lead = algo_lead   # let ALGO's return act as a 51st predictor
        self.shrink = shrink         # None, or entrywise James-Stein factor
        self.power = power           # conviction exponent: 1 = proportional, 0 = sign-only
        self.util = util             # target gross as a fraction of 50 * CAP
        self.rev_w = rev_w
        self.rev_lb = rev_lb
        self.min_days = min_days
        self.hedge = hedge
        self.cap_frac = cap_frac
        self.exact_cap = exact_cap
        self.band = band          # hysteresis: keep old sign unless |sig| clears this
        self.sig_ewma = sig_ewma  # blend today's signal with yesterday's
        self.reset()

    def reset(self):
        self.prev_sign = None
        self.prev_sig = None

    def __call__(self, prcSoFar):
        nInst, t = prcSoFar.shape
        r = np.diff(np.log(prcSoFar), axis=1)
        T = r.shape[1]
        if T < self.min_days:
            return np.zeros(nInst, dtype=int)

        algo = r[ALGO]
        resid = r - algo
        R = resid[1:]
        sd = R.std(axis=1); sd[sd < 1e-12] = 1e-12
        Z = (R - R.mean(axis=1, keepdims=True)) / sd[:, None]

        # optionally let ALGO lead (51 predictors -> 50 targets)
        if self.algo_lead:
            az = (algo - algo.mean()) / (algo.std() + 1e-12)
            Zp = np.vstack([Z, az])          # (51, T) predictors
        else:
            Zp = Z

        def leadlag(P, Tg, lag):
            a, b = P[:, :-lag], Tg[:, lag:]
            n = a.shape[1]
            return a @ b.T / n, n

        L1, n = leadlag(Zp, Z, 1)
        if self.algo_lead:
            np.fill_diagonal(L1[:50], 0.0)
        else:
            np.fill_diagonal(L1, 0.0)

        se = 1.0 / np.sqrt(n)
        if self.shrink is not None:
            # SOFT threshold: L -> sign(L) * max(|L| - lambda*se, 0). This is the
            # principled middle ground between keeping an entry whole (hard
            # threshold) and deleting it.
            # NOTE: a *global* multiplicative shrink would be a no-op here, because
            # gross exposure is renormalised afterwards. Shrinkage must be nonlinear.
            L1 = np.sign(L1) * np.maximum(np.abs(L1) - self.shrink * se, 0.0)
        if self.signif_se > 0:
            L1[np.abs(L1) < self.signif_se * se] = 0.0

        sig = L1.T @ Zp[:, -1]

        if self.lag2_w > 0 and T > 3:
            L2, n2 = leadlag(Zp, Z, 2)
            if self.algo_lead:
                np.fill_diagonal(L2[:50], 0.0)
            else:
                np.fill_diagonal(L2, 0.0)
            L2[np.abs(L2) < self.signif_se / np.sqrt(n2)] = 0.0
            sig2 = L2.T @ Zp[:, -2]
            sig = sig / (sig.std() + 1e-12) + self.lag2_w * sig2 / (sig2.std() + 1e-12)

        if self.rev_w > 0:
            rev = -Z[:, -self.rev_lb:].sum(axis=1)
            sig = ((1 - self.rev_w) * sig / (sig.std() + 1e-12)
                   + self.rev_w * rev / (rev.std() + 1e-12))

        sig = sig - sig.mean()

        if self.sig_ewma > 0 and self.prev_sig is not None:
            sig = (1 - self.sig_ewma) * sig + self.sig_ewma * self.prev_sig
        self.prev_sig = sig.copy()

        # hysteresis: only flip a position's sign when the signal is convincing.
        # Turnover is pure commission; a weak sign flip is not worth paying for.
        if self.band > 0:
            s_now = np.sign(sig)
            if self.prev_sign is not None:
                thresh = self.band * np.abs(sig).mean()
                weak = np.abs(sig) < thresh
                s_now = np.where(weak, self.prev_sign, s_now)
            self.prev_sign = s_now.copy()
            sig = s_now * np.maximum(np.abs(sig), 1e-12)

        # --- sizing ---
        px = prcSoFar[:, -1]
        raw = sig / sd                                   # mean-variance optimal direction
        if self.power != 1.0:                            # conviction exponent
            raw = np.sign(raw) * np.abs(raw) ** self.power

        if self.exact_cap:
            # Bang-bang in SHARE space: score ~= mu, and maximising
            #   mu = sum_i d_i * E[r_i]   s.t.  |d_i| <= cap
            # is a linear programme whose solution is d_i = cap * sign(pred_i).
            # eval.py's own limit is floor(CAP / price), so take exactly that.
            shares = np.sign(raw) * (CAP / px[1:]).astype(int)
            dollars = shares * px[1:]
        else:
            cap = self.cap_frac * CAP
            dollars = waterfill(raw, cap, self.util * 50 * cap)
            shares = (dollars / px[1:]).astype(int)

        hedge = -dollars.sum() if self.hedge else 0.0
        hedge = np.clip(hedge, -0.999 * ALGO_CAP, 0.999 * ALGO_CAP)

        out = np.zeros(nInst)
        out[1:] = shares
        out[ALGO] = int(hedge / px[ALGO])
        return out.astype(int)
