import requests

BASE = "http://localhost:8000"

endpoints = [
    ("GET",  "/",                       "Root redirect",          [302]),
    ("GET",  "/health",                 "Health check",           [200]),
    ("GET",  "/docs",                   "Swagger UI",             [200]),
    ("GET",  "/openapi.json",           "OpenAPI schema",         [200]),
    ("GET",  "/admin",                  "Admin (unauth)",         [307, 302]),
    ("GET",  "/admin/login",            "Admin login page",       [200]),
    ("POST", "/api/auth/register",      "Register (no body)",     [422]),
    ("POST", "/api/auth/login",         "Login (no body)",        [422]),
    ("GET",  "/api/auth/me",            "Profile (unauth)",       [401, 403]),
    ("GET",  "/api/home/summary",       "Home summary",           [401, 403]),
    ("GET",  "/api/tracker/daily",      "Tracker daily",          [401, 403]),
    ("GET",  "/api/tracker/weekly",     "Tracker weekly",         [401, 403]),
    ("GET",  "/api/assessment/history", "Assessment history",     [401, 403]),
    ("GET",  "/api/assessment/latest",  "Assessment latest",      [401, 403]),
    ("POST", "/api/assessment/generate","Assessment generate",    [401, 403, 422]),
    ("GET",  "/api/workout-log",        "Workout log",            [401, 403]),
    ("GET",  "/api/education",          "Education list",         [401, 403]),
    ("GET",  "/api/notifications",      "Notifications",          [401, 403]),
    ("GET",  "/api/progress",           "Progress summary",       [401, 403]),
    ("GET",  "/admin-api/stats",        "Admin stats API",        [200]),
]

pass_c = fail_c = warn_c = 0

print(f"{'METHOD':<6} {'ENDPOINT':<35} {'CODE':<6} {'RESULT':<15} DESCRIPTION")
print("-" * 92)

for method, path, desc, expected in endpoints:
    try:
        r = requests.request(method, BASE + path, timeout=5, allow_redirects=False)
        s = r.status_code
        if s in expected:
            tag = "[OK]"
            pass_c += 1
        elif s == 404:
            tag = "[FAIL-404]"
            fail_c += 1
        elif s == 503:
            tag = "[FAIL-503]"
            fail_c += 1
        else:
            tag = f"[WARN-{s}]"
            warn_c += 1
        print(f"{method:<6} {path:<35} {s:<6} {tag:<12} {desc}")
    except Exception as e:
        print(f"{method:<6} {path:<35} ERR    [ERROR]      {str(e)[:50]}")
        fail_c += 1

print("-" * 92)
print(f"TOTAL: {pass_c} PASS | {warn_c} WARN | {fail_c} FAIL")
