# Coventry University Course Scraper

A full-stack application that scrapes postgraduate course data from [coventry.ac.uk](https://www.coventry.ac.uk) in real time. The backend is built with FastAPI and Python, the frontend with React and TypeScript. All course data is fetched live — nothing is hardcoded.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Dependencies](#project-dependencies)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Running the Application](#running-the-application)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [How the Scraper Works](#how-the-scraper-works)
- [Output Format](#output-format)
- [Maintaining the Scraper](#maintaining-the-scraper)

---

## Prerequisites

Before setting up the project, make sure the following are installed on your system:

- **Python 3.11 or higher** — [Download](https://www.python.org/downloads/)
- **Node.js 18 or higher** (includes npm) — [Download](https://nodejs.org/)
- **pip** — Ships with Python. Verify with `pip --version`.
- **Git** — To clone the repository.

---

## Project Dependencies

### Backend (Python)

All backend dependencies are listed in `backend/requirements.txt`:

| Package             | Purpose                                      |
|---------------------|----------------------------------------------|
| fastapi >=0.111.0   | Web framework for the REST API               |
| uvicorn[standard]   | ASGI server to run the FastAPI app            |
| httpx               | Async HTTP client for fetching course pages   |
| beautifulsoup4      | HTML parsing and data extraction              |
| lxml                | Fast HTML/XML parser used by BeautifulSoup    |
| pydantic >=2.7.0    | Request/response validation and data models   |
| pydantic-settings   | Environment variable configuration            |
| python-multipart    | Form data handling in FastAPI                 |
| aiofiles            | Async file I/O                               |
| anyio               | Async compatibility layer                    |

### Frontend (Node.js / TypeScript)

All frontend dependencies are listed in `frontend/package.json`:

| Package                  | Purpose                                   |
|--------------------------|-------------------------------------------|
| react, react-dom         | UI framework                              |
| @tanstack/react-query    | Server state management and data fetching |
| axios                    | HTTP client for API calls                 |
| tailwindcss              | Utility-first CSS framework               |
| vite                     | Build tool and dev server                 |
| typescript               | Static type checking                      |

---

## Project Structure

```
coventry-scraper/
├── backend/
│   ├── main.py               # FastAPI application, CORS config, API routes
│   ├── scraper_service.py    # Async scraper logic, runs as a background task
│   ├── discovery.py          # Discovers course URLs from the A-Z listing page
│   ├── extractors.py         # Field-level extraction functions (one per data field)
│   ├── models.py             # Pydantic models: CourseRecord, ScrapeJob, ScrapeEvent
│   ├── job_store.py          # In-memory store for scrape job state
│   └── requirements.txt     # Python dependencies
└── frontend/
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── index.css
    │   ├── api/scraperApi.ts        # API client and SSE event wrapper
    │   ├── hooks/
    │   │   ├── useScrapeJob.ts      # React Query mutation and polling hook
    │   │   └── useSSELog.ts         # EventSource hook for live log streaming
    │   ├── components/
    │   │   ├── TerminalLog.tsx      # Real-time log output panel
    │   │   ├── CourseGrid.tsx       # Filtered grid of scraped course cards
    │   │   ├── CourseCard.tsx       # Expandable card showing all 27 fields
    │   │   ├── MetricBar.tsx        # Summary metric cards
    │   │   ├── JsonViewer.tsx       # JSON viewer with syntax highlighting and download
    │   │   └── FilterBar.tsx        # Search and campus filter controls
    │   └── types/index.ts           # Shared TypeScript interfaces
    ├── index.html
    ├── package.json
    ├── vite.config.ts               # Dev proxy: /api -> localhost:8000
    └── tailwind.config.ts
```

---

## Setup and Installation

### Step 1 — Clone the Repository

```bash
git clone <repository-url>
cd coventry-scraper
```

### Step 2 — Set Up the Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Step 3 — Set Up the Frontend

```bash
cd frontend

# Install Node.js dependencies
npm install
```

---

## Running the Application

Both the backend and frontend need to be running at the same time. Open two terminal windows.

### Terminal 1 — Start the Backend

```bash
cd coventry-scraper/backend
.venv\Scripts\activate        # or source .venv/bin/activate on macOS/Linux
uvicorn main:app --reload
```

The API server starts at `http://localhost:8000`. You can access the auto-generated API docs at `http://localhost:8000/docs`.

### Terminal 2 — Start the Frontend

```bash
cd coventry-scraper/frontend
npm run dev
```

The frontend starts at `http://localhost:5173`. The Vite dev server is configured to proxy all `/api/*` requests to `http://localhost:8000`, so no additional CORS setup is needed during development.

### Using the Application

1. Open `http://localhost:5173` in your browser.
2. Click the button to start a scrape job.
3. The terminal log panel shows real-time progress as pages are fetched and parsed.
4. Once scraping completes, course cards appear in the grid below.
5. Use the filter bar to search by course name or filter by campus.
6. Use the JSON viewer to inspect the raw output or download it as a file.

---

## Environment Variables

Optionally, create a `.env` file inside the `backend/` directory to override defaults:

```
TARGET_COUNT=5
REQUEST_DELAY=1.5
CORS_ORIGIN_PROD=
```

| Variable          | Default | Description                                              |
|-------------------|---------|----------------------------------------------------------|
| TARGET_COUNT      | 5       | Number of courses to scrape per job                      |
| REQUEST_DELAY     | 1.5     | Delay in seconds between HTTP requests (rate limiting)   |
| CORS_ORIGIN_PROD  | (empty) | Allowed origin for production deployments                |

---

## API Endpoints

| Method | Route                     | Description                                       |
|--------|---------------------------|---------------------------------------------------|
| POST   | `/api/scrape`             | Starts a new scrape job. Returns `{ job_id }`.    |
| GET    | `/api/stream/{job_id}`    | Server-Sent Events stream of live scrape progress |
| GET    | `/api/results/{job_id}`   | Returns the full job object including results     |
| GET    | `/api/jobs`               | Lists all jobs with summary metadata              |
| GET    | `/api/download/{job_id}`  | Downloads results as `coventry_courses_output.json` |
| GET    | `/api/health`             | Basic health check                                |

---

## How the Scraper Works

1. A `POST /api/scrape` request creates a new `ScrapeJob` and spawns an `asyncio` background task.
2. The background task uses `discovery.py` to find course page URLs from the Coventry University A-Z listing. If the listing page is unavailable, it falls back to a set of seed URLs.
3. For each discovered URL, the scraper fetches the page with `httpx`, waits `REQUEST_DELAY` seconds, then passes the HTML to the 27 extraction functions in `extractors.py`.
4. Each extracted course is validated against the `CourseRecord` Pydantic model and appended to the job's results list.
5. Throughout the process, `ScrapeEvent` objects (log messages, progress updates, course records) are appended to the job's event log.
6. The SSE endpoint (`GET /api/stream/{job_id}`) polls the event log every 300ms and streams new events to the frontend.
7. The frontend receives these events via the browser's native `EventSource` API, updating the terminal log and course grid in real time.

There are no external task brokers (Celery, Redis) and no browser automation tools (Selenium, Playwright). Everything runs in-process using Python's `asyncio`.

---

## Output Format

The scraper produces a JSON file named `coventry_courses_output.json`, downloadable via the `/api/download/{job_id}` endpoint or through the frontend's download button.

The file contains an array of course objects. Each object has the following 27 fields:

```json
[
  {
    "program_course_name": "Data Science and Computational Intelligence MSc",
    "university_name": "Coventry University",
    "course_website_url": "https://www.coventry.ac.uk/course-structure/pg/...",
    "campus": "Coventry Main Campus",
    "country": "United Kingdom",
    "address": "Priory Street, Coventry, CV1 5FB",
    "study_level": "Postgraduate",
    "course_duration": "1 year full-time",
    "all_intakes_available": "September 2025, January 2026",
    "mandatory_documents_required": "Transcript, Degree Certificate, ...",
    "yearly_tuition_fee": "19,350 GBP",
    "scholarship_availability": "Details on the university website",
    "gre_gmat_mandatory_min_score": "Not required",
    "indian_regional_institution_restrictions": "No specific restrictions listed",
    "class_12_boards_accepted": "All recognized boards",
    "gap_year_max_accepted": "Not specified",
    "min_duolingo": "Not listed",
    "english_waiver_class12": "Not available",
    "english_waiver_moi": "Available with conditions",
    "min_ielts": "6.5 overall, no component below 5.5",
    "kaplan_test_of_english": "Not listed",
    "min_pte": "59",
    "min_toefl": "79",
    "ug_academic_min_gpa": "2:2 or equivalent",
    "twelfth_pass_min_cgpa": "Not specified",
    "mandatory_work_exp": "Not required",
    "max_backlogs": "Not specified"
  }
]
```

All field values are strings. Fields where data is unavailable on the course page are filled with descriptive fallback text (e.g., "Not specified", "Not listed") rather than null or empty values. The exact values depend on what the live course pages contain at the time of scraping.

---

## Maintaining the Scraper

If Coventry University redesigns their website, the extraction logic may need to be updated. Each function in `backend/extractors.py` documents the CSS selectors it uses and what to look for if the page structure changes.

**To update a field extractor:**

1. Open a course page in your browser's developer tools.
2. Locate the HTML element that contains the field you need to fix.
3. Note the new class name, `data-` attribute, or heading text.
4. Edit the corresponding `extract_*` function in `extractors.py`.
5. Restart the backend server. Changes take effect immediately.

**If the course listing page URL changes:**

Update `AZ_LISTING_URL` in `backend/discovery.py`. If the URL pattern for individual course pages changes, update `COURSE_PATH_RE` in the same file. The `SEED_URLS` fallback list should also be refreshed with currently valid course URLs.
