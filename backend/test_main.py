"""
Unit tests for main.py - Audit Heatmap API
Run with: pytest backend/test_main.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import date, datetime

# Import the FastAPI app
import sys
sys.path.insert(0, 'backend')
from main import app

client = TestClient(app)


# ========================================
# MOCK DATA
# ========================================

class MockRow:
    """Mock database row object."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def create_mock_audit_row(id=1, audit_type="internal", title="Test Audit", 
                          description="Test description", audit_date=date(2025, 1, 15)):
    return MockRow(
        id=id,
        audit_type=audit_type,
        title=title,
        description=description,
        audit_date=audit_date,
        created_at=datetime(2025, 1, 15, 10, 0, 0),
        updated_at=datetime(2025, 1, 15, 10, 0, 0)
    )


# ========================================
# HEALTH CHECK TESTS
# ========================================

class TestHealthCheck:
    """Tests for /api/health endpoint."""
    
    @patch('main.get_db_connection')
    def test_health_check_healthy(self, mock_db):
        """Test health check returns healthy when DB is connected."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["database"] == "connected"
    
    @patch('main.get_db_connection')
    def test_health_check_unhealthy(self, mock_db):
        """Test health check returns unhealthy when DB fails."""
        mock_db.side_effect = Exception("Connection failed")
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"


# ========================================
# CREATE AUDIT TESTS
# ========================================

class TestCreateAudit:
    """Tests for POST /api/audits endpoint."""
    
    @patch('main.get_db_connection')
    def test_create_internal_audit_success(self, mock_db):
        """Test creating an internal audit."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = create_mock_audit_row()
        mock_db.return_value = mock_conn
        
        payload = {
            "audit_type": "internal",
            "title": "Test Audit",
            "description": "Test description",
            "audit_date": "2025-01-15"
        }
        
        response = client.post("/api/audits", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["audit_type"] == "internal"
        assert data["title"] == "Test Audit"
    
    @patch('main.get_db_connection')
    def test_create_external_audit_success(self, mock_db):
        """Test creating an external audit."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = create_mock_audit_row(audit_type="external")
        mock_db.return_value = mock_conn
        
        payload = {
            "audit_type": "external",
            "title": "External Audit",
            "description": "External audit description",
            "audit_date": "2025-02-20"
        }
        
        response = client.post("/api/audits", json=payload)
        
        assert response.status_code == 200
        assert response.json()["audit_type"] == "external"
    
    def test_create_audit_invalid_type(self):
        """Test creating audit with invalid audit_type returns 400."""
        payload = {
            "audit_type": "invalid",
            "title": "Test",
            "audit_date": "2025-01-15"
        }
        
        response = client.post("/api/audits", json=payload)
        
        assert response.status_code == 400
        assert "audit_type must be one of" in response.json()["detail"]
    
    def test_create_audit_missing_required_fields(self):
        """Test creating audit without required fields returns 422."""
        payload = {"audit_type": "internal"}  # Missing title and audit_date
        
        response = client.post("/api/audits", json=payload)
        
        assert response.status_code == 422
    
    @patch('main.get_db_connection')
    def test_create_audit_db_returns_null_row(self, mock_db):
        """Test creating audit when DB returns None (edge case for lines 58-65)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # Simulate DB returning no row
        mock_db.return_value = mock_conn
        
        payload = {
            "audit_type": "internal",
            "title": "Test Audit",
            "description": "Test description",
            "audit_date": "2025-01-15"
        }
        
        response = client.post("/api/audits", json=payload)
        
        # Now returns proper 500 with descriptive message
        assert response.status_code == 500
        assert "Failed to create audit" in response.json()["detail"]
    
    @patch('main.get_db_connection')
    def test_create_audit_db_connection_error(self, mock_db):
        """Test creating audit when DB connection fails."""
        mock_db.side_effect = Exception("Database connection failed")
        
        payload = {
            "audit_type": "internal",
            "title": "Test Audit",
            "description": "Test description",
            "audit_date": "2025-01-15"
        }
        
        response = client.post("/api/audits", json=payload)
        
        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]
    
    @patch('main.get_db_connection')
    def test_create_audit_commit_error(self, mock_db):
        """Test connection is closed even when commit fails."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = create_mock_audit_row()
        mock_conn.commit.side_effect = Exception("Commit failed")
        mock_db.return_value = mock_conn
        
        payload = {
            "audit_type": "internal",
            "title": "Test Audit",
            "description": "Test",
            "audit_date": "2025-01-15"
        }
        
        response = client.post("/api/audits", json=payload)
        
        assert response.status_code == 500
        # Verify connection is closed via finally block
        mock_conn.close.assert_called_once()


# ========================================
# GET AUDITS TESTS
# ========================================

class TestGetAudits:
    """Tests for GET /api/audits endpoint."""
    
    @patch('main.get_db_connection')
    def test_get_all_audits(self, mock_db):
        """Test getting all audits."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            create_mock_audit_row(id=1, audit_type="internal"),
            create_mock_audit_row(id=2, audit_type="external")
        ]
        mock_db.return_value = mock_conn
        
        response = client.get("/api/audits")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
    
    @patch('main.get_db_connection')
    def test_get_audits_filter_by_type(self, mock_db):
        """Test filtering audits by type."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            create_mock_audit_row(id=1, audit_type="internal")
        ]
        mock_db.return_value = mock_conn
        
        response = client.get("/api/audits?audit_type=internal")
        
        assert response.status_code == 200
    
    @patch('main.get_db_connection')
    def test_get_audits_filter_by_year(self, mock_db):
        """Test filtering audits by year."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_db.return_value = mock_conn
        
        response = client.get("/api/audits?year=2025")
        
        assert response.status_code == 200


# ========================================
# GET SINGLE AUDIT TESTS
# ========================================

class TestGetAuditById:
    """Tests for GET /api/audits/{id} endpoint."""
    
    @patch('main.get_db_connection')
    def test_get_audit_success(self, mock_db):
        """Test getting audit by ID."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = create_mock_audit_row(id=1)
        mock_db.return_value = mock_conn
        
        response = client.get("/api/audits/1")
        
        assert response.status_code == 200
        assert response.json()["id"] == 1
    
    @patch('main.get_db_connection')
    def test_get_audit_not_found(self, mock_db):
        """Test getting non-existent audit returns 404."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        mock_db.return_value = mock_conn
        
        response = client.get("/api/audits/999")
        
        assert response.status_code == 404


# ========================================
# UPDATE AUDIT TESTS
# ========================================

class TestUpdateAudit:
    """Tests for PUT /api/audits/{id} endpoint."""
    
    @patch('main.get_db_connection')
    def test_update_audit_success(self, mock_db):
        """Test updating audit."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = create_mock_audit_row(id=1, title="Updated Title")
        mock_db.return_value = mock_conn
        
        payload = {"title": "Updated Title"}
        response = client.put("/api/audits/1", json=payload)
        
        assert response.status_code == 200
    
    def test_update_audit_no_fields(self):
        """Test updating audit with no fields returns 400."""
        payload = {}
        response = client.put("/api/audits/1", json=payload)
        
        assert response.status_code == 400
        assert "No fields to update" in response.json()["detail"]
    
    @patch('main.get_db_connection')
    def test_update_audit_not_found(self, mock_db):
        """Test updating non-existent audit returns 404."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        mock_db.return_value = mock_conn
        
        payload = {"title": "Updated"}
        response = client.put("/api/audits/999", json=payload)
        
        assert response.status_code == 404


# ========================================
# DELETE AUDIT TESTS
# ========================================

class TestDeleteAudit:
    """Tests for DELETE /api/audits/{id} endpoint."""
    
    @patch('main.get_db_connection')
    def test_delete_audit_success(self, mock_db):
        """Test deleting audit."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_db.return_value = mock_conn
        
        response = client.delete("/api/audits/1")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Audit deleted successfully"
    
    @patch('main.get_db_connection')
    def test_delete_audit_not_found(self, mock_db):
        """Test deleting non-existent audit returns 404."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 0
        mock_db.return_value = mock_conn
        
        response = client.delete("/api/audits/999")
        
        assert response.status_code == 404


# ========================================
# HEATMAP ENDPOINT TESTS
# ========================================

class TestHeatmapEndpoint:
    """Tests for GET /api/heatmap/{year} endpoint."""
    
    @patch('main.get_db_connection')
    def test_get_heatmap_data(self, mock_db):
        """Test getting heatmap data for a year."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("2025-01-15", 2, 1, 3),
            ("2025-01-20", 1, 0, 1)
        ]
        mock_db.return_value = mock_conn
        
        response = client.get("/api/heatmap/2025")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["date"] == "2025-01-15"
        assert data[0]["internal"] == 2
        assert data[0]["external"] == 1
        assert data[0]["total"] == 3


# ========================================
# STATISTICS ENDPOINT TESTS
# ========================================

class TestStatsEndpoint:
    """Tests for GET /api/stats/{year} endpoint."""
    
    @patch('main.get_db_connection')
    def test_get_yearly_stats(self, mock_db):
        """Test getting yearly statistics."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (10, 6, 4)  # total, internal, external
        mock_db.return_value = mock_conn
        
        response = client.get("/api/stats/2025")
        
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2025
        assert data["total_audits"] == 10
        assert data["internal_count"] == 6
        assert data["external_count"] == 4
    
    @patch('main.get_db_connection')
    def test_get_yearly_stats_no_data(self, mock_db):
        """Test yearly stats with no audits returns zeros."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (None, None, None)
        mock_db.return_value = mock_conn
        
        response = client.get("/api/stats/2020")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_audits"] == 0


# ========================================
# AUDITS BY DATE TESTS
# ========================================

class TestAuditsByDate:
    """Tests for GET /api/audits/date/{date_str} endpoint."""
    
    @patch('main.get_db_connection')
    def test_get_audits_by_date(self, mock_db):
        """Test getting audits for a specific date."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            create_mock_audit_row(id=1),
            create_mock_audit_row(id=2)
        ]
        mock_db.return_value = mock_conn
        
        response = client.get("/api/audits/date/2025-01-15")
        
        assert response.status_code == 200
        assert len(response.json()) == 2


# ========================================
# INPUT VALIDATION TESTS (Phase 2)
# ========================================

class TestInputValidation:
    """Tests for input validation across all endpoints."""
    
    # --- Title validation tests ---
    def test_create_audit_empty_title(self):
        """Test creating audit with empty title returns 400."""
        payload = {
            "audit_type": "internal",
            "title": "   ",  # whitespace only
            "audit_date": "2025-01-15"
        }
        response = client.post("/api/audits", json=payload)
        assert response.status_code == 400
        assert "title cannot be empty" in response.json()["detail"]
    
    def test_create_audit_title_too_long(self):
        """Test creating audit with title > 255 chars returns 400."""
        payload = {
            "audit_type": "internal",
            "title": "A" * 256,
            "audit_date": "2025-01-15"
        }
        response = client.post("/api/audits", json=payload)
        assert response.status_code == 400
        assert "title cannot exceed 255 characters" in response.json()["detail"]
    
    def test_update_audit_empty_title(self):
        """Test updating audit with empty title returns 400."""
        payload = {"title": "   "}
        response = client.put("/api/audits/1", json=payload)
        assert response.status_code == 400
        assert "title cannot be empty" in response.json()["detail"]
    
    def test_update_audit_title_too_long(self):
        """Test updating audit with title > 255 chars returns 400."""
        payload = {"title": "B" * 256}
        response = client.put("/api/audits/1", json=payload)
        assert response.status_code == 400
        assert "title cannot exceed 255 characters" in response.json()["detail"]
    
    # --- audit_type validation tests ---
    def test_get_audits_invalid_audit_type(self):
        """Test filtering audits with invalid audit_type returns 400."""
        response = client.get("/api/audits?audit_type=invalid")
        assert response.status_code == 400
        assert "audit_type must be one of" in response.json()["detail"]
    
    # --- Year range validation tests ---
    def test_get_audits_year_too_low(self):
        """Test filtering audits with year < 1900 returns 400."""
        response = client.get("/api/audits?year=1800")
        assert response.status_code == 400
        assert "year must be between" in response.json()["detail"]
    
    def test_get_audits_year_too_high(self):
        """Test filtering audits with year > 2100 returns 400."""
        response = client.get("/api/audits?year=2200")
        assert response.status_code == 400
        assert "year must be between" in response.json()["detail"]
    
    def test_heatmap_year_too_low(self):
        """Test heatmap with year < 1900 returns 400."""
        response = client.get("/api/heatmap/1800")
        assert response.status_code == 400
        assert "year must be between" in response.json()["detail"]
    
    def test_heatmap_year_too_high(self):
        """Test heatmap with year > 2100 returns 400."""
        response = client.get("/api/heatmap/2200")
        assert response.status_code == 400
        assert "year must be between" in response.json()["detail"]
    
    def test_stats_year_too_low(self):
        """Test stats with year < 1900 returns 400."""
        response = client.get("/api/stats/1800")
        assert response.status_code == 400
        assert "year must be between" in response.json()["detail"]
    
    def test_stats_year_too_high(self):
        """Test stats with year > 2100 returns 400."""
        response = client.get("/api/stats/2200")
        assert response.status_code == 400
        assert "year must be between" in response.json()["detail"]
    
    # --- Date range validation tests ---
    def test_get_audits_start_after_end_date(self):
        """Test filtering audits with start_date > end_date returns 400."""
        response = client.get("/api/audits?start_date=2025-12-31&end_date=2025-01-01")
        assert response.status_code == 400
        assert "start_date cannot be after end_date" in response.json()["detail"]
    
    # --- Date string format validation tests ---
    def test_audits_by_date_invalid_format(self):
        """Test getting audits with invalid date format returns 400."""
        response = client.get("/api/audits/date/01-15-2025")  # Wrong format
        assert response.status_code == 400
        assert "YYYY-MM-DD format" in response.json()["detail"]
    
    def test_audits_by_date_invalid_date(self):
        """Test getting audits with invalid date value returns 400."""
        response = client.get("/api/audits/date/2025-02-30")  # Feb 30 doesn't exist
        assert response.status_code == 400
        assert "Invalid date value" in response.json()["detail"]
    
    def test_audits_by_date_invalid_month(self):
        """Test getting audits with invalid month returns 400."""
        response = client.get("/api/audits/date/2025-13-01")  # Month 13 invalid
        assert response.status_code == 400
        assert "Invalid date value" in response.json()["detail"]


# ========================================
# NULL SAFETY TESTS (Phase 3)
# ========================================

class TestNullSafety:
    """Tests for null safety and ID validation across endpoints."""
    
    # --- Audit ID validation tests ---
    def test_get_audit_zero_id(self):
        """Test getting audit with id=0 returns 400."""
        response = client.get("/api/audits/0")
        assert response.status_code == 400
        assert "audit_id must be a positive integer" in response.json()["detail"]
    
    def test_get_audit_negative_id(self):
        """Test getting audit with negative id returns 400."""
        response = client.get("/api/audits/-1")
        assert response.status_code == 400
        assert "audit_id must be a positive integer" in response.json()["detail"]
    
    def test_update_audit_zero_id(self):
        """Test updating audit with id=0 returns 400."""
        response = client.put("/api/audits/0", json={"title": "Test"})
        assert response.status_code == 400
        assert "audit_id must be a positive integer" in response.json()["detail"]
    
    def test_update_audit_negative_id(self):
        """Test updating audit with negative id returns 400."""
        response = client.put("/api/audits/-5", json={"title": "Test"})
        assert response.status_code == 400
        assert "audit_id must be a positive integer" in response.json()["detail"]
    
    def test_delete_audit_zero_id(self):
        """Test deleting audit with id=0 returns 400."""
        response = client.delete("/api/audits/0")
        assert response.status_code == 400
        assert "audit_id must be a positive integer" in response.json()["detail"]
    
    def test_delete_audit_negative_id(self):
        """Test deleting audit with negative id returns 400."""
        response = client.delete("/api/audits/-10")
        assert response.status_code == 400
        assert "audit_id must be a positive integer" in response.json()["detail"]
    
    # --- fetchall() null handling tests ---
    @patch('main.get_db_connection')
    def test_get_audits_returns_empty_when_fetchall_none(self, mock_db):
        """Test GET /api/audits handles None from fetchall gracefully."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = None  # Simulate None return
        mock_db.return_value = mock_conn
        
        response = client.get("/api/audits")
        
        assert response.status_code == 200
        assert response.json() == []
    
    @patch('main.get_db_connection')
    def test_heatmap_returns_empty_when_fetchall_none(self, mock_db):
        """Test GET /api/heatmap/{year} handles None from fetchall gracefully."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = None
        mock_db.return_value = mock_conn
        
        response = client.get("/api/heatmap/2025")
        
        assert response.status_code == 200
        assert response.json() == []
    
    @patch('main.get_db_connection')
    def test_audits_by_date_returns_empty_when_fetchall_none(self, mock_db):
        """Test GET /api/audits/date/{date} handles None from fetchall gracefully."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = None
        mock_db.return_value = mock_conn
        
        response = client.get("/api/audits/date/2025-01-15")
        
        assert response.status_code == 200
        assert response.json() == []
    
    @patch('main.get_db_connection')
    def test_stats_returns_zeros_when_fetchone_none(self, mock_db):
        """Test GET /api/stats/{year} handles None from fetchone gracefully."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        mock_db.return_value = mock_conn
        
        response = client.get("/api/stats/2025")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_audits"] == 0
        assert data["internal_count"] == 0
        assert data["external_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
