# Curse → Word

Aplicație web: compania încarcă pozele foii de pontaj, apasă un buton,
primește Word-ul gata generat. Cheia API Gemini stă doar pe server
(`.env` local / variabilă de mediu pe Render) — utilizatorii n-o văd
niciodată.

## Rulare locală (pentru tine, ca să testezi)

```bash
pip install -r requirements.txt
cp .env.example .env
```

Deschide `.env` și pune cheia ta reală:

```
GEMINI_API_KEY=AIza...
```

Apoi:

```bash
python app.py
```

Deschide `http://127.0.0.1:5000`.

## Deploy pe Render

1. Urcă folderul ăsta pe un repo GitHub (`.env` nu se urcă — e deja în
   `.gitignore`, doar `.env.example` merge pe git).
2. Pe [render.com](https://render.com) → **New +** → **Web Service** →
   conectezi repo-ul.
3. Render detectează `render.yaml` automat (sau setezi manual):
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app --workers 1 --threads 4 --timeout 120`
4. La **Environment Variables**, adaugi:
   - `GEMINI_API_KEY` = cheia ta reală
5. Deploy. Render îți dă un URL public (`https://ceva.onrender.com`) — pe
   ăla îl trimiți companiei.

Fără autentificare deocamdată — oricine are link-ul poate genera Word-uri
(consumă din cheia ta API). Dacă la un moment dat vrei o parolă simplă la
intrare, spune-mi și adaug.

### De ce `--workers 1`

Starea job-urilor de generare se ține în memorie (`JOBS = {}` în `app.py`).
Cu un singur worker + mai multe threads, cererile concurente merg bine
pentru volumul descris (câteva poze/lună). Dacă vreodată crește mult
volumul și ai nevoie de mai mulți workeri, starea trebuie mutată într-un
store extern (Redis) — altfel un worker nu vede job-urile pornite de alt
worker.

### Filesystem efemer pe Render

Pozele urcate și Word-urile generate se salvează în `/tmp/curse-app` —
temporar, dispar la fiecare restart/redeploy al serviciului. E intenționat:
aplicația nu ține istoric, doar procesează și livrează. Dacă la un moment
dat vrei istoric persistent (ex: să regăsești Word-uri vechi), trebuie
adăugat storage extern (S3, Render Disk etc.) — spune-mi dacă ajungem acolo.

## Cum se folosește (pentru echipa care încarcă pozele)

1. Trage pozele în zona punctată sau apasă pe ea și alege fișierele.
2. Click pe orice poză → preview mărit.
3. Poți șterge o poză din galerie dacă a fost încărcată greșit.
4. Opțional, schimbi numele fișierului rezultat.
5. Apasă **Generează Word** — vezi progres live.
6. Descarcă fișierul.

Dacă apar rânduri neclare (scris ilizibil) sau rute noi fără preț cunoscut,
apar listate sub rezultat, ca să fie verificate/completate manual în Word.

## Structura folderului

```
curse-app/
├── app.py               — serverul Flask (upload, generare, status)
├── core_extract.py       — logica de citire poze cu Gemini
├── core_build.py          — agregare + generare Word
├── requirements.txt
├── Procfile               — comanda de pornire pentru Render
├── render.yaml            — config Render (opțional, pentru deploy automat)
├── .env.example            — model pentru cheia API (copiezi ca .env local)
├── .gitignore
├── templates/
│   └── index.html          — interfața
└── static/
    ├── style.css
    └── app.js
```

## Reguli de preț (editabile)

În `core_build.py`, la începutul fișierului:

```python
PRET_66 = {
    "petresti-sebes-petresti",
    "petresti-rachita-petresti",
}
PRET_DEFAULT = 120
```

Dacă apar rute noi cu preț special, le adaugi aici și redeploy-ezi.

## Note

- Modelul folosit e `gemini-3.5-flash` — are un free tier generos, suficient
  pentru câteva poze/lună.
- Free tier-ul Render "adoarme" serviciul după inactivitate — primul request
  după o pauză poate dura ~30-50 secunde până pornește din nou. Dacă devine
  deranjant, treci pe planul plătit de Render (fără cold start).
