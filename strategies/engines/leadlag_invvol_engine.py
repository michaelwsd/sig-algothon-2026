"""Configurable lead-lag strategy engine, used for research.

The submission (too_much_alpha.py) is a frozen, self-contained copy of the chosen
configuration. This file exists so the backtester can compare variants.

Pipeline, all estimated causally from prcSoFar only, refit every day:
  1. log returns
  2. market beta on ALGO (optionally shrunk toward 1)
  3. residual (market-neutral) returns
  4. optional sector neutralisation (remove top-k residual principal components)
  5. lead-lag matrix L[i,j] = corr(resid_i today, resid_j tomorrow)
       - optional significance thresholding
       - optional SVD rank truncation (denoising)
  6. prediction, optional blend with a cross-sectional reversal sleeve
  7. size by prediction / residual-vol (mean-variance optimal when residuals are
     near-independent, which section 6 of the analysis established)
  8. hedge net market exposure with ALGO
  9. optional day-to-day position smoothing
"""
import numpy as np

ALGO = 0
CAP = 10_000
ALGO_CAP = 100_000


class LeadLag:
    def __init__(self, signif_se=0.0, beta_shrink=0.0, rank=0, sector_k=0,
                 smooth=1.0, rev_w=0.0, rev_lb=20, est_window=0,
                 scale_mode="max", gross_frac=0.60, target_frac=0.95, min_days=60):
        self.signif_se = signif_se     # zero lead-lag entries within this many s.e.
        self.beta_shrink = beta_shrink # shrink betas this fraction toward 1.0
        self.rank = rank               # SVD rank truncation of L (0 = off)
        self.sector_k = sector_k       # remove this many residual PCs (0 = off)
        self.smooth = smooth           # EWMA weight on today's target (1 = off)
        self.rev_w = rev_w             # weight on the reversal sleeve (0 = off)
        self.rev_lb = rev_lb
        self.est_window = est_window   # 0 = expanding, else rolling window length
        self.scale_mode = scale_mode   # "max" or "gross"
        self.gross_frac = gross_frac
        self.target_frac = target_frac
        self.min_days = min_days
        self.reset()

    def reset(self):
        self.prev = None

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _neutralise(Rz, k):
        """Remove the top-k principal components from standardised residuals."""
        T = Rz.shape[1]
        Cm = Rz @ Rz.T / T
        _, V = np.linalg.eigh(Cm)
        V = V[:, ::-1][:, :k]              # top-k eigenvectors
        F = V.T @ Rz                       # (k, T) factor time series
        Bf = (Rz @ F.T) @ np.linalg.inv(F @ F.T)
        return Rz - Bf @ F

    # ---------------------------------------------------------------- main
    def __call__(self, prcSoFar):
        nInst, t = prcSoFar.shape
        r = np.diff(np.log(prcSoFar), axis=1)
        if self.est_window:
            r = r[:, -self.est_window:]
        T = r.shape[1]
        if T < self.min_days:
            return np.zeros(nInst, dtype=int)

        # --- market beta and residuals ---
        algo = r[ALGO]
        betas = (r @ algo) / (algo.var() * T)
        betas = betas + self.beta_shrink * (1.0 - betas)
        resid = r - np.outer(betas, algo)

        R = resid[1:]                                  # (50, T) alpha universe
        resid_vol = R.std(axis=1)
        resid_vol[resid_vol < 1e-12] = 1e-12

        sd = R.std(axis=1, keepdims=True); sd[sd < 1e-12] = 1e-12
        Z = (R - R.mean(axis=1, keepdims=True)) / sd

        if self.sector_k:
            Z = self._neutralise(Z, self.sector_k)
            s2 = Z.std(axis=1, keepdims=True); s2[s2 < 1e-12] = 1e-12
            Z = Z / s2

        # --- lead-lag matrix ---
        today, tomo = Z[:, :-1], Z[:, 1:]
        n = today.shape[1]
        L = today @ tomo.T / n
        np.fill_diagonal(L, 0.0)

        if self.signif_se > 0:
            L[np.abs(L) < self.signif_se / np.sqrt(n)] = 0.0
        if 0 < self.rank < L.shape[0]:
            U, S, Vt = np.linalg.svd(L)
            L = (U[:, :self.rank] * S[:self.rank]) @ Vt[:self.rank]

        # --- prediction ---
        sig = L.T @ Z[:, -1]

        if self.rev_w > 0:
            rev = -Z[:, -self.rev_lb:].sum(axis=1)
            sig = ((1 - self.rev_w) * sig / (sig.std() + 1e-12)
                   + self.rev_w * rev / (rev.std() + 1e-12))
        sig = sig - sig.mean()                          # dollar-neutral signal

        # --- sizing: mean-variance optimal reduces to prediction / vol ---
        dollars = sig / resid_vol
        if self.scale_mode == "max":
            m = np.abs(dollars).max()
            if m > 0:
                dollars *= (self.target_frac * CAP) / m
        else:                                           # fixed gross exposure
            g = np.abs(dollars).sum()
            if g > 0:
                dollars *= (self.gross_frac * 50 * self.target_frac * CAP) / g
            dollars = np.clip(dollars, -self.target_frac * CAP, self.target_frac * CAP)

        # --- ALGO hedge for net market exposure ---
        hedge = -np.dot(dollars, betas[1:])
        hedge = np.clip(hedge, -self.target_frac * ALGO_CAP, self.target_frac * ALGO_CAP)

        dvec = np.zeros(nInst)
        dvec[1:] = dollars
        dvec[ALGO] = hedge
        target = dvec / prcSoFar[:, -1]

        if self.prev is not None and self.smooth < 1.0:
            target = self.smooth * target + (1 - self.smooth) * self.prev
        self.prev = target
        return target.astype(int)
