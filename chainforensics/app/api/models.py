"""
ChainForensics - Enhanced API Response Models

Pydantic models for sophisticated privacy analysis responses with:
- Detailed risk breakdowns
- Attack surface analysis
- Actionable recommendations
- Comparative context

Author: ChainForensics Team
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum


class RiskSeverity(str, Enum):
    """Risk severity levels for privacy threats."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PrivacyRating(str, Enum):
    """Overall privacy rating categories."""
    GREEN = "GREEN"       # Good privacy (70-100)
    YELLOW = "YELLOW"     # Moderate privacy (40-69)
    RED = "RED"           # Poor privacy (0-39)
    UNKNOWN = "UNKNOWN"   # Cannot determine


class RiskItem(BaseModel):
    """A specific privacy risk detected."""
    severity: RiskSeverity
    title: str
    description: str
    detection_confidence: float = Field(..., ge=0, le=1, description="Confidence in detection (0-1)")
    remediation: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "severity": "CRITICAL",
                "title": "Direct Exchange Link",
                "description": "UTXO received directly from known exchange with no mixing",
                "detection_confidence": 0.95,
                "remediation": "Use 2+ high-quality CoinJoins before spending"
            }
        }


class AttackVector(BaseModel):
    """A specific attack vector that could be used against this UTXO."""
    vector_name: str
    vulnerability_score: float = Field(..., ge=0, le=1, description="How vulnerable (0-1, higher = more vulnerable)")
    explanation: str
    example: str = Field(..., description="Concrete example of how attack would work")

    class Config:
        json_schema_extra = {
            "example": {
                "vector_name": "Timing Correlation",
                "vulnerability_score": 0.85,
                "explanation": "Transaction occurred 15 minutes after previous transaction",
                "example": "An adversary seeing exchange withdrawal at 10:00 AM and your spend at 10:15 AM can link them with high confidence"
            }
        }


class Factor(BaseModel):
    """A single factor contributing to privacy score."""
    factor: str
    impact: int = Field(..., description="Privacy score impact (negative = bad, positive = good)")
    explanation: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "factor": "Fast Spend (< 1 hour)",
                "impact": -15,
                "explanation": "UTXO was spent within 1 hour of creation, creating timing correlation risk"
            }
        }


class FactorCategory(BaseModel):
    """Group of related privacy factors."""
    category_name: str
    score_impact: int = Field(..., description="Total score impact from this category")
    factors: List[Factor]
    summary: str

    class Config:
        json_schema_extra = {
            "example": {
                "category_name": "Temporal Privacy",
                "score_impact": -15,
                "factors": [
                    {"factor": "Fast Spend", "impact": -15, "explanation": "Spent within 1 hour"}
                ],
                "summary": "POOR: Funds were moved too quickly, creating timing correlation risk"
            }
        }


class ActionItem(BaseModel):
    """An actionable recommendation to improve privacy."""
    priority: str = Field(..., description="HIGH, MEDIUM, or LOW priority")
    action: str
    expected_improvement: str
    difficulty: Optional[str] = Field(None, description="EASY, MODERATE, or HARD")

    class Config:
        json_schema_extra = {
            "example": {
                "priority": "HIGH",
                "action": "Use Whirlpool with 3+ remixes or Wasabi 2.0 with 10+ rounds",
                "expected_improvement": "+40-50 privacy points",
                "difficulty": "MODERATE"
            }
        }


class PrivacyBenchmark(BaseModel):
    """Comparative context for privacy score."""
    your_score: int
    benchmarks: Dict[str, int] = Field(..., description="Named benchmark scores for comparison")
    interpretation: str

    class Config:
        json_schema_extra = {
            "example": {
                "your_score": 35,
                "benchmarks": {
                    "direct_exchange_withdrawal": 25,
                    "single_coinjoin_fast_spend": 45,
                    "double_coinjoin_week_wait": 65,
                    "whirlpool_5_remixes_good_hygiene": 85,
                    "best_practice_privacy": 95
                },
                "interpretation": "Your privacy is slightly better than a direct exchange withdrawal with no mixing"
            }
        }


class EnhancedPrivacyScore(BaseModel):
    """
    Comprehensive privacy analysis with detailed breakdown.

    This is the main response model for enhanced privacy scoring.
    """

    # Core scores (existing)
    overall_score: int = Field(..., ge=0, le=100, description="Overall privacy score (0-100)")
    rating: PrivacyRating

    # NEW: Human-readable summary
    summary: str = Field(..., description="Natural language summary of privacy assessment")

    # NEW: Categorized factors
    privacy_factors: Dict[str, FactorCategory] = Field(
        ...,
        description="Privacy factors organized by category (temporal, amount, clustering, etc.)"
    )

    # NEW: Risk assessment
    critical_risks: List[RiskItem] = Field(default_factory=list, description="Critical severity risks")
    warnings: List[RiskItem] = Field(default_factory=list, description="High/medium severity warnings")

    # NEW: Actionable recommendations
    recommendations: List[ActionItem] = Field(default_factory=list, description="Prioritized action items")

    # NEW: Attack surface
    attack_vectors: Dict[str, AttackVector] = Field(
        default_factory=dict,
        description="Specific attack vectors adversary could exploit"
    )

    # NEW: Assessment metadata
    assessment_confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Confidence in this assessment (0-1)"
    )
    assessment_limitations: List[str] = Field(
        default_factory=list,
        description="Known limitations of this analysis"
    )

    # NEW: Comparative context
    privacy_context: Optional[PrivacyBenchmark] = Field(
        None,
        description="How this score compares to typical scenarios"
    )

    # Metadata
    execution_time_ms: Optional[int] = None
    analysis_depth: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "overall_score": 35,
                "rating": "RED",
                "summary": "⚠️ POOR PRIVACY: This UTXO is easily traceable. It was spent within 2 blocks of receiving funds from an exchange",
                "privacy_factors": {
                    "temporal": {
                        "category_name": "Temporal Privacy",
                        "score_impact": -15,
                        "factors": [{"factor": "Fast Spend", "impact": -15}],
                        "summary": "POOR: Funds moved too quickly"
                    }
                },
                "critical_risks": [
                    {
                        "severity": "CRITICAL",
                        "title": "Direct Exchange Link",
                        "description": "UTXO received directly from exchange",
                        "detection_confidence": 0.95,
                        "remediation": "Use CoinJoin before spending"
                    }
                ],
                "warnings": [],
                "recommendations": [
                    {
                        "priority": "HIGH",
                        "action": "Use Whirlpool with 3+ remixes",
                        "expected_improvement": "+40-50 points",
                        "difficulty": "MODERATE"
                    }
                ],
                "attack_vectors": {
                    "timing_correlation": {
                        "vector_name": "Timing Correlation",
                        "vulnerability_score": 0.85,
                        "explanation": "Spent within 1 hour of receipt",
                        "example": "Adversary can link transactions by timestamp"
                    }
                },
                "assessment_confidence": 0.85,
                "assessment_limitations": [
                    "Cannot detect network-level correlation",
                    "Cannot detect Wasabi 2.0 CoinJoins"
                ],
                "privacy_context": {
                    "your_score": 35,
                    "benchmarks": {
                        "direct_exchange_withdrawal": 25,
                        "single_coinjoin": 45
                    },
                    "interpretation": "Better than direct withdrawal but worse than single CoinJoin"
                }
            }
        }


class PeelingChainResult(BaseModel):
    """Result of peeling chain detection."""
    is_peeling_chain: bool
    chain_length: int
    transactions: List[str] = Field(default_factory=list, description="Transaction IDs in chain")
    confidence: float = Field(..., ge=0, le=1)
    confidence_percent: str
    total_peeled_sats: int
    total_peeled_btc: float
    remaining_sats: int
    remaining_btc: float
    payment_amounts_sats: List[int] = Field(default_factory=list)
    average_payment_sats: int
    privacy_impact: str = Field(..., description="none, low, high, critical")
    explanation: str
    confidence_factors: List[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "is_peeling_chain": True,
                "chain_length": 5,
                "transactions": ["tx1", "tx2", "tx3", "tx4", "tx5"],
                "confidence": 0.85,
                "confidence_percent": "85.0%",
                "total_peeled_sats": 5000000,
                "total_peeled_btc": 0.05,
                "remaining_sats": 1000000,
                "remaining_btc": 0.01,
                "payment_amounts_sats": [1000000, 1000000, 1000000, 1000000, 1000000],
                "average_payment_sats": 1000000,
                "privacy_impact": "critical",
                "explanation": "High-confidence peeling chain detected",
                "confidence_factors": ["Long chain (5 transactions)", "Similar payment amounts"]
            }
        }


class UnnecessaryInputResult(BaseModel):
    """Result of unnecessary input heuristic."""
    has_unnecessary: bool
    unnecessary_indices: List[int] = Field(default_factory=list)
    unnecessary_count: int
    minimum_inputs_needed: int
    total_inputs_used: int
    confidence: float = Field(..., ge=0, le=1)
    confidence_percent: str
    likely_change_output: Optional[int] = None
    explanation: str

    class Config:
        json_schema_extra = {
            "example": {
                "has_unnecessary": True,
                "unnecessary_indices": [2, 3],
                "unnecessary_count": 2,
                "minimum_inputs_needed": 1,
                "total_inputs_used": 3,
                "confidence": 0.90,
                "confidence_percent": "90.0%",
                "likely_change_output": 1,
                "explanation": "Transaction used 3 inputs but only 1 was needed"
            }
        }


class ClusterInfo(BaseModel):
    """Union-Find cluster result."""
    cluster_id: int
    addresses: List[str]
    total_value_sats: int
    transaction_count: int
    confidence: float = Field(..., ge=0, le=1, description="Confidence in clustering (0-1)")
    heuristic_type: str = Field(..., description="CIOH, script_hash, fee_rate, etc.")

    class Config:
        json_schema_extra = {
            "example": {
                "cluster_id": 0,
                "addresses": ["bc1q...", "1A1zP1..."],
                "total_value_sats": 50000000,
                "transaction_count": 5,
                "confidence": 0.85,
                "heuristic_type": "CIOH"
            }
        }


class CommunityDetectionResult(BaseModel):
    """Louvain community detection."""
    community_id: int
    nodes: List[str] = Field(..., description="Transaction IDs in this community")
    modularity_score: float = Field(..., description="Graph modularity (higher = better separation)")
    inter_community_edges: int
    intra_community_edges: int
    entity_type: str = Field(default="unknown", description="exchange, service, mixer, unknown")

    class Config:
        json_schema_extra = {
            "example": {
                "community_id": 1,
                "nodes": ["txid1", "txid2", "txid3"],
                "modularity_score": 0.87,
                "inter_community_edges": 5,
                "intra_community_edges": 20,
                "entity_type": "exchange"
            }
        }


class ImportantAddress(BaseModel):
    """PageRank result."""
    address: str
    pagerank_score: float = Field(..., description="PageRank score (higher = more central)")
    rank: int = Field(..., description="Rank by centrality (1 = most important)")
    inbound_connections: int
    outbound_connections: int
    total_value_btc: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                "pagerank_score": 0.156,
                "rank": 1,
                "inbound_connections": 50,
                "outbound_connections": 30,
                "total_value_btc": 10.5
            }
        }


class SubgraphPattern(BaseModel):
    """Detected pattern (ring, tree, fan)."""
    pattern_type: str = Field(..., description="ring, tree, fan_out, fan_in, peeling")
    nodes: List[str] = Field(..., description="Transaction IDs in this pattern")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence")
    privacy_implications: str = Field(..., description="What this pattern means for privacy")

    class Config:
        json_schema_extra = {
            "example": {
                "pattern_type": "ring",
                "nodes": ["txid1", "txid2", "txid3", "txid1"],
                "confidence": 0.90,
                "privacy_implications": "CRITICAL: Ring pattern - funds flowing in circle (money laundering indicator)"
            }
        }


# Export all models
__all__ = [
    "RiskSeverity",
    "PrivacyRating",
    "RiskItem",
    "AttackVector",
    "Factor",
    "FactorCategory",
    "ActionItem",
    "PrivacyBenchmark",
    "EnhancedPrivacyScore",
    "PeelingChainResult",
    "UnnecessaryInputResult",
    "ClusterInfo",
    "CommunityDetectionResult",
    "ImportantAddress",
    "SubgraphPattern",
]
