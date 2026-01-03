"""
ChainForensics Configuration
All settings loaded from environment variables with sensible defaults.
"""
import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "ChainForensics"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    API_PORT: int = int(os.getenv("API_PORT", "3000"))
    
    # CORS - LAN only by default
    CORS_ORIGINS: List[str] = [
        "http://localhost:8080",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
        "http://chainforensics-web:80",
    ]
    
    # Bitcoin Core RPC
    BITCOIN_RPC_HOST: str = os.getenv("BITCOIN_RPC_HOST", "umbrel.local")
    BITCOIN_RPC_PORT: int = int(os.getenv("BITCOIN_RPC_PORT", "8332"))
    BITCOIN_RPC_USER: str = os.getenv("BITCOIN_RPC_USER", "umbrel")
    BITCOIN_RPC_PASS: str = os.getenv("BITCOIN_RPC_PASS", "")
    BITCOIN_RPC_TIMEOUT: int = int(os.getenv("BITCOIN_RPC_TIMEOUT", "60"))
    
    # Fulcrum (Electrum Protocol Server)
    FULCRUM_HOST: str = os.getenv("FULCRUM_HOST", "")
    FULCRUM_PORT: int = int(os.getenv("FULCRUM_PORT", "50002"))
    
    # Mempool (optional)
    MEMPOOL_HOST: str = os.getenv("MEMPOOL_HOST", "")
    MEMPOOL_PORT: int = int(os.getenv("MEMPOOL_PORT", "3006"))
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/chainforensics.db")
    
    # Analysis settings
    MAX_TRACE_DEPTH: int = int(os.getenv("MAX_TRACE_DEPTH", "50"))
    DEFAULT_TRACE_DEPTH: int = int(os.getenv("DEFAULT_TRACE_DEPTH", "10"))
    ENABLE_BACKGROUND_INDEXER: bool = os.getenv("ENABLE_BACKGROUND_INDEXER", "true").lower() == "true"
    
    # Cache settings
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    
    # Job queue
    MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
    JOB_TIMEOUT_SECONDS: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "7200"))
    
    @property
    def bitcoin_rpc_url(self) -> str:
        """Construct Bitcoin RPC URL."""
        return f"http://{self.BITCOIN_RPC_USER}:{self.BITCOIN_RPC_PASS}@{self.BITCOIN_RPC_HOST}:{self.BITCOIN_RPC_PORT}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


# CoinJoin detection configurations
COINJOIN_CONFIGS = {
    "whirlpool": {
        "name": "Whirlpool",
        "min_outputs": 5,
        "max_outputs": 5,
        "denominations": [0.001, 0.01, 0.05, 0.5],
        "tolerance": 0.0001,
        "confidence_base": 0.95
    },
    "wasabi": {
        "name": "Wasabi",
        "min_equal_outputs": 10,
        "confidence_base": 0.85
    },
    "joinmarket": {
        "name": "JoinMarket",
        "min_inputs": 3,
        "min_outputs": 4,
        "confidence_base": 0.60
    }
}


# Known exchange patterns (public information only)
EXCHANGE_PATTERNS = {
    "batched_withdrawal": {
        "description": "Multiple outputs in single transaction",
        "min_outputs": 10
    },
    "consolidation": {
        "description": "Many inputs to few outputs",
        "min_inputs": 20,
        "max_outputs": 3
    },
    "round_timing": {
        "description": "Transactions at round time intervals",
        "interval_minutes": [15, 30, 60]
    }
}
