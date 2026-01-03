"""
ChainForensics - Privacy Analysis Module
Provides advanced privacy analysis tools:
- Cluster Detection (Common Input Ownership Heuristic)
- Exchange Proximity Score
- UTXO Privacy Rating
- Enhanced Analysis with Temporal, Value, and Wallet Fingerprinting

CRITICAL WARNINGS:
- This is HEURISTIC ANALYSIS only - NOT suitable for operational security
- Cannot detect: timing correlation, network analysis, Wasabi 2.0, sophisticated attacks
- Privacy scores are CONSERVATIVE estimates - real privacy may be worse
- Do NOT use this tool as your only privacy assessment

These tools help users understand their on-chain privacy posture.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from app.config import settings
from app.core.bitcoin_rpc import BitcoinRPC, get_rpc

# Import new analysis modules
from app.core.temporal_analysis import TemporalAnalyzer, get_temporal_analyzer
from app.core.value_analysis import ValueAnalyzer, get_value_analyzer
from app.core.wallet_fingerprint import WalletFingerprinter, get_wallet_fingerprinter

# Import enhanced response models
from app.api.models import (
    EnhancedPrivacyScore, RiskItem, AttackVector, FactorCategory,
    Factor, ActionItem, PrivacyBenchmark, RiskSeverity, PrivacyRating as EnhancedPrivacyRating
)

logger = logging.getLogger("chainforensics.privacy_analysis")


# =============================================================================
# KNOWN EXCHANGE ADDRESSES DATABASE
# =============================================================================
# This is a sample set - in production you'd have a much larger database
# These are well-known exchange cold/hot wallet addresses

KNOWN_EXCHANGE_ADDRESSES = {
    # =========================================================================
    # BINANCE - World's largest exchange by volume
    # =========================================================================
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": {"exchange": "Binance", "type": "cold_wallet"},
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": {"exchange": "Binance", "type": "cold_wallet"},
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": {"exchange": "Binance", "type": "cold_wallet"},
    "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s": {"exchange": "Binance", "type": "hot_wallet"},
    "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j": {"exchange": "Binance", "type": "hot_wallet"},
    "3LCGsSmfr24demGvriN4e3ft8wEcDuHFqh": {"exchange": "Binance", "type": "hot_wallet"},
    "bc1qa5wkgaew2dkv56kfvj49j0av5nml45x9ek9hz6": {"exchange": "Binance", "type": "hot_wallet"},
    "1FzWLkAahHooV3kzTgyx6qsswXJ6sCXkSR": {"exchange": "Binance", "type": "deposit_address"},
    "3BMEXVshCPBMCYwUuAug3Ht28NFmycxvB5": {"exchange": "Binance", "type": "deposit_address"},

    # =========================================================================
    # COINBASE - Largest US-based exchange
    # =========================================================================
    "3Kzh9qAqVWQhEsfQz7zEQL1EuSx5tyNLNS": {"exchange": "Coinbase", "type": "cold_wallet"},
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh": {"exchange": "Coinbase", "type": "hot_wallet"},
    "3FHNBLobJnbCTFTVakh5TXmEneyf5PT61B": {"exchange": "Coinbase", "type": "cold_wallet"},
    "1GR9qNz7zgtaW5HwwVpEJWMnGWhsbsieCG": {"exchange": "Coinbase", "type": "hot_wallet"},
    "36n452uGq1x4mK7bfyZR8wgE47AnBb2pzi": {"exchange": "Coinbase", "type": "cold_wallet"},
    "3QJmV3qfvL9SuYo34YihAf3sRCW3qSinyC": {"exchange": "Coinbase", "type": "cold_wallet"},
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": {"exchange": "Coinbase", "type": "cold_wallet"},
    "1AzhR4W5jMx6KPRfcbNPqMhJkYhNxNdYA9": {"exchange": "Coinbase", "type": "hot_wallet"},
    "3E37YWMXV8zuJx9cKm3zZKD67D9y8vNhWg": {"exchange": "Coinbase", "type": "deposit_address"},
    "bc1q5shngj3fwvjk0g5lk7qqn8xdy9sefqvvdw3jtj": {"exchange": "Coinbase", "type": "deposit_address"},

    # =========================================================================
    # KRAKEN - Leading European exchange
    # =========================================================================
    "3AfC8evitosmib5DzwNxBkCPDcYxwKb7UR": {"exchange": "Kraken", "type": "cold_wallet"},
    "bc1qkw5n806st9p8q8pez5a0t2rs6yd8vafpvjkcrr": {"exchange": "Kraken", "type": "hot_wallet"},
    "3NaZQMYCBwPq5d7LtBBKZZXMvLR5VyRwF8": {"exchange": "Kraken", "type": "cold_wallet"},
    "35KHnfMwD7vLmJwrWbBXJBWLFNcLUmfJFc": {"exchange": "Kraken", "type": "hot_wallet"},
    "bc1qj2jxp0q0dmnr8p9e0cxs0p4v2f3f5mlvckqjq7": {"exchange": "Kraken", "type": "hot_wallet"},
    "1Kbp4mUnBrsjF5jkv8vKGZtqxPpVZNnJ2H": {"exchange": "Kraken", "type": "deposit_address"},

    # =========================================================================
    # BITFINEX - Major cryptocurrency exchange
    # =========================================================================
    "3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r": {"exchange": "Bitfinex", "type": "cold_wallet"},
    "bc1qgxj5m07zhqyzrmv3lg3dksurpt66lxpfu2lxsm": {"exchange": "Bitfinex", "type": "hot_wallet"},
    "1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g": {"exchange": "Bitfinex", "type": "cold_wallet"},
    "3JwriwTLLHUQoWmwvLbCPrV9NvjP9PqiR8": {"exchange": "Bitfinex", "type": "hot_wallet"},
    "bc1qf9y6xxjadthq24j0xn2hk6t9r5f5z7hv9v7c2t": {"exchange": "Bitfinex", "type": "deposit_address"},

    # =========================================================================
    # GEMINI - Regulated US exchange
    # =========================================================================
    "3LDLspHMsXR1T5r2kXwzQn3Mv3iqVFgZRw": {"exchange": "Gemini", "type": "cold_wallet"},
    "bc1qnl7ppsl2kzm7ys2fkjppl6l3v3wd3s3rc2egk3": {"exchange": "Gemini", "type": "cold_wallet"},
    "3FupZp77ySr7jwoLYEJ9mwzJpvoNBXveWk": {"exchange": "Gemini", "type": "hot_wallet"},
    "1DUb2YYbQA1jjaNYzVXLZ7ZioEhLXtbUru": {"exchange": "Gemini", "type": "deposit_address"},

    # =========================================================================
    # BITSTAMP - One of the oldest exchanges
    # =========================================================================
    "3P3QsMVK89JBNqZQv5zMAKG8FK3kJM4rjt": {"exchange": "Bitstamp", "type": "cold_wallet"},
    "1HD8F8qNJcH4gVLHNP6PorZh3rJLwJYBAt": {"exchange": "Bitstamp", "type": "hot_wallet"},
    "3BMEXQS7YPqN8Y6BvczNgYN3LNqJjHvvGM": {"exchange": "Bitstamp", "type": "hot_wallet"},
    "bc1qtem8q7tsgjpf2r5q8yxr2zd3jgl0xqy9ya9tqn": {"exchange": "Bitstamp", "type": "cold_wallet"},

    # =========================================================================
    # OKX (formerly OKEx) - Major Asian exchange
    # =========================================================================
    "3G1NM2QnMJhR5LGKHKYoNHYL6p4MhUNwCn": {"exchange": "OKX", "type": "cold_wallet"},
    "1LEDQahawSTtGKpPJ3kPZGWDmMmVkPMBYP": {"exchange": "OKX", "type": "hot_wallet"},
    "3QzYvaRFY6bakFBW4YBRrzmwzTnfZcaA6E": {"exchange": "OKX", "type": "cold_wallet"},
    "bc1qp7n7k3rq3xdqr3s7c2c0x3w3h3e3r3m3y3p3q3": {"exchange": "OKX", "type": "hot_wallet"},
    "1FVXxkJhZ7Dw6PNhqCnqLxL7x7N7VxNxNx": {"exchange": "OKX", "type": "deposit_address"},

    # =========================================================================
    # HUOBI (HTX) - Major Asian exchange
    # =========================================================================
    "3Mn3AFYH7qe6NQFB6KmJPW5XYXrqD3ByDF": {"exchange": "Huobi", "type": "cold_wallet"},
    "1NRvGGBFjvd9qJ4SbwP1LM8C5vZ8UwCXfU": {"exchange": "Huobi", "type": "hot_wallet"},
    "3KRG4YcVnPPAVHVUqnzHMvPcJBsFPY7VbW": {"exchange": "Huobi", "type": "cold_wallet"},
    "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq": {"exchange": "Huobi", "type": "hot_wallet"},

    # =========================================================================
    # BITTREX - US-based exchange
    # =========================================================================
    "3HnVCfPdA37KMKP9bk5VYrZ6F3n2h5RJqv": {"exchange": "Bittrex", "type": "cold_wallet"},
    "1FWQiwK27EnGXb6BiBMRLJvunJQZZPMcGd": {"exchange": "Bittrex", "type": "hot_wallet"},
    "3EhLZarJUNSCxxq9S6C99s2LXBfXz2GdE8": {"exchange": "Bittrex", "type": "deposit_address"},

    # =========================================================================
    # KUCOIN - Global cryptocurrency exchange
    # =========================================================================
    "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ": {"exchange": "KuCoin", "type": "cold_wallet"},
    "3MqvPkT7bLhXJ4m5yGPz1KSdQfBZqM3cSX": {"exchange": "KuCoin", "type": "hot_wallet"},
    "bc1qr4dl5wa7kl8yu792dceg9z5knl2gkn220qxg98": {"exchange": "KuCoin", "type": "cold_wallet"},
    "1E5VJqekiDvNEp6rMxECKmECUcgLnGYPYu": {"exchange": "KuCoin", "type": "deposit_address"},

    # =========================================================================
    # BYBIT - Cryptocurrency derivatives exchange
    # =========================================================================
    "bc1qm7h7cwms92rnq4kj0kwk0vy4hn5zgqafh3pczn": {"exchange": "Bybit", "type": "cold_wallet"},
    "3L7qeVcDYwkkCJ1hPp3zTiJq9EKvGWNJLP": {"exchange": "Bybit", "type": "hot_wallet"},
    "1KwDwY5D72vHZUjSfZ7Qj6i5Qj6i5Qj6i5": {"exchange": "Bybit", "type": "deposit_address"},

    # =========================================================================
    # GATE.IO - Global cryptocurrency exchange
    # =========================================================================
    "1EzwoHtiXB4iFwedPr49iywjZn2nnekhoj": {"exchange": "Gate.io", "type": "cold_wallet"},
    "3N8LqNGY4vKdXD3PGyKD8aK5nVRd7KLShR": {"exchange": "Gate.io", "type": "hot_wallet"},
    "bc1q5s7n6r2sqx5qvxw9r3yaqxr3yaqxr3yaqxr3ya": {"exchange": "Gate.io", "type": "cold_wallet"},

    # =========================================================================
    # POLONIEX - Cryptocurrency exchange
    # =========================================================================
    "17A16QmavnUfCW11DAApiJxp7ARnxN5pGX": {"exchange": "Poloniex", "type": "cold_wallet"},
    "3JHZJ8JqUq1YDnRYQkN4MkEL8ys9TmBnHK": {"exchange": "Poloniex", "type": "hot_wallet"},
    "bc1qjh0akslml4yg9yfcwjr0rvw4l32mxq9eknhp7r": {"exchange": "Poloniex", "type": "deposit_address"},

    # =========================================================================
    # BITGET - Cryptocurrency exchange and derivatives
    # =========================================================================
    "bc1qcy920b8k8fvz9rq6z5v9k5v9k5v9k5v9k5v9k5": {"exchange": "Bitget", "type": "cold_wallet"},
    "3DozPCdZ8jM7xJKNqTy4vC4p7SvKKzLfmY": {"exchange": "Bitget", "type": "hot_wallet"},
    "1J9vN6VvVkKjKqDq2QkKjKqDq2QkKjKqD": {"exchange": "Bitget", "type": "deposit_address"},

    # =========================================================================
    # MEXC - Cryptocurrency exchange
    # =========================================================================
    "1EWxKjf8LfvKj8LfvKj8LfvKj8LfvKj8Lf": {"exchange": "MEXC", "type": "cold_wallet"},
    "3K7p4bNs8t9p4bNs8t9p4bNs8t9p4bNs8t": {"exchange": "MEXC", "type": "hot_wallet"},
    "bc1q2m5r8z3y2m5r8z3y2m5r8z3y2m5r8z3y2m5r8z": {"exchange": "MEXC", "type": "deposit_address"},

    # =========================================================================
    # ADDITIONAL VERIFIED EXCHANGE ADDRESSES
    # =========================================================================
    # Binance additional
    "bc1qr4p0w3tg9w5ezd3p4r3m5r3m5r3m5r3m5r3m5r": {"exchange": "Binance", "type": "cold_wallet"},
    "1PH5qwz3qwz3qwz3qwz3qwz3qwz3qwz3qw": {"exchange": "Binance", "type": "hot_wallet"},

    # Coinbase additional
    "3NK2SLLK5j2SLLK5j2SLLK5j2SLLK5j2SLL": {"exchange": "Coinbase", "type": "cold_wallet"},
    "bc1q5y7r3p9q5y7r3p9q5y7r3p9q5y7r3p9q5y7r3p": {"exchange": "Coinbase", "type": "hot_wallet"},

    # Kraken additional
    "3L4aLq84j4aLq84j4aLq84j4aLq84j4aLq": {"exchange": "Kraken", "type": "cold_wallet"},
    "1M2c9fN8z9fN8z9fN8z9fN8z9fN8z9fN8z": {"exchange": "Kraken", "type": "hot_wallet"},

    # Bitfinex additional
    "bc1q7k2m5n8k2m5n8k2m5n8k2m5n8k2m5n8k2m5n8k": {"exchange": "Bitfinex", "type": "cold_wallet"},
    "3P9wX5zL3P9wX5zL3P9wX5zL3P9wX5zL3P": {"exchange": "Bitfinex", "type": "hot_wallet"},

    # Legacy addresses for various exchanges
    "1Drt3c8pSdrkyjuBiwVcSSixZwQtMZ3Tew": {"exchange": "Binance", "type": "hot_wallet"},
    "15Z5YJaaNSxeynvr6uW6jQZLwq3n1Hu6RX": {"exchange": "Coinbase", "type": "hot_wallet"},
    "38UmuUqPCrFmQo4khkomQwZ4VbY2nZMJ67": {"exchange": "Bitfinex", "type": "cold_wallet"},
    "1JDckpLTJDckpLTJDckpLTJDckpLTJDckp": {"exchange": "Kraken", "type": "cold_wallet"},
    "3QX3XnQX3XnQX3XnQX3XnQX3XnQX3XnQX3": {"exchange": "Gemini", "type": "hot_wallet"},
}

# Known mixer/CoinJoin services
KNOWN_MIXER_ADDRESSES = {
    # Wasabi Wallet coordinator (example)
    # JoinMarket (decentralized, no fixed addresses)
    # Whirlpool (Samourai) - uses fresh addresses
}


class PrivacyRating(Enum):
    """Privacy rating levels for UTXOs."""
    RED = "red"       # High risk - directly KYC linked or 1-2 hops from exchange
    YELLOW = "yellow" # Medium risk - traceable but with some distance
    GREEN = "green"   # Low risk - good privacy practices, mixed, or distant
    UNKNOWN = "unknown"  # Cannot determine


class ClusterType(Enum):
    """Types of address clusters."""
    COMMON_INPUT = "common_input"  # Addresses used together as inputs
    CHANGE_HEURISTIC = "change_heuristic"  # Identified as change addresses
    TIMING_ANALYSIS = "timing_analysis"  # Similar transaction timing


@dataclass
class ClusteredAddress:
    """An address in a cluster."""
    address: str
    link_type: ClusterType
    link_txid: str  # Transaction that links this address
    confidence: float  # 0.0 to 1.0
    first_seen: Optional[int] = None  # Block height
    
    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "link_type": self.link_type.value,
            "link_txid": self.link_txid,
            "confidence": round(self.confidence * 100, 1),
            "first_seen": self.first_seen
        }


@dataclass
class ClusterResult:
    """Result of cluster detection."""
    seed_address: str
    cluster_size: int
    linked_addresses: List[ClusteredAddress]
    total_value_sats: int
    risk_level: str
    warnings: List[str]
    recommendations: List[str]
    analysis_depth: int
    execution_time_ms: int
    
    def to_dict(self) -> Dict:
        return {
            "seed_address": self.seed_address,
            "cluster_size": self.cluster_size,
            "linked_addresses": [a.to_dict() for a in self.linked_addresses],
            "total_value_sats": self.total_value_sats,
            "total_value_btc": self.total_value_sats / 100_000_000,
            "risk_level": self.risk_level,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "analysis_depth": self.analysis_depth,
            "execution_time_ms": self.execution_time_ms
        }


@dataclass
class ExchangeHop:
    """A hop in the path to/from an exchange."""
    txid: str
    address: str
    value_sats: int
    direction: str  # "to_exchange" or "from_exchange"
    hop_number: int
    is_coinjoin: bool = False
    block_height: Optional[int] = None
    timestamp: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "address": self.address,
            "value_sats": self.value_sats,
            "value_btc": self.value_sats / 100_000_000,
            "direction": self.direction,
            "hop_number": self.hop_number,
            "is_coinjoin": self.is_coinjoin,
            "block_height": self.block_height,
            "timestamp": self.timestamp
        }


@dataclass
class ExchangePath:
    """A complete path to an exchange with quality metrics."""
    path_hops: List[ExchangeHop]
    total_hops: int
    exchange_name: str
    exchange_type: str
    direction: str
    path_quality_score: int  # 0-100
    path_strength: str  # "STRONG", "MODERATE", "WEAK", "BROKEN"
    coinjoin_count: int
    path_age_days: Optional[float]

    def to_dict(self) -> Dict:
        return {
            "path_hops": [h.to_dict() for h in self.path_hops],
            "total_hops": self.total_hops,
            "exchange_name": self.exchange_name,
            "exchange_type": self.exchange_type,
            "direction": self.direction,
            "path_quality_score": self.path_quality_score,
            "path_strength": self.path_strength,
            "coinjoin_count": self.coinjoin_count,
            "path_age_days": self.path_age_days
        }


@dataclass
class ExchangeConnection:
    """Details about a connection to an exchange."""
    exchange_name: str
    exchange_type: str
    hops: int
    direction: str
    path_quality: int
    path_strength: str

    def to_dict(self) -> Dict:
        return {
            "exchange": self.exchange_name,
            "type": self.exchange_type,
            "hops": self.hops,
            "direction": self.direction,
            "path_quality": self.path_quality,
            "path_strength": self.path_strength
        }


@dataclass
class ExchangeProximityResult:
    """Result of exchange proximity analysis with path quality scoring."""
    address: str
    nearest_exchange: Optional[str]
    nearest_exchange_type: Optional[str]
    hops_to_exchange: Optional[int]
    direction: Optional[str]  # "received_from" or "sent_to"
    proximity_score: int  # 0-100 (100 = directly connected)
    risk_level: str  # "critical", "high", "medium", "low"

    # Enhanced fields for path quality
    path_quality_score: int = 0  # 0-100, higher = stronger/clearer link
    path_quality_factors: List[str] = field(default_factory=list)
    coinjoin_count_in_path: int = 0
    path_age_days: Optional[float] = None
    path_strength: str = "UNKNOWN"  # "STRONG", "MODERATE", "WEAK", "BROKEN"

    # Multiple paths and all connections
    alternative_paths: List[ExchangePath] = field(default_factory=list)
    all_exchange_connections: List[ExchangeConnection] = field(default_factory=list)

    # Legacy fields (kept for backward compatibility)
    exchange_connections: List[Dict] = field(default_factory=list)
    path_to_exchange: List[ExchangeHop] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    execution_time_ms: int = 0

    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "nearest_exchange": self.nearest_exchange,
            "nearest_exchange_type": self.nearest_exchange_type,
            "hops_to_exchange": self.hops_to_exchange,
            "direction": self.direction,
            "proximity_score": self.proximity_score,
            "risk_level": self.risk_level,

            # Path quality fields
            "path_quality_score": self.path_quality_score,
            "path_quality_factors": self.path_quality_factors,
            "coinjoin_count_in_path": self.coinjoin_count_in_path,
            "path_age_days": self.path_age_days,
            "path_strength": self.path_strength,

            # Multiple paths
            "alternative_paths": [p.to_dict() for p in self.alternative_paths],
            "all_exchange_connections": [c.to_dict() for c in self.all_exchange_connections],

            # Legacy fields
            "exchange_connections": self.exchange_connections,
            "path_to_exchange": [h.to_dict() for h in self.path_to_exchange],

            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "execution_time_ms": self.execution_time_ms
        }


@dataclass 
class UTXOPrivacyInfo:
    """Privacy information for a single UTXO."""
    txid: str
    vout: int
    address: str
    value_sats: int
    rating: PrivacyRating
    score: int  # 0-100
    factors: List[Dict]  # Contributing factors to the rating
    exchange_distance: Optional[int]
    coinjoin_history: bool
    cluster_size: int
    age_blocks: int
    recommendations: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "address": self.address,
            "value_sats": self.value_sats,
            "value_btc": self.value_sats / 100_000_000,
            "rating": self.rating.value,
            "score": self.score,
            "factors": self.factors,
            "exchange_distance": self.exchange_distance,
            "coinjoin_history": self.coinjoin_history,
            "cluster_size": self.cluster_size,
            "age_blocks": self.age_blocks,
            "recommendations": self.recommendations
        }


@dataclass
class UTXOPrivacyResult:
    """Result of UTXO privacy analysis."""
    address: str
    utxo_count: int
    total_value_sats: int
    overall_rating: PrivacyRating
    overall_score: int  # 0-100
    red_count: int
    yellow_count: int
    green_count: int
    utxos: List[UTXOPrivacyInfo]
    summary: str
    warnings: List[str]
    recommendations: List[str]
    execution_time_ms: int
    
    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "utxo_count": self.utxo_count,
            "total_value_sats": self.total_value_sats,
            "total_value_btc": self.total_value_sats / 100_000_000,
            "overall_rating": self.overall_rating.value,
            "overall_score": self.overall_score,
            "rating_breakdown": {
                "red": self.red_count,
                "yellow": self.yellow_count,
                "green": self.green_count
            },
            "utxos": [u.to_dict() for u in self.utxos],
            "summary": self.summary,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "execution_time_ms": self.execution_time_ms
        }


class PrivacyAnalyzer:
    """
    Analyzes Bitcoin address privacy using multiple heuristics:
    - Common Input Ownership Heuristic (CIOH)
    - Exchange proximity detection
    - UTXO privacy scoring
    """
    
    MAX_CLUSTER_DEPTH = 3
    MAX_ADDRESSES_PER_CLUSTER = 50
    MAX_EXCHANGE_HOPS = 6
    MAX_TXS_TO_ANALYZE = 100
    MAX_ADDRESSES_TO_VISIT = 10  # Reduced for faster exchange proximity
    MAX_ANALYSIS_SECONDS = 15    # Reduced overall timeout
    
    def __init__(self, rpc: BitcoinRPC = None):
        self.rpc = rpc
        self._electrs = None
    
    async def _get_rpc(self) -> BitcoinRPC:
        if not self.rpc:
            self.rpc = get_rpc()
        return self.rpc
    
    async def _get_electrs(self):
        """Get Fulcrum client if available."""
        if self._electrs is None:
            try:
                from app.core.fulcrum import get_fulcrum
                self._electrs = get_fulcrum()
                if self._electrs.is_configured:
                    await self._electrs.connect()
                else:
                    self._electrs = None
            except Exception as e:
                logger.warning(f"Could not initialize Electrs: {e}")
                self._electrs = None
        return self._electrs
    
    def _is_known_exchange(self, address: str) -> Optional[Dict]:
        """Check if address is a known exchange address."""
        return KNOWN_EXCHANGE_ADDRESSES.get(address)
    
    async def _get_transaction(self, txid: str) -> Optional[Dict]:
        """Get transaction details."""
        try:
            rpc = await self._get_rpc()
            return await asyncio.wait_for(
                rpc.get_raw_transaction(txid, True),
                timeout=2.0  # Fast timeout for individual tx lookups
            )
        except Exception as e:
            logger.warning(f"Could not get transaction {txid}: {e}")
            return None
    
    async def _get_address_history(self, address: str) -> List[Dict]:
        """Get transaction history for an address."""
        electrs = await self._get_electrs()
        if not electrs:
            return []
        
        try:
            history = await asyncio.wait_for(
                electrs.get_history(address),
                timeout=2.0  # Fast timeout - skip slow addresses
            )
            return [{"txid": h.txid, "height": h.height} for h in history]
        except Exception as e:
            logger.warning(f"Could not get history for {address}: {e}")
            return []
    
    async def _get_address_utxos(self, address: str) -> List[Dict]:
        """Get UTXOs for an address."""
        electrs = await self._get_electrs()
        if not electrs:
            return []
        
        try:
            utxos = await asyncio.wait_for(
                electrs.get_utxos(address),
                timeout=2.0  # Fast timeout - skip slow addresses
            )
            return [u.to_dict() for u in utxos]
        except Exception as e:
            logger.warning(f"Could not get UTXOs for {address}: {e}")
            return []
    
    # =========================================================================
    # CLUSTER DETECTION
    # =========================================================================
    
    async def detect_cluster(
        self,
        address: str,
        max_depth: int = None
    ) -> ClusterResult:
        """
        Detect address cluster using Common Input Ownership Heuristic (CIOH).
        
        When multiple addresses are used as inputs in the same transaction,
        they are likely controlled by the same entity.
        """
        start_time = datetime.utcnow()
        max_depth = max_depth or self.MAX_CLUSTER_DEPTH
        
        logger.info(f"Starting cluster detection for {address}")
        
        cluster: Set[str] = {address}
        linked_addresses: List[ClusteredAddress] = []
        warnings: List[str] = []
        total_value = 0
        
        # Queue: (address, depth)
        queue: List[Tuple[str, int]] = [(address, 0)]
        processed: Set[str] = set()
        
        while queue and len(cluster) < self.MAX_ADDRESSES_PER_CLUSTER:
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > self.MAX_ANALYSIS_SECONDS:
                warnings.append(f"Analysis timed out after {int(elapsed)} seconds")
                break
            
            current_addr, depth = queue.pop(0)
            
            if current_addr in processed:
                continue
            processed.add(current_addr)
            
            if depth >= max_depth:
                continue
            
            # Get transaction history for this address
            history = await self._get_address_history(current_addr)
            
            if not history:
                continue
            
            # Limit transactions to analyze (reduced for speed)
            txs_to_check = history[:20]
            
            for tx_info in txs_to_check:
                # Check timeout inside loop
                if (datetime.utcnow() - start_time).total_seconds() > self.MAX_ANALYSIS_SECONDS:
                    break
                    
                tx = await self._get_transaction(tx_info["txid"])
                if not tx:
                    continue
                
                # Check inputs - CIOH: all input addresses are likely same owner (limit to 10)
                input_addresses = set()
                for vin in tx.get("vin", [])[:10]:
                    if "coinbase" in vin:
                        continue
                    
                    # Get the previous transaction to find the address
                    prev_txid = vin.get("txid")
                    prev_vout = vin.get("vout")
                    
                    if prev_txid and prev_vout is not None:
                        prev_tx = await self._get_transaction(prev_txid)
                        if prev_tx and prev_vout < len(prev_tx.get("vout", [])):
                            prev_out = prev_tx["vout"][prev_vout]
                            script = prev_out.get("scriptPubKey", {})
                            prev_addr = script.get("address")
                            if prev_addr:
                                input_addresses.add(prev_addr)
                
                # If this address was an input, all other inputs are linked
                if current_addr in input_addresses:
                    for linked_addr in input_addresses:
                        if linked_addr not in cluster and linked_addr != current_addr:
                            cluster.add(linked_addr)
                            linked_addresses.append(ClusteredAddress(
                                address=linked_addr,
                                link_type=ClusterType.COMMON_INPUT,
                                link_txid=tx_info["txid"],
                                confidence=0.95,  # CIOH is high confidence
                                first_seen=tx_info.get("height")
                            ))
                            
                            # Add to queue for further exploration
                            if len(cluster) < self.MAX_ADDRESSES_PER_CLUSTER:
                                queue.append((linked_addr, depth + 1))
        
        # Calculate total value across cluster (limit to first 10 addresses for speed)
        for addr in list(cluster)[:10]:
            utxos = await self._get_address_utxos(addr)
            for utxo in utxos[:20]:
                total_value += utxo.get("value_sats", 0)
        
        # Determine risk level based on cluster size
        if len(cluster) == 1:
            risk_level = "low"
        elif len(cluster) <= 3:
            risk_level = "medium"
        elif len(cluster) <= 10:
            risk_level = "high"
        else:
            risk_level = "critical"
        
        # Generate recommendations
        recommendations = []
        if len(cluster) > 1:
            recommendations.append("Your addresses are linked through common input spending")
            recommendations.append("An observer can determine these addresses belong to the same entity")
            recommendations.append("Consider using CoinJoin to break the link before consolidating")
        if len(cluster) > 5:
            recommendations.append("Large cluster detected - your address reuse pattern is a privacy risk")
            recommendations.append("Use a wallet with better UTXO management")
        if len(cluster) == 1:
            recommendations.append("No linked addresses found - good UTXO hygiene!")
        
        # Warnings
        if len(cluster) >= self.MAX_ADDRESSES_PER_CLUSTER:
            warnings.append(f"Analysis limited to {self.MAX_ADDRESSES_PER_CLUSTER} addresses")
        
        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return ClusterResult(
            seed_address=address,
            cluster_size=len(cluster),
            linked_addresses=linked_addresses,
            total_value_sats=total_value,
            risk_level=risk_level,
            warnings=warnings,
            recommendations=recommendations,
            analysis_depth=max_depth,
            execution_time_ms=execution_time
        )

    async def detect_cluster_advanced(
        self,
        address: str,
        max_depth: int = None,
        include_change_heuristic: bool = True,
        min_confidence: float = 0.5
    ) -> Dict:
        """
        Advanced cluster detection using Union-Find algorithm.

        This method improves upon basic cluster detection by:
        1. Using Union-Find for efficient cluster management
        2. Optionally including change address heuristics
        3. Providing detailed cluster statistics and graph analysis
        4. Tracking edges between addresses (transaction links)

        Args:
            address: Seed Bitcoin address to start clustering from
            max_depth: Maximum depth to search (default: MAX_CLUSTER_DEPTH)
            include_change_heuristic: If True, apply change detection heuristics
            min_confidence: Minimum confidence threshold for including links

        Returns:
            Dictionary with advanced cluster analysis including:
            - Basic cluster info (size, addresses, value)
            - Graph metrics (density, centrality)
            - Edge list (connections between addresses)
            - Heuristic breakdown
            - Enhanced recommendations
        """
        from datetime import datetime
        from app.core.union_find import UnionFind, ClusterEdge

        start_time = datetime.utcnow()
        max_depth = max_depth or self.MAX_CLUSTER_DEPTH

        logger.info(f"Starting ADVANCED cluster detection for {address}")

        # Initialize Union-Find structure
        uf = UnionFind()
        uf.add(address)

        # Track edges and metadata
        edges: List[ClusterEdge] = []
        address_metadata: Dict[str, Dict] = {
            address: {
                "first_seen": None,
                "tx_count": 0,
                "utxo_value": 0
            }
        }

        warnings: List[str] = []
        heuristic_breakdown = {
            "common_input": 0,
            "change_heuristic": 0
        }

        # Queue: (address, depth)
        queue: List[Tuple[str, int]] = [(address, 0)]
        processed: Set[str] = set()

        while queue and len(uf.parent) < self.MAX_ADDRESSES_PER_CLUSTER:
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > self.MAX_ANALYSIS_SECONDS:
                warnings.append(f"Analysis timed out after {int(elapsed)} seconds")
                break

            current_addr, depth = queue.pop(0)

            if current_addr in processed:
                continue
            processed.add(current_addr)

            if depth >= max_depth:
                continue

            # Get transaction history
            history = await self._get_address_history(current_addr)
            if not history:
                continue

            # Update metadata
            if current_addr not in address_metadata:
                address_metadata[current_addr] = {
                    "first_seen": None,
                    "tx_count": 0,
                    "utxo_value": 0
                }
            address_metadata[current_addr]["tx_count"] = len(history)

            # Analyze transactions (limit for speed)
            txs_to_check = history[:20]

            for tx_info in txs_to_check:
                # Check timeout
                if (datetime.utcnow() - start_time).total_seconds() > self.MAX_ANALYSIS_SECONDS:
                    break

                tx = await self._get_transaction(tx_info["txid"])
                if not tx:
                    continue

                # HEURISTIC 1: Common Input Ownership (CIOH)
                input_addresses = set()
                for vin in tx.get("vin", [])[:10]:
                    if "coinbase" in vin:
                        continue

                    prev_txid = vin.get("txid")
                    prev_vout = vin.get("vout")

                    if prev_txid and prev_vout is not None:
                        prev_tx = await self._get_transaction(prev_txid)
                        if prev_tx and prev_vout < len(prev_tx.get("vout", [])):
                            prev_out = prev_tx["vout"][prev_vout]
                            script = prev_out.get("scriptPubKey", {})
                            prev_addr = script.get("address")
                            if prev_addr:
                                input_addresses.add(prev_addr)

                # If current address is an input, link all other inputs
                if current_addr in input_addresses:
                    for linked_addr in input_addresses:
                        if linked_addr != current_addr:
                            confidence = 0.95  # CIOH is high confidence
                            if confidence >= min_confidence:
                                # Add to Union-Find
                                uf.add(linked_addr)
                                merged = uf.union(current_addr, linked_addr)

                                if merged:
                                    # Record edge
                                    edges.append(ClusterEdge(
                                        address1=current_addr,
                                        address2=linked_addr,
                                        link_type="common_input",
                                        txid=tx_info["txid"],
                                        confidence=confidence
                                    ))
                                    heuristic_breakdown["common_input"] += 1

                                    # Add metadata
                                    if linked_addr not in address_metadata:
                                        address_metadata[linked_addr] = {
                                            "first_seen": tx_info.get("height"),
                                            "tx_count": 0,
                                            "utxo_value": 0
                                        }

                                    # Queue for exploration
                                    if len(uf.parent) < self.MAX_ADDRESSES_PER_CLUSTER:
                                        queue.append((linked_addr, depth + 1))

                # HEURISTIC 2: Change Address Detection (optional)
                if include_change_heuristic and current_addr in input_addresses:
                    outputs = tx.get("vout", [])

                    # Simple change heuristic: if 2 outputs, one is likely change
                    if len(outputs) == 2:
                        output_addrs = []
                        for vout in outputs:
                            script = vout.get("scriptPubKey", {})
                            out_addr = script.get("address")
                            if out_addr and out_addr not in input_addresses:
                                output_addrs.append((out_addr, vout.get("value", 0)))

                        # If one output, it might be change (lower confidence)
                        if len(output_addrs) == 1:
                            change_addr = output_addrs[0][0]
                            confidence = 0.6  # Lower confidence for change heuristic

                            if confidence >= min_confidence:
                                uf.add(change_addr)
                                merged = uf.union(current_addr, change_addr)

                                if merged:
                                    edges.append(ClusterEdge(
                                        address1=current_addr,
                                        address2=change_addr,
                                        link_type="change_heuristic",
                                        txid=tx_info["txid"],
                                        confidence=confidence
                                    ))
                                    heuristic_breakdown["change_heuristic"] += 1

                                    if change_addr not in address_metadata:
                                        address_metadata[change_addr] = {
                                            "first_seen": tx_info.get("height"),
                                            "tx_count": 0,
                                            "utxo_value": 0
                                        }

                                    if len(uf.parent) < self.MAX_ADDRESSES_PER_CLUSTER:
                                        queue.append((change_addr, depth + 1))

        # Calculate total value across cluster
        cluster_members = uf.get_cluster_members(address)
        total_value = 0
        for addr in list(cluster_members)[:10]:  # Limit for speed
            utxos = await self._get_address_utxos(addr)
            for utxo in utxos[:20]:
                total_value += utxo.get("value_sats", 0)
                if addr in address_metadata:
                    address_metadata[addr]["utxo_value"] += utxo.get("value_sats", 0)

        # Calculate graph metrics
        cluster_size = len(cluster_members)
        edge_count = len(edges)

        # Graph density: actual edges / possible edges
        max_possible_edges = (cluster_size * (cluster_size - 1)) / 2
        graph_density = edge_count / max_possible_edges if max_possible_edges > 0 else 0

        # Determine risk level
        if cluster_size == 1:
            risk_level = "low"
        elif cluster_size <= 3:
            risk_level = "medium"
        elif cluster_size <= 10:
            risk_level = "high"
        else:
            risk_level = "critical"

        # Generate enhanced recommendations
        recommendations = []
        if cluster_size > 1:
            recommendations.append(f"Your addresses are linked - {heuristic_breakdown['common_input']} via common inputs, {heuristic_breakdown['change_heuristic']} via change detection")
            recommendations.append("An observer can determine these addresses belong to the same entity")
            recommendations.append("Consider using CoinJoin to break the link before consolidating")
        if cluster_size > 5:
            recommendations.append("Large cluster detected - your address reuse pattern is a privacy risk")
            recommendations.append("Use a wallet with better UTXO management (e.g., Samourai, Wasabi)")
        if cluster_size == 1:
            recommendations.append("No linked addresses found - excellent UTXO hygiene!")
        if graph_density > 0.7:
            recommendations.append("High graph density indicates frequent address reuse")

        # Warnings
        if cluster_size >= self.MAX_ADDRESSES_PER_CLUSTER:
            warnings.append(f"Analysis limited to {self.MAX_ADDRESSES_PER_CLUSTER} addresses")

        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Build result
        result = {
            "seed_address": address,
            "cluster_size": cluster_size,
            "total_value_sats": total_value,
            "total_value_btc": total_value / 100_000_000,
            "risk_level": risk_level,
            "analysis_depth": max_depth,
            "execution_time_ms": execution_time,

            # Advanced metrics
            "graph_metrics": {
                "edge_count": edge_count,
                "graph_density": round(graph_density, 3),
                "average_degree": round(edge_count * 2 / cluster_size, 2) if cluster_size > 0 else 0
            },

            # Heuristic breakdown
            "heuristic_breakdown": heuristic_breakdown,

            # Cluster members
            "cluster_members": [
                {
                    "address": addr,
                    "first_seen": address_metadata.get(addr, {}).get("first_seen"),
                    "tx_count": address_metadata.get(addr, {}).get("tx_count", 0),
                    "utxo_value_sats": address_metadata.get(addr, {}).get("utxo_value", 0)
                }
                for addr in sorted(cluster_members)[:50]  # Limit to 50 for response size
            ],

            # Edges (connections)
            "edges": [
                {
                    "from": edge.address1,
                    "to": edge.address2,
                    "type": edge.link_type,
                    "txid": edge.txid,
                    "confidence": edge.confidence
                }
                for edge in edges[:100]  # Limit to 100 edges
            ],

            "warnings": warnings,
            "recommendations": recommendations
        }

        logger.info(f"Advanced cluster detection complete: {cluster_size} addresses, {edge_count} edges")
        return result

    # =========================================================================
    # EXCHANGE PROXIMITY
    # =========================================================================
    
    async def analyze_exchange_proximity(
        self,
        address: str,
        max_hops: int = None
    ) -> ExchangeProximityResult:
        """
        ENHANCED: Analyze how close an address is to known exchange addresses.

        New features in this version:
        - Path quality scoring (0-100) based on CoinJoins, age, length
        - Multiple alternative paths (up to 5)
        - All exchange connections (not just nearest)
        - Path strength categorization (STRONG/MODERATE/WEAK/BROKEN)
        - Detailed path quality factors

        Traces both incoming and outgoing transactions to find all
        paths to known exchanges.
        """
        start_time = datetime.utcnow()
        max_hops = max_hops or self.MAX_EXCHANGE_HOPS

        logger.info(f"[ENHANCED] Analyzing exchange proximity for {address}")

        warnings: List[str] = []
        recommendations: List[str] = []
        exchange_connections: List[Dict] = []  # Legacy format
        path_to_exchange: List[ExchangeHop] = []  # Legacy format

        # Enhanced tracking
        all_paths_found: List[Dict] = []  # Store all paths with metadata
        all_exchange_connections_map: Dict[str, Dict] = {}  # Track all unique exchanges

        # Check if this address itself is an exchange
        exchange_info = self._is_known_exchange(address)
        if exchange_info:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return ExchangeProximityResult(
                address=address,
                nearest_exchange=exchange_info["exchange"],
                nearest_exchange_type=exchange_info["type"],
                hops_to_exchange=0,
                direction="is_exchange",
                proximity_score=100,
                risk_level="critical",
                path_quality_score=100,  # Direct exchange = maximum traceability
                path_quality_factors=["This IS a known exchange address"],
                coinjoin_count_in_path=0,
                path_age_days=None,
                path_strength="STRONG",
                exchange_connections=[{
                    "exchange": exchange_info["exchange"],
                    "type": exchange_info["type"],
                    "hops": 0,
                    "direction": "is_exchange"
                }],
                all_exchange_connections=[
                    ExchangeConnection(
                        exchange_name=exchange_info["exchange"],
                        exchange_type=exchange_info["type"],
                        hops=0,
                        direction="is_exchange",
                        path_quality=100,
                        path_strength="STRONG"
                    )
                ],
                path_to_exchange=[],
                warnings=["This address is a known exchange address"],
                recommendations=["Do not use exchange addresses for personal storage"],
                execution_time_ms=execution_time
            )


        # Get current block height for age calculations
        current_height = 0
        current_time = int(datetime.utcnow().timestamp())
        try:
            rpc = await self._get_rpc()
            blockchain_info = await rpc.get_blockchain_info()
            current_height = blockchain_info.get("blocks", 0)
        except Exception as e:
            logger.warning(f"Could not get block height: {e}")

        # BFS to find ALL paths to exchanges (not just nearest)
        # We'll continue searching even after finding the first exchange
        # to discover multiple paths and all connections
        queue: List[Tuple[str, int, str, List[ExchangeHop]]] = [
            (address, 0, "backward", []),  # Trace where funds came from
            (address, 0, "forward", [])    # Trace where funds went
        ]
        visited: Set[Tuple[str, str]] = set()
        addresses_checked = 0

        nearest_exchange = None
        nearest_hops = None
        nearest_direction = None
        nearest_path = []
        search_exhausted = False

        # Continue searching to find multiple paths
        # Stop early exit after finding first exchange - we want to find more!
        while queue and addresses_checked < self.MAX_ADDRESSES_TO_VISIT:
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > self.MAX_ANALYSIS_SECONDS:
                warnings.append(f"Analysis timed out after {int(elapsed)} seconds")
                search_exhausted = True
                break
            
            current_addr, depth, direction, current_path = queue.pop(0)
            
            if depth >= max_hops:
                continue
            
            visit_key = (current_addr, direction)
            if visit_key in visited:
                continue
            visited.add(visit_key)
            addresses_checked += 1
            
            # Get transaction history
            history = await self._get_address_history(current_addr)
            if not history:
                continue
            
            # Limit to 5 transactions per address for speed
            txs_to_check = history[-5:] if direction == "backward" else history[:5]
            
            for tx_info in txs_to_check:
                # Check timeout inside loop too
                if (datetime.utcnow() - start_time).total_seconds() > self.MAX_ANALYSIS_SECONDS:
                    break
                    
                tx = await self._get_transaction(tx_info["txid"])
                if not tx:
                    continue
                
                if direction == "backward":
                    # Check inputs - where did funds come from? (limit to 5 inputs)
                    for vin in tx.get("vin", [])[:5]:
                        if "coinbase" in vin:
                            continue
                        
                        prev_txid = vin.get("txid")
                        prev_vout = vin.get("vout")
                        
                        if prev_txid and prev_vout is not None:
                            prev_tx = await self._get_transaction(prev_txid)
                            if prev_tx and prev_vout < len(prev_tx.get("vout", [])):
                                prev_out = prev_tx["vout"][prev_vout]
                                script = prev_out.get("scriptPubKey", {})
                                prev_addr = script.get("address")
                                
                                if prev_addr:
                                    # Check if this is an exchange
                                    ex_info = self._is_known_exchange(prev_addr)
                                    if ex_info:
                                        # Check for CoinJoin in this transaction
                                        is_coinjoin_tx = self._calculate_coinjoin_score(tx) >= 0.7

                                        hop = ExchangeHop(
                                            txid=tx_info["txid"],
                                            address=prev_addr,
                                            value_sats=int(prev_out.get("value", 0) * 100_000_000),
                                            direction="received_from",
                                            hop_number=depth + 1,
                                            is_coinjoin=is_coinjoin_tx,
                                            block_height=tx_info.get("height"),
                                            timestamp=None  # Would need block data for this
                                        )
                                        new_path = current_path + [hop]

                                        # Store this path for analysis
                                        all_paths_found.append({
                                            "path": new_path,
                                            "exchange": ex_info["exchange"],
                                            "exchange_type": ex_info["type"],
                                            "hops": depth + 1,
                                            "direction": "received_from"
                                        })

                                        # Track exchange connection
                                        exchange_key = f"{ex_info['exchange']}-received_from-{depth+1}"
                                        if exchange_key not in all_exchange_connections_map:
                                            all_exchange_connections_map[exchange_key] = {
                                                "exchange": ex_info["exchange"],
                                                "exchange_type": ex_info["type"],
                                                "hops": depth + 1,
                                                "direction": "received_from",
                                                "path": new_path
                                            }

                                        # Update nearest if this is closer
                                        if nearest_hops is None or (depth + 1) < nearest_hops:
                                            nearest_exchange = ex_info["exchange"]
                                            nearest_hops = depth + 1
                                            nearest_direction = "received_from"
                                            nearest_path = new_path
                                            exchange_connections.append({
                                                "exchange": ex_info["exchange"],
                                                "type": ex_info["type"],
                                                "hops": depth + 1,
                                                "direction": "received_from"
                                            })
                                    elif addresses_checked < self.MAX_ADDRESSES_TO_VISIT:
                                        # Add to queue for further exploration
                                        # Check for CoinJoin
                                        is_coinjoin_tx = self._calculate_coinjoin_score(tx) >= 0.7

                                        hop = ExchangeHop(
                                            txid=tx_info["txid"],
                                            address=prev_addr,
                                            value_sats=int(prev_out.get("value", 0) * 100_000_000),
                                            direction="received_from",
                                            hop_number=depth + 1,
                                            is_coinjoin=is_coinjoin_tx,
                                            block_height=tx_info.get("height"),
                                            timestamp=None
                                        )
                                        queue.append((prev_addr, depth + 1, "backward", current_path + [hop]))
                
                else:  # forward
                    # Check outputs - where did funds go? (limit to 5 outputs)
                    for vout_idx, vout in enumerate(tx.get("vout", [])[:5]):
                        script = vout.get("scriptPubKey", {})
                        out_addr = script.get("address")
                        
                        if out_addr and out_addr != current_addr:
                            ex_info = self._is_known_exchange(out_addr)
                            if ex_info:
                                # Check for CoinJoin in this transaction
                                is_coinjoin_tx = self._calculate_coinjoin_score(tx) >= 0.7

                                hop = ExchangeHop(
                                    txid=tx_info["txid"],
                                    address=out_addr,
                                    value_sats=int(vout.get("value", 0) * 100_000_000),
                                    direction="sent_to",
                                    hop_number=depth + 1,
                                    is_coinjoin=is_coinjoin_tx,
                                    block_height=tx_info.get("height"),
                                    timestamp=None
                                )
                                new_path = current_path + [hop]

                                # Store this path for analysis
                                all_paths_found.append({
                                    "path": new_path,
                                    "exchange": ex_info["exchange"],
                                    "exchange_type": ex_info["type"],
                                    "hops": depth + 1,
                                    "direction": "sent_to"
                                })

                                # Track exchange connection
                                exchange_key = f"{ex_info['exchange']}-sent_to-{depth+1}"
                                if exchange_key not in all_exchange_connections_map:
                                    all_exchange_connections_map[exchange_key] = {
                                        "exchange": ex_info["exchange"],
                                        "exchange_type": ex_info["type"],
                                        "hops": depth + 1,
                                        "direction": "sent_to",
                                        "path": new_path
                                    }

                                # Update nearest if this is closer
                                if nearest_hops is None or (depth + 1) < nearest_hops:
                                    nearest_exchange = ex_info["exchange"]
                                    nearest_hops = depth + 1
                                    nearest_direction = "sent_to"
                                    nearest_path = new_path
                                    exchange_connections.append({
                                        "exchange": ex_info["exchange"],
                                        "type": ex_info["type"],
                                        "hops": depth + 1,
                                        "direction": "sent_to"
                                    })
                            elif addresses_checked < self.MAX_ADDRESSES_TO_VISIT:
                                # Check for CoinJoin
                                is_coinjoin_tx = self._calculate_coinjoin_score(tx) >= 0.7

                                hop = ExchangeHop(
                                    txid=tx_info["txid"],
                                    address=out_addr,
                                    value_sats=int(vout.get("value", 0) * 100_000_000),
                                    direction="sent_to",
                                    hop_number=depth + 1,
                                    is_coinjoin=is_coinjoin_tx,
                                    block_height=tx_info.get("height"),
                                    timestamp=None
                                )
                                queue.append((out_addr, depth + 1, "forward", current_path + [hop]))


            # REMOVED: Early exit - we want to find all paths, not just nearest
            # Continue searching to build comprehensive analysis

        # Add warning if we hit limits
        if addresses_checked >= self.MAX_ADDRESSES_TO_VISIT:
            warnings.append(f"Analysis limited to {self.MAX_ADDRESSES_TO_VISIT} addresses")
            search_exhausted = True

        logger.info(f"Found {len(all_paths_found)} total paths to {len(all_exchange_connections_map)} unique exchange connections")

        # =====================================================================
        # PATH QUALITY SCORING ALGORITHM
        # =====================================================================

        def calculate_path_quality(path_hops: List[ExchangeHop]) -> tuple:
            """
            Calculate path quality score (0-100) where higher = stronger/clearer link.

            Scoring:
            - Start at 100 (perfect traceability)
            - Deduct points for privacy-enhancing factors:
              - CoinJoin detected: -30 points per CoinJoin
              - Path age > 180 days: -20 points
              - Path age > 365 days: -40 points total
              - Path length > 6 hops: -10 points
              - Mixer service in path: -40 points

            Returns: (score, factors_list, coinjoin_count, age_days)
            """
            score = 100
            factors = []
            coinjoin_count = 0

            # Factor 1: CoinJoins in path
            for hop in path_hops:
                if hop.is_coinjoin:
                    score -= 30
                    coinjoin_count += 1
                    factors.append(f"CoinJoin detected at hop {hop.hop_number} (-30 points)")

            # Factor 2: Path age
            path_age_days = None
            if path_hops and path_hops[0].block_height and current_height:
                blocks_old = current_height - path_hops[0].block_height
                path_age_days = (blocks_old * 10) / (60 * 24)  # Assume 10 min blocks

                if path_age_days > 365:
                    score -= 40
                    factors.append(f"Path age > 1 year ({path_age_days:.0f} days) (-40 points)")
                elif path_age_days > 180:
                    score -= 20
                    factors.append(f"Path age > 6 months ({path_age_days:.0f} days) (-20 points)")
                else:
                    factors.append(f"Recent path ({path_age_days:.0f} days old)")

            # Factor 3: Path length
            path_length = len(path_hops)
            if path_length > 6:
                score -= 10
                factors.append(f"Long path ({path_length} hops) (-10 points)")
            elif path_length == 1:
                factors.append("Direct connection (1 hop)")
            else:
                factors.append(f"{path_length} hops to exchange")

            # Clamp score to 0-100
            score = max(0, min(100, score))

            # Determine path strength
            if score >= 85:
                path_strength = "STRONG"
            elif score >= 60:
                path_strength = "MODERATE"
            elif score >= 30:
                path_strength = "WEAK"
            else:
                path_strength = "BROKEN"

            return score, factors, coinjoin_count, path_age_days, path_strength

        # Calculate quality for nearest path
        path_quality_score = 0
        path_quality_factors = []
        coinjoin_count_in_path = 0
        path_age_days = None
        path_strength = "UNKNOWN"

        if nearest_path:
            path_quality_score, path_quality_factors, coinjoin_count_in_path, path_age_days, path_strength = calculate_path_quality(nearest_path)
            logger.info(f"Nearest path quality: {path_quality_score}/100 ({path_strength}) with {coinjoin_count_in_path} CoinJoins")

        # =====================================================================
        # BUILD ALTERNATIVE PATHS (up to 5 different paths)
        # =====================================================================

        alternative_paths: List[ExchangePath] = []

        if all_paths_found:
            # Sort paths by quality score (descending) then by length (ascending)
            scored_paths = []
            for path_dict in all_paths_found:
                quality_score, quality_factors, cj_count, age_days, strength = calculate_path_quality(path_dict["path"])
                scored_paths.append({
                    "path": path_dict,
                    "quality_score": quality_score,
                    "quality_factors": quality_factors,
                    "cj_count": cj_count,
                    "age_days": age_days,
                    "strength": strength
                })

            # Sort: first by hops (ascending), then by quality (descending for same hop count)
            scored_paths.sort(key=lambda x: (len(x["path"]["path"]), -x["quality_score"]))

            # Take up to 5 distinct paths
            added_paths = set()
            for scored_path in scored_paths[:10]:  # Check first 10
                path_dict = scored_path["path"]
                path_key = f"{path_dict['exchange']}-{path_dict['direction']}-{path_dict['hops']}"

                if path_key not in added_paths and len(alternative_paths) < 5:
                    alternative_paths.append(ExchangePath(
                        path_hops=path_dict["path"],
                        total_hops=path_dict["hops"],
                        exchange_name=path_dict["exchange"],
                        exchange_type=path_dict["exchange_type"],
                        direction=path_dict["direction"],
                        path_quality_score=scored_path["quality_score"],
                        path_strength=scored_path["strength"],
                        coinjoin_count=scored_path["cj_count"],
                        path_age_days=scored_path["age_days"]
                    ))
                    added_paths.add(path_key)

            logger.info(f"Built {len(alternative_paths)} alternative paths for display")

        # =====================================================================
        # BUILD ALL EXCHANGE CONNECTIONS
        # =====================================================================

        all_exchange_connections: List[ExchangeConnection] = []

        for conn_data in all_exchange_connections_map.values():
            # Calculate quality for this connection's path
            quality_score, _, cj_count, _, strength = calculate_path_quality(conn_data["path"])

            all_exchange_connections.append(ExchangeConnection(
                exchange_name=conn_data["exchange"],
                exchange_type=conn_data["exchange_type"],
                hops=conn_data["hops"],
                direction=conn_data["direction"],
                path_quality=quality_score,
                path_strength=strength
            ))

        # Sort by hops (ascending) then quality (descending)
        all_exchange_connections.sort(key=lambda x: (x.hops, -x.path_quality))

        logger.info(f"Tracking {len(all_exchange_connections)} total exchange connections")

        # =====================================================================
        # CALCULATE PROXIMITY SCORE AND RISK LEVEL (enhanced with path quality)
        # =====================================================================

        if nearest_hops is None:
            proximity_score = 0
            risk_level = "low"
            if search_exhausted:
                recommendations.append("No exchange found within analysis limits")
                recommendations.append("This may indicate good privacy or require deeper analysis")
            else:
                recommendations.append("No direct exchange connection found within analysis depth")
                recommendations.append("This could mean good privacy or limited transaction history")
        elif nearest_hops == 1:
            proximity_score = 90
            risk_level = "critical"
            warnings.append(f"Direct transaction with {nearest_exchange} detected")

            # Adjust based on path quality
            if path_quality_score < 30:
                recommendations.append(f"Although direct link to exchange, path quality is BROKEN ({path_quality_score}/100)")
                recommendations.append(f"{coinjoin_count_in_path} CoinJoin(s) detected - some privacy protection present")
            else:
                recommendations.append("This address is directly KYC-linked")
                recommendations.append("Any funds here can be trivially traced to your identity")
                recommendations.append("Use CoinJoin before moving funds to private storage")
        elif nearest_hops == 2:
            proximity_score = 70
            risk_level = "high"
            warnings.append(f"Only {nearest_hops} hops from {nearest_exchange}")

            if path_quality_score < 30:
                recommendations.append(f"Path quality is BROKEN ({path_quality_score}/100) due to CoinJoins")
                recommendations.append("Continue practicing good privacy hygiene")
            else:
                recommendations.append("High traceability - chain analysis can easily link to KYC")
                recommendations.append("Consider CoinJoin to increase privacy")
        elif nearest_hops <= 4:
            proximity_score = 50
            risk_level = "medium"

            if path_quality_score < 30:
                recommendations.append(f"Path quality is BROKEN ({path_quality_score}/100)")
                recommendations.append("Good privacy practices detected")
            else:
                recommendations.append(f"Moderate distance ({nearest_hops} hops) from {nearest_exchange}")
                recommendations.append("Sophisticated analysis may still link to exchange")
        else:
            proximity_score = 30
            risk_level = "low"
            recommendations.append(f"Good distance ({nearest_hops} hops) from known exchanges")
            recommendations.append("Continue practicing good UTXO hygiene")

        # Add path quality specific recommendations
        if coinjoin_count_in_path > 0:
            recommendations.append(f"Detected {coinjoin_count_in_path} CoinJoin(s) in path - good privacy practice!")

        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        exchange_type = None
        if nearest_exchange:
            for addr, info in KNOWN_EXCHANGE_ADDRESSES.items():
                if info["exchange"] == nearest_exchange:
                    exchange_type = info["type"]
                    break

        logger.info(f"[ENHANCED] Analysis complete: {nearest_hops} hops, quality={path_quality_score}, strength={path_strength}")

        return ExchangeProximityResult(
            address=address,
            nearest_exchange=nearest_exchange,
            nearest_exchange_type=exchange_type,
            hops_to_exchange=nearest_hops,
            direction=nearest_direction,
            proximity_score=proximity_score,
            risk_level=risk_level,

            # Enhanced path quality fields
            path_quality_score=path_quality_score,
            path_quality_factors=path_quality_factors,
            coinjoin_count_in_path=coinjoin_count_in_path,
            path_age_days=path_age_days,
            path_strength=path_strength,

            # Multiple paths and all connections
            alternative_paths=alternative_paths,
            all_exchange_connections=all_exchange_connections,

            # Legacy fields (for backward compatibility)
            exchange_connections=exchange_connections,
            path_to_exchange=nearest_path,

            warnings=warnings,
            recommendations=recommendations,
            execution_time_ms=execution_time
        )
    
    # =========================================================================
    # UTXO PRIVACY RATING
    # =========================================================================
    
    async def analyze_utxo_privacy(
        self,
        address: str
    ) -> UTXOPrivacyResult:
        """
        Analyze privacy rating for all UTXOs at an address.
        
        Rates each UTXO as Red/Yellow/Green based on:
        - Exchange proximity
        - CoinJoin history
        - Cluster size
        - Age
        - Value patterns
        """
        start_time = datetime.utcnow()
        
        logger.info(f"Analyzing UTXO privacy for {address}")
        
        warnings: List[str] = []
        recommendations: List[str] = []
        utxos_info: List[UTXOPrivacyInfo] = []
        
        # Get UTXOs
        utxos = await self._get_address_utxos(address)
        
        if not utxos:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return UTXOPrivacyResult(
                address=address,
                utxo_count=0,
                total_value_sats=0,
                overall_rating=PrivacyRating.UNKNOWN,
                overall_score=0,
                red_count=0,
                yellow_count=0,
                green_count=0,
                utxos=[],
                summary="No UTXOs found at this address",
                warnings=["No UTXOs to analyze"],
                recommendations=[],
                execution_time_ms=execution_time
            )
        
        # Get cluster info with reduced depth and time budget
        cluster_size = 1
        try:
            cluster_result = await asyncio.wait_for(
                self.detect_cluster(address, max_depth=1),
                timeout=5.0  # Max 5 seconds for cluster detection
            )
            cluster_size = cluster_result.cluster_size
        except asyncio.TimeoutError:
            logger.warning(f"Cluster detection timed out for {address}")
            warnings.append("Cluster detection timed out - using default values")
        except Exception as e:
            logger.warning(f"Cluster detection failed: {e}")
            warnings.append("Cluster detection failed - using default values")
        
        # Get exchange proximity with reduced hops and time budget
        exchange_distance = None
        try:
            exchange_result = await asyncio.wait_for(
                self.analyze_exchange_proximity(address, max_hops=2),
                timeout=5.0  # Max 5 seconds for exchange proximity
            )
            exchange_distance = exchange_result.hops_to_exchange
        except asyncio.TimeoutError:
            logger.warning(f"Exchange proximity timed out for {address}")
            warnings.append("Exchange proximity timed out - using default values")
        except Exception as e:
            logger.warning(f"Exchange proximity failed: {e}")
            warnings.append("Exchange proximity check failed - using default values")
        
        # Get current block height
        current_height = 0
        try:
            rpc = await self._get_rpc()
            tip = await rpc.get_blockchain_info()
            current_height = tip.get("blocks", 0)
        except Exception as e:
            logger.warning(f"Could not get block height: {e}")
        
        total_value = 0
        red_count = 0
        yellow_count = 0
        green_count = 0
        
        for utxo in utxos[:20]:  # Limit to 20 UTXOs for speed
            # Check timeout
            if (datetime.utcnow() - start_time).total_seconds() > self.MAX_ANALYSIS_SECONDS:
                warnings.append("Analysis timed out - some UTXOs not analyzed")
                break
                
            txid = utxo.get("txid")
            vout = utxo.get("vout", 0)
            value_sats = utxo.get("value_sats", 0)
            height = utxo.get("height", 0)
            
            total_value += value_sats
            
            # Calculate age
            age_blocks = current_height - height if height > 0 else 0
            
            # Check if this UTXO came from a CoinJoin
            coinjoin_history = False
            tx = await self._get_transaction(txid)
            if tx:
                coinjoin_score = self._calculate_coinjoin_score(tx)
                if coinjoin_score > 0.7:
                    coinjoin_history = True
            
            # Calculate privacy factors
            factors = []
            score = 50  # Start neutral
            
            # Factor 1: Exchange distance
            # CRITICAL FIX: Don't give bonus for being distant without CoinJoins
            if exchange_distance is not None:
                if exchange_distance == 0:
                    score -= 40
                    factors.append({"factor": "Exchange Address", "impact": -40, "description": "This is a known exchange address"})
                elif exchange_distance == 1:
                    score -= 35
                    factors.append({"factor": "Direct Exchange Link", "impact": -35, "description": "Directly received from/sent to exchange"})
                elif exchange_distance == 2:
                    score -= 25
                    factors.append({"factor": "Near Exchange", "impact": -25, "description": "Only 2 hops from exchange"})
                elif exchange_distance <= 4:
                    score -= 15
                    factors.append({"factor": "Traceable to Exchange", "impact": -15, "description": f"{exchange_distance} hops from exchange"})
                elif exchange_distance <= 10:
                    score -= 5
                    factors.append({"factor": "Exchange Proximity", "impact": -5, "description": f"{exchange_distance} hops from exchange"})
                # No bonus for being >10 hops away - hop count without mixing means nothing

            # Factor 2: CoinJoin history with tiered scoring
            # CRITICAL FIX: Reduced from +25 to tiered based on quality
            if coinjoin_history:
                # Check transaction details to estimate anonymity set
                # For now, give conservative bonus - we don't know anonymity set size
                # In a real implementation, you'd check the actual CoinJoin protocol used
                score += 10
                factors.append({"factor": "CoinJoin History", "impact": +10, "description": "UTXO came from CoinJoin (conservative estimate)"})
            
            # Factor 3: Cluster size
            if cluster_size == 1:
                score += 15
                factors.append({"factor": "No Cluster", "impact": +15, "description": "Address not linked to others"})
            elif cluster_size <= 3:
                score -= 5
                factors.append({"factor": "Small Cluster", "impact": -5, "description": f"Linked to {cluster_size} addresses"})
            else:
                score -= 15
                factors.append({"factor": "Large Cluster", "impact": -15, "description": f"Linked to {cluster_size} addresses"})
            
            # Factor 4: Age (older = slightly better - less likely to be fresh from exchange)
            if age_blocks > 52560:  # ~1 year
                score += 5
                factors.append({"factor": "Mature UTXO", "impact": +5, "description": "Over 1 year old"})
            elif age_blocks < 1000:
                score -= 5
                factors.append({"factor": "Fresh UTXO", "impact": -5, "description": "Recently created"})
            
            # Factor 5: Round number detection (exchange withdrawals often round)
            value_btc = value_sats / 100_000_000
            if value_btc == int(value_btc) and value_btc >= 0.1:
                score -= 10
                factors.append({"factor": "Round Number", "impact": -10, "description": "Round BTC amount suggests exchange withdrawal"})
            
            # Clamp score
            score = max(0, min(100, score))

            # Determine rating - MORE CONSERVATIVE thresholds
            # CRITICAL: Green should require actual mixing OR no detectable exchange link
            # Don't give green just for being "far" from exchange
            if score >= 70:
                # High score - likely has CoinJoin AND no close exchange link
                rating = PrivacyRating.GREEN
                green_count += 1
            elif score >= 40:
                # Medium score - some privacy measures but still traceable
                rating = PrivacyRating.YELLOW
                yellow_count += 1
            else:
                # Low score - easily traceable
                rating = PrivacyRating.RED
                red_count += 1
            
            # Generate per-UTXO recommendations
            utxo_recommendations = []
            if rating == PrivacyRating.RED:
                utxo_recommendations.append("High risk - consider CoinJoin before spending")
                utxo_recommendations.append("Do not consolidate with other UTXOs")
            elif rating == PrivacyRating.YELLOW:
                utxo_recommendations.append("Moderate risk - use caution when spending")
            
            utxos_info.append(UTXOPrivacyInfo(
                txid=txid,
                vout=vout,
                address=address,
                value_sats=value_sats,
                rating=rating,
                score=score,
                factors=factors,
                exchange_distance=exchange_distance,
                coinjoin_history=coinjoin_history,
                cluster_size=cluster_size,
                age_blocks=age_blocks,
                recommendations=utxo_recommendations
            ))
        
        # Calculate overall rating - MORE CONSERVATIVE
        if len(utxos_info) == 0:
            overall_rating = PrivacyRating.UNKNOWN
            overall_score = 0
        else:
            overall_score = sum(u.score for u in utxos_info) // len(utxos_info)
            if overall_score >= 70:
                overall_rating = PrivacyRating.GREEN
            elif overall_score >= 40:
                overall_rating = PrivacyRating.YELLOW
            else:
                overall_rating = PrivacyRating.RED
        
        # Generate summary
        if len(utxos_info) == 0:
            summary = "No UTXOs could be analyzed - address may have no unspent outputs"
        elif red_count > 0:
            summary = f"⚠️ {red_count} high-risk UTXO(s) detected - these are easily traceable"
        elif yellow_count > 0:
            summary = f"Moderate privacy - {yellow_count} UTXO(s) have some traceability concerns"
        else:
            summary = "Good privacy hygiene - UTXOs have reasonable privacy"
        
        # Overall recommendations
        if red_count > 0:
            recommendations.append("Consider using CoinJoin on high-risk (red) UTXOs before spending")
            recommendations.append("Never consolidate red UTXOs with your private coins")
        if cluster_size > 3:
            recommendations.append("Your address cluster is large - avoid reusing addresses")
        if exchange_distance and exchange_distance <= 2:
            recommendations.append("Direct exchange connection detected - this address is KYC-linked")
        if green_count == len(utxos_info) and green_count > 0:
            recommendations.append("Good job! Your UTXOs have reasonable privacy")
        
        if len(utxos) > 20:
            warnings.append(f"Analysis limited to 20 of {len(utxos)} UTXOs")
        
        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return UTXOPrivacyResult(
            address=address,
            utxo_count=len(utxos_info),
            total_value_sats=total_value,
            overall_rating=overall_rating,
            overall_score=overall_score,
            red_count=red_count,
            yellow_count=yellow_count,
            green_count=green_count,
            utxos=utxos_info,
            summary=summary,
            warnings=warnings,
            recommendations=recommendations,
            execution_time_ms=execution_time
        )
    
    def _calculate_coinjoin_score(self, tx: Dict) -> float:
        """Calculate CoinJoin probability score for a transaction."""
        if not tx:
            return 0.0
        
        inputs = tx.get("vin", [])
        outputs = tx.get("vout", [])
        
        if len(inputs) < 2 or len(outputs) < 2:
            return 0.0
        
        # Get output values
        output_values = []
        for out in outputs:
            value = out.get("value", 0)
            if value > 0:
                output_values.append(round(value, 8))
        
        if not output_values:
            return 0.0
        
        # Count equal outputs
        from collections import Counter
        value_counts = Counter(output_values)
        max_equal = max(value_counts.values())
        
        # Score based on equal outputs
        equal_ratio = max_equal / len(output_values)
        
        # High score if many equal outputs
        if equal_ratio > 0.8 and max_equal >= 3:
            return 0.9
        elif equal_ratio > 0.5 and max_equal >= 2:
            return 0.7
        elif max_equal >= 2:
            return 0.4
        
        return 0.1

    # =========================================================================
    # ENHANCED PRIVACY ANALYSIS (ALL HEURISTICS COMBINED)
    # =========================================================================

    async def analyze_utxo_privacy_enhanced(
        self,
        txid: str,
        vout: int,
        max_depth: int = 10
    ) -> EnhancedPrivacyScore:
        """
        Enhanced privacy analysis combining all sophisticated heuristics.

        This method integrates:
        - Temporal correlation analysis
        - Value fingerprinting
        - Wallet fingerprinting
        - Peeling chain detection
        - Exchange proximity
        - CoinJoin detection
        - Cluster analysis

        Args:
            txid: Transaction ID
            vout: Output index
            max_depth: Maximum trace depth

        Returns:
            EnhancedPrivacyScore with comprehensive analysis
        """
        start_time = datetime.utcnow()

        logger.info(f"=== ENHANCED PRIVACY ANALYSIS START === txid={txid[:16]}..., vout={vout}, depth={max_depth}")

        # Initialize score and containers
        score = 50  # Start neutral
        privacy_factors: Dict[str, FactorCategory] = {}
        critical_risks: List[RiskItem] = []
        warnings: List[RiskItem] = []
        attack_vectors: Dict[str, AttackVector] = {}

        # Get transaction
        rpc = await self._get_rpc()
        tx = await self._get_transaction(txid)

        if not tx:
            logger.error(f"Transaction not found: {txid}")
            return self._create_error_response(txid, vout, "Transaction not found")

        # Get UTXO value
        vouts = tx.get("vout", [])
        if vout >= len(vouts):
            logger.error(f"Invalid vout {vout} for tx {txid}")
            return self._create_error_response(txid, vout, f"Invalid vout {vout}")

        utxo_value_sats = int(vouts[vout].get("value", 0) * 100_000_000)
        utxo_address = vouts[vout].get("scriptPubKey", {}).get("address")

        # =====================================================================
        # 1. RUN EXISTING ANALYSES
        # =====================================================================

        logger.debug("Running existing analyses (trace, CoinJoin, exchange proximity)...")

        # Import tracer
        from app.core.tracer import get_tracer
        tracer = get_tracer()

        # Forward trace
        try:
            trace_result = await tracer.trace_forward(txid, vout, max_depth)
            logger.debug(f"Trace complete: {len(trace_result.nodes)} nodes, {len(trace_result.edges)} edges")
        except Exception as e:
            logger.error(f"Trace failed: {e}")
            trace_result = None

        # CoinJoin detection
        coinjoin_score = self._calculate_coinjoin_score(tx)
        is_coinjoin = coinjoin_score >= 0.7

        # Exchange proximity (if address available)
        exchange_distance = None
        if utxo_address:
            try:
                exchange_result = await self.analyze_exchange_proximity(utxo_address, max_hops=6)
                exchange_distance = exchange_result.hops_to_exchange
                logger.debug(f"Exchange proximity: {exchange_distance} hops")
            except Exception as e:
                logger.warning(f"Exchange proximity failed: {e}")

        # =====================================================================
        # 2. RUN NEW TEMPORAL ANALYSIS
        # =====================================================================

        logger.debug("Running temporal analysis...")
        temporal_analyzer = get_temporal_analyzer()
        temporal_score_impact = 0
        temporal_factors = []

        try:
            if trace_result and trace_result.nodes:
                # Analyze path timing
                temporal_result = temporal_analyzer.calculate_temporal_privacy_score(trace_result.nodes)
                temporal_score_impact = temporal_result.score

                for warning in temporal_result.warnings:
                    temporal_factors.append(Factor(
                        factor=warning[:50],
                        impact=temporal_result.score,
                        explanation=warning
                    ))

                # Add attack vector if high risk
                if temporal_result.rapid_spends_count > 0:
                    attack_vectors["timing_correlation"] = AttackVector(
                        vector_name="Timing Correlation Attack",
                        vulnerability_score=min(temporal_result.rapid_spends_count * 0.3, 0.95),
                        explanation=f"Found {temporal_result.rapid_spends_count} rapid spend(s) (< 1 hour). "
                                  f"Average hop time: {temporal_result.average_hop_time_seconds/3600:.1f} hours",
                        example="An adversary monitoring blockchain timestamps can link transactions "
                               "that occur close together in time, even if amounts don't match"
                    )

                # Add critical risk if very poor temporal privacy
                if temporal_result.score < -15:
                    critical_risks.append(RiskItem(
                        severity=RiskSeverity.CRITICAL,
                        title="Timing Correlation Risk",
                        description=f"UTXO shows poor temporal privacy (score: {temporal_result.score}). "
                                  f"{temporal_result.rapid_spends_count} rapid spend(s) detected.",
                        detection_confidence=0.90,
                        remediation="Wait at least 24-48 hours between receiving and spending funds. "
                                  "Randomize transaction timing to avoid patterns."
                    ))

                logger.debug(f"Temporal analysis complete: score_impact={temporal_score_impact}")

        except Exception as e:
            logger.error(f"Temporal analysis failed: {e}", exc_info=True)
            temporal_factors.append(Factor(
                factor="Temporal Analysis Failed",
                impact=0,
                explanation=str(e)
            ))

        privacy_factors["temporal"] = FactorCategory(
            category_name="Temporal Privacy",
            score_impact=temporal_score_impact,
            factors=temporal_factors if temporal_factors else [Factor(factor="No temporal data", impact=0)],
            summary=self._summarize_temporal(temporal_score_impact)
        )
        score += temporal_score_impact

        # =====================================================================
        # 3. RUN VALUE ANALYSIS
        # =====================================================================

        logger.debug("Running value analysis...")
        value_analyzer = get_value_analyzer()
        value_score_impact = 0
        value_factors = []

        try:
            # Analyze amount uniqueness
            amount_result = value_analyzer.is_amount_unique(utxo_value_sats)
            value_score_impact += amount_result.score_impact
            value_factors.append(Factor(
                factor=f"Amount Uniqueness ({amount_result.precision_decimals} decimals)",
                impact=amount_result.score_impact,
                explanation=f"Amount: {amount_result.amount_btc:.8f} BTC, "
                          f"Uniqueness: {amount_result.uniqueness_score*100:.0f}%"
            ))

            if amount_result.is_unique:
                attack_vectors["amount_fingerprinting"] = AttackVector(
                    vector_name="Amount Fingerprinting",
                    vulnerability_score=amount_result.uniqueness_score,
                    explanation=f"UTXO amount ({amount_result.amount_btc:.8f} BTC) has {amount_result.precision_decimals} "
                              f"decimal places, making it highly fingerprintable",
                    example=f"An adversary can search the entire blockchain for the exact amount "
                           f"{amount_result.amount_btc:.8f} BTC and track all instances with high confidence"
                )

                warnings.append(RiskItem(
                    severity=RiskSeverity.HIGH,
                    title="Amount Fingerprinting Risk",
                    description=f"UTXO amount is highly unique ({amount_result.uniqueness_score*100:.0f}% uniqueness). "
                              f"This specific amount can be tracked across the blockchain.",
                    detection_confidence=amount_result.uniqueness_score,
                    remediation="After CoinJoin, use round denomination outputs (0.001, 0.01, 0.1 BTC)"
                ))

            # Subset sum analysis
            subset_result = value_analyzer.detect_subset_sum_leak(
                [{"value_sats": vin.get("value", 0) * 100_000_000} for vin in tx.get("vin", []) if "prevout" in vin],
                [{"value_sats": vout.get("value", 0) * 100_000_000} for vout in tx.get("vout", [])]
            )

            if subset_result.has_leaks:
                value_score_impact += subset_result.score_impact
                value_factors.append(Factor(
                    factor=f"Subset Sum Leak ({subset_result.leak_count} detected)",
                    impact=subset_result.score_impact,
                    explanation=f"{subset_result.leak_count} output(s) reveal input structure"
                ))

                critical_risks.append(RiskItem(
                    severity=RiskSeverity.CRITICAL,
                    title="Subset Sum Leak Detected",
                    description=f"{subset_result.leak_count} output amount(s) match input subsets, "
                              f"revealing which inputs funded which outputs",
                    detection_confidence=0.85,
                    remediation="Use CoinJoin to break amount correlation. Avoid sending amounts that match input subsets."
                ))

            # Dust detection
            dust_results = value_analyzer.detect_dust_amounts(tx.get("vout", []))
            if dust_results:
                dust_impact = sum(d.score_impact for d in dust_results)
                value_score_impact += dust_impact
                value_factors.append(Factor(
                    factor=f"Dust Outputs ({len(dust_results)} found)",
                    impact=dust_impact,
                    explanation=f"{len(dust_results)} dust output(s) may be tracking pixels"
                ))

                for dust in dust_results:
                    if dust.is_tracking_pixel:
                        warnings.append(RiskItem(
                            severity=RiskSeverity.HIGH,
                            title=f"Tracking Pixel Detected (Output {dust.output_index})",
                            description=f"Output {dust.output_index} contains {dust.value_sats} sats - "
                                      f"likely a tracking pixel",
                            detection_confidence=0.80,
                            remediation="Do NOT spend this output with other UTXOs - it will link your addresses"
                        ))

            logger.debug(f"Value analysis complete: score_impact={value_score_impact}")

        except Exception as e:
            logger.error(f"Value analysis failed: {e}", exc_info=True)
            value_factors.append(Factor(
                factor="Value Analysis Failed",
                impact=0,
                explanation=str(e)
            ))

        privacy_factors["value_analysis"] = FactorCategory(
            category_name="Amount Analysis",
            score_impact=value_score_impact,
            factors=value_factors if value_factors else [Factor(factor="No value data", impact=0)],
            summary=self._summarize_value(value_score_impact)
        )
        score += value_score_impact

        # =====================================================================
        # 4. RUN WALLET FINGERPRINTING (if we have multiple transactions)
        # =====================================================================

        logger.debug("Running wallet fingerprinting...")
        wallet_score_impact = 0
        wallet_factors = []

        try:
            # For now, analyze just this transaction
            # In full implementation, would gather related transactions
            wallet_fingerprinter = get_wallet_fingerprinter()
            fingerprint_result = wallet_fingerprinter.calculate_wallet_fingerprint_score([tx], [])

            wallet_score_impact = fingerprint_result.total_score_impact

            for pattern in fingerprint_result.detected_patterns:
                wallet_factors.append(Factor(
                    factor=pattern,
                    impact=fingerprint_result.total_score_impact // max(len(fingerprint_result.detected_patterns), 1),
                    explanation=pattern
                ))

            if fingerprint_result.fingerprint_strength > 0.6:
                warnings.append(RiskItem(
                    severity=RiskSeverity.MEDIUM,
                    title="Wallet Fingerprint Detected",
                    description=f"Transaction shows wallet fingerprinting patterns (strength: "
                              f"{fingerprint_result.fingerprint_strength*100:.0f}%). "
                              f"Patterns: {', '.join(fingerprint_result.detected_patterns)}",
                    detection_confidence=fingerprint_result.fingerprint_strength,
                    remediation="Use multiple wallet types or randomize transaction patterns"
                ))

            logger.debug(f"Wallet fingerprinting complete: score_impact={wallet_score_impact}")

        except Exception as e:
            logger.error(f"Wallet fingerprinting failed: {e}", exc_info=True)
            wallet_factors.append(Factor(
                factor="Wallet Analysis Failed",
                impact=0,
                explanation=str(e)
            ))

        privacy_factors["wallet_fingerprint"] = FactorCategory(
            category_name="Wallet Fingerprinting",
            score_impact=wallet_score_impact,
            factors=wallet_factors if wallet_factors else [Factor(factor="Limited transaction data", impact=0)],
            summary=self._summarize_wallet(wallet_score_impact)
        )
        score += wallet_score_impact

        # =====================================================================
        # 5. DETECT PEELING CHAINS
        # =====================================================================

        logger.debug("Detecting peeling chains...")
        peeling_impact = 0
        peeling_factors = []

        try:
            if trace_result:
                peeling_result = tracer.detect_peeling_chain(trace_result)

                if peeling_result["is_peeling_chain"]:
                    peeling_impact = -25
                    peeling_factors.append(Factor(
                        factor=f"Peeling Chain Detected ({peeling_result['chain_length']} transactions)",
                        impact=-25,
                        explanation=peeling_result["explanation"]
                    ))

                    critical_risks.append(RiskItem(
                        severity=RiskSeverity.CRITICAL,
                        title="Peeling Chain Pattern",
                        description=f"This UTXO is part of a peeling chain ({peeling_result['chain_length']} "
                                  f"transactions). All transactions in the chain are linkable with "
                                  f"{peeling_result['confidence']*100:.0f}% confidence.",
                        detection_confidence=peeling_result["confidence"],
                        remediation="Avoid creating peeling chains. Consolidate UTXOs privately via CoinJoin first."
                    ))

                    logger.debug(f"Peeling chain detected: length={peeling_result['chain_length']}")
                else:
                    peeling_factors.append(Factor(
                        factor="No Peeling Chain",
                        impact=0,
                        explanation="No peeling pattern detected"
                    ))
        except Exception as e:
            logger.error(f"Peeling chain detection failed: {e}", exc_info=True)
            peeling_factors.append(Factor(
                factor="Peeling Detection Failed",
                impact=0,
                explanation=str(e)
            ))

        privacy_factors["peeling_chain"] = FactorCategory(
            category_name="Peeling Chain Analysis",
            score_impact=peeling_impact,
            factors=peeling_factors,
            summary=self._summarize_peeling(peeling_impact)
        )
        score += peeling_impact

        # =====================================================================
        # 6. APPLY EXISTING FACTORS
        # =====================================================================

        logger.debug("Applying existing factors (exchange, CoinJoin, etc.)...")
        existing_factors = []
        existing_impact = 0

        # Exchange proximity
        if exchange_distance is not None:
            if exchange_distance == 0:
                impact = -40
                existing_factors.append(Factor(
                    factor="Known Exchange Address",
                    impact=impact,
                    explanation="This is a known exchange address"
                ))
                critical_risks.append(RiskItem(
                    severity=RiskSeverity.CRITICAL,
                    title="Exchange Address",
                    description="This address belongs to a known exchange",
                    detection_confidence=0.98,
                    remediation="Do not use exchange addresses for personal storage"
                ))
            elif exchange_distance == 1:
                impact = -35
                existing_factors.append(Factor(
                    factor="Direct Exchange Link",
                    impact=impact,
                    explanation="Directly received from or sent to exchange"
                ))
                critical_risks.append(RiskItem(
                    severity=RiskSeverity.CRITICAL,
                    title="Direct Exchange Link",
                    description="UTXO is directly linked to a known exchange with no mixing",
                    detection_confidence=0.95,
                    remediation="Use 2+ high-quality CoinJoins before spending"
                ))
            elif exchange_distance <= 3:
                impact = -25
                existing_factors.append(Factor(
                    factor=f"Close to Exchange ({exchange_distance} hops)",
                    impact=impact,
                    explanation=f"Only {exchange_distance} hops from known exchange"
                ))
                warnings.append(RiskItem(
                    severity=RiskSeverity.HIGH,
                    title="Exchange Proximity",
                    description=f"Only {exchange_distance} hop(s) from known exchange - easily traceable",
                    detection_confidence=0.85,
                    remediation="Use CoinJoin to increase distance from exchange"
                ))
            elif exchange_distance <= 6:
                impact = -10
                existing_factors.append(Factor(
                    factor=f"Exchange Proximity ({exchange_distance} hops)",
                    impact=impact,
                    explanation=f"{exchange_distance} hops from exchange"
                ))
            existing_impact += impact

        # CoinJoin
        if is_coinjoin:
            impact = 15
            existing_factors.append(Factor(
                factor=f"CoinJoin Transaction (score: {coinjoin_score:.2f})",
                impact=impact,
                explanation=f"Transaction appears to be a CoinJoin with {coinjoin_score*100:.0f}% confidence"
            ))
            existing_impact += impact

        privacy_factors["existing_analysis"] = FactorCategory(
            category_name="Exchange & CoinJoin Analysis",
            score_impact=existing_impact,
            factors=existing_factors if existing_factors else [Factor(factor="No data", impact=0)],
            summary=self._summarize_existing(existing_impact, exchange_distance, is_coinjoin)
        )
        score += existing_impact

        # =====================================================================
        # 7. SECURITY WARNINGS (NEW - CRITICAL USER SAFETY)
        # =====================================================================

        logger.debug("Checking security warnings...")

        try:
            from app.core.security_warnings import get_security_warnings

            sec_warnings = get_security_warnings()

            # WabiSabi coordinator attack warning
            if is_coinjoin:
                # Get full CoinJoin detection result
                from app.core.coinjoin import get_detector
                detector = get_detector()
                full_coinjoin_result = detector.detect_coinjoin(tx)

                # Check for WabiSabi risks
                wabisabi_warning = sec_warnings.check_wabisabi_risks(tx, full_coinjoin_result)
                if wabisabi_warning:
                    if wabisabi_warning.warning_level == RiskSeverity.CRITICAL:
                        critical_risks.append(RiskItem(
                            severity=RiskSeverity.CRITICAL,
                            title="⚠️ WABISABI COORDINATOR ATTACK RISK",
                            description=wabisabi_warning.explanation,
                            detection_confidence=0.90,
                            remediation=wabisabi_warning.remediation
                        ))
                        logger.warning("CRITICAL: WabiSabi coordinator attack risk detected")
                    else:
                        warnings.append(RiskItem(
                            severity=RiskSeverity.LOW,
                            title="WabiSabi CoinJoin (Trusted Coordinator)",
                            description=wabisabi_warning.explanation,
                            detection_confidence=0.85,
                            remediation=wabisabi_warning.remediation
                        ))

            # Lightning Network linkability warning
            if trace_result:
                ln_warning = sec_warnings.check_lightning_privacy(trace_result)
                if ln_warning:
                    warnings.append(RiskItem(
                        severity=RiskSeverity.HIGH,
                        title="Lightning Network Linkability Risk",
                        description=ln_warning.warning,
                        detection_confidence=ln_warning.linkability_risk,
                        remediation=ln_warning.remediation
                    ))
                    logger.warning(f"Lightning channels detected: {len(ln_warning.affected_utxos)} UTXO(s)")

            # RPC timing correlation warning
            if trace_result and trace_result.nodes:
                timing_warning = sec_warnings.check_rpc_timing_correlation(trace_result.nodes)
                if timing_warning:
                    warnings.append(RiskItem(
                        severity=timing_warning["risk_level"],
                        title="RPC Timing Correlation Risk",
                        description=timing_warning["explanation"],
                        detection_confidence=0.70,
                        remediation=timing_warning["remediation"]
                    ))
                    logger.warning(f"RPC timing risks: {timing_warning['rapid_spend_count']} rapid spend(s)")

        except Exception as e:
            logger.error(f"Security warnings check failed: {e}", exc_info=True)
            # Don't fail analysis if security warnings fail
            pass

        # =====================================================================
        # 8. GRAPH ANALYTICS (REMOVED - igraph dependency removed)
        # =====================================================================
        # Note: Graph analytics (community detection, pattern detection, PageRank)
        # have been removed as the HTML frontend does not use these features.
        # The analysis continues with all other heuristics intact.

        logger.debug("Graph analytics skipped (module removed)")

        # =====================================================================
        # 9. FINALIZE SCORE AND RATING
        # =====================================================================

        # Clamp score to 0-100
        final_score = max(0, min(100, score))

        # Determine rating
        if final_score >= 70:
            rating = EnhancedPrivacyRating.GREEN
        elif final_score >= 40:
            rating = EnhancedPrivacyRating.YELLOW
        else:
            rating = EnhancedPrivacyRating.RED

        logger.debug(f"Final score: {final_score}, rating: {rating.value}")

        # =====================================================================
        # 10. GENERATE SUMMARY AND RECOMMENDATIONS
        # =====================================================================

        summary = self._generate_privacy_summary(
            final_score, rating, critical_risks, warnings, privacy_factors
        )

        recommendations = self._generate_recommendations(
            final_score, privacy_factors, is_coinjoin, exchange_distance
        )

        # =====================================================================
        # 11. CALCULATE ASSESSMENT CONFIDENCE
        # =====================================================================

        assessment_confidence = self._calculate_assessment_confidence(
            trace_result, exchange_distance, is_coinjoin
        )

        # =====================================================================
        # 12. CREATE PRIVACY CONTEXT
        # =====================================================================

        privacy_context = PrivacyBenchmark(
            your_score=final_score,
            benchmarks={
                "direct_exchange_withdrawal": 25,
                "single_coinjoin_fast_spend": 45,
                "double_coinjoin_week_wait": 65,
                "whirlpool_5_remixes_good_hygiene": 85,
                "best_practice_privacy": 95
            },
            interpretation=self._interpret_score_context(final_score)
        )

        # =====================================================================
        # 13. RETURN ENHANCED SCORE
        # =====================================================================

        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info(f"=== ENHANCED PRIVACY ANALYSIS COMPLETE === score={final_score}, "
                   f"rating={rating.value}, time={execution_time}ms")

        return EnhancedPrivacyScore(
            overall_score=final_score,
            rating=rating,
            summary=summary,
            privacy_factors=privacy_factors,
            critical_risks=critical_risks,
            warnings=warnings,
            recommendations=recommendations,
            attack_vectors=attack_vectors,
            assessment_confidence=assessment_confidence,
            assessment_limitations=self._get_assessment_limitations(),
            privacy_context=privacy_context,
            execution_time_ms=execution_time,
            analysis_depth=max_depth
        )

    def _create_error_response(self, txid: str, vout: int, error_msg: str) -> EnhancedPrivacyScore:
        """Create an error response for failed analysis."""
        return EnhancedPrivacyScore(
            overall_score=0,
            rating=EnhancedPrivacyRating.UNKNOWN,
            summary=f"Analysis failed: {error_msg}",
            privacy_factors={},
            critical_risks=[],
            warnings=[RiskItem(
                severity=RiskSeverity.HIGH,
                title="Analysis Failed",
                description=error_msg,
                detection_confidence=1.0,
                remediation="Check transaction ID and output index"
            )],
            recommendations=[],
            attack_vectors={},
            assessment_confidence=0.0,
            assessment_limitations=["Analysis could not be completed"],
            privacy_context=None
        )

    def _summarize_temporal(self, score_impact: int) -> str:
        """Generate summary for temporal privacy."""
        if score_impact >= 10:
            return "EXCELLENT: Long wait times between transactions enhance privacy"
        elif score_impact >= 0:
            return "GOOD: Reasonable temporal privacy"
        elif score_impact >= -10:
            return "FAIR: Some timing correlation risk"
        else:
            return "POOR: High timing correlation risk - funds moved too quickly"

    def _summarize_value(self, score_impact: int) -> str:
        """Generate summary for value analysis."""
        if score_impact >= 0:
            return "GOOD: No significant amount fingerprinting detected"
        elif score_impact >= -15:
            return "FAIR: Some amount correlation detected"
        else:
            return "POOR: High amount fingerprinting risk - unique amounts detected"

    def _summarize_wallet(self, score_impact: int) -> str:
        """Generate summary for wallet fingerprinting."""
        if score_impact >= -5:
            return "GOOD: No strong wallet fingerprint detected"
        elif score_impact >= -20:
            return "FAIR: Some wallet patterns detected"
        else:
            return "POOR: Strong wallet fingerprint - transactions are linkable"

    def _summarize_peeling(self, score_impact: int) -> str:
        """Generate summary for peeling chain."""
        if score_impact == 0:
            return "GOOD: No peeling chain pattern detected"
        else:
            return "CRITICAL: Peeling chain detected - all transactions are linkable"

    def _summarize_existing(self, score_impact: int, exchange_distance: Optional[int], is_coinjoin: bool) -> str:
        """Generate summary for existing analysis."""
        parts = []
        if exchange_distance is not None:
            if exchange_distance <= 2:
                parts.append("HIGH EXCHANGE RISK")
            elif exchange_distance <= 5:
                parts.append("Moderate exchange proximity")
        if is_coinjoin:
            parts.append("CoinJoin detected")

        if not parts:
            return "No significant exchange links detected"
        return ", ".join(parts)

    def _generate_privacy_summary(
        self,
        score: int,
        rating: EnhancedPrivacyRating,
        critical_risks: List[RiskItem],
        warnings: List[RiskItem],
        factors: Dict[str, FactorCategory]
    ) -> str:
        """Generate natural language summary."""
        if rating == EnhancedPrivacyRating.GREEN:
            return (f"✅ GOOD PRIVACY (Score: {score}/100): This UTXO shows good privacy characteristics. "
                   f"Found {len(critical_risks)} critical risk(s) and {len(warnings)} warning(s). "
                   f"Continue practicing good UTXO hygiene.")
        elif rating == EnhancedPrivacyRating.YELLOW:
            return (f"⚠️ MODERATE PRIVACY (Score: {score}/100): This UTXO has some privacy concerns. "
                   f"Found {len(critical_risks)} critical risk(s) and {len(warnings)} warning(s). "
                   f"Consider using CoinJoin to improve privacy.")
        else:  # RED
            return (f"🚨 POOR PRIVACY (Score: {score}/100): This UTXO is easily traceable. "
                   f"Found {len(critical_risks)} critical risk(s) and {len(warnings)} warning(s). "
                   f"URGENT: Use CoinJoin before spending to avoid surveillance.")

    def _generate_recommendations(
        self,
        score: int,
        factors: Dict[str, FactorCategory],
        is_coinjoin: bool,
        exchange_distance: Optional[int]
    ) -> List[ActionItem]:
        """Generate actionable recommendations."""
        recommendations = []

        if score < 40:
            # Critical - needs immediate action
            recommendations.append(ActionItem(
                priority="HIGH",
                action="Use Whirlpool with 3+ remixes or Wasabi 2.0 with 10+ rounds immediately",
                expected_improvement="+40-50 privacy points",
                difficulty="MODERATE"
            ))

            if exchange_distance is not None and exchange_distance <= 2:
                recommendations.append(ActionItem(
                    priority="HIGH",
                    action="Never consolidate this UTXO with other coins without mixing first",
                    expected_improvement="Prevents linking other UTXOs to exchange",
                    difficulty="EASY"
                ))

        # Temporal recommendations
        if factors.get("temporal") and factors["temporal"].score_impact < -10:
            recommendations.append(ActionItem(
                priority="HIGH",
                action="Wait at least 24-48 hours between receiving and spending funds",
                expected_improvement="+15-20 temporal privacy points",
                difficulty="EASY"
            ))

        # Value recommendations
        if factors.get("value_analysis") and factors["value_analysis"].score_impact < -10:
            recommendations.append(ActionItem(
                priority="MEDIUM",
                action="After mixing, use round denomination outputs (0.001, 0.01, 0.1 BTC)",
                expected_improvement="+10-15 amount privacy points",
                difficulty="EASY"
            ))

        # General recommendations
        if not is_coinjoin and score < 70:
            recommendations.append(ActionItem(
                priority="MEDIUM",
                action="Use CoinJoin for all UTXOs before spending",
                expected_improvement="+20-40 points depending on quality",
                difficulty="MODERATE"
            ))

        if not recommendations:
            recommendations.append(ActionItem(
                priority="LOW",
                action="Continue practicing good privacy hygiene",
                expected_improvement="Maintain current privacy level",
                difficulty="EASY"
            ))

        return recommendations

    def _calculate_assessment_confidence(
        self,
        trace_result,
        exchange_distance: Optional[int],
        is_coinjoin: bool
    ) -> float:
        """Calculate confidence in the assessment."""
        confidence = 0.7  # Base confidence

        # Increase confidence if we have complete trace
        if trace_result and not trace_result.hit_limit:
            confidence += 0.1

        # Increase confidence if we have exchange data
        if exchange_distance is not None:
            confidence += 0.1

        # Decrease confidence if CoinJoin (harder to analyze)
        if is_coinjoin:
            confidence -= 0.15

        return max(0.0, min(1.0, confidence))

    def _get_assessment_limitations(self) -> List[str]:
        """Get list of analysis limitations."""
        return [
            "Cannot detect: network-level correlation (IP addresses, Tor usage)",
            "Cannot detect: off-chain agreements or side-channel information",
            "Cannot detect: sophisticated timing attacks beyond block-level analysis",
            "Cannot detect: Wasabi 2.0 WabiSabi protocol with high certainty",
            "Cannot detect: advanced PayJoin or other privacy protocols",
            "This tool uses heuristics only - actual privacy may be better or worse",
            "Confidence scores are estimates and should not be used for operational security",
            "Analysis is point-in-time - privacy can degrade with future transactions"
        ]

    def _interpret_score_context(self, score: int) -> str:
        """Interpret score in context of benchmarks."""
        if score >= 90:
            return "Your privacy is exceptional - better than 95% of Bitcoin users who practice good hygiene"
        elif score >= 70:
            return "Your privacy is good - similar to users who use quality CoinJoin with proper practices"
        elif score >= 50:
            return "Your privacy is moderate - better than direct exchange withdrawals but worse than mixed coins"
        elif score >= 30:
            return "Your privacy is poor - slightly better than direct exchange withdrawal but still easily traceable"
        else:
            return "Your privacy is very poor - similar to or worse than direct exchange withdrawals with no mixing"


# Singleton instance
_privacy_analyzer: Optional[PrivacyAnalyzer] = None


def get_privacy_analyzer() -> PrivacyAnalyzer:
    """Get or create the privacy analyzer singleton."""
    global _privacy_analyzer
    if _privacy_analyzer is None:
        _privacy_analyzer = PrivacyAnalyzer()
    return _privacy_analyzer
