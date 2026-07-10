import math
from typing import List, Dict, Any


def distance_2d(ax: float, ay: float, bx: float, by: float) -> float:
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def angle_between(a: Dict[str, float], b: Dict[str, float], c: Dict[str, float]) -> float:
    ab = (a["x"] - b["x"], a["y"] - b["y"])
    cb = (c["x"] - b["x"], c["y"] - b["y"])
    dot = ab[0] * cb[0] + ab[1] * cb[1]
    mag_ab = math.sqrt(ab[0] ** 2 + ab[1] ** 2)
    mag_cb = math.sqrt(cb[0] ** 2 + cb[1] ** 2)
    if mag_ab == 0 or mag_cb == 0:
        return 0.0
    cos_theta = max(-1.0, min(1.0, dot / (mag_ab * mag_cb)))
    return math.degrees(math.acos(cos_theta))


def compute_wsr(landmarks: Dict[int, Dict[str, float]]) -> float:
    ls = landmarks.get(11)
    rs = landmarks.get(12)
    lh = landmarks.get(23)
    rh = landmarks.get(24)
    if not all([ls, rs, lh, rh]):
        return 0.0
    shoulder_w = distance_landd(ls["x"], ls["y"], rs["x"], rs["y"])
    waist_w = distance_landd(lh["x"], lh["y"], rh["x"], rh["y"])
    if shoulder_w == 0:
        return 0.0
    return round(waist_w / shoulder_w, 3)


def distance_landd(ax: float, ay: float, bx: float, by: float) -> float:
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def compute_shoulder_balance(landmarks: List[Dict[str, Any]]) -> float:
    left_shoulder = None
    right_shoulder = None
    for lm in landmarks:
        if lm["index"] == 11:
            left_shoulder = lm
        elif lm["index"] == 12:
            right_shoulder = lm
    if not left_shoulder or not right_shoulder:
        return 0.0
    return round(abs(left_shoulder["y"] - right_shoulder["y"]), 3)


def compute_posture_score(landmarks: List[Dict[str, Any]]) -> float:
    nose = None
    left_ear = None
    right_ear = None
    mid_shoulder_y = 0.0
    count = 0
    for lm in landmarks:
        if lm["index"] == 0:
            nose = lm
        elif lm["index"] == 7:
            left_ear = lm
        elif lm["index"] == 8:
            right_ear = lm
        elif lm["index"] in (11, 12):
            mid_shoulder_y += lm["y"]
            count += 1
    if not nose or not left_ear or not right_ear or count == 0:
        return 50.0
    mid_shoulder_y /= count
    ear_y = (left_ear["y"] + right_ear["y"]) / 2
    head_forward = abs(nose["x"] - (left_ear["x"] + right_ear["x"]) / 2)
    score = 100.0 - (head_forward * 50 + abs(ear_y - mid_shoulder_y) * 30)
    return round(max(0.0, min(100.0, score)), 1)