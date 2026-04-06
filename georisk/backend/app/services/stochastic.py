"""
Multi-model stochastic engine.
Three parametric hazard models per peril, each producing a 10,000-year event table.
Models are blended at the EP-curve level with configurable weights.
"""
import logging
from dataclasses import dataclass, field

import numpy as np

from app.services.vulnerability import seismic_mdr, flood_mdr, wind_mdr

logger = logging.getLogger(__name__)

RETURN_PERIODS = [10, 25, 50, 100, 250, 500, 1000]

INTENSITY_UNITS = {"seismic": "g", "flood": "ft", "wind": "mph"}

MODEL_PARAMS = {
    "seismic": {
        "conservative": {"freq_mult": 1.3, "intensity_mult": 1.2, "label": "Conservative"},
        "best_estimate": {"freq_mult": 1.0, "intensity_mult": 1.0, "label": "Best Estimate"},
        "optimistic": {"freq_mult": 0.7, "intensity_mult": 0.85, "label": "Optimistic"},
    },
    "flood": {
        "conservative": {"freq_mult": 1.4, "intensity_mult": 1.25, "label": "Conservative"},
        "best_estimate": {"freq_mult": 1.0, "intensity_mult": 1.0, "label": "Best Estimate"},
        "optimistic": {"freq_mult": 0.65, "intensity_mult": 0.8, "label": "Optimistic"},
    },
    "wind": {
        "conservative": {"freq_mult": 1.25, "intensity_mult": 1.15, "label": "Conservative"},
        "best_estimate": {"freq_mult": 1.0, "intensity_mult": 1.0, "label": "Best Estimate"},
        "optimistic": {"freq_mult": 0.75, "intensity_mult": 0.9, "label": "Optimistic"},
    },
}

DEFAULT_BLEND_WEIGHTS = {"conservative": 0.25, "best_estimate": 0.50, "optimistic": 0.25}


@dataclass
class LocationHazard:
    base_seismic_freq: float = 0.0
    base_seismic_pga: float = 0.0
    base_flood_freq: float = 0.0
    base_flood_depth: float = 0.0
    base_wind_freq: float = 0.0
    base_wind_speed: float = 0.0


@dataclass
class EventTableResult:
    peril: str
    model_id: str
    n_years: int
    aal: float
    annual_losses: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))
    oep: dict = field(default_factory=dict)
    aep: dict = field(default_factory=dict)
    params_used: dict = field(default_factory=dict)
    intensity_unit: str = ""
    event_sample: list[dict] = field(default_factory=list)


class _EventSampler:
    def __init__(self, rng: np.random.Generator, top_k: int = 200, random_k: int = 200):
        self._rng = rng
        self._top_k = int(max(0, top_k))
        self._random_k = int(max(0, random_k))
        self._top: list[tuple[float, dict]] = []
        self._random: list[dict] = []
        self._seen = 0

    def consider(self, loss: float, record: dict) -> None:
        self._seen += 1

        if self._top_k > 0:
            if len(self._top) < self._top_k:
                self._top.append((loss, record))
            else:
                min_i = 0
                min_loss = self._top[0][0]
                for i in range(1, len(self._top)):
                    if self._top[i][0] < min_loss:
                        min_loss = self._top[i][0]
                        min_i = i
                if loss > min_loss:
                    self._top[min_i] = (loss, record)

        if self._random_k > 0:
            if len(self._random) < self._random_k:
                self._random.append(record)
            else:
                j = int(self._rng.integers(0, self._seen))
                if j < self._random_k:
                    self._random[j] = record

    def sampled(self) -> list[dict]:
        top_sorted = [r for _, r in sorted(self._top, key=lambda t: t[0], reverse=True)]
        top_keys = {(r.get("year"), r.get("event_index")) for r in top_sorted}
        random_unique = [r for r in self._random if (r.get("year"), r.get("event_index")) not in top_keys]
        return top_sorted + random_unique


def _base_hazard_for_location(lat: float, lon: float, pga: float,
                               flood_zone: str, wind_prob: float) -> LocationHazard:
    if pga >= 0.6:
        eq_freq = 0.08
    elif pga >= 0.3:
        eq_freq = 0.04
    elif pga >= 0.1:
        eq_freq = 0.015
    else:
        eq_freq = 0.005

    flood_freq_map = {"V": 0.05, "VE": 0.05, "A": 0.02, "AE": 0.025,
                      "AH": 0.02, "AO": 0.018, "B": 0.005, "X": 0.002,
                      "C": 0.001, "D": 0.008}
    fl_freq = flood_freq_map.get(flood_zone, 0.002)

    base_depth_map = {"V": 8.0, "VE": 9.0, "A": 5.0, "AE": 6.0,
                      "AH": 3.0, "AO": 2.5, "B": 1.5, "X": 0.5,
                      "C": 0.3, "D": 2.0}
    fl_depth = base_depth_map.get(flood_zone, 0.5)

    wind_freq = max(0.001, wind_prob / 100.0 * 0.06)
    if wind_prob > 60:
        base_speed = 120.0
    elif wind_prob > 30:
        base_speed = 95.0
    elif wind_prob > 10:
        base_speed = 75.0
    else:
        base_speed = 50.0

    return LocationHazard(
        base_seismic_freq=eq_freq,
        base_seismic_pga=max(pga, 0.01),
        base_flood_freq=fl_freq,
        base_flood_depth=fl_depth,
        base_wind_freq=wind_freq,
        base_wind_speed=base_speed,
    )


def _generate_seismic_events(hazard: LocationHazard, model_params: dict,
                              tiv: float, construction: str,
                              n_years: int, rng: np.random.Generator,
                              collect_events: bool = False,
                              sampler: _EventSampler | None = None) -> EventTableResult:
    freq = hazard.base_seismic_freq * model_params["freq_mult"]
    base_pga = hazard.base_seismic_pga * model_params["intensity_mult"]
    annual_losses = np.zeros(n_years)
    ln_sigma = 0.6

    for yr in range(n_years):
        n_events = rng.poisson(freq)
        yr_total_loss = 0.0
        for ei in range(int(n_events)):
            pga = float(rng.lognormal(np.log(base_pga), ln_sigma))
            dmg = seismic_mdr(pga, construction)
            dr = float(rng.normal(dmg.mean_dr, dmg.sigma_dr))
            dr = max(0.0, min(1.0, dr))
            loss = dr * tiv
            yr_total_loss += loss
            if collect_events and sampler is not None:
                sampler.consider(loss, {
                    "year": int(yr + 1),
                    "event_index": int(ei + 1),
                    "intensity": float(pga),
                    "mean_dr": float(dmg.mean_dr),
                    "dr": float(dr),
                    "loss": float(loss),
                })
        annual_losses[yr] = yr_total_loss

    return _build_result(
        "seismic",
        model_params.get("_id", ""),
        n_years,
        annual_losses,
        params_used={
            "freq": float(freq),
            "base_pga": float(base_pga),
            "ln_sigma": float(ln_sigma),
            "freq_mult": float(model_params["freq_mult"]),
            "intensity_mult": float(model_params["intensity_mult"]),
        },
        intensity_unit=INTENSITY_UNITS["seismic"],
        event_sample=sampler.sampled() if (collect_events and sampler is not None) else [],
    )


def _generate_flood_events(hazard: LocationHazard, model_params: dict,
                            tiv: float, occupancy: str, stories: int,
                            n_years: int, rng: np.random.Generator,
                            collect_events: bool = False,
                            sampler: _EventSampler | None = None) -> EventTableResult:
    freq = hazard.base_flood_freq * model_params["freq_mult"]
    base_depth = hazard.base_flood_depth * model_params["intensity_mult"]
    annual_losses = np.zeros(n_years)
    ln_sigma = 0.7

    for yr in range(n_years):
        n_events = rng.poisson(freq)
        yr_total = 0.0
        for ei in range(int(n_events)):
            depth = float(rng.lognormal(np.log(max(base_depth, 0.1)), ln_sigma))
            dmg = flood_mdr(depth, stories, occupancy)
            dr = float(rng.normal(dmg.mean_dr, dmg.sigma_dr))
            dr = max(0.0, min(1.0, dr))
            loss = dr * tiv
            yr_total += loss
            if collect_events and sampler is not None:
                sampler.consider(loss, {
                    "year": int(yr + 1),
                    "event_index": int(ei + 1),
                    "intensity": float(depth),
                    "mean_dr": float(dmg.mean_dr),
                    "dr": float(dr),
                    "loss": float(loss),
                })
        annual_losses[yr] = yr_total

    return _build_result(
        "flood",
        model_params.get("_id", ""),
        n_years,
        annual_losses,
        params_used={
            "freq": float(freq),
            "base_depth": float(base_depth),
            "ln_sigma": float(ln_sigma),
            "freq_mult": float(model_params["freq_mult"]),
            "intensity_mult": float(model_params["intensity_mult"]),
        },
        intensity_unit=INTENSITY_UNITS["flood"],
        event_sample=sampler.sampled() if (collect_events and sampler is not None) else [],
    )


def _generate_wind_events(hazard: LocationHazard, model_params: dict,
                           tiv: float, construction: str,
                           n_years: int, rng: np.random.Generator,
                           collect_events: bool = False,
                           sampler: _EventSampler | None = None) -> EventTableResult:
    freq = hazard.base_wind_freq * model_params["freq_mult"]
    base_speed = hazard.base_wind_speed * model_params["intensity_mult"]
    annual_losses = np.zeros(n_years)
    weibull_k = 2.5

    for yr in range(n_years):
        n_events = rng.poisson(freq)
        yr_total = 0.0
        for ei in range(int(n_events)):
            speed = float(rng.weibull(weibull_k) * base_speed * 0.7 + 30)
            dmg = wind_mdr(speed, construction)
            dr = float(rng.normal(dmg.mean_dr, dmg.sigma_dr))
            dr = max(0.0, min(1.0, dr))
            loss = dr * tiv
            yr_total += loss
            if collect_events and sampler is not None:
                sampler.consider(loss, {
                    "year": int(yr + 1),
                    "event_index": int(ei + 1),
                    "intensity": float(speed),
                    "mean_dr": float(dmg.mean_dr),
                    "dr": float(dr),
                    "loss": float(loss),
                })
        annual_losses[yr] = yr_total

    return _build_result(
        "wind",
        model_params.get("_id", ""),
        n_years,
        annual_losses,
        params_used={
            "freq": float(freq),
            "base_speed": float(base_speed),
            "weibull_k": float(weibull_k),
            "freq_mult": float(model_params["freq_mult"]),
            "intensity_mult": float(model_params["intensity_mult"]),
        },
        intensity_unit=INTENSITY_UNITS["wind"],
        event_sample=sampler.sampled() if (collect_events and sampler is not None) else [],
    )


def _build_result(peril: str, model_id: str, n_years: int,
                  annual_losses: np.ndarray,
                  params_used: dict | None = None,
                  intensity_unit: str = "",
                  event_sample: list[dict] | None = None) -> EventTableResult:
    aal = float(np.mean(annual_losses))
    sorted_losses = np.sort(annual_losses)[::-1]

    oep = {}
    aep = {}
    for rp in RETURN_PERIODS:
        idx = max(0, int(n_years / rp) - 1)
        idx = min(idx, len(sorted_losses) - 1)
        oep[rp] = float(sorted_losses[idx])
        aep[rp] = float(sorted_losses[idx])

    return EventTableResult(peril=peril, model_id=model_id, n_years=n_years,
                            aal=aal, annual_losses=annual_losses, oep=oep, aep=aep,
                            params_used=params_used or {}, intensity_unit=intensity_unit,
                            event_sample=event_sample or [])


def run_stochastic_for_location(
    lat: float, lon: float, tiv: float,
    construction: str, occupancy: str, stories: int,
    pga: float, flood_zone: str, wind_prob: float,
    n_years: int = 10000, seed: int | None = None,
    collect_events: bool = False,
    top_k_events: int = 200,
    random_k_events: int = 200,
) -> dict:
    rng = np.random.default_rng(seed)
    hazard = _base_hazard_for_location(lat, lon, pga, flood_zone, wind_prob)

    results_by_peril: dict[str, dict[str, EventTableResult]] = {
        "seismic": {}, "flood": {}, "wind": {},
    }

    for model_id, params in MODEL_PARAMS["seismic"].items():
        p = {**params, "_id": model_id}
        sampler = _EventSampler(rng, top_k=top_k_events, random_k=random_k_events) if collect_events else None
        results_by_peril["seismic"][model_id] = _generate_seismic_events(
            hazard, p, tiv, construction, n_years, rng,
            collect_events=collect_events, sampler=sampler)

    for model_id, params in MODEL_PARAMS["flood"].items():
        p = {**params, "_id": model_id}
        sampler = _EventSampler(rng, top_k=top_k_events, random_k=random_k_events) if collect_events else None
        results_by_peril["flood"][model_id] = _generate_flood_events(
            hazard, p, tiv, occupancy, stories, n_years, rng,
            collect_events=collect_events, sampler=sampler)

    for model_id, params in MODEL_PARAMS["wind"].items():
        p = {**params, "_id": model_id}
        sampler = _EventSampler(rng, top_k=top_k_events, random_k=random_k_events) if collect_events else None
        results_by_peril["wind"][model_id] = _generate_wind_events(
            hazard, p, tiv, construction, n_years, rng,
            collect_events=collect_events, sampler=sampler)

    return results_by_peril


def blend_models(results_by_peril: dict, weights: dict | None = None) -> dict:
    w = weights or DEFAULT_BLEND_WEIGHTS
    blended = {}

    for peril, models in results_by_peril.items():
        blended_aal = 0.0
        blended_oep = {rp: 0.0 for rp in RETURN_PERIODS}
        blended_aep = {rp: 0.0 for rp in RETURN_PERIODS}
        model_details = []

        for model_id, result in models.items():
            wt = w.get(model_id, 1.0 / len(models))
            blended_aal += result.aal * wt
            for rp in RETURN_PERIODS:
                blended_oep[rp] += result.oep.get(rp, 0) * wt
                blended_aep[rp] += result.aep.get(rp, 0) * wt
            model_details.append({
                "model_id": model_id,
                "label": MODEL_PARAMS[peril][model_id]["label"],
                "weight": wt,
                "aal": round(result.aal, 2),
                "oep": {str(k): round(v, 2) for k, v in result.oep.items()},
            })

        blended[peril] = {
            "blended_aal": round(blended_aal, 2),
            "blended_oep": {str(k): round(v, 2) for k, v in blended_oep.items()},
            "blended_aep": {str(k): round(v, 2) for k, v in blended_aep.items()},
            "models": model_details,
        }

    total_aal = sum(p["blended_aal"] for p in blended.values())
    blended["all_perils"] = {
        "total_aal": round(total_aal, 2),
        "total_oep": {
            str(rp): round(sum(blended[p]["blended_oep"].get(str(rp), 0) for p in results_by_peril), 2)
            for rp in RETURN_PERIODS
        },
    }

    return blended
