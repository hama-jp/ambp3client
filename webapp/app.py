"""
FastAPI Real-time Dashboard for AMB P3 Client
リアルタイムラップタイム表示・音声読み上げ対応
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import mysql.connector
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Configuration loader
def load_config(config_file="conf.yaml"):
    """Load configuration from YAML file"""
    default_config = {
        "mysql_host": "127.0.0.1",
        "mysql_port": 3306,
        "mysql_db": "cars",
        "mysql_user": "car",
        "mysql_password": "cars",
    }

    # Get project root directory
    project_root = Path(__file__).parent.parent
    config_path = project_root / config_file

    try:
        with open(config_path, "r") as f:
            file_config = yaml.safe_load(f) or {}
        logger.info(f"Loaded config from {config_path}")
    except FileNotFoundError:
        logger.warning(f"Config file {config_path} not found, using defaults")
        file_config = {}

    # Merge configs
    config = {**default_config, **file_config}

    # Rename mysql_password to mysql_pass for consistency
    if "mysql_password" in config:
        config["mysql_pass"] = config["mysql_password"]

    return config


class AppConfig:
    """Simple config class for webapp"""

    def __init__(self, config_dict):
        self.mysql_host = config_dict.get("mysql_host", "127.0.0.1")
        self.mysql_port = config_dict.get("mysql_port", 3306)
        self.mysql_db = config_dict.get("mysql_db", "cars")
        self.mysql_user = config_dict.get("mysql_user", "car")
        self.mysql_pass = config_dict.get(
            "mysql_pass", config_dict.get("mysql_password", "cars")
        )


app = FastAPI(title="AMB P3 Dashboard", version="1.0.0")

# Get static files directory
STATIC_DIR = Path(__file__).parent / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Database connection manager
class DatabaseManager:
    """Manages database connections with automatic reconnection."""

    def __init__(self, config: AppConfig):
        """Initialize database manager.

        Args:
            config: AppConfig instance with database connection parameters
        """
        self.config = config
        self.connection = None

    def connect(self):
        """Connect to MySQL database"""
        try:
            conn_params = {
                "host": self.config.mysql_host,
                "user": self.config.mysql_user,
                "password": self.config.mysql_pass,
                "database": self.config.mysql_db,
            }
            # Add port if not default
            if self.config.mysql_port != 3306:
                conn_params["port"] = self.config.mysql_port

            self.connection = mysql.connector.connect(**conn_params)
            logger.info(
                f"Database connected successfully to {self.config.mysql_host}:{self.config.mysql_port}/{self.config.mysql_db}"
            )
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def ensure_connection(self):
        """Ensure database connection is alive"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
        except Exception as e:
            logger.error(f"Failed to ensure connection: {e}")
            self.connect()

    def execute_query(self, query: str, params: tuple = None):
        """Execute query and return results.

        Args:
            query: SQL query string
            params: Optional query parameters tuple

        Returns:
            List of result dictionaries
        """
        self.ensure_connection()
        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            return results
        finally:
            cursor.close()

    def close(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Database connection closed")


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register new WebSocket connection.

        Args:
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            f"Client connected. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        """Unregister WebSocket connection.

        Args:
            websocket: WebSocket connection to unregister
        """
        self.active_connections.remove(websocket)
        logger.info(
            f"Client disconnected. Total connections: {len(self.active_connections)}"
        )

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients.

        Args:
            message: Dictionary message to broadcast as JSON
        """
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)


# Pydantic models
class LapData(BaseModel):
    pass_id: int
    transponder_id: int
    rtc_time: int
    lap_time: Optional[float] = None


class TransponderInfo(BaseModel):
    transponder_id: int
    name: Optional[str] = None
    car_number: Optional[int] = None


class LapStats(BaseModel):
    transponder_id: int
    total_laps: int
    best_lap: Optional[float] = None
    average_lap: Optional[float] = None
    latest_lap: Optional[float] = None
    latest_lap_time: Optional[int] = None


# Global instances
config = AppConfig(load_config())
db_manager = DatabaseManager(config)
websocket_manager = ConnectionManager()

# In-memory cache for last processed pass_id per transponder
last_processed_pass: Dict[int, int] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    db_manager.connect()
    # Start background task for monitoring new laps
    asyncio.create_task(monitor_new_laps())
    logger.info("FastAPI app started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    db_manager.close()
    logger.info("FastAPI app shutdown")


@app.get("/")
async def root():
    """Serve main dashboard HTML"""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/transponders", response_model=List[TransponderInfo])
async def get_transponders():
    """Get list of all transponders with car info"""
    query = """
        SELECT DISTINCT l.transponder_id, c.name, c.car_number
        FROM laps l
        LEFT JOIN cars c ON l.transponder_id = c.transponder_id
        ORDER BY l.rtc_time DESC
        LIMIT 100
    """
    results = db_manager.execute_query(query)

    transponders = []
    seen = set()
    for row in results:
        tid = row["transponder_id"]
        if tid not in seen:
            transponders.append(
                TransponderInfo(
                    transponder_id=tid,
                    name=row.get("name"),
                    car_number=row.get("car_number"),
                )
            )
            seen.add(tid)

    return transponders


@app.get("/api/laps/{transponder_id}", response_model=LapStats)
async def get_lap_stats(transponder_id: int, limit: int = 50):
    """Get lap statistics for a specific transponder"""
    # Get laps with lap times
    query = """
        SELECT
            l1.pass_id,
            l1.transponder_id,
            l1.rtc_time,
            (l1.rtc_time - l2.rtc_time) / 1000000.0 as lap_time
        FROM laps l1
        LEFT JOIN laps l2 ON l2.transponder_id = l1.transponder_id
            AND l2.rtc_time < l1.rtc_time
            AND l2.pass_id = (
                SELECT MAX(pass_id)
                FROM laps
                WHERE transponder_id = l1.transponder_id
                AND rtc_time < l1.rtc_time
            )
        WHERE l1.transponder_id = %s
        ORDER BY l1.rtc_time DESC
        LIMIT %s
    """

    results = db_manager.execute_query(query, (transponder_id, limit))

    if not results:
        return LapStats(transponder_id=transponder_id, total_laps=0)

    # Calculate statistics
    lap_times = [
        row["lap_time"] for row in results if row["lap_time"] and row["lap_time"] > 0
    ]

    stats = LapStats(
        transponder_id=transponder_id,
        total_laps=len(results),
        best_lap=min(lap_times) if lap_times else None,
        average_lap=sum(lap_times) / len(lap_times) if lap_times else None,
        latest_lap=lap_times[0] if lap_times else None,
        latest_lap_time=results[0]["rtc_time"] if results else None,
    )

    return stats


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time lap updates"""
    await websocket_manager.connect(websocket)

    try:
        while True:
            # Keep connection alive and receive client messages
            data = await websocket.receive_text()
            # Echo back for connection check
            await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        websocket_manager.disconnect(websocket)


async def monitor_new_laps():
    """Background task to monitor database for new laps"""
    logger.info("Starting lap monitoring background task")

    while True:
        try:
            # Get active transponders from recent laps (last 24 hours)
            query = """
                SELECT DISTINCT transponder_id
                FROM laps
                WHERE rtc_time > UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR) * 1000000
            """
            transponders = db_manager.execute_query(query)

            for trans_row in transponders:
                transponder_id = trans_row["transponder_id"]

                # Get latest lap for this transponder
                lap_query = """
                    SELECT
                        l1.pass_id,
                        l1.transponder_id,
                        l1.rtc_time,
                        (l1.rtc_time - l2.rtc_time) / 1000000.0 as lap_time
                    FROM laps l1
                    LEFT JOIN laps l2 ON l2.transponder_id = l1.transponder_id
                        AND l2.pass_id = (
                            SELECT MAX(pass_id)
                            FROM laps
                            WHERE transponder_id = l1.transponder_id
                            AND rtc_time < l1.rtc_time
                        )
                    WHERE l1.transponder_id = %s
                    ORDER BY l1.rtc_time DESC
                    LIMIT 1
                """

                lap_results = db_manager.execute_query(lap_query, (transponder_id,))

                if lap_results:
                    latest_lap = lap_results[0]
                    pass_id = latest_lap["pass_id"]

                    # Check if this is a new lap
                    if (
                        transponder_id not in last_processed_pass
                        or last_processed_pass[transponder_id] < pass_id
                    ):
                        last_processed_pass[transponder_id] = pass_id

                        # Get updated stats
                        stats = await get_lap_stats(transponder_id, limit=50)

                        # Broadcast to all connected clients
                        await websocket_manager.broadcast(
                            {
                                "type": "new_lap",
                                "transponder_id": transponder_id,
                                "lap_time": latest_lap["lap_time"],
                                "stats": stats.dict(),
                            }
                        )

                        logger.info(
                            f"New lap detected - Transponder: {transponder_id}, Time: {latest_lap['lap_time']:.2f}s"
                        )

        except Exception as e:
            logger.error(f"Error in lap monitoring: {e}")

        # Check every 0.5 seconds
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
