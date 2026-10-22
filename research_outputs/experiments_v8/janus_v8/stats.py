import numpy as np
from scipy.stats import beta


def paired_binary(a, b, alpha=0.05):
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    if len(a) != len(b) or not len(a):
        raise ValueError('Nonempty, exactly paired observations required')
    n = len(a)
    w, l = int(np.sum(a & ~b)), int(np.sum(b & ~a))
    def lower(k):
        return float(beta.ppf(alpha/4, k, n-k+1)) if k else 0.0
    def upper(k):
        return float(beta.ppf(1-alpha/4, k+1, n-k)) if k < n else 1.0
    return dict(n=n, wins=w, losses=l, mean=(w-l)/n,
                lo=lower(w)-upper(l), hi=upper(w)-lower(l), alpha=alpha,
                method='conservative simultaneous Clopper-Pearson marginals')


def paired_bootstrap(differences, seed=20261019, replicates=5000, alpha=0.05):
    d = np.asarray(differences, dtype=float)
    if not len(d) or not np.isfinite(d).all():
        raise ValueError('Finite, nonempty question-level differences required')
    rng = np.random.default_rng(seed)
    # Batched draws bound memory and preserve one declared RNG sequence.
    means = []
    for start in range(0, replicates, 100):
        ix = rng.integers(0, len(d), (min(100, replicates-start), len(d)))
        means.extend(d[ix].mean(axis=1).tolist())
    lo, hi = np.quantile(means, [alpha/2, 1-alpha/2])
    return dict(n=len(d), mean=float(d.mean()), lo=float(lo), hi=float(hi),
                seed=seed, replicates=replicates, alpha=alpha,
                method='paired question-cluster percentile bootstrap')
