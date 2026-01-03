"""
ChainForensics - CoinJoin Detection Module
Detects various CoinJoin protocols: Whirlpool, Wasabi v1, Wasabi v2 (WabiSabi), JoinMarket, PayJoin.

IMPORTANT:
- Wasabi 2.0 (WabiSabi) uses variable output amounts and is MUCH harder to detect
- Detection confidence for WabiSabi is intentionally lower
- Many sophisticated CoinJoins may go undetected entirely
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import Counter
from enum import Enum

from app.config import COINJOIN_CONFIGS

logger = logging.getLogger("chainforensics.coinjoin")


class CoinJoinProtocol(Enum):
    """Known CoinJoin protocols."""
    NONE = "none"
    WHIRLPOOL = "whirlpool"
    WASABI_V1 = "wasabi_v1"
    WASABI_V2 = "wasabi_v2"  # WabiSabi - much harder to detect
    JOINMARKET = "joinmarket"
    PAYJOIN = "payjoin"
    UNKNOWN = "unknown_coinjoin"


@dataclass
class DetectionResult:
    """Result of CoinJoin detection."""
    txid: str
    score: float  # 0.0 to 1.0
    protocol: CoinJoinProtocol
    confidence: float
    heuristics_matched: List[str] = field(default_factory=list)
    heuristics_failed: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "score": self.score,
            "protocol": self.protocol.value,
            "confidence": self.confidence,
            "is_coinjoin": self.score >= 0.5,
            "heuristics_matched": self.heuristics_matched,
            "heuristics_failed": self.heuristics_failed,
            "details": self.details
        }


@dataclass
class TransactionStats:
    """Statistics about a transaction for CoinJoin detection."""
    input_count: int
    output_count: int
    unique_input_values: int
    unique_output_values: int
    max_equal_outputs: int
    equal_output_value: Optional[float]
    total_input_value: float
    total_output_value: float
    output_values: List[float]
    input_values: List[float]
    output_script_types: List[str]
    input_script_types: List[str]
    is_coinbase: bool
    
    @classmethod
    def from_transaction(cls, tx: Dict) -> "TransactionStats":
        """Create stats from transaction dict."""
        vins = tx.get("vin", [])
        vouts = tx.get("vout", [])
        
        is_coinbase = any("coinbase" in vin for vin in vins)
        
        # Get output values
        output_values = [out["value"] for out in vouts]
        output_script_types = [out.get("scriptPubKey", {}).get("type", "unknown") for out in vouts]
        
        # Get input values (if available)
        input_values = [vin.get("value", 0) for vin in vins if "value" in vin]
        input_script_types = [vin.get("prevout", {}).get("scriptPubKey", {}).get("type", "unknown") for vin in vins]
        
        # Count equal outputs
        value_counts = Counter([round(v, 8) for v in output_values])
        max_equal = max(value_counts.values()) if value_counts else 0
        equal_value = None
        if max_equal >= 2:
            equal_value = max(value_counts.keys(), key=lambda k: value_counts[k])
        
        return cls(
            input_count=len(vins),
            output_count=len(vouts),
            unique_input_values=len(set(round(v, 8) for v in input_values)) if input_values else 0,
            unique_output_values=len(value_counts),
            max_equal_outputs=max_equal,
            equal_output_value=equal_value,
            total_input_value=sum(input_values),
            total_output_value=sum(output_values),
            output_values=output_values,
            input_values=input_values,
            output_script_types=output_script_types,
            input_script_types=input_script_types,
            is_coinbase=is_coinbase
        )


class CoinJoinDetector:
    """Detects CoinJoin transactions using multiple heuristics."""
    
    def __init__(self):
        self.config = COINJOIN_CONFIGS
    
    def analyze_transaction(self, tx: Dict) -> DetectionResult:
        """
        Analyze a transaction for CoinJoin characteristics.
        Returns detection result with score and identified protocol.
        """
        txid = tx.get("txid", "unknown")
        stats = TransactionStats.from_transaction(tx)
        
        # Skip coinbase transactions
        if stats.is_coinbase:
            return DetectionResult(
                txid=txid,
                score=0.0,
                protocol=CoinJoinProtocol.NONE,
                confidence=1.0,
                heuristics_failed=["is_coinbase"]
            )
        
        # Run all detection heuristics
        results = []
        
        # Whirlpool detection
        whirlpool_result = self._detect_whirlpool(stats)
        results.append(("whirlpool", whirlpool_result))
        
        # Wasabi v1 detection
        wasabi_v1_result = self._detect_wasabi_v1(stats)
        results.append(("wasabi_v1", wasabi_v1_result))

        # Wasabi v2 (WabiSabi) detection
        wasabi_v2_result = self._detect_wasabi_v2(stats)
        results.append(("wasabi_v2", wasabi_v2_result))
        
        # JoinMarket detection
        joinmarket_result = self._detect_joinmarket(stats)
        results.append(("joinmarket", joinmarket_result))
        
        # PayJoin detection
        payjoin_result = self._detect_payjoin(stats)
        results.append(("payjoin", payjoin_result))
        
        # Find best match
        best_protocol = CoinJoinProtocol.NONE
        best_score = 0.0
        best_confidence = 0.0
        matched_heuristics = []
        failed_heuristics = []
        details = {}
        
        for protocol_name, (score, confidence, matched, failed, proto_details) in results:
            details[protocol_name] = {
                "score": score,
                "confidence": confidence,
                "matched": matched,
                "failed": failed
            }
            
            if score > best_score:
                best_score = score
                best_confidence = confidence
                best_protocol = getattr(CoinJoinProtocol, protocol_name.upper())
                matched_heuristics = matched
                failed_heuristics = failed
        
        # Check for generic coinjoin pattern if no specific protocol matched
        if best_score < 0.5:
            generic_score, generic_confidence = self._detect_generic_coinjoin(stats)
            if generic_score > best_score:
                best_score = generic_score
                best_confidence = generic_confidence
                best_protocol = CoinJoinProtocol.UNKNOWN if generic_score >= 0.5 else CoinJoinProtocol.NONE
                matched_heuristics = ["generic_equal_outputs", "generic_multiple_participants"]
        
        # Add statistics to details
        details["stats"] = {
            "input_count": stats.input_count,
            "output_count": stats.output_count,
            "max_equal_outputs": stats.max_equal_outputs,
            "unique_output_values": stats.unique_output_values,
            "equal_output_value_btc": stats.equal_output_value
        }
        
        return DetectionResult(
            txid=txid,
            score=best_score,
            protocol=best_protocol,
            confidence=best_confidence,
            heuristics_matched=matched_heuristics,
            heuristics_failed=failed_heuristics,
            details=details
        )
    
    def _detect_whirlpool(self, stats: TransactionStats) -> Tuple[float, float, List[str], List[str], Dict]:
        """
        Detect Whirlpool CoinJoin pattern.
        Characteristics:
        - Exactly 5 outputs
        - All outputs are equal
        - Specific denominations (0.001, 0.01, 0.05, 0.5 BTC)
        """
        config = self.config["whirlpool"]
        matched = []
        failed = []
        details = {}
        
        # Check output count
        if stats.output_count == 5:
            matched.append("exactly_5_outputs")
        else:
            failed.append(f"output_count_{stats.output_count}_not_5")
            return (0.0, 0.0, matched, failed, details)
        
        # Check all outputs equal
        if stats.max_equal_outputs == 5:
            matched.append("all_outputs_equal")
        else:
            failed.append("outputs_not_all_equal")
            return (0.1, 0.3, matched, failed, details)
        
        # Check denomination
        equal_value = stats.equal_output_value
        tolerance = config["tolerance"]
        is_valid_denom = any(
            abs(equal_value - denom) < tolerance
            for denom in config["denominations"]
        )
        
        if is_valid_denom:
            matched.append(f"valid_denomination_{equal_value}")
            details["denomination_btc"] = equal_value
            return (0.95, 0.95, matched, failed, details)
        else:
            matched.append("non_standard_denomination")
            details["denomination_btc"] = equal_value
            # Still likely Whirlpool but unusual denomination
            return (0.80, 0.70, matched, failed, details)
    
    def _detect_wasabi_v1(self, stats: TransactionStats) -> Tuple[float, float, List[str], List[str], Dict]:
        """
        Detect Wasabi v1 CoinJoin pattern.
        Characteristics:
        - Many equal outputs (10+)
        - Change outputs present
        - Large number of participants
        """
        config = self.config["wasabi"]
        matched = []
        failed = []
        details = {}

        # Check for many equal outputs
        if stats.max_equal_outputs >= config["min_equal_outputs"]:
            matched.append(f"many_equal_outputs_{stats.max_equal_outputs}")
            details["equal_outputs"] = stats.max_equal_outputs
        else:
            failed.append(f"equal_outputs_{stats.max_equal_outputs}_below_threshold")
            return (0.0, 0.0, matched, failed, details)

        # Check for change outputs (non-equal values)
        change_count = stats.output_count - stats.max_equal_outputs
        if change_count > 0:
            matched.append(f"has_change_outputs_{change_count}")
            details["change_outputs"] = change_count

        # Calculate score based on number of equal outputs
        base_score = min(0.85, 0.5 + (stats.max_equal_outputs - 10) * 0.05)
        confidence = min(0.9, 0.6 + (stats.max_equal_outputs - 10) * 0.03)

        return (base_score, confidence, matched, failed, details)

    def _detect_wasabi_v2(self, stats: TransactionStats) -> Tuple[float, float, List[str], List[str], Dict]:
        """
        Detect Wasabi v2 (WabiSabi) CoinJoin pattern.

        Characteristics:
        - Variable output amounts (NOT all equal like v1)
        - Many participants (10+ inputs and outputs)
        - High participant count is key signal
        - Much harder to detect than v1

        CRITICAL: This detection has lower confidence because WabiSabi
        is designed to look like normal transactions.
        """
        matched = []
        failed = []
        details = {}

        # WabiSabi requires many participants
        if stats.input_count < 10:
            failed.append(f"inputs_{stats.input_count}_below_10")
            return (0.0, 0.0, matched, failed, details)

        if stats.output_count < 10:
            failed.append(f"outputs_{stats.output_count}_below_10")
            return (0.0, 0.0, matched, failed, details)

        matched.append(f"many_participants_{stats.input_count}_inputs_{stats.output_count}_outputs")
        details["inputs"] = stats.input_count
        details["outputs"] = stats.output_count

        # Check for some equal outputs (there may be some, but not all)
        if stats.max_equal_outputs >= 5:
            matched.append(f"some_equal_outputs_{stats.max_equal_outputs}")
            details["equal_outputs"] = stats.max_equal_outputs
        else:
            # Still possible, but lower confidence
            details["equal_outputs"] = stats.max_equal_outputs

        # Check for variable amounts (higher uniqueness ratio than v1)
        if stats.output_count > 0:
            uniqueness_ratio = stats.unique_output_values / stats.output_count
            details["uniqueness_ratio"] = round(uniqueness_ratio, 2)

            # WabiSabi should have MORE unique values than v1
            if uniqueness_ratio > 0.5:
                matched.append("high_output_diversity")
            else:
                # Lower diversity might indicate v1, not v2
                failed.append("low_output_diversity_may_be_v1")

        # Score is moderate - WabiSabi is hard to detect with certainty
        # Higher participant count = higher confidence
        base_score = 0.50 + min(0.20, (stats.input_count - 10) * 0.02)
        confidence = 0.40 + min(0.25, (stats.input_count - 10) * 0.02)

        # Boost if we found some equal outputs (hybrid approach)
        if stats.max_equal_outputs >= 5:
            base_score += 0.10
            confidence += 0.10

        return (base_score, confidence, matched, failed, details)
    
    def _detect_joinmarket(self, stats: TransactionStats) -> Tuple[float, float, List[str], List[str], Dict]:
        """
        Detect JoinMarket CoinJoin pattern.
        Characteristics:
        - Variable number of participants
        - Maker/taker structure
        - Some equal outputs (maker outputs)
        - Mixed input types possible
        """
        config = self.config["joinmarket"]
        matched = []
        failed = []
        details = {}
        
        # Check minimum inputs
        if stats.input_count >= config["min_inputs"]:
            matched.append(f"sufficient_inputs_{stats.input_count}")
        else:
            failed.append(f"inputs_{stats.input_count}_below_minimum")
            return (0.0, 0.0, matched, failed, details)
        
        # Check minimum outputs
        if stats.output_count >= config["min_outputs"]:
            matched.append(f"sufficient_outputs_{stats.output_count}")
        else:
            failed.append(f"outputs_{stats.output_count}_below_minimum")
            return (0.1, 0.2, matched, failed, details)
        
        # Check for some equal outputs (makers)
        if stats.max_equal_outputs >= 2:
            matched.append(f"has_equal_outputs_{stats.max_equal_outputs}")
            details["maker_outputs"] = stats.max_equal_outputs
        else:
            failed.append("no_equal_outputs")
            return (0.2, 0.3, matched, failed, details)
        
        # JoinMarket has variable structure, so confidence is lower
        score = 0.60
        confidence = 0.55
        
        # Boost score if structure matches typical JoinMarket
        if stats.unique_output_values <= stats.output_count / 2:
            matched.append("typical_value_distribution")
            score += 0.1
            confidence += 0.1
        
        return (score, confidence, matched, failed, details)
    
    def _detect_payjoin(self, stats: TransactionStats) -> Tuple[float, float, List[str], List[str], Dict]:
        """
        Detect PayJoin (P2EP) pattern.
        Characteristics:
        - 2 participants (sender + receiver)
        - Receiver adds input to disguise as regular transaction
        - Usually 2-3 outputs
        - Hard to detect reliably
        """
        matched = []
        failed = []
        details = {}
        
        # PayJoin is very hard to detect as it's designed to look like regular tx
        # We can only flag suspicious patterns
        
        # Check for multiple inputs with different script types
        unique_script_types = len(set(stats.input_script_types))
        if unique_script_types >= 2 and stats.input_count >= 2 and stats.input_count <= 5:
            matched.append("mixed_input_types")
            details["input_script_types"] = stats.input_script_types
        else:
            failed.append("no_mixed_inputs_or_wrong_count")
            return (0.0, 0.0, matched, failed, details)
        
        # Check output count (usually 2-3 for PayJoin)
        if 2 <= stats.output_count <= 4:
            matched.append("typical_output_count")
        else:
            failed.append(f"unusual_output_count_{stats.output_count}")
            return (0.1, 0.2, matched, failed, details)
        
        # PayJoin detection is inherently uncertain
        return (0.40, 0.35, matched, failed, details)
    
    def _detect_generic_coinjoin(self, stats: TransactionStats) -> Tuple[float, float]:
        """
        Detect generic CoinJoin pattern not matching specific protocols.
        """
        score = 0.0
        
        # Many equal outputs is a strong signal
        if stats.max_equal_outputs >= 5:
            score += 0.3
        elif stats.max_equal_outputs >= 3:
            score += 0.15
        
        # Many participants
        if stats.input_count >= 5:
            score += 0.2
        elif stats.input_count >= 3:
            score += 0.1
        
        # Output count significantly higher than typical
        if stats.output_count >= 10:
            score += 0.2
        elif stats.output_count >= 5:
            score += 0.1
        
        # Low ratio of unique values to outputs suggests CoinJoin
        if stats.output_count > 0:
            uniqueness_ratio = stats.unique_output_values / stats.output_count
            if uniqueness_ratio < 0.3:
                score += 0.2
            elif uniqueness_ratio < 0.5:
                score += 0.1
        
        confidence = min(0.7, score)
        return (score, confidence)
    
    def batch_analyze(self, transactions: List[Dict]) -> List[DetectionResult]:
        """Analyze multiple transactions."""
        return [self.analyze_transaction(tx) for tx in transactions]
    
    def get_coinjoin_history(self, tx_list: List[Dict]) -> Dict:
        """
        Analyze a list of transactions (e.g., from a trace) for CoinJoin history.
        Returns summary of CoinJoin activity.
        """
        results = self.batch_analyze(tx_list)
        
        coinjoins = [r for r in results if r.score >= 0.5]
        
        protocol_counts = Counter(r.protocol.value for r in coinjoins)
        total_score = sum(r.score for r in coinjoins)
        
        return {
            "total_transactions": len(tx_list),
            "coinjoin_count": len(coinjoins),
            "coinjoin_percentage": (len(coinjoins) / len(tx_list) * 100) if tx_list else 0,
            "protocol_breakdown": dict(protocol_counts),
            "average_coinjoin_score": (total_score / len(coinjoins)) if coinjoins else 0,
            "coinjoin_txids": [r.txid for r in coinjoins],
            "all_results": [r.to_dict() for r in results]
        }


# Singleton instance
_detector_instance: Optional[CoinJoinDetector] = None


def get_detector() -> CoinJoinDetector:
    """Get or create detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = CoinJoinDetector()
    return _detector_instance
