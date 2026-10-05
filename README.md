# AI Gallery Search

A personal photo gallery you can search by date, location, people, objects,
scenes, or plain-English queries ("beach photos from my trip in 2025").

This repo is being built in phases (see **Roadmap** below). **All 9
planned phases through broader test coverage — foundation, auth, photo
upload/EXIF/thumbnails, the AI-indexing pipeline, vector + hybrid search,
face detection/clustering, object detection/tagging, full UI, rate
limiting, a jobs/retry API, and hardened test coverage — are complete,
running, and tested (92 passing tests).** Phase 10 (production Docker
hardening + deployment docs) is next.

---

## 1. Read this first: what actually works right now

**Phase 1** — auth foundation, full 14-table schema, JWT login.
**Phase 2** — photo upload (single/multiple/folder, drag-and-drop), real
EXIF extraction (date with source-tracked fallback, GPS, camera info),
EXIF-aware thumbnails, SHA-256 dedup, upload validation, and per-user
isolation on every photo endpoint.
**Phase 3** — the AI indexing pipeline's plumbing:
- **pgvector is for real.** `postgresql-16-pgvector` is installed, the
  `vector` extension is enabled, `photo_embeddings.embedding` and
  `face_embeddings.embedding` are genuine `vector(512)` columns with HNSW
  cosine-similarity indexes — not a JSON placeholder.
- **Alembic now manages the schema** (`backend/alembic/`) instead of
  Phase 1/2's `create_all()` shortcut — autogenerate correctly picked up
  every table including the vector columns.
- **A swappable embedder interface** (`app/ai/embedder.py`): `OpenCLIPEmbedder`
  (`app/ai/clip_embedder.py`) is the real, complete implementation for
  production use; `DeterministicStubEmbedder` (`app/ai/stub_embedder.py`) is
  a dependency-free pixel-based stand-in used only where real CLIP can't
  run. `app/ai/factory.py` picks one via the `EMBEDDING_BACKEND` setting —
  nothing else in the codebase needs to know which is active.
**Phase 4** — `POST /api/search/semantic`: embeds free text and ranks the
user's photos by pgvector cosine similarity, with a configurable
`min_similarity` threshold and search history logging.
**Phase 5** — natural-language + hybrid search:
- `app/services/query_parser.py` splits free text into a date range and
  whatever's left over — exact dates, month/year, year-only, ranges
  ("January 2024 to March 2024"), and relative phrases (today, yesterday,
  this week, this/last month, this/last year, last summer). Pure Python,
  zero dependencies, fully unit-tested (18 tests, no DB needed).
- `app/services/ranking.py` applies the date range as a plain SQL filter
  (per spec: never burn a vector query on a pure date lookup), then ranks
  any remaining text by cosine similarity, combining both with the
  weighted formula from spec section 12 — renormalized over whichever
  signals are actually active, since object/face scoring (Phases 6/7)
  don't exist yet and shouldn't silently deflate every score.
- `POST /api/search` is now the main endpoint: give it
  `"August 2025 with cars"` and it returns the date-filtered, similarity-
  ranked results with the parsed filters echoed back.
- **A real bug found by actually running it**: "photos from August 2025"
  was leaving `"photos"` as a leftover semantic query, which silently
  turned a pure date lookup into a similarity-filtered one and dropped
  valid results. Fixed by stripping generic gallery-app filler words
  ("photos", "show", "my", ...) — regression-tested.

**52 passing pytest tests** across auth, upload/EXIF, embeddings, and
search — including one that proves a date filter correctly excludes a
photo outside the date range even when it's visually identical to one
that's in range.

**Phase 6** — face detection, clustering, and naming:
- **Real face detection, genuinely working in this sandbox**: OpenCV's
  Haar Cascade classifier ships its model data inside the
  `opencv-python-headless` package itself — no download needed. Verified
  live, end-to-end, through the actual upload API against a real
  photograph fetched from a public GitHub test-data repo (not shipped in
  this codebase — see below): correctly detected exactly one face, created
  a `Person`, and the rename/photo-listing endpoints worked against it.
  It's a real, working baseline (not a placeholder) — just weaker than a
  modern deep-learning detector, which is a reasonable future upgrade.
- **A real schema gap found while building this**: the spec's original
  `photo_people` table only links at the photo level, which can't tell
  which specific face in a multi-person photo belongs to which person.
  Added `faces.person_id` (migration `1c7c4ca831da`) as what clustering
  actually assigns to; `photo_people` stays as a derived per-photo index
  for search.
- Face *recognition* (matching the same person across photos) needs real
  embeddings (`app/ai/arcface_embedder.py`, complete code, same
  torch/model-download wall as CLIP) — `DeterministicFaceStubEmbedder`
  is the sandbox stand-in, same honesty rules as the image embedder stub.
- Incremental nearest-neighbor clustering (`app/services/face_processor.py`):
  a new face joins an existing person if it's within
  `FACE_CLUSTER_SIMILARITY_THRESHOLD` of any of that person's known faces
  (scoped per-user), else starts a new unnamed person.
- `GET /api/people`, `PATCH /api/people/{id}` (naming), `GET
  /api/people/{id}/photos` — plus a People page in the frontend with
  inline rename and a click-through photo view.

**58 passing pytest tests** total — the 6 new ones cover: same face across
two photos clusters into one person, a different face starts a new person,
renaming persists, and people/faces never cross user boundaries even when
two users have identical-looking faces.

**Phase 7** — object detection, tagging, and a real capability upgrade to
search:
- **Real YOLOv8n object detection, genuinely working here — unlike CLIP
  and ArcFace.** The reason: Ultralytics hosts its checkpoints as plain
  GitHub Release assets, which this sandbox's network allow-list happens
  to permit (unlike huggingface.co / openaipublic.azureedge.net). `pip
  install torch` also succeeded this time — Phase 3's "No space left on
  device" was a transient disk-space problem, not a hard block; by Phase 7
  enough space had been freed. Verified live through the actual upload API
  against a real photo: correctly detected a bus and 3 people.
- A rule-based caption/tag generator (`caption_generator.py`) built from
  the real object/face detections — explicitly not an ML captioning model
  (that needs the same blocked weights as CLIP/ArcFace), but honest and
  functional.
- **Named-person and detected-object search became real hard filters, not
  just theoretical weight slots** — since Phase 6 gives real (if
  stub-embedded) person clustering and Phase 7 gives real object
  detection, `ranking.py` was rewritten to actually extract a person name
  and/or object class out of the query text and filter on them, before
  whatever's left goes to vector search. "Photos with Athar", "photos with
  cars", and "photos with Athar and a car" (the spec's own examples) now
  all resolve to genuine filters end-to-end.
- **Two real bugs found by actually running this end-to-end**, both the
  same species as a bug from Phase 5:
  1. The first live object-detection request appeared to return zero
     detections. Turned out not to be a bug at all — CPU-bound YOLO
     inference in this resource-constrained sandbox took ~15-20 seconds on
     a cold run (vs ~150ms in an isolated script with no other load), and
     my first verification simply didn't wait long enough. Confirmed by
     adding temporary debug logging and re-timing; no code was wrong.
  2. A **real** bug: "photos with a bus" left a bare "a" behind after the
     object-name extraction, silently turning a pure object-filter query
     into a (falsely) similarity-filtered one that matched nothing. Fixed
     by adding articles/conjunctions ("a", "an", "the", "and") to the
     filler-word list — regression-tested.

**68 passing pytest tests** in total. The dedicated real-YOLO test
(`test_object_detection.py`) needs network access on first run to fetch
`yolov8n.pt` (cached locally afterward); every other test stays fully
offline via `OBJECT_DETECTION_BACKEND=none` in the sandbox's `.env`.

**Phase 8** — full UI: albums, timeline, locations, settings, and a
richer photo experience:
- **Albums**: create, add/remove photos, browse contents — with per-user
  isolation tested (including that you can't add someone else's photo to
  your album, not just "silently adds nothing").
- **Timeline**: year/month grouped counts (`GET /api/photos/timeline`)
  driven off `capture_date`, with drill-down filtering added to
  `GET /api/photos` (`capture_year`/`capture_month` params).
- **Locations**: clusters photos by rounded GPS coordinates. Checked
  reverse geocoding here too (spec section 18) — Nominatim and
  BigDataCloud both returned `403` from this sandbox, the same class of
  block as Hugging Face/OpenAI. `location_name` stays `null` unless set
  some other way; the UI is honest about showing coordinates instead of
  place names.
- **Settings**: a real "delete all photos and AI data" endpoint (spec
  section 21) — wipes photos, embeddings, faces, detected objects, people,
  albums, and search history for the user, removes the actual files from
  disk, and keeps the account itself.
- **Two more real Postgres bugs found by actually running the locations
  query**: `round(double precision, integer)` doesn't exist in Postgres
  (needs an explicit cast to `numeric`), and Postgres has no `min()`/
  `max()` aggregate for `uuid` either (worked around with a cast to
  `text` and back). Neither would show up from reading the code — only
  from executing it against a real database.
- Frontend: Photo Detail page (full image, EXIF, GPS, camera, people,
  objects, caption, favorite/delete/download), Albums page, Locations
  page, Timeline page (year/month sidebar), Settings page, and an
  upgraded Photos page (multi-select, bulk delete, add-to-album, favorite
  indicator, click-through to detail).

**78 passing pytest tests** total. Verified live end-to-end through the
running server: upload with EXIF date+GPS → correct timeline grouping →
correct location cluster → album creation/linking → favorite toggle → full
photo detail — all matching exactly what the frontend calls.

**Phase 9** — rate limiting, a jobs/retry API, and closing real test gaps:
- **Rate limiting** (spec section 20) on `/api/auth/register` and
  `/api/auth/login` via `slowapi`, keyed by client IP — the classic
  brute-force/enumeration targets. Not applied globally: a photo-heavy
  app's upload/search endpoints see legitimate high-frequency use from a
  single logged-in user, so a blanket limit there would just be friction
  without much security benefit. The test confirms the limiter mechanism
  itself actually rejects excess requests (a 429 after the limit), not
  just that a decorator is present.
- **`GET /api/jobs`, `GET /api/jobs/{id}`, `POST
  /api/photos/{id}/reprocess`** (spec sections 23 and 27: "mark failed
  jobs and allow retry"). Tested against a *real* simulated failure — the
  embedder is made to raise mid-pipeline, confirmed the photo lands in
  `processing_status="failed"` with a failed job row, then confirmed
  `/reprocess` actually recovers it once the simulated failure is removed.
- Closed genuine coverage gaps rather than padding the test count:
  JWT edge cases beyond "no token" (expired, malformed, wrong signature,
  and a well-formed token for a user id that no longer exists — all
  correctly rejected), a year-only query through the *actual*
  `/api/search` endpoint (not just the parser's unit test), the
  database-level `uq_user_file_hash` constraint that backstops the
  app-level dedup check (verified by bypassing the app check and
  confirming Postgres itself raises `IntegrityError`), and proof that a
  late pipeline step failing (object detection) doesn't erase earlier
  steps' committed work (EXIF, thumbnail, embedding all survive; the
  photo stays `ready`).
- Also cleaned up a harmless but confusing leftover: a stray `{api`
  directory from a Phase 1 shell brace-expansion bug (a `mkdir -p
  app/{api/routes,...}` command that didn't get brace-expanded, so it
  literally created a directory named `{api`) — found while reviewing the
  full file tree for this phase, removed.

**92 passing pytest tests** total.

### Important limitation: this sandbox cannot run real CLIP or ArcFace (confirmed, not assumed)

This isn't a guess — I hit these walls directly while building Phases 3 and 6:
- Hugging Face and OpenAI's model-weight hosts both return `403` from this
  sandbox's network allow-list (only pypi/npm/github/apt-style hosts are
  reachable) — this blocks both CLIP and ArcFace/insightface's model downloads.
- `pip install torch` itself failed here with **"No space left on
  device"** — the CPU wheel alone doesn't fit in this container's disk.

So `OpenCLIPEmbedder` and `ArcFaceEmbedder` are real, complete code — but
genuinely untestable in this environment. Face *detection* is the
exception: OpenCV's Haar Cascade needs no model download (see Phase 6
above), so it's real and working here even though face *recognition*
(telling two photos of the same person apart) isn't.

To get real semantic search:

    pip install torch open_clip_torch
    # in .env: EMBEDDING_BACKEND=clip

To get real face recognition:

    pip install insightface onnxruntime
    # in .env: FACE_EMBEDDING_BACKEND=arcface

on a machine with normal internet access (GPU optional — CPU inference
works, just slower per photo/face). The first photo/face processed after
that triggers a one-time download of the respective model checkpoint.

---

## 2. Architecture

```
React Frontend (Vite/TS/Tailwind)
       |
       | REST (JWT bearer auth)
       v
FastAPI Backend
       |
       +--------------------+
       |                    |
       v                    v
  PostgreSQL           AI Processing (Phase 3+)
   + pgvector           - CLIP/OpenCLIP embeddings
  (Phase 3+)            - Face detection + embeddings
       |                - Object detection (YOLO)
       |                - Captioning/tagging
       |                - EXIF extraction
       v
  Redis + Celery/RQ (Phase 3+, background jobs)
```

Photo processing is designed to be fully asynchronous: uploads create a
`processing_jobs` row and return immediately; a worker pool does EXIF
extraction, thumbnailing, embedding, face/object detection, and captioning
in the background, updating `photos.processing_status` as it goes.

---

## 3. Project structure

```
ai-gallery-search/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # auth.py, photos.py, search.py, people.py, albums.py,
│   │   │                      # locations.py, settings.py, jobs.py, stats.py
│   │   ├── core/             # config, database, security (JWT/bcrypt), rate_limit, deps
│   │   ├── models/           # SQLAlchemy models — the full 14-table schema (+faces.person_id, Phase 6)
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── services/         # storage, hashing, exif, thumbnail, photo_processor,
│   │   │                      # search, query_parser, ranking, face_processor,
│   │   │                      # object_processor, caption_generator
│   │   ├── ai/                # embedder.py/clip_embedder.py/stub_embedder.py/factory.py (images),
│   │   │                      # face_detector.py/haar_face_detector.py (real), arcface_embedder.py/
│   │   │                      # face_embedder_stub.py/face_factory.py (faces), object_detector.py/
│   │   │                      # yolo_object_detector.py (real)/object_detector_noop.py/object_factory.py
│   │   ├── workers/          # (future) Celery/RQ tasks, if the sync BackgroundTasks
│   │   │                      # approach ever needs to scale beyond a single process
│   │   └── main.py
│   ├── alembic/               # versioned schema migrations (pgvector, faces.person_id, etc.)
│   ├── tests/                 # test_auth, test_photos, test_embeddings, test_search,
│   │                           # test_query_parser, test_hybrid_search, test_face_detection,
│   │                           # test_face_clustering, test_object_detection, test_object_search,
│   │                           # test_person_search, test_phase8_features, test_phase9_features,
│   │                           # test_phase9_edge_cases — 92 passing
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/              # axios client with auto-refresh, auth calls
│   │   ├── context/          # AuthContext
│   │   ├── components/       # ProtectedRoute, Thumbnail (auth'd blob fetch)
│   │   └── pages/            # LoginPage, RegisterPage, DashboardPage, PhotosPage,
│   │                          # PhotoDetailPage, SearchResultsPage, PeoplePage,
│   │                          # AlbumsPage, LocationsPage, TimelinePage, SettingsPage
│   ├── Dockerfile, nginx.conf
│   └── .env.example
├── docker-compose.yml
├── .env.example
└── README.md (this file)
```

---

## 4. Running it

### Option A — Docker Compose (recommended once you're off the sandbox)

```bash
cp .env.example .env          # fill in a real JWT_SECRET_KEY
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

The backend image runs `alembic upgrade head` automatically before starting
(see `backend/Dockerfile`).

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:5173

### Option B — Run locally without Docker

**Backend:**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Make sure Postgres is running and DATABASE_URL in .env points at it
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Running tests

```bash
cd backend
createdb ai_gallery_test   # or: psql -c "CREATE DATABASE ai_gallery_test;"
psql ai_gallery_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
pytest -q
```

Tests force `EMBEDDING_BACKEND=deterministic_stub` (via `.env`) so they never
need real CLIP weights — see section 5 below.

---

## 5. Database & the embedding pipeline

Schema is managed by **Alembic** (`backend/alembic/`) — run migrations
before starting the app:

```bash
cd backend
alembic upgrade head
```

`photo_embeddings.embedding` and `face_embeddings.embedding` are real
pgvector `vector(512)` columns with HNSW cosine-similarity indexes (the
baseline migration creates the `vector` extension, the tables, and the
indexes together).

The embedding step itself is pluggable via `EMBEDDING_BACKEND`:
- `clip` (recommended for any real deployment) — `app/ai/clip_embedder.py`,
  a complete OpenCLIP implementation. Requires `pip install torch
  open_clip_torch` and internet access to fetch the pretrained checkpoint on
  first use.
- `deterministic_stub` — `app/ai/stub_embedder.py`, a dependency-free
  pixel-based stand-in. It produces a real 512-dim vector so the storage and
  cosine-similarity plumbing works end-to-end, but it has no semantic
  understanding of image content — don't expect "beach" to find beach
  photos with this backend. It exists specifically for environments (like
  the sandbox this was built in) that can't reach Hugging Face/OpenAI's
  model hosts or don't have room for torch.

Swapping backends is a one-line `.env` change; nothing else in the codebase
needs to know which is active.

---

## 6. Security & privacy (what's implemented, what's planned)

Implemented now:
- Bcrypt password hashing, JWT access + refresh tokens with `type` claims
  (a refresh token can never be replayed as an access token — tested),
  and rejection of expired, malformed, tampered, and reference-to-
  nonexistent-user tokens (all tested — Phase 9).
- Every protected route resolves the user from the token and every query is
  scoped to `user_id` — no endpoint currently allows fetching another
  user's data (tested across photos, albums, people, jobs, and search).
- Generic "incorrect email or password" error, so login can't be used to
  enumerate registered emails.
- Rate limiting on `/api/auth/register` and `/api/auth/login` (`slowapi`,
  keyed by IP) — the classic brute-force/enumeration targets.
- Path-traversal-safe file storage (every stored file gets a UUID name;
  `LocalStorage._safe_join` rejects any resolved path that escapes its
  root) and upload validation (real image-content verification via
  Pillow, not just the declared MIME type; file-size limits).
- SHA-256 dedup enforced at the database level (`uq_user_file_hash`), not
  just the application-level check — tested by bypassing the app check
  directly.
- "Delete all photos and AI data" (`POST /api/settings/delete-all-data`,
  Settings page) — a real, tested full wipe of photos, embeddings, faces,
  detected objects, people, albums, and search history; the account
  itself is kept.

Photos and embeddings stay on your own filesystem/Postgres instance by
default — no third-party AI API calls are made unless you explicitly
configure the real CLIP/ArcFace backends (which fetch model weights, not
photo data, from their providers).

Not yet implemented: CSRF protection (relevant if this is ever deployed
with cookie-based auth instead of bearer tokens), and a broader rate limit
across upload/search endpoints for a multi-tenant deployment (the current
limiter only covers auth, on the reasoning that a single logged-in user's
legitimate usage shouldn't be throttled — revisit if this ever serves
untrusted or shared-credential traffic).

---

## 7. Roadmap

- [x] **Phase 1** — Frontend + backend foundation, PostgreSQL schema, JWT auth
- [x] **Phase 2** — Photo upload/import, EXIF extraction, thumbnailing, dedup by SHA-256
- [x] **Phase 3** — AI indexing pipeline (pgvector schema + HNSW indexes, swappable CLIP/stub embedder, embeddings stored on upload)
- [x] **Phase 4** — Vector similarity search API (`/api/search/semantic`, threshold filtering, search history, frontend search results page)
- [x] **Phase 5** — Natural-language query parsing (dates, ranges, relative phrases) + hybrid ranked search (`POST /api/search`)
- [x] **Phase 6** — Face detection (real, OpenCV Haar Cascade), clustering, and naming (`/api/people`)
- [x] **Phase 7** — Object detection (real, YOLOv8n), rule-based captions/tags, and person/object-aware hybrid search
- [x] **Phase 8** — Full UI: photo grid enhancements, photo detail, timeline, albums, locations, settings ("delete all my data")
- [x] **Phase 9** — Broader test coverage: rate limiting, jobs/retry API, JWT edge cases, DB-level dedup constraint, pipeline partial-failure resilience (92 tests total)
- [ ] **Phase 10** — Production Docker hardening + deployment docs

---

## 8. Troubleshooting

- **`ImportError: email-validator is not installed`** — run
  `pip install email-validator` (already pinned in `requirements.txt`).
- **Backend can't reach Postgres** — confirm the service is running
  (`pg_isready`) and `DATABASE_URL` in `.env` matches your host/port/credentials.
- **`relation "vector" does not exist` / migration fails on vector type** —
  the `vector` extension needs superuser rights to create; make sure the DB
  user in `DATABASE_URL` can run `CREATE EXTENSION`, or run
  `CREATE EXTENSION vector;` manually first.
- **CORS errors in the browser** — make sure `CORS_ORIGINS` in the backend
  `.env` includes the exact frontend origin you're using (protocol + host + port).


  & "C:\Users\Lenovo\Downloads\postgresql-18.6-3-windows-x64-binaries (1)\pgsql\bin\pg_ctl.exe" -D "C:\PostgreSQL\data" -l "C:\PostgreSQL\postgres.log" start


  cd "C:\Users\Lenovo\Downloads\ai-gallery-search (1)\ai-gallery-search\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload



cd "C:\Users\Lenovo\Downloads\ai-gallery-search (1)\ai-gallery-search\frontend"
npm run dev
