"""Smoke test manual de la API: recorre el flujo completo (login docente,
listar materias, previsualizar PDF, procesar, login direccion, resumen y
reporte PDF) contra un servidor ya corriendo en localhost:8000.

Requiere:
  - El servidor: uvicorn backend.main:app --reload --port 8000
  - Los usuarios de prueba ya creados (ver db/seed.py y el docente de
    ejemplo creado desde la app), y los archivos de ejemplo en ejemplos/.

Uso:
    python tests/test_api_smoke.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import httpx

RAIZ = Path(__file__).resolve().parent.parent
BASE = "http://localhost:8000"
EXCEL_REAL = RAIZ / "documentos" / "MI-DO-FO16 Formato Gestiòn y Autoevaluacion Docente-2026-1_corte_2_IA.xlsx"
PDF_EJEMPLO = RAIZ / "ejemplos" / "Notas_sistemas_opertivo_corte_2.pdf"


def main():
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": "wquinonez", "password": "docente123"})
    assert r.status_code == 200, r.text
    print("LOGIN docente:", r.status_code)
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    with open(EXCEL_REAL, "rb") as f:
        r = httpx.post(f"{BASE}/api/informes/materias-excel", headers=headers, files={"excel": f})
    assert r.status_code == 200, r.text
    print("MATERIAS:", r.json())

    with open(PDF_EJEMPLO, "rb") as f:
        r = httpx.post(f"{BASE}/api/informes/pdf-preview", headers=headers, files={"pdf": f}, data={"corte": 2})
    assert r.status_code == 200, r.text
    preview = r.json()
    print("PREVIEW:", preview["materia_detectada"], preview["n_estudiantes"], preview["conteo_estado"])

    with open(EXCEL_REAL, "rb") as fe, open(PDF_EJEMPLO, "rb") as fp:
        r = httpx.post(
            f"{BASE}/api/informes/procesar",
            headers=headers,
            data={"corte": 2, "materias": ["SISTEMAS OPERATIVOS"], "asistencias_regular": [""]},
            files=[("excel", fe), ("pdfs", fp)],
            timeout=30,
        )
    assert r.status_code == 200, r.text
    data = r.json()
    print("PROCESAR OK, materias:", [res["materia"] for res in data["resultados"]])

    r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "cambiar123"})
    assert r.status_code == 200, r.text
    headers_dir = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = httpx.get(f"{BASE}/api/docentes", headers=headers_dir)
    assert r.status_code == 200, r.text
    docentes = r.json()
    print("DOCENTES:", [d["nombre_completo"] for d in docentes])

    if docentes:
        docente_id = docentes[0]["id"]
        r = httpx.get(f"{BASE}/api/reportes/docente/{docente_id}", headers=headers_dir)
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf", r.text
        print(f"REPORTE PDF: {len(r.content)} bytes")

    print("\nTodo OK.")


if __name__ == "__main__":
    main()
