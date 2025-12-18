# 🗺️ HEATMAP PROJECT - CONTEXT MAP
> **Single Source of Truth for AI Sessions**  
> Last Updated: 2024-12-18

---

## 📋 Project Metadata

| Attribute | Value |
|-----------|-------|
| **Project Name** | Audit Heatmap |
| **Core Goal** | Visualize internal/external audits on an interactive calendar heatmap |
| **Architecture** | Client-Server (REST API) |

### Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript | ES6+ |
| **Backend API** | Python + FastAPI | 3.14 / 0.115+ |
| **Database** | Microsoft SQL Server | MSSQL |
| **DB Driver** | pyodbc | 5.1+ |
| **ASGI Server** | Uvicorn | 0.32+ |
| **Config** | python-dotenv | 1.0+ |
| **Validation** | Pydantic | 2.10+ |

---

## 📁 File Index Table

| File Name | Purpose | Key Logic/Patterns |
|-----------|---------|-------------------|
| `01_Architecture.md` | High-level design & Data Flow | API endpoints, CORS, request lifecycle |
| `02_DataModels.md` | DB Schema & DTOs | `Audits` table, Pydantic models |
| `03_BusinessLogic.md` | Calculation rules & Services | Heatmap aggregation, date filtering |
| `04_UI_Guidelines.md` | Frontend implementation rules | Calendar rendering, color scales |
| `05_API_Reference.md` | REST API documentation | Endpoints, payloads, responses |

---

## 🔒 Global Rules (Anti-Hallucination)

### Python/FastAPI Rules
- ✅ Always use `async def` for route handlers
- ✅ Use Pydantic models for request/response validation
- ✅ Use `pyodbc` with parameterized queries (prevent SQL injection)
- ✅ Close DB connections in `finally` blocks or use context managers
- ✅ Use `python-dotenv` for environment configuration
- ✅ Return proper HTTP status codes (200, 201, 400, 404, 500)

### Database Rules
- ✅ Database name: `heatmapdb`
- ✅ Use Windows Authentication (`Trusted_Connection=yes`) by default
- ✅ Use `ODBC Driver 17 for SQL Server`
- ✅ Always use parameterized queries, never string concatenation
- ✅ Use `NVARCHAR` for text fields (Unicode support)

### Frontend Rules
- ✅ Use `fetch()` API for HTTP requests
- ✅ Handle loading states and errors gracefully
- ✅ Use CSS Grid/Flexbox for calendar layout
- ✅ Color scale: Green (low) → Yellow → Red (high audit density)
- ✅ Store API base URL in config constant

### API Design Rules
- ✅ Base URL: `http://localhost:8000/api`
- ✅ Use RESTful conventions: `GET /audits`, `POST /audits`, `DELETE /audits/{id}`
- ✅ JSON request/response bodies
- ✅ Enable CORS for frontend communication

---

## 🗂️ Project Structure

```
audit-heatmap/
├── index.html          # Main frontend page
├── script.js           # Frontend JavaScript logic
├── styles.css          # Styling & heatmap colors
├── HeatmapDocs/        # AI Context Documentation
│   └── 00_CONTEXT_MAP.md
└── backend/
    ├── main.py         # FastAPI application & routes
    ├── database.py     # MSSQL connection & init
    ├── models.py       # Pydantic schemas
    ├── requirements.txt
    ├── run.bat         # Windows startup script
    └── .env            # Environment config (git-ignored)
```

---

## 🚀 Quick Start Commands

```powershell
# Activate virtual environment
& ".venv\Scripts\Activate.ps1"

# Install dependencies
pip install -r backend/requirements.txt

# Initialize database
python backend/database.py

# Start API server
uvicorn backend.main:app --reload --port 8000
```

---

## 📝 Session Handoff Notes
> *Use this section to pass context between AI sessions*

- [ ] Backend API routes implemented
- [ ] Frontend connected to API
- [ ] CRUD operations tested
- [ ] Heatmap visualization complete
