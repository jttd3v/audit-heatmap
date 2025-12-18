from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import date
import pyodbc

from database import get_db_connection, init_database
from models import AuditCreate, AuditUpdate, AuditResponse, AuditCountByDate, YearlyStats

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
# CRUD ENDPOINTS
# ========================================

@app.post("/api/audits", response_model=AuditResponse, tags=["Audits"])
async def create_audit(audit: AuditCreate):
    """Create a new audit (internal or external)."""
    if audit.audit_type not in ['internal', 'external']:
        raise HTTPException(status_code=400, detail="audit_type must be 'internal' or 'external'")
    
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
        conn.commit()
        conn.close()
        
        return AuditResponse(
            id=row.id,
            audit_type=row.audit_type,
            title=row.title,
            description=row.description,
            audit_date=row.audit_date,
            created_at=row.created_at,
            updated_at=row.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audits", response_model=List[AuditResponse], tags=["Audits"])
async def get_audits(
    audit_type: Optional[str] = Query(None, description="Filter by 'internal' or 'external'"),
    year: Optional[int] = Query(None, description="Filter by year"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date")
):
    """Get all audits with optional filters."""
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
        conn.close()
        
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


@app.get("/api/audits/{audit_id}", response_model=AuditResponse, tags=["Audits"])
async def get_audit(audit_id: int):
    """Get a specific audit by ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, audit_type, title, description, audit_date, created_at, updated_at 
            FROM Audits WHERE id = ?
        """, (audit_id,))
        
        row = cursor.fetchone()
        conn.close()
        
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


@app.put("/api/audits/{audit_id}", response_model=AuditResponse, tags=["Audits"])
async def update_audit(audit_id: int, audit: AuditUpdate):
    """Update an existing audit."""
    try:
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
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
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
        conn.commit()
        conn.close()
        
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


@app.delete("/api/audits/{audit_id}", tags=["Audits"])
async def delete_audit(audit_id: int):
    """Delete an audit."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM Audits WHERE id = ?", (audit_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Audit not found")
        
        conn.commit()
        conn.close()
        
        return {"message": "Audit deleted successfully", "id": audit_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# HEATMAP SPECIFIC ENDPOINTS
# ========================================

@app.get("/api/heatmap/{year}", response_model=List[AuditCountByDate], tags=["Heatmap"])
async def get_heatmap_data(year: int):
    """Get audit counts grouped by date for heatmap visualization."""
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
        conn.close()
        
        return [
            AuditCountByDate(
                date=row[0],
                internal=row[1],
                external=row[2],
                total=row[3]
            )
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/{year}", response_model=YearlyStats, tags=["Statistics"])
async def get_yearly_stats(year: int):
    """Get yearly statistics for the heatmap header."""
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
        conn.close()
        
        return YearlyStats(
            year=year,
            total_audits=row[0] or 0,
            internal_count=row[1] or 0,
            external_count=row[2] or 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audits/date/{date_str}", response_model=List[AuditResponse], tags=["Audits"])
async def get_audits_by_date(date_str: str):
    """Get all audits for a specific date (for tooltip/detail view)."""
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
        conn.close()
        
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


# ========================================
# HEALTH CHECK
# ========================================

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Check API and database health."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
