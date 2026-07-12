"""Engine6 = v2 + GLS whitening of the PREDICTOR.

VERDICT (tested): SHELF, do not ship. Walk-forward selection/holdout peak at a=0.92
(eval 500.6 vs v2 480.65), but the FROZEN test (fit C0 on days 1-250, trade 251-500
blind — the best proxy for the live drop) gives a=0.9 -> 345.5 vs v2's 355.7. C0^-1
amplifies the noisiest eigen-directions, so a stale frozen C0 hurts. Sound theory,
real offline gain, rejected by the one test that mimics live. Kept as a documented
candidate to RE-TEST on the Jul 16 data, not to ship on offline numbers.


v2 computes sig = L' z, where L[i,j] = corr(z_i[t], z_j[t+1]). That is a MARGINAL
(univariate-screen) estimator. The VAR(1) regression coefficient is

    A = E[z[t+1] z[t]'] E[z[t] z[t]']^-1 = L' C0^-1

so the correct signal is L' (C0^-1 z) -- i.e. whiten today's cross-section before
propagating it through L. v2 implicitly assumes C0 = I, justified in CLAUDE.md by
"average pairwise correlation is -0.010 after hedging". But average correlation ~0
does NOT imply C0 ~ I: the residuals still carry TWO sector factors (eigenvalues
4.03 and 2.75 vs an MP noise ceiling of 1.73). So the assumption is false.

Intuition: if two names in the same sector both jumped today, the marginal estimator
double-counts the shared sector move. Whitening propagates each name's DISTINCTIVE
move instead.

C0^-1 amplifies small-eigenvalue directions, which are the noisiest, so we shrink:
    C0_a = (1-a) C0 + a I,   a in [0,1],   a=1 recovers v2 exactly.
"""
import numpy as np

ALGO = 0
CAP = 10_000.0
ALGO_CAP = 100_000.0


class Engine6:
    def __init__(self, signif_se=1.0, rev_w=0.25, rev_lb=20, band=0.30, min_days=60,
                 whiten=1.0, whiten_rev=False, hedge_w=1.0):
        self.signif_se, self.rev_w, self.rev_lb = signif_se, rev_w, rev_lb
        self.band, self.min_days, self.hedge_w = band, min_days, hedge_w
        self.whiten = whiten          # a: 1.0 = v2 (no whitening), 0.0 = full GLS
        self.whiten_rev = whiten_rev  # also whiten the reversal sleeve's input
        self.reset()

    def reset(self):
        self.prev_sign = None

    def __call__(self, prcSoFar):
        nInst, t = prcSoFar.shape
        r = np.diff(np.log(prcSoFar), axis=1)
        T = r.shape[1]
        if T < self.min_days:
            return np.zeros(nInst, dtype=int)

        R = (r - r[ALGO])[1:]
        sd = R.std(axis=1); sd[sd < 1e-12] = 1e-12
        Z = (R - R.mean(axis=1, keepdims=True)) / sd[:, None]

        today, tomo = Z[:, :-1], Z[:, 1:]
        n = today.shape[1]
        L = today @ tomo.T / n
        np.fill_diagonal(L, 0.0)
        L[np.abs(L) < self.signif_se / np.sqrt(n)] = 0.0

        # --- GLS: whiten today's cross-section before propagating through L ---
        x = Z[:, -1]
        if self.whiten < 1.0:
            C0 = (Z @ Z.T) / Z.shape[1]
            a = self.whiten
            Ca = (1 - a) * C0 + a * np.eye(50)
            x = np.linalg.solve(Ca, x)
        sig_ll = L.T @ x

        rv = Z[:, -self.rev_lb:].sum(axis=1)
        if self.whiten_rev and self.whiten < 1.0:
            C0 = (Z @ Z.T) / Z.shape[1]
            a = self.whiten
            rv = np.linalg.solve((1 - a) * C0 + a * np.eye(50), rv)
        sig_rev = -rv

        sig = ((1 - self.rev_w) * sig_ll / (sig_ll.std() + 1e-12)
               + self.rev_w * sig_rev / (sig_rev.std() + 1e-12))
        sig = sig - sig.mean()

        sign = np.sign(sig)
        if self.band > 0 and self.prev_sign is not None:
            weak = np.abs(sig) < self.band * np.abs(sig).mean()
            sign = np.where(weak, self.prev_sign, sign)
        self.prev_sign = sign.copy()

        px = prcSoFar[:, -1]
        shares = sign * (CAP / px[1:]).astype(int)
        dollars = shares * px[1:]
        hedge = np.clip(-self.hedge_w * dollars.sum(), -0.999 * ALGO_CAP, 0.999 * ALGO_CAP)
        out = np.zeros(nInst)
        out[1:] = shares
        out[ALGO] = int(hedge / px[ALGO])
        return out.astype(int)
