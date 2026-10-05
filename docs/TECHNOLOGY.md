# AtharVision AI - Technology Documentation

## 1. Project Summary

AtharVision AI is a personal AI photo gallery that lets users upload, organize, inspect, and search photos using:

- Natural-language search
- Dates and timeline grouping
- GPS and place metadata
- People and face grouping
- Detected objects and categories
- Albums and favorites
- Laptop webcam capture

The application uses a React frontend, a FastAPI backend, PostgreSQL with pgvector, and an image-processing pipeline.

## 2. Technology Stack

| Area | Technology | Purpose |
|---|---|---|
| Frontend language | TypeScript | Type-safe UI and API models |
| Frontend framework | React 19 | Component-based user interface |
| Frontend build tool | Vite 8 | Development server and production bundling |
| Frontend routing | React Router 7 | Login, dashboard, photos, people, locations, albums, settings |
| Frontend styling | Tailwind CSS 4 | Utility styling and responsive layout |
| HTTP client | Axios | REST API calls and JWT refresh handling |
| Backend language | Python 3.11 | API and processing services |
| Backend framework | FastAPI | REST API, validation, OpenAPI documentation |
| ASGI server | Uvicorn | Runs the FastAPI application |
| ORM | SQLAlchemy 2 | Database models and queries |
| Database migration | Alembic | Versioned schema migrations |
| Database | PostgreSQL | Users, photos, metadata, AI results, albums, history |
| Vector database support | pgvector | 512-dimensional image and face vectors |
| PostgreSQL driver | psycopg2-binary | Python to PostgreSQL connection |
| Image processing | Pillow | Decode images, validate images, generate thumbnails |
| EXIF parsing | piexif and Pillow | Capture date, GPS, camera information |
| HEIC support | pillow-heif | Read HEIC images where supported |
| Object detection | Ultralytics YOLOv8n | Detect objects such as people, cats, cars, and laptops |
| Face detection | OpenCV Haar Cascade | Detect faces locally without model downloads |
| Face embedding | Deterministic stub locally / ArcFace option | Group similar faces; ArcFace is the production option |
| Image embedding | Deterministic stub locally / OpenCLIP option | Semantic image and text search |
| Authentication | JWT via python-jose | Access and refresh tokens |
| Password security | Passlib + bcrypt | Hash and verify passwords |
| Rate limiting | SlowAPI | Limits login and registration attempts |
| Testing | Pytest + HTTPX | API, service, and integration tests |

## 3. Repository Structure

```text
ai-gallery-search/
|-- backend/
|   |-- app/
|   |   |-- ai/                 AI interfaces, YOLO, OpenCV, embeddings
|   |   |-- api/routes/          FastAPI route modules
|   |   |-- core/                Config, database, security, dependencies
|   |   |-- models/              SQLAlchemy database models
|   |   |-- schemas/             Pydantic request and response schemas
|   |   |-- services/            Upload, EXIF, thumbnails, search, ranking
|   |-- alembic/                Database migrations
|   |-- tests/                  Backend tests
|   |-- requirements.txt        Python dependencies
|   |-- .env                    Local runtime configuration
|-- frontend/
|   |-- src/
|   |   |-- api/                Axios API modules
|   |   |-- components/         Shared UI components and application shell
|   |   |-- context/            Authentication state
|   |   |-- pages/              Application screens
|   |-- package.json            Node dependencies and scripts
|-- docs/
|   |-- TECHNOLOGY.md          This document
|-- docker-compose.yml          PostgreSQL, Redis, backend, frontend services
```

## 4. Frontend Architecture

The frontend is a React single-page application.

### Main screens

- Login and registration
- Dashboard command center
- Photos library
- Photo detail
- Smart filters
- People
- Locations
- Timeline
- Albums
- Settings
- Search results

### Frontend flow

```mermaid
flowchart LR
    Browser[Browser] --> Router[React Router]
    Router --> Shell[AppShell]
    Shell --> Pages[Protected Pages]
    Pages --> API[Axios API Client]
    API --> Auth[JWT access token]
    API --> Backend[FastAPI REST API]
    Backend --> API
```

### Authentication behavior

1. User submits email and password.
2. Axios sends the request to `/api/auth/login`.
3. Backend returns an access token and refresh token.
4. Tokens are stored by the authentication context.
5. Protected routes redirect unauthenticated users to `/login`.
6. Axios attempts token refresh after an expired access-token response.

## 5. Backend Architecture

The backend is organized around route modules, services, AI interfaces, and persistence models.

### Route modules

| Route prefix | Responsibility |
|---|---|
| `/api/auth` | Register, login, refresh token, current user |
| `/api/photos` | Upload, list, detail, thumbnail, original, favorite, delete |
| `/api/search` | Semantic search, hybrid search, search history |
| `/api/people` | Face groups, rename people, person photo collections |
| `/api/locations` | GPS clusters and all location photos |
| `/api/albums` | Create albums and manage album photos |
| `/api/jobs` | Processing job inspection and photo retry |
| `/api/settings` | Delete all user photo and AI data |
| `/api/stats` | Dashboard counts |

### Backend flow

```mermaid
flowchart TD
    Client[React browser] --> AuthMiddleware[JWT authentication]
    AuthMiddleware --> Routes[FastAPI routes]
    Routes --> Schemas[Pydantic schemas]
    Routes --> Services[Domain services]
    Services --> ORM[SQLAlchemy ORM]
    ORM --> PostgreSQL[(PostgreSQL + pgvector)]
    Services --> Storage[Local photo storage]
    Services --> AI[AI adapters]
    AI --> YOLO[YOLO object detector]
    AI --> OpenCV[OpenCV face detector]
    AI --> Embeddings[CLIP or deterministic image embeddings]
```

## 6. Database

The default local database configuration is:

```text
postgresql+psycopg2://postgres:postgres@localhost:5432/ai_gallery
```

Schema changes are managed by Alembic. The vector extension is used for `vector(512)` columns and cosine similarity search.

### Tables

| Table | Purpose | Important relationships |
|---|---|---|
| `users` | User accounts and password hashes | Owns photos, people, albums, history |
| `photos` | Original photo records and processing state | Belongs to one user |
| `photo_metadata` | EXIF, dates, GPS, camera, caption, tags | One-to-one with photos |
| `processing_jobs` | EXIF, thumbnail, embedding, face, object job records | Belongs to a photo and user |
| `photo_embeddings` | Image embedding vectors | One-to-one with photos |
| `faces` | Detected face boxes and assigned person IDs | Belongs to photo and optionally person |
| `face_embeddings` | Face recognition vectors | Belongs to a face |
| `people` | Per-user face groups | Has many faces and photo links |
| `photo_people` | Derived photo-to-person search links | Many-to-many photos and people |
| `objects` | Shared detected object vocabulary | Examples: person, cat, laptop |
| `photo_objects` | Photo-to-object links and confidence | Many-to-many photos and objects |
| `albums` | User-created collections | Belongs to one user |
| `album_photos` | Album-to-photo links | Many-to-many albums and photos |
| `search_history` | Original query, parsed filters, result count | Belongs to one user |

### Database relationships

```mermaid
erDiagram
    USERS ||--o{ PHOTOS : owns
    PHOTOS ||--|| PHOTO_METADATA : has
    PHOTOS ||--o{ PROCESSING_JOBS : creates
    PHOTOS ||--o| PHOTO_EMBEDDINGS : has
    PHOTOS ||--o{ FACES : contains
    FACES ||--o| FACE_EMBEDDINGS : has
    PEOPLE ||--o{ FACES : groups
    PHOTOS ||--o{ PHOTO_PEOPLE : links
    PEOPLE ||--o{ PHOTO_PEOPLE : links
    OBJECTS ||--o{ PHOTO_OBJECTS : labels
    PHOTOS ||--o{ PHOTO_OBJECTS : contains
    USERS ||--o{ PEOPLE : owns
    USERS ||--o{ ALBUMS : owns
    ALBUMS ||--o{ ALBUM_PHOTOS : contains
    PHOTOS ||--o{ ALBUM_PHOTOS : appears
    USERS ||--o{ SEARCH_HISTORY : creates
```

## 7. Upload and AI Processing Flow

Uploads support multiple files, drag-and-drop, folder selection, and laptop webcam capture.

```mermaid
sequenceDiagram
    participant U as User
    participant F as React frontend
    participant A as FastAPI upload route
    participant S as Local storage
    participant D as PostgreSQL
    participant P as Photo processor
    participant M as AI models

    U->>F: Select file or capture webcam photo
    F->>F: Request browser GPS for webcam capture
    F->>A: POST /api/photos/upload multipart form
    A->>A: Validate size, MIME type, image bytes
    A->>A: SHA-256 duplicate check
    A->>S: Save original photo
    A->>D: Create pending photo and optional GPS metadata
    A-->>F: Return accepted result
    A->>P: Start background processing
    P->>S: Read original bytes
    P->>P: Extract EXIF and fallback capture date
    P->>S: Generate and save thumbnail
    P->>M: Generate image embedding
    P->>M: Detect faces and group people
    P->>M: Detect objects with YOLO
    P->>D: Save metadata, vectors, labels, and jobs
    P->>D: Mark photo ready
    F->>A: Poll photo list
    A-->>F: Return ready photo
```

### Processing stages

1. Validate the uploaded image.
2. Detect duplicate content using SHA-256.
3. Save the original file under the user storage directory.
4. Create a database row with `pending` status.
5. Extract EXIF date, GPS, camera, orientation, width, and height.
6. Use file timestamps when capture date is absent.
7. Generate a maximum 480px thumbnail.
8. Generate an image embedding.
9. Detect and cluster faces.
10. Detect objects and store confidence values.
11. Generate rule-based captions and tags.
12. Mark the photo `ready` unless an essential stage fails.

## 8. Search Flow

The main search endpoint is `POST /api/search`.

```mermaid
flowchart TD
    Query[User query] --> Date[Parse dates and relative phrases]
    Date --> Person[Match named person]
    Person --> Object[Match exact object or category alias]
    Object --> Location[Match saved place name or Place metadata]
    Location --> Remaining[Remaining semantic text]
    Remaining -->|Text exists| Embed[Create text embedding]
    Embed --> Vector[pgvector cosine search]
    Remaining -->|No text| SQL[SQL filters only]
    Vector --> Combine[Combine active scores]
    SQL --> Combine
    Combine --> Results[User-scoped search results]
    Results --> History[Save search history]
```

### Supported category aliases

- `people`, `man`, `men`, `woman`, `women` map to the detected `person` class.
- `animal` and `animals` map to detected animal classes such as `cat`, `dog`, and `bird`.
- `fruit` and `fruits` map to detected classes such as `apple`, `banana`, and `orange`.
- `place` returns photos with GPS or saved place metadata.
- Exact object labels such as `cat`, `laptop`, `car`, or `person` are also supported.

All results are filtered by the authenticated user and exclude deleted photos.

## 9. Location Flow

### GPS sources

1. Original mobile photo EXIF GPS data.
2. Browser geolocation for laptop webcam captures.
3. Manually stored `location_name` values.

For webcam captures, the browser requests location permission and reverse-geocodes coordinates through Nominatim when available. The coordinates are still saved if reverse geocoding is unavailable.

```mermaid
flowchart LR
    Photo[Photo capture] --> GPS{GPS available?}
    GPS -->|EXIF| Extract[Extract latitude and longitude]
    GPS -->|Browser permission| BrowserGPS[Browser geolocation]
    GPS -->|No| None[No location metadata]
    BrowserGPS --> Reverse[Reverse geocode place name]
    Extract --> Store[Store GPS and optional place name]
    Reverse --> Store
    Store --> LocationPage[Locations page and Place filter]
```

## 10. Current Local AI Configuration

The local Windows setup uses lightweight fallbacks where model dependencies or model downloads are unavailable:

```text
EMBEDDING_BACKEND=deterministic_stub
FACE_DETECTION_BACKEND=haarcascade
FACE_EMBEDDING_BACKEND=deterministic_stub
OBJECT_DETECTION_BACKEND=yolo
```

This means:

- YOLO object detection is active.
- OpenCV Haar face detection is active.
- Deterministic face embeddings are used for local grouping.
- Deterministic image embeddings are used for local semantic search.

For production-quality semantic image search and face recognition, install the optional model libraries and weights:

```text
pip install torch open_clip_torch
pip install insightface onnxruntime
```

Then configure:

```text
EMBEDDING_BACKEND=clip
FACE_EMBEDDING_BACKEND=arcface
```

## 11. Runtime Commands

### Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload
```

Backend URL: `http://127.0.0.1:8000`

Health check:

```text
GET /api/health
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL is normally `http://localhost:5173`. If that port is busy, Vite selects another port such as `5174`.

### Validation

```powershell
cd frontend
npm run build

cd ..\backend
pytest -q
```

## 12. Security and Reliability

- Passwords are stored as bcrypt hashes, never plaintext.
- JWT access and refresh tokens use separate token types.
- Photo, album, person, location, and search data are user-scoped.
- Uploads validate actual image bytes instead of trusting MIME types.
- SHA-256 deduplication prevents repeated uploads per user.
- Login and registration are rate-limited with SlowAPI.
- Failed processing stages create job records and support retry.
- Original files are stored outside the frontend public directory.
- Alembic manages schema changes instead of automatic table creation.

## 13. Known Limitations

- Laptop webcams do not provide GPS themselves; browser location permission is required.
- Place names depend on reverse-geocoding availability. GPS coordinates remain the fallback.
- YOLO can detect its trained object vocabulary, but it cannot reliably identify every landmark. A landmark such as the Taj Mahal may need a saved place name or manual tag.
- Haar Cascade face detection is a local baseline and is less accurate than modern deep-learning face detectors.
- Deterministic embeddings are suitable for local plumbing and testing, but CLIP and ArcFace provide better production search and identity matching.
- Redis and a dedicated worker are represented in `docker-compose.yml`; the standalone Windows workflow currently uses FastAPI background tasks.
