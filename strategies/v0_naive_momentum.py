"""v0 — the organisers' starter. Naive one-day own-momentum.  eval.py score: 0.10

Recovered from git commit 937a1ac. Kept because it is the strawman the whole
competition is built around, and because our analysis explains exactly why it
cannot work:

  * It buys whatever went up yesterday and sells whatever went down.
  * Own-return lag-1 autocorrelation has a split-half stability of +0.072, i.e.
    the instruments that *look* like they trend do not do it again in the other
    half of the data. It is sample noise.
  * It also accumulates positions (`currentPos + rpos`) rather than targeting a
    holding, so it drifts into whatever the caps allow.

Do not submit. This exists as a baseline and a cautionary tale.
"""
import numpy as np

nInst=51
currentPos = np.zeros(nInst)
def getMyPosition (prcSoFar):
    global currentPos
    (nins,nt) = prcSoFar.shape
    if (nt < 2):
        return np.zeros(nins)
    lastRet = np.log(prcSoFar[:,-1] / prcSoFar[:,-2])
    lNorm = np.sqrt(lastRet.dot(lastRet))
    lastRet /= lNorm
    rpos = np.array([int(x) for x in 5000 * lastRet / prcSoFar[:,-1]])
    currentPos = np.array([int(x) for x in currentPos+rpos])
    return currentPos
