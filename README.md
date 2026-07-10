# PostureFit Backend API

Backend server untuk aplikasi **PostureFit** — aplikasi kebugaran berbasis Flutter yang menggunakan analisis postur (Computer Vision) dan metode **SAW (Simple Additive Weighting)** untuk memberikan rekomendasi workout yang dipersonalisasi.

---

## 🛠️ Tech Stack

| Komponen | Teknologi |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy |
| Database | MySQL (via PyMySQL) |
| Auth | JWT (python-jose + bcrypt) |
| Admin Panel | sqladmin |
| Server | Uvicorn |

---

## 📁 Struktur Proyek

```
posturfit_backend/
│
├── routers/                    # API route handlers per domain
│   ├── auth_router.py          # /api/auth  — register, login, profile
│   ├── cv_router.py            # /api/assessment — vitality scan & SAW
│   ├── home_router.py          # /api/home — dashboard summary
│   ├── tracker_router.py       # /api/tracker — daily activity tracking
│   ├── workout_log_router.py   # /api/workout-log — session history
│   ├── education_router.py     # /api/education — article content
│   ├── notification_router.py  # /api/notifications — user notifications
│   └── progress_router.py      # /api/progress — chart data
│
├── main.py                     # App entry point, CORS, router includes
├── models.py                   # SQLAlchemy ORM models (database schema)
├── schemas.py                  # Pydantic schemas (request/response validation)
├── database.py                 # DB engine & session factory
├── auth.py                     # JWT logic — token creation & verification
├── admin_panel.py              # sqladmin dashboard views
├── saw_engine.py               # SAW algorithm implementation
├── fitness_analysis.py         # CV analysis & BMI calculations
│
├── .env                        # Environment variables (tidak di-commit)
├── .env.example                # Template env (aman untuk di-commit)
├── .gitignore                  # Ignore rules
├── requirements.txt            # Python dependencies
└── README.md                   # Dokumentasi ini
```

---

## 🚀 Cara Menjalankan

### 1. Prasyarat
- Python 3.10+
- MySQL (Laragon / XAMPP)
- Laragon sudah aktif dan database `posturfit` sudah dibuat

### 2. Setup Pertama Kali

```bash
# Clone / buka folder project
cd posturfit_backend

# Aktivasi virtual environment
.\venv\Scripts\activate

# Install dependensi (jika venv baru)
pip install -r requirements.txt

# Salin file env
copy .env.example .env
# Edit .env sesuai konfigurasi database Anda
```

### 3. Jalankan Server

```bash
# Development (auto-reload saat ada perubahan file)
.\venv\Scripts\uvicorn.exe main:app --reload

# Production
.\venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000
```

### 4. Akses

| Halaman | URL |
|---|---|
| API Docs (Swagger) | http://localhost:8000/docs |
| Admin Dashboard | http://localhost:8000/admin |
| Health Check | http://localhost:8000/ |

---

## 🔐 Autentikasi (JWT)

API ini menggunakan **JWT Bearer Token**. Cara mendapatkan token:

1. **Register**: `POST /api/auth/register` dengan `name`, `email`, `password`
2. **Login**: `POST /api/auth/login` → dapatkan `access_token`
3. **Gunakan token**: Sertakan di header setiap request:
   ```
   Authorization: Bearer <access_token>
   ```

---

## 📡 API Endpoints

| Method | Endpoint | Keterangan |
|---|---|---|
| POST | `/api/auth/register` | Daftar akun baru |
| POST | `/api/auth/login` | Login, dapatkan token |
| GET | `/api/auth/me` | Profil user saat ini |
| PUT | `/api/auth/profile` | Update profil |
| POST | `/api/assessment/generate` | Generate rekomendasi SAW |
| GET | `/api/assessment/latest` | Assessment terakhir |
| GET | `/api/assessment/history` | Riwayat assessment |
| POST | `/api/tracker/daily` | Update tracker harian |
| GET | `/api/tracker/daily` | Data tracker hari ini |
| GET | `/api/tracker/weekly` | Data tracker 7 hari |
| GET | `/api/home/summary` | Ringkasan dashboard |
| GET | `/api/workout-log` | Riwayat latihan |
| POST | `/api/workout-log` | Tambah log latihan |
| GET | `/api/education` | List artikel edukasi |
| GET | `/api/notifications` | Daftar notifikasi |
| PATCH | `/api/notifications/{id}/read` | Tandai sudah dibaca |
| GET | `/api/progress` | Data chart progress |

---

## 🗃️ Database

Tabel utama:
- `users` — Data profil pengguna
- `cv_assessments` — Hasil scan & analisis SAW
- `daily_trackers` — Tracking aktivitas harian
- `daily_workout_plans` — Rencana latihan harian
- `workout_tasks` — Detail task latihan
- `workout_logs` — Riwayat sesi latihan
- `education_articles` — Konten artikel edukasi
- `notifications` — Notifikasi per-user

> Semua tabel dibuat otomatis saat server pertama kali dijalankan.
