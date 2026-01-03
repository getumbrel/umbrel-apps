"""
ChainForensics Database Module
Async SQLAlchemy setup with SQLite/PostgreSQL support.
"""
import os
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, BigInteger, ForeignKey, Index
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship

from app.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()


# ============== Database Models ==============

class Transaction(Base):
    """Cached transaction data."""
    __tablename__ = "transactions"
    
    txid = Column(String(64), primary_key=True)
    block_hash = Column(String(64), nullable=True)
    block_height = Column(Integer, nullable=True)
    block_time = Column(DateTime, nullable=True)
    size = Column(Integer)
    vsize = Column(Integer)
    weight = Column(Integer)
    version = Column(Integer)
    locktime = Column(Integer)
    fee_sats = Column(BigInteger, nullable=True)
    input_count = Column(Integer)
    output_count = Column(Integer)
    total_output_sats = Column(BigInteger)
    is_coinbase = Column(Boolean, default=False)
    coinjoin_score = Column(Float, nullable=True)
    coinjoin_type = Column(String(50), nullable=True)
    cached_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    inputs = relationship("TransactionInput", back_populates="transaction", cascade="all, delete-orphan")
    outputs = relationship("TransactionOutput", back_populates="transaction", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_tx_block_height', 'block_height'),
        Index('idx_tx_block_time', 'block_time'),
        Index('idx_tx_coinjoin', 'coinjoin_score'),
    )


class TransactionInput(Base):
    """Transaction inputs."""
    __tablename__ = "transaction_inputs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    txid = Column(String(64), ForeignKey("transactions.txid", ondelete="CASCADE"))
    vin_index = Column(Integer)
    prev_txid = Column(String(64), nullable=True)  # Null for coinbase
    prev_vout = Column(Integer, nullable=True)
    value_sats = Column(BigInteger, nullable=True)
    address = Column(String(100), nullable=True)
    script_type = Column(String(20), nullable=True)
    
    transaction = relationship("Transaction", back_populates="inputs")
    
    __table_args__ = (
        Index('idx_input_prev_txid', 'prev_txid'),
        Index('idx_input_address', 'address'),
    )


class TransactionOutput(Base):
    """Transaction outputs (UTXOs)."""
    __tablename__ = "transaction_outputs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    txid = Column(String(64), ForeignKey("transactions.txid", ondelete="CASCADE"))
    vout_index = Column(Integer)
    value_sats = Column(BigInteger)
    address = Column(String(100), nullable=True)
    script_type = Column(String(20))
    script_hex = Column(Text, nullable=True)
    spent_txid = Column(String(64), nullable=True)
    spent_vin = Column(Integer, nullable=True)
    is_spent = Column(Boolean, default=False)
    
    transaction = relationship("Transaction", back_populates="outputs")
    
    __table_args__ = (
        Index('idx_output_address', 'address'),
        Index('idx_output_spent', 'is_spent'),
        Index('idx_output_spent_txid', 'spent_txid'),
    )


class AddressCluster(Base):
    """Address clustering data."""
    __tablename__ = "address_clusters"
    
    address = Column(String(100), primary_key=True)
    cluster_id = Column(Integer, index=True)
    first_seen_height = Column(Integer, nullable=True)
    first_seen_time = Column(DateTime, nullable=True)
    label = Column(String(200), nullable=True)
    label_source = Column(String(50), nullable=True)  # 'user', 'heuristic', 'import'
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AddressLabel(Base):
    """User-defined address labels."""
    __tablename__ = "address_labels"
    
    address = Column(String(100), primary_key=True)
    label = Column(String(200))
    category = Column(String(50))  # 'exchange', 'personal', 'merchant', etc.
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnalysisJob(Base):
    """Background analysis job tracking."""
    __tablename__ = "analysis_jobs"
    
    id = Column(String(36), primary_key=True)  # UUID
    job_type = Column(String(50))  # 'trace_forward', 'trace_backward', 'cluster', 'full_analysis'
    status = Column(String(20), default="queued")  # 'queued', 'running', 'completed', 'failed', 'cancelled'
    target_txid = Column(String(64), nullable=True)
    target_address = Column(String(100), nullable=True)
    parameters = Column(Text, nullable=True)  # JSON parameters
    progress = Column(Integer, default=0)  # 0-100
    result = Column(Text, nullable=True)  # JSON result
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_job_status', 'status'),
        Index('idx_job_created', 'created_at'),
    )


class CoinJoinAnalysis(Base):
    """Cached CoinJoin analysis results."""
    __tablename__ = "coinjoin_analyses"
    
    txid = Column(String(64), primary_key=True)
    score = Column(Float)
    detected_protocol = Column(String(50), nullable=True)
    confidence = Column(Float)
    equal_outputs_count = Column(Integer)
    unique_output_values = Column(Integer)
    analysis_details = Column(Text)  # JSON
    analyzed_at = Column(DateTime, default=datetime.utcnow)


class TraceCache(Base):
    """Cached trace results."""
    __tablename__ = "trace_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_type = Column(String(20))  # 'forward', 'backward'
    start_txid = Column(String(64))
    start_vout = Column(Integer, nullable=True)
    max_depth = Column(Integer)
    result = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_trace_lookup', 'trace_type', 'start_txid', 'start_vout', 'max_depth'),
    )


class GraphCommunity(Base):
    """Louvain community detection cache."""
    __tablename__ = "graph_communities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(Integer, ForeignKey("trace_cache.id", ondelete="CASCADE"), nullable=True)
    community_id = Column(Integer, nullable=False)
    node_txid = Column(String(64), nullable=False)
    modularity_score = Column(Float)
    entity_type = Column(String(50))  # 'exchange', 'mixer', 'service', 'unknown'
    detected_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_community_trace', 'trace_id'),
        Index('idx_community_txid', 'node_txid'),
    )


class PageRankScore(Base):
    """PageRank scores for important addresses."""
    __tablename__ = "pagerank_scores"

    address = Column(String(100), primary_key=True)
    score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)
    inbound_count = Column(Integer, default=0)
    outbound_count = Column(Integer, default=0)
    total_value_sats = Column(BigInteger, default=0)
    calculated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_pagerank_score', 'score'),
        Index('idx_pagerank_rank', 'rank'),
    )


class WalletFingerprint(Base):
    """Wallet software identification."""
    __tablename__ = "wallet_fingerprints"

    txid = Column(String(64), primary_key=True)
    wallet_type = Column(String(50), nullable=False)  # "Bitcoin Core", "Electrum", "Wasabi"
    confidence = Column(Float, nullable=False)
    fee_rate_pattern = Column(String(50))
    locktime_pattern = Column(String(50))
    uses_bip69 = Column(Boolean, default=False)
    detected_patterns = Column(Text)  # JSON array
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_wallet_type', 'wallet_type'),
        Index('idx_wallet_confidence', 'confidence'),
    )


# ============== Database Functions ==============

async def init_db():
    """Initialize database tables."""
    # Ensure data directory exists
    os.makedirs("./data", exist_ok=True)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    """Drop all tables (use with caution)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
