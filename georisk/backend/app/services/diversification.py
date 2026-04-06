"""
Portfolio diversification module.
Computes marginal PML contribution, diversification benefit, and concentration index.
"""
import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


def compute_diversification(
    property_results: list[dict],
    return_period: int = 250,
) -> dict:
    if not property_results:
        return {"error": "No properties"}

    standalone_pmls = []
    property_ids = []
    aals = []

    for pr in property_results:
        pid = pr.get("property_id", 0)
        property_ids.append(pid)
        pml = 0.0
        aal = 0.0
        for peril in ["seismic", "flood", "wind"]:
            pdata = pr.get("blended", {}).get(peril, {})
            pml += float(pdata.get("blended_oep", {}).get(str(return_period), 0))
            aal += float(pdata.get("blended_aal", 0))
        standalone_pmls.append(pml)
        aals.append(aal)

    standalone_pmls_arr = np.array(standalone_pmls)
    aals_arr = np.array(aals)

    sum_standalone = float(np.sum(standalone_pmls_arr))

    n = len(standalone_pmls)
    corr_factor = 0.3
    portfolio_pml = float(np.sqrt(np.sum(standalone_pmls_arr ** 2) +
                                   2 * corr_factor * np.sum(
                                       standalone_pmls_arr[i] * standalone_pmls_arr[j]
                                       for i in range(n) for j in range(i + 1, n)
                                   )))

    diversification_benefit = max(0, sum_standalone - portfolio_pml)
    diversification_pct = diversification_benefit / sum_standalone * 100 if sum_standalone > 0 else 0

    marginals = []
    for i, (pid, sa_pml, aal) in enumerate(zip(property_ids, standalone_pmls, aals)):
        remaining = np.delete(standalone_pmls_arr, i)
        if len(remaining) > 0:
            portfolio_without = float(np.sqrt(np.sum(remaining ** 2) +
                                              2 * corr_factor * np.sum(
                                                  remaining[ii] * remaining[jj]
                                                  for ii in range(len(remaining))
                                                  for jj in range(ii + 1, len(remaining))
                                              )))
        else:
            portfolio_without = 0.0

        marginal = portfolio_pml - portfolio_without
        share_of_benefit = (sa_pml / sum_standalone * diversification_benefit) if sum_standalone > 0 else 0
        diversified_pml = sa_pml - share_of_benefit

        marginals.append({
            "property_id": pid,
            "standalone_pml": round(sa_pml, 2),
            "marginal_pml": round(marginal, 2),
            "diversified_pml": round(diversified_pml, 2),
            "diversification_benefit": round(share_of_benefit, 2),
            "aal": round(float(aal), 2),
            "pml_share_pct": round(sa_pml / sum_standalone * 100, 2) if sum_standalone > 0 else 0,
        })

    tivs = [pr.get("tiv", 0) for pr in property_results]
    hhi = _herfindahl_index(tivs)

    return {
        "return_period": return_period,
        "portfolio_pml": round(portfolio_pml, 2),
        "sum_standalone_pml": round(sum_standalone, 2),
        "diversification_benefit": round(diversification_benefit, 2),
        "diversification_pct": round(diversification_pct, 2),
        "portfolio_aal": round(float(np.sum(aals_arr)), 2),
        "hhi_concentration": round(hhi, 4),
        "n_properties": n,
        "accounts": sorted(marginals, key=lambda x: x["standalone_pml"], reverse=True),
    }


def _herfindahl_index(values: list[float]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    shares = [v / total for v in values]
    return sum(s * s for s in shares)
