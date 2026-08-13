"""
app.py — Interfata web pentru automatizarea curse -> Word.

Rulare locala:
    python app.py
apoi deschide http://127.0.0.1:5000 in browser.

Rulare productie (Render):
    gunicorn app:app
Cheia GEMINI_API_KEY se citeste din variabilele de mediu / .env -- utilizatorii
nu o vad si nu o introduc niciodata in interfata.
"""

import os
import uuid
import threading
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_from_directory

import core_extract
import core_build

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

BASE_DIR = Path(__file__).parent
# In productie (Render), filesystem-ul e efemer -- folosim /tmp explicit ca sa fie clar
# ca aceste fisiere sunt temporare, nu stocare persistenta. Local functioneaza identic.
DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp/curse-app"))
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "output"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # 60 MB total, poze de telefon sunt mari

# stare simpla, in-memory, a job-urilor de generare.
# Pe Render cu un singur worker (gunicorn -w 1) e suficient de robust pentru
# volumul descris (cateva poze/luna); daca vreodata cresc workerii, mutati
# starea intr-un store extern (Redis) -- in-memory nu e vizibila intre procese.
JOBS = {}


@app.route("/static/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/static/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    files = request.files.getlist("photos")
    if not files:
        return jsonify({"error": "Nicio poza primita"}), 400

    saved = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXT:
            continue
        unique_name = f"{uuid.uuid4().hex[:10]}{ext}"
        dest = UPLOAD_DIR / unique_name
        f.save(dest)
        saved.append({
            "id": unique_name,
            "original_name": f.filename,
            "url": f"/static/uploads/{unique_name}",
        })

    if not saved:
        return jsonify({"error": "Niciun fisier valid (accept: jpg, jpeg, png, webp)"}), 400

    return jsonify({"files": saved})


@app.route("/api/uploads/<file_id>", methods=["DELETE"])
def delete_upload(file_id):
    path = UPLOAD_DIR / file_id
    if path.exists() and path.is_file():
        path.unlink()
        return jsonify({"ok": True})
    return jsonify({"error": "Fisier inexistent"}), 404


def _run_generation(job_id: str, file_ids: list, api_key: str, output_name: str):
    job = JOBS[job_id]
    try:
        image_paths = [UPLOAD_DIR / fid for fid in file_ids]
        image_paths = [p for p in image_paths if p.exists()]

        def progress(i, total, filename):
            job["status"] = "extracting"
            job["progress"] = {"current": i + 1, "total": total, "filename": filename}

        raw_results = core_extract.extract_all(image_paths, api_key, progress_callback=progress)

        job["status"] = "building"
        output_path = OUTPUT_DIR / output_name
        result = core_build.run_pipeline(raw_results, output_path)

        job["status"] = "done"
        job["result"] = {
            "output_file": output_name,
            "output_url": f"/static/output/{output_name}",
            "total_general": result["total_general"],
            "randuri_count": len(result["randuri_finale"]),
            "randuri_fara_pret": [
                {"index": idx, "data": data, "ruta": ruta}
                for idx, data, ruta in result["randuri_fara_pret"]
            ],
            "randuri_neclare": result["randuri_neclare"],
        }
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/api/generate", methods=["POST"])
def generate():
    if not GEMINI_API_KEY:
        # eroare de configurare a serverului, nu a utilizatorului -- mesaj generic
        return jsonify({"error": "Serverul nu este configurat corect. Contactati administratorul."}), 500

    data = request.get_json(force=True)
    file_ids = data.get("file_ids", [])
    luna_label = (data.get("luna_label") or "curse").strip()

    if not file_ids:
        return jsonify({"error": "Nicio poza selectata"}), 400

    safe_label = "".join(c for c in luna_label if c.isalnum() or c in ("-", "_")) or "curse"
    output_name = f"{safe_label}.docx"

    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "starting", "progress": None, "result": None, "error": None}

    thread = threading.Thread(
        target=_run_generation,
        args=(job_id, file_ids, GEMINI_API_KEY, output_name),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job inexistent"}), 404
    return jsonify(job)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Deschide in browser: http://127.0.0.1:{port}\n")
    app.run(debug=False, host="0.0.0.0", port=port)
