from dataclasses import dataclass, field
from typing import Dict, List, Tuple


CRITERIA_WEIGHTS: Dict[str, float] = {
    "bmi":    0.35,
    "whtr":   0.25,
    "wsr":    0.20,
    "lingkar": 0.12,
    "umur":   0.08,
}

CRITERIA_TYPE: Dict[str, str] = {
    "bmi":    "benefit",
    "whtr":   "benefit",
    "wsr":    "benefit",
    "lingkar": "benefit",
    "umur":   "cost",
}


# ---------------------------------------------------------------------------
# Recommendation catalog per body category
# ---------------------------------------------------------------------------
RECOMMENDATIONS: Dict[str, str] = {
    "Obesitas": (
        "Fokus pada defisit kalori (500–700 kkal/hari). "
        "Latihan low-impact: jalan cepat 30 menit/hari, swimming, atau cycling. "
        "Kurangi karbohidrat olahan, perbanyak serat dan protein tanpa lemak."
    ),
    "Skinnyfat": (
        "Body recomposition: latihan beban 3–4×/minggu (compound movements). "
        "Asupan protein tinggi (1.6–2.2 g/kg BB). "
        "Cardio ringan 2×/minggu untuk menjaga kesehatan kardiovaskular."
    ),
    "Kurus": (
        "Surplus kalori 300–500 kkal/hari dengan makanan padat nutrisi. "
        "Latihan beban progresif 3×/minggu (fokus compound lifts). "
        "Tidur cukup 7–9 jam untuk pemulihan optimal."
    ),
    "Normal": (
        "Maintenance & hipertrofi: latihan beban 4×/minggu. "
        "Pertahankan asupan protein 1.4–1.8 g/kg BB. "
        "Cardio moderat 2–3×/minggu untuk kesehatan jantung."
    ),
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class SawAlternative:
    """A single alternative (body category) in the decision matrix."""
    name: str
    raw_scores: Dict[str, float] = field(default_factory=dict)
    norm_scores: Dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0


# ---------------------------------------------------------------------------
# Main SAW function
# ---------------------------------------------------------------------------
def calculate_saw(
    bmi: float,
    whtr: float,
    umur: int,
    lingkar_perut_cm: float,
    wsr: float = 0.0,
) -> Tuple[str, str, Dict[str, float]]:
    alternatives: List[SawAlternative] = [
        SawAlternative(
            name="Obesitas",
            raw_scores={
                "bmi":     _suitability(bmi,             30.0, 50.0),
                "whtr":    _suitability(whtr,             0.60, 1.00),
                "wsr":     _suitability(wsr,              0.85, 1.00),
                "lingkar": _suitability(lingkar_perut_cm, 90.0, 150.0),
                "umur":    1.0,
            },
        ),
        SawAlternative(
            name="Skinnyfat",
            raw_scores={
                "bmi":     _suitability(bmi,             18.5, 24.9),
                "whtr":    _suitability(whtr,             0.50, 0.59),
                "wsr":     _suitability(wsr,              0.75, 0.90),
                "lingkar": _suitability(lingkar_perut_cm, 75.0, 89.9),
                "umur":    1.0,
            },
        ),
        SawAlternative(
            name="Kurus",
            raw_scores={
                "bmi":     _suitability(bmi,             10.0, 18.4),
                "whtr":    _suitability(whtr,             0.30, 0.49),
                "wsr":     _suitability(wsr,              0.40, 0.65),
                "lingkar": _suitability(lingkar_perut_cm, 40.0, 74.9),
                "umur":    1.0,
            },
        ),
        SawAlternative(
            name="Normal",
            raw_scores={
                "bmi":     _suitability(bmi,             18.5, 24.9),
                "whtr":    _suitability(whtr,             0.40, 0.49),
                "wsr":     _suitability(wsr,              0.60, 0.80),
                "lingkar": _suitability(lingkar_perut_cm, 60.0, 89.9),
                "umur":    1.0,
            },
        ),
    ]

    criteria = list(CRITERIA_WEIGHTS.keys())
    max_vals = {c: max(a.raw_scores[c] for a in alternatives) for c in criteria}

    for alt in alternatives:
        for c in criteria:
            if max_vals[c] != 0:
                alt.norm_scores[c] = alt.raw_scores[c] / max_vals[c]
            else:
                alt.norm_scores[c] = 0.0

    for alt in alternatives:
        alt.final_score = round(
            sum(alt.norm_scores[c] * CRITERIA_WEIGHTS[c] for c in criteria), 4
        )

    winner = max(alternatives, key=lambda a: a.final_score)
    scores_dict = {alt.name: alt.final_score for alt in alternatives}

    return winner.name, RECOMMENDATIONS[winner.name], scores_dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _suitability(value: float, lo: float, hi: float) -> float:
    """
    Menghitung seberapa cocok 'value' masuk ke dalam rentang [lo, hi].
    Return 1.0 jika masuk rentang. Jika di luar, nilainya berkurang mendekati 0.
    """
    if lo <= value <= hi:
        return 1.0
    
    dist = min(abs(value - lo), abs(value - hi))
    range_span = max(hi - lo, 5.0) # minimal span 5 agar penalti tidak terlalu ekstrem
    
    # Skor berkurang seiring jauhnya jarak dari rentang ideal
    return max(0.0, 1.0 - (dist / range_span))

