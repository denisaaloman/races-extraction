"""
core_extract.py — Logica de extragere din poze (Gemini), reutilizabila de app.py.
"""

import os
import json
import time
from pathlib import Path
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"

PROMPT = """Aceasta este o poza cu un tabel scris de mana, in limba romana, care contine
curse auto pe santiere. Structura tabelului: coloane NR / DATA / PROGRAM LUCRU / ORE-KM / SANTIER.

In coloana ORE-KM / SANTIER, fiecare rand contine fie:
  (A) cuvantul "CURSA" urmat de o ruta (ex: "CURSA Petresti-Alba-Petresti")
      -> ACESTEA SUNT RELEVANTE, le extragi.
  (B) un NUMAR (ex: "304", "117", "82") urmat de o ruta
      -> ACESTEA SUNT KILOMETRAJ, NU LE EXTRAGI. Ignora complet aceste randuri.

Uneori langa un rand CURSA e scris manual "(2 CURSE)" sau similar, insemnand ca acea cursa
s-a facut de 2 ori in ziua respectiva - in acest caz pune "nr_curse": 2 pentru acel rand.
Daca nu e specificat, "nr_curse": 1.

Aceeasi ruta poate aparea de mai multe ori in aceeasi zi pe randuri CURSA separate (nu doar
cu adnotarea "(N CURSE)") - extrage-le ca randuri separate, agregarea o fac eu ulterior.

Rutele incep si se termina intotdeauna cu "Petresti". Pastreaza EXACT ortografia vazuta in
poza (fara diacritice daca originalul nu are), doar corecteaza erori clare de citire OCR,
nu de ortografie.

Returneaza STRICT un JSON (fara alt text, fara ```), cu urmatoarea structura:

{
  "firma": "<text de la FIRMA, daca se vede>",
  "luna": "<text de la LUNA, daca se vede>",
  "randuri": [
    {"data": "DD.MM.YYYY", "ruta": "Petresti-Alba-Petresti", "nr_curse": 1},
    ...
  ],
  "randuri_neclare": [
    {"data": "DD.MM.YYYY", "text_partial": "ce ai reusit sa citesti", "motiv": "scris neclar / rupt / etc"}
  ]
}

Daca un rand CURSA e neclar / nu poti citi ruta sau data cu incredere, NU il ghici -- pune-l
in "randuri_neclare" cu ce ai reusit sa descifrezi, ca sa il verific manual. E mai bine sa
raportezi ca neclar decat sa inventezi.
"""


def guess_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return "image/jpeg"


def extract_from_image(client: genai.Client, path: Path) -> dict:
    image_bytes = path.read_bytes()
    mime_type = guess_mime_type(path)

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {
            "firma": None, "luna": None, "randuri": [], "randuri_neclare": [],
            "eroare": str(e), "raspuns_brut": text,
        }


def extract_all(image_paths, api_key: str, progress_callback=None):
    """
    image_paths: lista de Path catre poze.
    progress_callback: functie optionala apelata cu (index, total, filename) inainte
                        de fiecare procesare, pentru a raporta progresul catre UI.
    Returneaza lista de rezultate (unul per poza), fiecare cu "_sursa_fisier" adaugat.
    """
    client = genai.Client(api_key=api_key)
    results = []
    total = len(image_paths)
    for i, path in enumerate(image_paths):
        if progress_callback:
            progress_callback(i, total, path.name)
        result = extract_from_image(client, path)
        result["_sursa_fisier"] = path.name
        results.append(result)
        time.sleep(0.3)
    return results
