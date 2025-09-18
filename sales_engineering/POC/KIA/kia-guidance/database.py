import sqlite3
from typing import Dict, List, Any

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect('compliance_data.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create analysis_log table (updated schema from DetailDesign.md)
    c.execute('''
        CREATE TABLE IF NOT EXISTS analysis_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filename TEXT NOT NULL,
            page_number INTEGER,
            model_id TEXT NOT NULL,
            response_time_seconds REAL NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            compliance_status TEXT NOT NULL
        )
    ''')
    
    # Create violations_log table (updated schema from DetailDesign.md)
    c.execute('''
        CREATE TABLE IF NOT EXISTS violations_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            rule_violated TEXT NOT NULL,
            description TEXT NOT NULL,
            FOREIGN KEY (analysis_id) REFERENCES analysis_log (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def log_analysis(filename: str, page_number: int, model_id: str, response_time: float, 
                input_tokens: int, output_tokens: int, compliance_status: str) -> int:
    """Logs a new analysis record and returns the new record's ID."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO analysis_log (filename, page_number, model_id, response_time_seconds, 
                                input_tokens, output_tokens, compliance_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (filename, page_number, model_id, response_time, input_tokens, output_tokens, compliance_status))
    analysis_id = c.lastrowid
    conn.commit()
    conn.close()
    return analysis_id

def log_violation(analysis_id: int, rule_violated: str, description: str):
    """Logs a specific violation linked to an analysis record."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO violations_log (analysis_id, rule_violated, description)
        VALUES (?, ?, ?)
    ''', (analysis_id, rule_violated, description))
    conn.commit()
    conn.close()

def get_statistics() -> Dict[str, Any]:
    """Retrieves aggregated statistics for the dashboard."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Total analysis count
    total_requests = c.execute('SELECT COUNT(*) FROM analysis_log').fetchone()[0]
    
    # Assets analyzed (count unique filename + page combinations)
    total_assets = c.execute('''
        SELECT COUNT(DISTINCT filename || COALESCE(page_number, 0)) 
        FROM analysis_log
    ''').fetchone()[0]
    
    # Compliance rate
    compliant_requests = c.execute('''
        SELECT COUNT(*) FROM analysis_log 
        WHERE compliance_status = 'Compliant'
    ''').fetchone()[0]
    compliance_rate = (compliant_requests / total_requests * 100) if total_requests > 0 else 0
    
    # Average response time
    avg_response_time = c.execute('''
        SELECT AVG(response_time_seconds) FROM analysis_log
    ''').fetchone()[0] or 0
    
    # Token usage by model
    tokens_by_model = c.execute('''
        SELECT model_id, 
               SUM(input_tokens + output_tokens) as total_tokens,
               SUM(input_tokens) as input_tokens,
               SUM(output_tokens) as output_tokens
        FROM analysis_log 
        GROUP BY model_id
    ''').fetchall()
    
    # Requests over time (last 30 days)
    requests_over_time = c.execute('''
        SELECT DATE(timestamp) as date, COUNT(*) as count
        FROM analysis_log
        WHERE timestamp >= datetime('now', '-30 days')
        GROUP BY DATE(timestamp)
        ORDER BY date
    ''').fetchall()
    
    conn.close()
    
    return {
        "total_requests": total_requests,
        "total_assets": total_assets,
        "compliance_rate": compliance_rate,
        "avg_response_time": avg_response_time,
        "tokens_by_model": [dict(row) for row in tokens_by_model],
        "requests_over_time": [dict(row) for row in requests_over_time]
    }

def get_common_violations(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves the most common violation types."""
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT rule_violated, COUNT(*) as count 
        FROM violations_log 
        GROUP BY rule_violated 
        ORDER BY count DESC 
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_recent_analysis(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves the most recent analysis records."""
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT timestamp, filename, page_number, model_id, compliance_status, 
               response_time_seconds, input_tokens, output_tokens
        FROM analysis_log 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_compliance_trend(days: int = 30) -> List[Dict[str, Any]]:
    """Get compliance trend over specified number of days."""
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT DATE(timestamp) as date,
               COUNT(*) as total_analyses,
               SUM(CASE WHEN compliance_status = 'Compliant' THEN 1 ELSE 0 END) as compliant_count,
               ROUND(SUM(CASE WHEN compliance_status = 'Compliant' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as compliance_rate
        FROM analysis_log
        WHERE timestamp >= datetime('now', '-{} days')
        GROUP BY DATE(timestamp)
        ORDER BY date
    '''.format(days)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

if __name__ == '__main__':
    init_db()
    print("Database initialized with updated schema.")
