"""
Technical pricing module.
Converts stochastic simulation output into insurance pricing metrics.
"""
import math
import logging

import numpy as np

from app.services.stochastic import RETURN_PERIODS

logger = logging.getLogger(__name__)

DEFAULT_COST_OF_CAPITAL = 0.10
DEFAULT_EXPENSE_LOAD = 0.15


def compute_technical_price(
    tiv: float,
    blended_result: dict,
    cost_of_capital: float = DEFAULT_COST_OF_CAPITAL,
    expense_load: float = DEFAULT_EXPENSE_LOAD,
) -> dict:
    total_aal = blended_result.get("all_perils", {}).get("total_aal", 0)
    technical_rate = total_aal / tiv if tiv > 0 else 0

    peril_breakdown = {}
    for peril in ["seismic", "flood", "wind"]:
        pdata = blended_result.get(peril, {})
        p_aal = pdata.get("blended_aal", 0)
        p_rate = p_aal / tiv if tiv > 0 else 0
        oep_250 = pdata.get("blended_oep", {}).get("250", 0)
        oep_500 = pdata.get("blended_oep", {}).get("500", 0)

        cv = _estimate_cv_from_ep(p_aal, oep_250)
        risk_load_factor = cv * cost_of_capital
        loaded_rate = p_rate * (1.0 + risk_load_factor + expense_load)

        peril_breakdown[peril] = {
            "aal": round(p_aal, 2),
            "technical_rate_pct": round(p_rate * 100, 4),
            "cv": round(cv, 3),
            "risk_load_factor": round(risk_load_factor, 4),
            "loaded_rate_pct": round(loaded_rate * 100, 4),
            "oep_100": pdata.get("blended_oep", {}).get("100", 0),
            "oep_250": oep_250,
            "oep_500": oep_500,
            "premium": round(loaded_rate * tiv, 2),
        }

    total_premium = sum(p["premium"] for p in peril_breakdown.values())
    total_loaded_rate = total_premium / tiv if tiv > 0 else 0

    oep_all = blended_result.get("all_perils", {}).get("total_oep", {})
    total_cv = _estimate_cv_from_ep(total_aal, float(oep_all.get("250", 0)))
    total_risk_load = total_cv * cost_of_capital

    return {
        "tiv": tiv,
        "total_aal": round(total_aal, 2),
        "technical_rate_pct": round(technical_rate * 100, 4),
        "total_cv": round(total_cv, 3),
        "total_risk_load_factor": round(total_risk_load, 4),
        "total_loaded_rate_pct": round(total_loaded_rate * 100, 4),
        "total_premium": round(total_premium, 2),
        "expense_load_pct": round(expense_load * 100, 2),
        "cost_of_capital_pct": round(cost_of_capital * 100, 2),
        "peril_breakdown": peril_breakdown,
        "pml": {
            str(rp): round(float(oep_all.get(str(rp), 0)), 2) for rp in RETURN_PERIODS
        },
    }


def _estimate_cv_from_ep(aal: float, oep_250: float) -> float:
    if aal <= 0:
        return 0.0
    sigma_approx = max(oep_250 - aal, aal * 0.5)
    return sigma_approx / aal


def build_ep_curve_data(blended_result: dict) -> dict:
    curves = {}
    for peril in ["seismic", "flood", "wind"]:
        pdata = blended_result.get(peril, {})
        oep_points = []
        aep_points = []
        for rp in RETURN_PERIODS:
            prob = 1.0 / rp
            oep_val = pdata.get("blended_oep", {}).get(str(rp), 0)
            aep_val = pdata.get("blended_aep", {}).get(str(rp), 0)
            oep_points.append({"return_period": rp, "probability": round(prob, 6), "loss": round(float(oep_val), 2)})
            aep_points.append({"return_period": rp, "probability": round(prob, 6), "loss": round(float(aep_val), 2)})

        model_curves = []
        for m in pdata.get("models", []):
            m_oep = []
            for rp in RETURN_PERIODS:
                m_oep.append({"return_period": rp, "loss": round(float(m["oep"].get(str(rp), 0)), 2)})
            model_curves.append({"model_id": m["model_id"], "label": m["label"], "weight": m["weight"], "oep": m_oep})

        curves[peril] = {"oep": oep_points, "aep": aep_points, "models": model_curves}

    all_oep = blended_result.get("all_perils", {}).get("total_oep", {})
    total_points = []
    for rp in RETURN_PERIODS:
        total_points.append({
            "return_period": rp,
            "probability": round(1.0 / rp, 6),
            "loss": round(float(all_oep.get(str(rp), 0)), 2),
        })
    curves["all_perils"] = {"oep": total_points}

    return curves
