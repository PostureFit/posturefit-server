def calculate_bmi(berat_kg: float, tinggi_cm: float) -> float:
    tinggi_m = tinggi_cm / 100.0
    if tinggi_m <= 0:
        return 0.0
    return round(berat_kg / (tinggi_m ** 2), 1)


def calculate_whtr(lingkar_perut_cm: float, tinggi_cm: float) -> float:
    if tinggi_cm <= 0:
        return 0.0
    return round(lingkar_perut_cm / tinggi_cm, 3)