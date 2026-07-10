import os
import json
from typing import Optional

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from google import genai

load_dotenv()

_API_KEY = os.getenv("GEMINI_API_KEY")
if not _API_KEY:
    print("[LLM] GEMINI_API_KEY tidak diatur — LLM tidak aktif, fallback ke template SAW.")

_client = genai.Client(api_key=_API_KEY) if _API_KEY else None

_PROMPT_TEMPLATE = """Kamu adalah asisten kebugaran profesional Indonesia yang ahli dalam analisis postur tubuh dan rekomendasi olahraga.

Data user:
- Kategori tubuh: {kategori} (hasil SAW engine: Obesitas/Skinnyfat/Kurus/Normal)
- BMI: {bmi}
- WSR (Waist-to-Shoulder Ratio): {wsr} (0.5-1.0, semakin tinggi = pinggang lebih lebar dari bahu)
- Posture Score: {posture_score}/100
- Shoulder Balance: {shoulder_balance} (deviasi tinggi bahu kiri-kanan dalam normalized coordinates; 0 = seimbang, >0.05 = miring)
- Fokus user: {fokus} (Defisit Kalori/Surplus Kalori/Pertahankan)
- Lingkungan latihan: {lingkungan} (Rumah/GYM/Calisthenics)

Berdasarkan data di atas, buat:

1. **Analisis postur** — 2-3 kalimat menjelaskan kondisi postur user dan apa artinya.

2. **3-4 rekomendasi olahraga SPESIFIK** dalam Bahasa Indonesia. Setiap rekomendasi HARUS berisi:
   - Nama latihan (dalam Bahasa Indonesia)
   - Durasi (misal: 3 set x 12 repetisi, atau 30 menit)
   - Frekuensi per minggu
   - Alasan mengapa latihan ini cocok dengan postur tubuh user (kaitkan dengan WSR, posture score, atau kategori)

3. **Tambahan** — 1 tips lifestyle singkat (tidur, nutrisi, atau postur sehari-hari)

Output dalam format JSON seperti contoh di bawah, TANPA MARKDOWN:
{{"analisis": "...", "rekomendasi": [{{"nama": "...", "durasi": "...", "frekuensi": "...", "alasan": "..."}}], "tips": "..."}}"""


def generate_recommendation(
    kategori: str,
    bmi: float,
    wsr: float,
    posture_score: float,
    shoulder_balance: float,
    fokus: str,
    lingkungan: str,
) -> Optional[dict]:
    if not _client:
        return None

    prompt = _PROMPT_TEMPLATE.format(
        kategori=kategori,
        bmi=bmi,
        wsr=wsr,
        posture_score=posture_score,
        shoulder_balance=shoulder_balance,
        fokus=fokus,
        lingkungan=lingkungan,
    )

    try:
        response = _client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("```json").strip("```").strip()
        parsed = json.loads(text)
        return parsed
    except Exception as e:
        print(f"[LLM] Error generating recommendation: {e}")
        return None