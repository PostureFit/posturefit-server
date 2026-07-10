import numpy as np
import cv2
import mediapipe as mp

from mediapipe_utils import (
    compute_wsr,
    compute_shoulder_balance,
    compute_posture_score,
)

mp_pose = mp.solutions.pose

# Landmark topology (COCO, 33 landmarks)
SKELETON_CONNECTIONS = [
    (11, 12),  # shoulders
    (11, 23),  # left shoulder → hip
    (12, 24),  # right shoulder → hip
    (23, 24),  # hips
    (11, 13), (13, 15),  # left arm
    (12, 14), (14, 16),  # right arm
    (23, 25), (25, 27),  # left leg
    (24, 26), (26, 28),  # right leg
    (27, 29), (29, 31),  # left foot
    (28, 30), (30, 32),  # right foot
]

KEY_LANDMARK_INDICES = [
    0, 7, 8,   # nose, ears
    11, 12,    # shoulders
    13, 14,    # elbows
    15, 16,    # wrists
    23, 24,    # hips
    25, 26,    # knees
    27, 28,    # ankles
    29, 30,    # heels
    31, 32,    # foot indices
]


def analyze_pose(image_bytes: bytes) -> dict:
    if not image_bytes or len(image_bytes) < 100:
        return {"error": "Gambar kosong atau terlalu kecil. Unggah foto yang valid."}
    arr = np.frombuffer(image_bytes, np.uint8)
    try:
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except cv2.error:
        return {"error": "Gagal membaca gambar. Format tidak didukung atau file rusak."}
    if image is None:
        return {"error": "Gagal membaca gambar. Format tidak didukung."}

    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:
        results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        if not results.pose_landmarks:
            return {
                "error": "Tubuh tidak terdeteksi. Pastikan foto dengan posisi tegak, pakaian tidak longgar, dan seluruh tubuh terlihat."
            }

        raw_landmarks = results.pose_landmarks.landmark

        landmarks_dict = {}
        landmarks_list = []
        for i in KEY_LANDMARK_INDICES:
            lm = raw_landmarks[i]
            entry = {
                "index": i,
                "x": round(lm.x, 4),
                "y": round(lm.y, 4),
                "z": round(lm.z, 4),
                "visibility": round(lm.visibility, 3),
            }
            landmarks_dict[i] = {"x": lm.x, "y": lm.y, "z": lm.z}
            landmarks_list.append(entry)

        wsr = compute_wsr(landmarks_dict)
        shoulder_balance = compute_shoulder_balance(landmarks_list)
        posture_score = compute_posture_score(landmarks_list)

        line_connections = []
        for a, b in SKELETON_CONNECTIONS:
            la = landmarks_dict.get(a)
            lb = landmarks_dict.get(b)
            if la and lb:
                line_connections.append({
                    "from": {"x": round(la["x"], 4), "y": round(la["y"], 4)},
                    "to": {"x": round(lb["x"], 4), "y": round(lb["y"], 4)},
                })

        return {
            "wsr": wsr,
            "shoulder_balance": shoulder_balance,
            "posture_score": posture_score,
            "landmarks": landmarks_list,
            "connections": line_connections,
            "img_width": image.shape[1],
            "img_height": image.shape[0],
        }


def draw_pose_skeleton(image_bytes: bytes, landmarks: list, connections: list, output_path: str):
    """Draw pose skeleton (landmarks + connections) on image and save to output_path."""
    arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        return
    h, w = image.shape[:2]

    for conn in connections:
        x1 = int(conn["from"]["x"] * w)
        y1 = int(conn["from"]["y"] * h)
        x2 = int(conn["to"]["x"] * w)
        y2 = int(conn["to"]["y"] * h)
        cv2.line(image, (x1, y1), (x2, y2), (0, 255, 255), 2)

    for lm in landmarks:
        x = int(lm["x"] * w)
        y = int(lm["y"] * h)
        cv2.circle(image, (x, y), 5, (0, 255, 0), -1)

    cv2.imwrite(output_path, image)