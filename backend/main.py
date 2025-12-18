from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import date
from pathlib import Path
import pyodbc
import re

from database import get_db_connection, init_database
from models import AuditCreate, AuditUpdate, AuditResponse, AuditCountByDate, YearlyStats

# Get the project root directory (parent of backend folder)
PROJECT_ROOT = Path(__file__).parent.parent

# ========================================
# VALIDATION CONSTANTS
# ========================================
VALID_AUDIT_TYPES = ['internal', 'external']
MIN_YEAR = 1900
MAX_YEAR = 2100
MAX_TITLE_LENGTH = 255
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')  # YYYY-MM-DD format

# Initialize FastAPI app
app = FastAPI(
    title="Audit Heatmap API",
    description="API for managing internal and external audits with heatmap visualization",
    version="1.0.0"
)

# CORS middleware - allows frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_database()


# ========================================
# ROOT & STATIC FILES
# ========================================

@app.get("/", tags=["Frontend"])
async def serve_index():
    """Serve the main index.html page."""
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/styles.css", tags=["Frontend"])
async def serve_css():
    """Serve the CSS file."""
    return FileResponse(PROJECT_ROOT / "styles.css")


@app.get("/script.js", tags=["Frontend"])
async def serve_js():
    """Serve the JavaScript file."""
    return FileResponse(PROJECT_ROOT / "script.js")


# ========================================
# CRUD ENDPOINTS
# ========================================

@app.post("/api/audits", response_model=AuditResponse, tags=["Audits"])
async def create_audit(audit: AuditCreate):
    """Create a new audit (internal or external)."""
    # Input validation
    if audit.audit_type not in VALID_AUDIT_TYPES:
        raise HTTPException(status_code=400, detail=f"audit_type must be one of: {VALID_AUDIT_TYPES}")
    
    if not audit.title or not audit.title.strip():
        raise HTTPException(status_code=400, detail="title cannot be empty")
    
    if len(audit.title) > MAX_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail=f"title cannot exceed {MAX_TITLE_LENGTH} characters")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Audits (audit_type, title, description, audit_date)
            OUTPUT INSERTED.id, INSERTED.audit_type, INSERTED.title, INSERTED.description, 
                   INSERTED.audit_date, INSERTED.created_at, INSERTED.updated_at
            VALUES (?, ?, ?, ?)
        """, (audit.audit_type, audit.title, audit.description, audit.audit_date))
        
        row = cursor.fetchone()
        
        # Guard clause: ensure row was returned before commit
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create audit - database returned no data")
        
        conn.commit()
        
        return AuditResponse(
            id=row.id,
            audit_type=row.audit_type,
            title=row.title,
            description=row.description,
            audit_date=row.audit_date,
            created_at=row.created_at,
            updated_at=row.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get("/api/audits", response_model=List[AuditResponse], tags=["Audits"])
async def get_audits(
    audit_type: Optional[str] = Query(None, description="Filter by 'internal' or 'external'"),
    year: Optional[int] = Query(None, description="Filter by year"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date")
):
    """Get all audits with optional filters."""
    # Input validation
    if audit_type and audit_type not in VALID_AUDIT_TYPES:
        raise HTTPException(status_code=400, detail=f"audit_type must be one of: {VALID_AUDIT_TYPES}")
    
    if year and (year < MIN_YEAR or year > MAX_YEAR):
        raise HTTPException(status_code=400, detail=f"year must be between {MIN_YEAR} and {MAX_YEAR}")
    
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date cannot be after end_date")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT id, audit_type, title, description, audit_date, created_at, updated_at FROM Audits WHERE 1=1"
        params = []
        
        if audit_type:
            query += " AND audit_type = ?"
            params.append(audit_type)
        
        if year:
            query += " AND YEAR(audit_date) = ?"
            params.append(year)
        
        if start_date:
            query += " AND audit_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND audit_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY audit_date DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Handle None or empty result gracefully
        if rows is None:
            return []
        
        return [
            AuditResponse(
                id=row.id,
                audit_type=row.audit_type,
                title=row.title,
                description=row.description,
                audit_date=row.audit_date,
                created_at=row.created_at,
                updated_at=row.updated_at
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get("/api/audits/{audit_id}", response_model=AuditResponse, tags=["Audits"])
async def get_audit(audit_id: int):
    """Get a specific audit by ID."""
    # Input validation
    if audit_id <= 0:
        raise HTTPException(status_code=400, detail="audit_id must be a positive integer")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, audit_type, title, description, audit_date, created_at, updated_at 
            FROM Audits WHERE id = ?
        """, (audit_id,))
        
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Audit not found")
        
        return AuditResponse(
            id=row.id,
            audit_type=row.audit_type,
            title=row.title,
            description=row.description,
            audit_date=row.audit_date,
            created_at=row.created_at,
            updated_at=row.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.put("/api/audits/{audit_id}", response_model=AuditResponse, tags=["Audits"])
async def update_audit(audit_id: int, audit: AuditUpdate):
    """Update an existing audit."""
    # Input validation
    if audit_id <= 0:
        raise HTTPException(status_code=400, detail="audit_id must be a positive integer")
    
    conn = None
    try:
        # Validate before opening connection
        if audit.title is None and audit.description is None and audit.audit_date is None:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Title validation
        if audit.title is not None:
            if not audit.title.strip():
                raise HTTPException(status_code=400, detail="title cannot be empty")
            if len(audit.title) > MAX_TITLE_LENGTH:
                raise HTTPException(status_code=400, detail=f"title cannot exceed {MAX_TITLE_LENGTH} characters")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build dynamic update query
        updates = []
        params = []
        
        if audit.title is not None:
            updates.append("title = ?")
            params.append(audit.title)
        
        if audit.description is not None:
            updates.append("description = ?")
            params.append(audit.description)
        
        if audit.audit_date is not None:
            updates.append("audit_date = ?")
            params.append(audit.audit_date)
        
        updates.append("updated_at = GETDATE()")
        params.append(audit_id)
        
        query = f"""
            UPDATE Audits SET {', '.join(updates)} 
            OUTPUT INSERTED.id, INSERTED.audit_type, INSERTED.title, INSERTED.description,
                   INSERTED.audit_date, INSERTED.created_at, INSERTED.updated_at
            WHERE id = ?
        """
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Audit not found")
        
        conn.commit()
        
        return AuditResponse(
            id=row.id,
            audit_type=row.audit_type,
            title=row.title,
            description=row.description,
            audit_date=row.audit_date,
            created_at=row.created_at,
            updated_at=row.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.delete("/api/audits/{audit_id}", tags=["Audits"])
async def delete_audit(audit_id: int):
    """Delete an audit."""
    # Input validation
    if audit_id <= 0:
        raise HTTPException(status_code=400, detail="audit_id must be a positive integer")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM Audits WHERE id = ?", (audit_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Audit not found")
        
        conn.commit()
        
        return {"message": "Audit deleted successfully", "id": audit_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ========================================
# HEATMAP SPECIFIC ENDPOINTS
# ========================================

@app.get("/api/heatmap/{year}", response_model=List[AuditCountByDate], tags=["Heatmap"])
async def get_heatmap_data(year: int):
    """Get audit counts grouped by date for heatmap visualization."""
    # Input validation
    if year < MIN_YEAR or year > MAX_YEAR:
        raise HTTPException(status_code=400, detail=f"year must be between {MIN_YEAR} and {MAX_YEAR}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                CONVERT(VARCHAR(10), audit_date, 120) as [date],
                SUM(CASE WHEN audit_type = 'internal' THEN 1 ELSE 0 END) as [internal],
                SUM(CASE WHEN audit_type = 'external' THEN 1 ELSE 0 END) as [external],
                COUNT(*) as [total]
            FROM Audits
            WHERE YEAR(audit_date) = ?
            GROUP BY audit_date
            ORDER BY audit_date
        """, (year,))
        
        rows = cursor.fetchall()
        
        # Handle None or empty result gracefully
        if rows is None:
            return []
        
        return [
            AuditCountByDate(
                date=row[0],
                internal=row[1] or 0,
                external=row[2] or 0,
                total=row[3] or 0
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get("/api/stats/{year}", response_model=YearlyStats, tags=["Statistics"])
async def get_yearly_stats(year: int):
    """Get yearly statistics for the heatmap header."""
    # Input validation
    if year < MIN_YEAR or year > MAX_YEAR:
        raise HTTPException(status_code=400, detail=f"year must be between {MIN_YEAR} and {MAX_YEAR}")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as [total],
                SUM(CASE WHEN audit_type = 'internal' THEN 1 ELSE 0 END) as [internal],
                SUM(CASE WHEN audit_type = 'external' THEN 1 ELSE 0 END) as [external]
            FROM Audits
            WHERE YEAR(audit_date) = ?
        """, (year,))
        
        row = cursor.fetchone()
        
        # Guard clause: handle case where row is None
        if not row:
            return YearlyStats(year=year, total_audits=0, internal_count=0, external_count=0)
        
        return YearlyStats(
            year=year,
            total_audits=row[0] or 0,
            internal_count=row[1] or 0,
            external_count=row[2] or 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@app.get("/api/audits/date/{date_str}", response_model=List[AuditResponse], tags=["Audits"])
async def get_audits_by_date(date_str: str):
    """Get all audits for a specific date (for tooltip/detail view)."""
    # Input validation - ensure date format is YYYY-MM-DD
    if not DATE_PATTERN.match(date_str):
        raise HTTPException(status_code=400, detail="date_str must be in YYYY-MM-DD format")
    
    # Validate date components are valid
    try:
        year, month, day = map(int, date_str.split('-'))
        date(year, month, day)  # Will raise ValueError if invalid
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date value")
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, audit_type, title, description, audit_date, created_at, updated_at 
            FROM Audits 
            WHERE CONVERT(VARCHAR(10), audit_date, 120) = ?
            ORDER BY audit_type, created_at
        """, (date_str,))
        
        rows = cursor.fetchall()
        
        # Handle None or empty result gracefully
        if rows is None:
            return []
        
        return [
            AuditResponse(
                id=row.id,
                audit_type=row.audit_type,
                title=row.title,
                description=row.description,
                audit_date=row.audit_date,
                created_at=row.created_at,
                updated_at=row.updated_at
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ========================================
# HEALTH CHECK
# ========================================

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Check API and database health."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
