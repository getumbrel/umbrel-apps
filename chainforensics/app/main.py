#!/usr/bin/env python3
"""
ChainForensics - Enterprise Blockchain Analysis Platform
Main FastAPI Application
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from sqlalchemy import text

from app.config import settings
from app.database import init_db, get_db
from app.api import transactions, analysis, visualizations, jobs, addresses, kyc, privacy
from app.core.bitcoin_rpc import BitcoinRPC
from app.workers.indexer import start_background_indexer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("chainforensics")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# Cache for health check to avoid hammering Bitcoin RPC
_health_cache = {
    "data": None,
    "timestamp": None,
    "ttl_seconds": 10  # Cache health for 10 seconds
}

async def get_health_data():
    """Get health data with caching."""
    now = datetime.utcnow()
    
    # Return cached data if fresh
    if (_health_cache["data"] is not None and 
        _health_cache["timestamp"] is not None and
        (now - _health_cache["timestamp"]).total_seconds() < _health_cache["ttl_seconds"]):
        return _health_cache["data"]
    
    # Build fresh health data
    health = {
        "status": "healthy",
        "timestamp": now.isoformat(),
        "components": {}
    }
    
    # Check Bitcoin RPC
    try:
        rpc = BitcoinRPC()
        info = await rpc.get_blockchain_info()
        health["components"]["bitcoin_core"] = {
            "status": "connected",
            "blocks": info.get("blocks"),
            "chain": info.get("chain"),
            "verification_progress": info.get("verificationprogress")
        }
    except Exception as e:
        health["components"]["bitcoin_core"] = {
            "status": "disconnected",
            "error": str(e)
        }
        health["status"] = "degraded"
    
    # Check database
    try:
        async with get_db() as db:
            await db.execute(text("SELECT 1"))
        health["components"]["database"] = {"status": "connected"}
    except Exception as e:
        health["components"]["database"] = {
            "status": "disconnected",
            "error": str(e)
        }
        health["status"] = "degraded"
    
    # Check Fulcrum
    try:
        from app.core.fulcrum import check_fulcrum_connection
        fulcrum_status = await check_fulcrum_connection()
        health["components"]["fulcrum"] = fulcrum_status
    except Exception as e:
        health["components"]["fulcrum"] = {
            "status": "not_available",
            "error": str(e)
        }
    
    # Cache the result
    _health_cache["data"] = health
    _health_cache["timestamp"] = now
    
    return health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("=" * 60)
    logger.info("ChainForensics Starting Up")
    logger.info("=" * 60)
    
    # Initialize database
    await init_db()
    logger.info("✓ Database initialized")
    
    # Test Bitcoin RPC connection
    try:
        rpc = BitcoinRPC()
        info = await rpc.get_blockchain_info()
        logger.info(f"✓ Bitcoin Core connected - Block height: {info.get('blocks', 'N/A')}")
    except Exception as e:
        logger.warning(f"⚠ Bitcoin Core not connected: {e}")
    
    # Start background indexer if enabled
    if settings.ENABLE_BACKGROUND_INDEXER:
        asyncio.create_task(start_background_indexer())
        logger.info("✓ Background indexer started")
    else:
        logger.info("ℹ Background indexer disabled")
    
    logger.info("=" * 60)
    logger.info("ChainForensics Ready")
    logger.info(f"API: http://0.0.0.0:{settings.API_PORT}")
    logger.info(f"Docs: http://0.0.0.0:{settings.API_PORT}/docs")
    logger.info("=" * 60)
    
    yield
    
    # Cleanup
    logger.info("ChainForensics shutting down...")

# Create FastAPI app
app = FastAPI(
    title="ChainForensics",
    description="Enterprise Blockchain Analysis Platform - Privacy-focused UTXO forensics",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware (LAN only in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["Transactions"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(visualizations.router, prefix="/api/v1/visualizations", tags=["Visualizations"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(addresses.router, prefix="/api/v1/addresses", tags=["Addresses"])
app.include_router(kyc.router, prefix="/api/v1/kyc", tags=["KYC Privacy Check"])
app.include_router(privacy.router, prefix="/api/v1/privacy", tags=["Privacy Analysis"])
# Graph Analytics router removed - endpoints not used by HTML frontend


@app.get("/")
async def root():
    """Root endpoint - basic info."""
    return {
        "service": "ChainForensics",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check():
    """Detailed health check at root level."""
    return await get_health_data()


@app.get("/api/v1/health")
async def api_health_check():
    """
    Detailed health check at API path.
    This is what the frontend calls to check status.
    """
    return await get_health_data()


@app.get("/api/v1/fulcrum-status")
async def fulcrum_operational_status():
    """
    Get Fulcrum operational health status.

    This tracks actual operation success/failure, not just connectivity.
    Use this to show warnings when Fulcrum is having issues.
    """
    from app.core.fulcrum import get_health_tracker
    tracker = get_health_tracker()
    return await tracker.get_status()


@app.get("/api/v1/fulcrum-test/{txid}")
async def fulcrum_test_transaction(txid: str):
    """
    Diagnostic endpoint to test what Fulcrum returns for a transaction.
    This tests the actual Fulcrum connection used by the app.
    """
    from app.core.fulcrum import get_fulcrum

    fulcrum = get_fulcrum()
    result = {
        "txid": txid,
        "connected": fulcrum._connected,
        "writer_exists": fulcrum._writer is not None,
        "writer_closing": fulcrum._writer.is_closing() if fulcrum._writer else None,
    }

    try:
        # Test raw call
        raw_result = await fulcrum._call("blockchain.transaction.get", [txid, True])
        result["raw_call_type"] = type(raw_result).__name__
        result["raw_call_is_dict"] = isinstance(raw_result, dict)
        if isinstance(raw_result, dict):
            result["raw_call_keys"] = list(raw_result.keys())
            result["raw_call_has_vout"] = "vout" in raw_result
        else:
            result["raw_call_preview"] = str(raw_result)[:200]
    except Exception as e:
        result["raw_call_error"] = f"{type(e).__name__}: {e}"
    
    try:
        # Test get_transaction method
        tx = await fulcrum.get_transaction(txid, verbose=True)
        result["get_tx_type"] = type(tx).__name__ if tx else "None"
        result["get_tx_is_dict"] = isinstance(tx, dict)
        if isinstance(tx, dict):
            result["get_tx_keys"] = list(tx.keys())
            result["get_tx_has_vout"] = "vout" in tx
    except Exception as e:
        result["get_tx_error"] = f"{type(e).__name__}: {e}"

    return result


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for live updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            # Could add commands like 'subscribe' to specific events
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Export manager for use in other modules
def get_ws_manager():
    return manager


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
