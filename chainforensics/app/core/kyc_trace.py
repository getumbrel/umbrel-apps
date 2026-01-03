"""
ChainForensics - KYC Privacy Trace Module
Analyzes if funds from a known KYC withdrawal can be traced to current holdings.

This module helps users check their own privacy by simulating what an
adversary who knows their exchange withdrawal details could discover.

CRITICAL WARNINGS:
- This tool provides HEURISTIC ANALYSIS ONLY and should NOT be used for operational security
- It cannot detect: timing correlation, Wasabi 2.0, sophisticated PayJoin, network analysis
- Undetectable attacks exist that this tool cannot warn you about
- A high privacy score does NOT mean your privacy is actually good
- This is for educational/research purposes only
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter

from app.config import settings
from app.core.bitcoin_rpc import BitcoinRPC, get_rpc
from app.core.entity_recognition import identify_entity

logger = logging.getLogger("chainforensics.kyc_trace")


class TrailStatus(Enum):
    """Status of a trace trail."""
    ACTIVE = "active"           # Trail is clear and traceable
    COLD = "cold"               # Trail confidence dropped below 5% (truly cold)
    DEAD_END = "dead_end"       # Trail hit an unspent UTXO
    DEPTH_LIMIT = "depth_limit" # Hit max depth
    LOST = "lost"               # Cannot follow (no Fulcrum, etc)


class ConfidenceLevel(Enum):
    """Confidence levels for attribution."""
    HIGH = "high"       # 70-100% - Very likely same owner
    MEDIUM = "medium"   # 40-69% - Possibly same owner
    LOW = "low"         # 20-39% - Unlikely same owner
    NEGLIGIBLE = "negligible"  # <20% - Almost certainly not traceable


@dataclass
class PathNode:
    """A node in the trace path."""
    txid: str
    vout: int
    value_sats: int
    address: Optional[str]
    block_height: Optional[int]
    block_time: Optional[datetime]
    is_coinjoin: bool
    coinjoin_score: float
    coinjoin_count_in_path: int  # How many CoinJoins we've passed through
    coinjoin_protocol: str  # Protocol detected (whirlpool, wasabi, etc)
    anonymity_set_size: int  # Estimated anonymity set for this CoinJoin
    depth: int
    is_change: bool = False
    change_probability: float = 0.0
    cumulative_confidence: float = 1.0  # Running confidence score through path
    
    @property
    def value_btc(self) -> float:
        return self.value_sats / 100_000_000
    
    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "value_sats": self.value_sats,
            "value_btc": self.value_btc,
            "address": self.address,
            "block_height": self.block_height,
            "block_time": self.block_time.isoformat() if self.block_time else None,
            "is_coinjoin": self.is_coinjoin,
            "coinjoin_score": self.coinjoin_score,
            "coinjoin_count_in_path": self.coinjoin_count_in_path,
            "coinjoin_protocol": self.coinjoin_protocol,
            "anonymity_set_size": self.anonymity_set_size,
            "depth": self.depth,
            "is_change": self.is_change,
            "change_probability": self.change_probability,
            "cumulative_confidence": round(self.cumulative_confidence * 100, 1)
        }


@dataclass
class ProbableDestination:
    """A probable final destination for the traced funds."""
    address: str
    value_sats: int
    confidence_score: float  # 0.0 to 1.0
    confidence_level: ConfidenceLevel
    path_length: int
    coinjoins_passed: int
    trail_status: TrailStatus
    reasoning: List[str]
    path: List[PathNode]
    
    @property
    def value_btc(self) -> float:
        return self.value_sats / 100_000_000
    
    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "value_sats": self.value_sats,
            "value_btc": self.value_btc,
            "confidence_score": round(self.confidence_score * 100, 1),
            "confidence_level": self.confidence_level.value,
            "confidence_percent": f"{self.confidence_score * 100:.1f}%",
            "path_length": self.path_length,
            "coinjoins_passed": self.coinjoins_passed,
            "trail_status": self.trail_status.value,
            "reasoning": self.reasoning,
            "path": [n.to_dict() for n in self.path]
        }


@dataclass
class KYCTraceResult:
    """Complete result of a KYC privacy trace."""
    exchange_txid: str
    destination_address: str
    original_value_sats: int
    trace_depth: int
    
    # Results
    probable_destinations: List[ProbableDestination] = field(default_factory=list)
    total_traced_sats: int = 0
    total_untraceable_sats: int = 0
    coinjoins_encountered: int = 0
    
    # Analysis
    overall_privacy_score: float = 0.0  # 0-100, higher = more private
    privacy_rating: str = "unknown"
    summary: str = ""
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Metadata
    execution_time_ms: int = 0
    electrs_enabled: bool = False
    
    @property
    def original_value_btc(self) -> float:
        return self.original_value_sats / 100_000_000
    
    def to_dict(self) -> Dict:
        return {
            "exchange_txid": self.exchange_txid,
            "destination_address": self.destination_address,
            "original_value_sats": self.original_value_sats,
            "original_value_btc": self.original_value_btc,
            "trace_depth": self.trace_depth,
            "probable_destinations": [d.to_dict() for d in self.probable_destinations],
            "total_traced_sats": self.total_traced_sats,
            "total_traced_btc": self.total_traced_sats / 100_000_000,
            "total_untraceable_sats": self.total_untraceable_sats,
            "total_untraceable_btc": self.total_untraceable_sats / 100_000_000,
            "untraceable_percent": round(self.total_untraceable_sats / max(self.original_value_sats, 1) * 100, 1),
            "coinjoins_encountered": self.coinjoins_encountered,
            "overall_privacy_score": round(self.overall_privacy_score, 1),
            "privacy_rating": self.privacy_rating,
            "summary": self.summary,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "execution_time_ms": self.execution_time_ms,
            "electrs_enabled": self.electrs_enabled,
            "destination_count": len(self.probable_destinations),
            "high_confidence_destinations": len([d for d in self.probable_destinations if d.confidence_level == ConfidenceLevel.HIGH]),
            "medium_confidence_destinations": len([d for d in self.probable_destinations if d.confidence_level == ConfidenceLevel.MEDIUM])
        }


class KYCPrivacyTracer:
    """
    Traces funds from a known KYC exchange withdrawal to probable current holdings.
    
    This helps users understand what an adversary with knowledge of their
    exchange withdrawal could potentially discover about their current holdings.
    """
    
    # Depth presets with complexity descriptions
    DEPTH_PRESETS = {
        "quick": {
            "depth": 3,
            "label": "Quick Scan",
            "description": "Fast check, 1-3 hops only",
            "complexity": "Low"
        },
        "standard": {
            "depth": 6,
            "label": "Standard",
            "description": "Balanced depth, covers most patterns",
            "complexity": "Medium"
        },
        "deep": {
            "depth": 10,
            "label": "Deep Scan",
            "description": "Thorough analysis, may take longer",
            "complexity": "High"
        },
        "thorough": {
            "depth": 15,
            "label": "Thorough",
            "description": "Very deep analysis, intensive",
            "complexity": "Very High"
        }
    }
    
    MAX_DEPTH = 15  # Absolute maximum
    MAX_TRANSACTIONS = 300
    MAX_QUEUE_SIZE = 1000
    COINJOIN_THRESHOLD = 0.7  # Score above this = CoinJoin
    CONFIDENCE_COLD_THRESHOLD = 0.05  # Trail is "cold" when confidence drops below 5%
    MAX_CONSECUTIVE_ELECTRS_FAILURES = 3  # Stop using Fulcrum after 3 failures
    MAX_TRACE_TIME_SECONDS = 60  # 60 second overall timeout
    
    def __init__(self, rpc: BitcoinRPC = None):
        self.rpc = rpc or get_rpc()
        self._tx_cache: Dict[str, Dict] = {}
        self._electrs = None
        self._electrs_checked = False
        self._electrs_failures = 0  # Track Electrs failures during trace
    
    async def _get_electrs(self):
        """Lazy load Fulcrum client."""
        if not self._electrs_checked:
            try:
                from app.core.fulcrum import get_fulcrum
                self._electrs = get_fulcrum()
                if self._electrs.is_configured:
                    await self._electrs.connect()
                else:
                    self._electrs = None
            except Exception as e:
                logger.debug(f"Electrs not available: {e}")
                self._electrs = None
            self._electrs_checked = True
        return self._electrs
    
    async def _get_transaction(self, txid: str) -> Optional[Dict]:
        """Get transaction with caching."""
        if txid in self._tx_cache:
            cached = self._tx_cache[txid]
            # Validate cached data is a dict, not a string
            if isinstance(cached, dict):
                return cached
            else:
                # Invalid cached data, remove it
                del self._tx_cache[txid]
        
        try:
            tx = await self.rpc.get_raw_transaction(txid, True)
            # Validate response is a dict (not a hex string)
            if tx and isinstance(tx, dict):
                self._tx_cache[txid] = tx
                return tx
            elif tx and isinstance(tx, str):
                # Got hex string instead of dict - verbose mode may have failed
                logger.warning(f"Got hex string instead of dict for tx {txid}")
                return None
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch transaction {txid}: {e}")
            return None
    
    def _calculate_coinjoin_score(self, tx: Dict) -> float:
        """
        Calculate CoinJoin probability score.
        Returns score 0.0-1.0 indicating likelihood of CoinJoin.
        """
        vouts = tx.get("vout", [])
        vins = tx.get("vin", [])

        if len(vouts) < 2:
            return 0.0

        values = [round(out.get("value", 0), 8) for out in vouts]
        value_counts = Counter(values)

        if not value_counts:
            return 0.0

        max_equal = max(value_counts.values())
        num_outputs = len(vouts)
        num_inputs = len(vins)

        # Whirlpool: exactly 5 equal outputs
        if num_outputs == 5 and max_equal == 5:
            return 0.95

        # Wasabi v1: many equal outputs (10+)
        if max_equal >= 10:
            return 0.90

        # Wasabi v2 (WabiSabi): variable outputs but many participants
        # Much harder to detect - look for high participant count
        if num_inputs >= 10 and num_outputs >= 10 and max_equal >= 5:
            return 0.70  # Lower confidence for WabiSabi

        # JoinMarket / Generic
        if max_equal >= 5 and num_inputs >= 3:
            return 0.75

        if max_equal >= 3 and num_inputs >= 2:
            return 0.50

        return 0.0

    def _get_coinjoin_details(self, tx: Dict, coinjoin_score: float) -> Tuple[str, int]:
        """
        Get CoinJoin protocol and estimated anonymity set size.

        Returns:
            (protocol_name, anonymity_set_size)
        """
        vouts = tx.get("vout", [])
        vins = tx.get("vin", [])

        if coinjoin_score < self.COINJOIN_THRESHOLD:
            return ("none", 0)

        values = [round(out.get("value", 0), 8) for out in vouts]
        value_counts = Counter(values)
        max_equal = max(value_counts.values()) if value_counts else 0

        num_outputs = len(vouts)
        num_inputs = len(vins)

        # Whirlpool: 5 equal outputs
        if num_outputs == 5 and max_equal == 5:
            return ("whirlpool", 5)

        # Wasabi v1: many equal outputs
        if max_equal >= 10:
            return ("wasabi_v1", max_equal)

        # Wasabi v2 (WabiSabi): high participant count, variable amounts
        if num_inputs >= 10 and num_outputs >= 10:
            # Anonymity set is harder to determine - use minimum of inputs/outputs
            return ("wasabi_v2", min(num_inputs, num_outputs))

        # JoinMarket: variable structure
        if max_equal >= 5 and num_inputs >= 3:
            # JoinMarket anonymity set is number of makers + taker
            # Conservative estimate: max_equal outputs likely from makers
            return ("joinmarket", max_equal)

        # Generic/unknown CoinJoin
        return ("unknown", max(max_equal, 2))

    def _calculate_coinjoin_confidence_degradation(
        self,
        protocol: str,
        anonymity_set_size: int,
        prev_confidence: float
    ) -> float:
        """
        Calculate how much confidence degrades when passing through a CoinJoin.

        Args:
            protocol: CoinJoin protocol (whirlpool, wasabi_v1, etc)
            anonymity_set_size: Number of participants in the mix
            prev_confidence: Confidence before this CoinJoin

        Returns:
            New confidence score (0.0-1.0)

        Privacy Model:
        - After a CoinJoin, an observer must guess which output belongs to the target
        - With perfect mixing, confidence = 1 / anonymity_set_size
        - In practice, various attacks (amount correlation, timing, etc) increase confidence
        - We apply a conservative multiplier based on protocol strength
        """
        if anonymity_set_size < 2:
            # Not actually a CoinJoin
            return prev_confidence

        # Base degradation: 1 / anonymity_set_size
        base_degradation = 1.0 / anonymity_set_size

        # Protocol-specific multipliers (higher = worse privacy)
        # These account for known weaknesses and attack surfaces
        protocol_multipliers = {
            "whirlpool": 1.5,      # Good protocol, but only 5 participants
            "wasabi_v1": 1.3,      # Good anonymity sets, some known attacks
            "wasabi_v2": 1.8,      # Variable amounts make it harder to verify mixing quality
            "joinmarket": 2.0,     # Variable structure, harder to assess
            "unknown": 2.5         # Unknown protocol, assume worst case
        }

        multiplier = protocol_multipliers.get(protocol, 2.5)

        # Calculate new confidence
        # Each CoinJoin multiplies previous confidence by degradation factor
        new_confidence = prev_confidence * (base_degradation * multiplier)

        # Floor at near-zero (never truly 0%)
        return max(new_confidence, 0.001)
    
    def _detect_unnecessary_inputs(
        self,
        tx: Dict,
        payment_output_idx: Optional[int] = None
    ) -> Dict:
        """
        Detect if transaction used more inputs than necessary.

        If a transaction could have been funded with fewer inputs, the additional
        inputs are "unnecessary" and this strongly suggests all inputs belong to
        the same wallet (common input ownership heuristic).

        This also helps identify which output is change.

        Args:
            tx: Transaction dict
            payment_output_idx: Known payment output index (if known)

        Returns:
            Dictionary with analysis results
        """
        vins = tx.get("vin", [])
        vouts = tx.get("vout", [])

        if not vins or not vouts:
            return {
                "has_unnecessary": False,
                "unnecessary_indices": [],
                "minimum_inputs_needed": 0,
                "total_inputs_used": 0,
                "confidence": 0.0,
                "likely_change_output": None,
                "explanation": "Insufficient input/output data"
            }

        # Get input values
        # Note: In real implementation, we'd need to look up previous transactions
        # For now, we'll use prevout data if available
        input_values = []
        for idx, vin in enumerate(vins):
            if "prevout" in vin:
                value_sats = int(vin["prevout"].get("value", 0) * 100_000_000)
                if value_sats > 0:
                    input_values.append((idx, value_sats))

        # Get output values
        output_values = []
        for idx, vout in enumerate(vouts):
            value_sats = int(vout.get("value", 0) * 100_000_000)
            output_values.append((idx, value_sats))

        if not input_values or not output_values:
            return {
                "has_unnecessary": False,
                "unnecessary_indices": [],
                "minimum_inputs_needed": 0,
                "total_inputs_used": len(vins),
                "confidence": 0.0,
                "likely_change_output": None,
                "explanation": "Cannot determine input values"
            }

        # Calculate total output (what needs to be funded)
        total_output = sum(v for _, v in output_values)

        # Estimate fee (approximate - real fee would need full calculation)
        # Typical fee for 1-input, 2-output tx is ~20,000 sats
        estimated_fee = 20000 + (len(input_values) * 10000)  # +10k per additional input

        # Target amount to fund
        target_amount = total_output + estimated_fee

        # Sort inputs by value (descending - use largest first)
        sorted_inputs = sorted(input_values, key=lambda x: x[1], reverse=True)

        # Find minimum inputs needed
        cumulative = 0
        minimum_needed = 0
        for idx, value in sorted_inputs:
            cumulative += value
            minimum_needed += 1
            if cumulative >= target_amount:
                break

        total_used = len(input_values)
        unnecessary_count = total_used - minimum_needed
        has_unnecessary = unnecessary_count > 0

        # Identify which inputs are unnecessary
        # The smallest inputs that weren't needed
        if has_unnecessary:
            necessary_inputs = set(idx for idx, _ in sorted_inputs[:minimum_needed])
            unnecessary_indices = [idx for idx, _ in sorted_inputs if idx not in necessary_inputs]
        else:
            unnecessary_indices = []

        # Calculate confidence that all inputs are from same wallet
        if has_unnecessary:
            # Strong evidence of common ownership if 2+ unnecessary inputs
            if unnecessary_count >= 2:
                confidence = 0.90
            elif unnecessary_count == 1:
                confidence = 0.75
            else:
                confidence = 0.50
        else:
            # All inputs were needed - weaker evidence
            confidence = 0.30

        # Try to identify change output
        likely_change = None

        if has_unnecessary and len(output_values) >= 2:
            # Change output often receives the sum of unnecessary inputs
            unnecessary_sum = sum(v for i, v in input_values if i in unnecessary_indices)

            # Find output closest to unnecessary sum
            min_diff = float('inf')
            for out_idx, out_value in output_values:
                diff = abs(out_value - unnecessary_sum)
                if diff < min_diff:
                    min_diff = diff
                    likely_change = out_idx

            # Only confident if difference is small (within fee tolerance)
            if min_diff > 100000:  # 0.001 BTC tolerance
                likely_change = None

        # Generate explanation
        if has_unnecessary:
            explanation = (
                f"Transaction used {total_used} input(s) but only {minimum_needed} were needed to fund outputs. "
                f"The {unnecessary_count} unnecessary input(s) suggest all inputs belong to same wallet. "
                f"Confidence: {int(confidence*100)}%."
            )
        else:
            explanation = (
                f"Transaction used minimum inputs ({minimum_needed}) needed to fund outputs. "
                f"Weak evidence for common ownership (confidence: {int(confidence*100)}%)."
            )

        return {
            "has_unnecessary": has_unnecessary,
            "unnecessary_indices": unnecessary_indices,
            "unnecessary_count": unnecessary_count,
            "minimum_inputs_needed": minimum_needed,
            "total_inputs_used": total_used,
            "confidence": round(confidence, 3),
            "confidence_percent": f"{confidence * 100:.1f}%",
            "likely_change_output": likely_change,
            "explanation": explanation
        }

    def _detect_change_output(
        self,
        tx: Dict,
        input_addresses: Set[str],
        output_idx: int,
        original_value: int
    ) -> Tuple[bool, float]:
        """
        Detect if an output is likely change.

        Returns (is_change, probability)

        CRITICAL: Address reuse is a VERY STRONG signal and dominates other heuristics.

        Now enhanced with unnecessary input heuristic.
        """
        vouts = tx.get("vout", [])
        if output_idx >= len(vouts):
            return False, 0.0

        output = vouts[output_idx]
        output_value = int(output.get("value", 0) * 100_000_000)
        output_script = output.get("scriptPubKey", {})
        output_address = output_script.get("address")
        output_type = output_script.get("type", "")

        # Heuristic 1: Address reuse (sending back to input address)
        # This is EXTREMELY strong evidence - if you send back to an input address,
        # it's almost certainly change (95%+ confidence)
        if output_address and output_address in input_addresses:
            return True, 0.95

        # If no address reuse, use weaker heuristics
        probability = 0.0

        # Heuristic 2: Unnecessary input analysis (NEW - powerful heuristic)
        unnecessary_result = self._detect_unnecessary_inputs(tx, output_idx)
        if unnecessary_result["likely_change_output"] == output_idx:
            # This output matches the unnecessary input pattern
            probability += 0.30  # Strong signal
            logger.debug(f"Output {output_idx} identified as likely change via unnecessary input heuristic")

        # Heuristic 3: Same script type as inputs
        input_types = set()
        for vin in tx.get("vin", []):
            if "prevout" in vin:
                input_types.add(vin["prevout"].get("scriptPubKey", {}).get("type", ""))

        if output_type in input_types:
            probability += 0.15

        # Heuristic 4: Non-round number (change is often "weird" amounts)
        value_btc = output_value / 100_000_000
        # Check if it's a round number
        is_round = (value_btc * 1000) % 1 == 0  # Multiple of 0.001
        if not is_round:
            probability += 0.20

        # Heuristic 5: Smaller than largest output (often payment is larger)
        max_output = max(int(v.get("value", 0) * 100_000_000) for v in vouts)
        if output_value < max_output:
            probability += 0.15

        # Heuristic 6: Position (change often last, but not always)
        if output_idx == len(vouts) - 1:
            probability += 0.10

        return probability > 0.35, min(probability, 0.85)  # Increased max from 0.80 to 0.85
    
    def _calculate_path_confidence(
        self,
        path: List[PathNode],
        original_value: int
    ) -> Tuple[float, List[str]]:
        """
        Calculate confidence score for a traced path using cumulative model.

        Returns (confidence_score, reasoning_list)

        NEW MODEL:
        - Start with 100% confidence
        - Degrade confidence through each CoinJoin based on anonymity set
        - Apply smaller penalties for path length and value changes
        - The last node in the path has cumulative_confidence already calculated
        """
        if not path:
            return 0.0, ["Empty path"]

        reasoning = []

        # Get the final cumulative confidence from the last node
        confidence = path[-1].cumulative_confidence

        path_length = len(path)
        coinjoins = sum(1 for n in path if n.is_coinjoin)

        # Add explanations
        if path_length == 1:
            reasoning.append("Direct transfer (1 hop)")
        elif path_length <= 3:
            reasoning.append(f"Short path ({path_length} hops)")
        else:
            reasoning.append(f"Longer path ({path_length} hops)")

        # Explain CoinJoin impact
        if coinjoins == 0:
            reasoning.append("No CoinJoins in path - easily traceable")
        elif coinjoins == 1:
            reasoning.append(f"Passed through 1 CoinJoin (confidence: {confidence*100:.1f}%)")
        elif coinjoins >= 2:
            reasoning.append(f"Passed through {coinjoins} CoinJoins (confidence: {confidence*100:.1f}%)")

        # Value similarity analysis
        if path:
            final_value = path[-1].value_sats
            value_ratio = final_value / max(original_value, 1)

            if value_ratio > 0.9:
                reasoning.append("Value very similar to original (>90%)")
            elif value_ratio > 0.5:
                reasoning.append(f"Value is {value_ratio*100:.0f}% of original")
            elif value_ratio > 0.1:
                reasoning.append(f"Value is {value_ratio*100:.0f}% of original (likely split)")
            else:
                # Very small fraction suggests mixing or many splits
                confidence *= 0.7  # Reduce confidence for value splits
                reasoning.append(f"Value is only {value_ratio*100:.1f}% of original (split/mixed)")

        # Change detection analysis
        change_nodes = [n for n in path if n.is_change]
        if change_nodes:
            high_confidence_change = [n for n in change_nodes if n.change_probability > 0.8]
            if high_confidence_change:
                # Following change outputs increases traceability
                confidence *= 1.1  # Slightly boost confidence
                confidence = min(confidence, 1.0)  # Cap at 100%
                reasoning.append(f"Path follows {len(high_confidence_change)} high-confidence change output(s)")
            else:
                reasoning.append(f"Path follows {len(change_nodes)} possible change output(s)")

        return min(max(confidence, 0.0), 1.0), reasoning
    
    def _get_confidence_level(self, score: float) -> ConfidenceLevel:
        """Convert score to confidence level."""
        if score >= 0.7:
            return ConfidenceLevel.HIGH
        elif score >= 0.4:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.NEGLIGIBLE
    
    async def _find_spending_tx(self, txid: str, vout: int, address: str) -> Optional[str]:
        """Find transaction that spent a specific output using Electrs."""
        electrs = await self._get_electrs()
        if not electrs:
            return None
        
        try:
            # Add timeout to prevent hanging on large addresses
            history = await asyncio.wait_for(
                electrs.get_history(address),
                timeout=20.0  # 20 second timeout for history lookup (was 60s)
            )
            
            # Check if history is valid
            if not history or not isinstance(history, list):
                return None
            
            for hist_tx in history:
                if hist_tx.txid == txid:
                    continue
                
                try:
                    full_tx = await self._get_transaction(hist_tx.txid)
                    # Double-check it's a dict (not string/None)
                    if not full_tx or not isinstance(full_tx, dict):
                        continue
                    
                    for vin in full_tx.get("vin", []):
                        if isinstance(vin, dict) and vin.get("txid") == txid and vin.get("vout") == vout:
                            return hist_tx.txid
                except Exception:
                    continue
            
            return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout finding spending tx for {txid}:{vout}")
            # Force reconnection after timeout - the connection is likely corrupted
            logger.warning("Forcing Electrs reconnection due to timeout")
            try:
                await electrs.disconnect()
            except:
                pass
            self._electrs_failures = getattr(self, '_electrs_failures', 0) + 1
            return None
        except Exception as e:
            logger.warning(f"Error finding spending tx for {txid}:{vout}: {e}")
            # Force reconnection after any exception too
            try:
                await electrs.disconnect()
            except:
                pass
            # Track this failure for reporting
            self._electrs_failures = getattr(self, '_electrs_failures', 0) + 1
            return None
    
    async def trace_kyc_withdrawal(
        self,
        exchange_txid: str,
        destination_address: str,
        depth_preset: str = "standard"
    ) -> KYCTraceResult:
        """
        Trace a KYC exchange withdrawal to find probable current holdings.
        
        Args:
            exchange_txid: Transaction ID of the exchange withdrawal
            destination_address: Address that received the withdrawal
            depth_preset: One of "quick", "standard", "deep", "thorough"
        
        Returns:
            KYCTraceResult with probable destinations and privacy analysis
        """
        start_time = datetime.utcnow()
        self._electrs_failures = 0  # Reset failure counter for this trace
        
        # Get depth from preset
        preset = self.DEPTH_PRESETS.get(depth_preset, self.DEPTH_PRESETS["standard"])
        max_depth = min(preset["depth"], self.MAX_DEPTH)
        
        result = KYCTraceResult(
            exchange_txid=exchange_txid,
            destination_address=destination_address,
            original_value_sats=0,
            trace_depth=max_depth
        )
        
        # Check Electrs availability
        electrs = await self._get_electrs()
        result.electrs_enabled = electrs is not None
        
        if not electrs:
            result.warnings.append("Electrs not available - forward tracing will be limited")
        
        # Get the initial transaction
        tx = await self._get_transaction(exchange_txid)
        if not tx or not isinstance(tx, dict):
            result.warnings.append(f"Transaction not found: {exchange_txid}")
            result.summary = "Could not find the exchange transaction"
            return result
        
        # Find the output that went to destination_address
        start_vout = None
        start_value = 0
        
        for idx, vout in enumerate(tx.get("vout", [])):
            script = vout.get("scriptPubKey", {})
            addr = script.get("address")
            if addr == destination_address:
                start_vout = idx
                start_value = int(vout.get("value", 0) * 100_000_000)
                break
        
        if start_vout is None:
            result.warnings.append(f"Destination address {destination_address} not found in transaction outputs")
            result.summary = "The destination address was not found in the transaction"
            return result
        
        result.original_value_sats = start_value
        
        # BFS to trace funds forward
        # Queue: (txid, vout, depth, coinjoin_count, path, current_value, cumulative_confidence)
        queue: List[Tuple[str, int, int, int, List[PathNode], int, float]] = [
            (exchange_txid, start_vout, 0, 0, [], start_value, 1.0)
        ]
        
        visited: Set[Tuple[str, int]] = set()
        destinations: List[ProbableDestination] = []
        tx_count = 0
        coinjoin_txids: Set[str] = set()
        consecutive_electrs_failures = 0
        electrs_disabled = False
        
        while queue and tx_count < self.MAX_TRANSACTIONS:
            # Check overall timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > self.MAX_TRACE_TIME_SECONDS:
                result.warnings.append(f"Trace timeout ({self.MAX_TRACE_TIME_SECONDS}s) reached - returning partial results")
                break
            
            if len(queue) > self.MAX_QUEUE_SIZE:
                result.warnings.append("Queue size exceeded, some paths truncated")
                queue = queue[:self.MAX_QUEUE_SIZE]
            
            current_txid, current_vout, depth, cj_count, path, tracked_value, _ = queue.pop(0)
            
            if (current_txid, current_vout) in visited:
                continue
            visited.add((current_txid, current_vout))
            
            # Depth limit check
            if depth > max_depth:
                # Add as destination with depth limit status
                if path:
                    conf_score, reasoning = self._calculate_path_confidence(path, start_value)
                    reasoning.append("Hit depth limit")
                    destinations.append(ProbableDestination(
                        address=path[-1].address or "unknown",
                        value_sats=tracked_value,
                        confidence_score=conf_score * 0.5,  # Reduce confidence at limit
                        confidence_level=self._get_confidence_level(conf_score * 0.5),
                        path_length=len(path),
                        coinjoins_passed=cj_count,
                        trail_status=TrailStatus.DEPTH_LIMIT,
                        reasoning=reasoning,
                        path=path
                    ))
                continue
            
            # Get transaction
            tx = await self._get_transaction(current_txid)
            if not tx or not isinstance(tx, dict):
                continue
            
            tx_count += 1
            
            # Get output info
            vouts = tx.get("vout", [])
            if current_vout >= len(vouts):
                continue
            
            output = vouts[current_vout]
            value_sats = int(output.get("value", 0) * 100_000_000)
            script = output.get("scriptPubKey", {})
            address = script.get("address")
            script_type = script.get("type", "unknown")
            
            block_height = tx.get("blockheight") or tx.get("height")
            block_time = None
            if tx.get("blocktime"):
                block_time = datetime.utcfromtimestamp(tx["blocktime"])
            
            # Check if this is a CoinJoin
            cj_score = self._calculate_coinjoin_score(tx)
            is_coinjoin = cj_score >= self.COINJOIN_THRESHOLD

            current_cj_count = cj_count
            coinjoin_protocol = "none"
            anonymity_set = 0

            if is_coinjoin:
                current_cj_count += 1
                coinjoin_txids.add(current_txid)
                # Get CoinJoin details for confidence calculation
                coinjoin_protocol, anonymity_set = self._get_coinjoin_details(tx, cj_score)

            # Get input addresses for change detection
            input_addresses: Set[str] = set()
            for vin in tx.get("vin", []):
                if "prevout" in vin:
                    addr = vin["prevout"].get("scriptPubKey", {}).get("address")
                    if addr:
                        input_addresses.add(addr)

            # Detect change
            is_change, change_prob = self._detect_change_output(
                tx, input_addresses, current_vout, tracked_value
            )

            # Calculate cumulative confidence for this node
            # Start with previous confidence (or 1.0 if first node)
            prev_confidence = path[-1].cumulative_confidence if path else 1.0

            # Degrade confidence if this is a CoinJoin
            if is_coinjoin:
                current_confidence = self._calculate_coinjoin_confidence_degradation(
                    coinjoin_protocol, anonymity_set, prev_confidence
                )
            else:
                # Small degradation for each hop (chain analysis uncertainty)
                current_confidence = prev_confidence * 0.95

            # Create path node with cumulative confidence
            node = PathNode(
                txid=current_txid,
                vout=current_vout,
                value_sats=value_sats,
                address=address,
                block_height=block_height,
                block_time=block_time,
                is_coinjoin=is_coinjoin,
                coinjoin_score=cj_score,
                coinjoin_count_in_path=current_cj_count,
                coinjoin_protocol=coinjoin_protocol,
                anonymity_set_size=anonymity_set,
                depth=depth,
                is_change=is_change,
                change_probability=change_prob,
                cumulative_confidence=current_confidence
            )

            current_path = path + [node]

            # NEW: Check if confidence dropped below threshold (trail truly cold)
            if current_confidence < self.CONFIDENCE_COLD_THRESHOLD:
                conf_score, reasoning = self._calculate_path_confidence(current_path, start_value)
                reasoning.append(f"Trail confidence dropped to {current_confidence*100:.2f}% (below 5% threshold)")
                reasoning.append(f"Passed through {current_cj_count} CoinJoin(s) - trail is cold")

                destinations.append(ProbableDestination(
                    address=address or "unknown",
                    value_sats=value_sats,
                    confidence_score=conf_score,
                    confidence_level=self._get_confidence_level(conf_score),
                    path_length=len(current_path),
                    coinjoins_passed=current_cj_count,
                    trail_status=TrailStatus.COLD,
                    reasoning=reasoning,
                    path=current_path
                ))
                result.total_untraceable_sats += value_sats
                continue
            
            # Check if UTXO is unspent
            utxo_status = await self.rpc.get_tx_out(current_txid, current_vout)
            
            if utxo_status:
                # Unspent - this is a destination
                conf_score, reasoning = self._calculate_path_confidence(current_path, start_value)
                reasoning.append("UTXO is unspent (current holding)")
                
                destinations.append(ProbableDestination(
                    address=address or "unknown",
                    value_sats=value_sats,
                    confidence_score=conf_score,
                    confidence_level=self._get_confidence_level(conf_score),
                    path_length=len(current_path),
                    coinjoins_passed=current_cj_count,
                    trail_status=TrailStatus.DEAD_END,
                    reasoning=reasoning,
                    path=current_path
                ))
                result.total_traced_sats += value_sats
            else:
                # Spent - try to find where it went
                if electrs and address and not electrs_disabled:
                    spending_txid = await self._find_spending_tx(current_txid, current_vout, address)
                    
                    if spending_txid:
                        consecutive_electrs_failures = 0  # Reset on success
                        spending_tx = await self._get_transaction(spending_txid)
                        if spending_tx and isinstance(spending_tx, dict):
                            # Add all outputs of spending tx to queue
                            for out_idx, out in enumerate(spending_tx.get("vout", [])):
                                out_value = int(out.get("value", 0) * 100_000_000)
                                if (spending_txid, out_idx) not in visited:
                                    queue.append((
                                        spending_txid,
                                        out_idx,
                                        depth + 1,
                                        current_cj_count,
                                        current_path,
                                        out_value,
                                        current_confidence  # Pass cumulative confidence forward
                                    ))
                    else:
                        # Electrs lookup failed
                        consecutive_electrs_failures += 1
                        if consecutive_electrs_failures >= self.MAX_CONSECUTIVE_ELECTRS_FAILURES:
                            electrs_disabled = True
                            result.warnings.append(
                                f"Electrs disabled after {consecutive_electrs_failures} consecutive failures"
                            )
                        
                        # Spent but can't find spending tx
                        conf_score, reasoning = self._calculate_path_confidence(current_path, start_value)
                        reasoning.append("UTXO spent but spending transaction not found")
                        
                        destinations.append(ProbableDestination(
                            address=address or "unknown",
                            value_sats=value_sats,
                            confidence_score=conf_score * 0.3,
                            confidence_level=ConfidenceLevel.LOW,
                            path_length=len(current_path),
                            coinjoins_passed=current_cj_count,
                            trail_status=TrailStatus.LOST,
                            reasoning=reasoning,
                            path=current_path
                        ))
                else:
                    # No Electrs - can't follow
                    conf_score, reasoning = self._calculate_path_confidence(current_path, start_value)
                    reasoning.append("Cannot follow spent output (Electrs required)")
                    
                    destinations.append(ProbableDestination(
                        address=address or "unknown",
                        value_sats=value_sats,
                        confidence_score=conf_score * 0.5,
                        confidence_level=self._get_confidence_level(conf_score * 0.5),
                        path_length=len(current_path),
                        coinjoins_passed=current_cj_count,
                        trail_status=TrailStatus.LOST,
                        reasoning=reasoning,
                        path=current_path
                    ))
        
        # Sort destinations by confidence
        destinations.sort(key=lambda d: d.confidence_score, reverse=True)
        result.probable_destinations = destinations
        result.coinjoins_encountered = len(coinjoin_txids)
        
        # Check for Electrs failures during trace
        electrs_failures = getattr(self, '_electrs_failures', 0)
        if electrs_failures > 0:
            result.warnings.append(f"Electrs connection issues: {electrs_failures} lookup(s) failed - results may be incomplete")
            self._electrs_failures = 0  # Reset counter
        
        # Calculate overall privacy score
        result.overall_privacy_score = self._calculate_overall_privacy(result)
        result.privacy_rating = self._get_privacy_rating(result.overall_privacy_score)
        
        # Generate summary and recommendations
        result.summary = self._generate_summary(result)
        result.recommendations = self._generate_recommendations(result)
        
        result.execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return result
    
    def _calculate_overall_privacy(self, result: KYCTraceResult) -> float:
        """
        Calculate overall privacy score (0-100, higher = more private).

        CRITICAL CHANGES:
        - Removed path complexity bonus (hops without mixing provide NO privacy)
        - Made CoinJoin scoring dependent on anonymity set size, not just count
        - Penalize "lost trails" (Fulcrum failures shouldn't boost privacy scores)
        """
        if not result.probable_destinations:
            return 100.0  # Nothing traceable = maximum privacy

        score = 0.0

        # Factor 1: Proportion with truly cold trails (0-50 points)
        # Only count trails that went COLD (confidence < 5%), not just "lost"
        total = result.original_value_sats
        if total > 0:
            cold_trails = [d for d in result.probable_destinations if d.trail_status == TrailStatus.COLD]
            cold_value = sum(d.value_sats for d in cold_trails)
            cold_ratio = cold_value / total
            score += cold_ratio * 50

        # Factor 2: No high-confidence destinations (0-30 points)
        high_conf = [d for d in result.probable_destinations if d.confidence_level == ConfidenceLevel.HIGH]
        if not high_conf:
            score += 30
        elif len(high_conf) == 1:
            score += 10
        # If 2+ high confidence destinations, no bonus

        # Factor 3: CoinJoin quality scoring (0-20 points)
        # Look at the actual anonymity sets used, not just count
        if result.coinjoins_encountered >= 2:
            # Multiple CoinJoins is better
            # Check if any trails actually went cold
            if any(d.trail_status == TrailStatus.COLD for d in result.probable_destinations):
                score += 20  # Actually achieved cold trails
            else:
                score += 10  # CoinJoins used but trails still traceable
        elif result.coinjoins_encountered == 1:
            score += 5  # One CoinJoin is minimal privacy

        # REMOVED: Path complexity bonus - hop count without mixing is meaningless

        # Penalty: Penalize "lost" trails (these are Fulcrum failures, not privacy wins)
        lost_trails = [d for d in result.probable_destinations if d.trail_status == TrailStatus.LOST]
        if lost_trails:
            lost_value = sum(d.value_sats for d in lost_trails)
            lost_ratio = lost_value / total if total > 0 else 0
            # Don't penalize too harshly, but don't give full credit either
            # Reduce score by up to 10 points if all trails are "lost"
            score -= lost_ratio * 10

        return max(0.0, min(score, 100.0))
    
    def _get_privacy_rating(self, score: float) -> str:
        """
        Convert privacy score to rating.

        CRITICAL: Thresholds are now MORE CONSERVATIVE.
        Users need 2+ CoinJoins with cold trails to get "good" rating.
        """
        if score >= 70:
            return "good"  # Lowered from "excellent" - reserve for truly exceptional privacy
        elif score >= 50:
            return "moderate"  # Raised threshold
        elif score >= 30:
            return "poor"  # Raised threshold
        else:
            return "very_poor"
    
    def _generate_summary(self, result: KYCTraceResult) -> str:
        """Generate human-readable summary with appropriate caveats."""
        high_conf = [d for d in result.probable_destinations if d.confidence_level == ConfidenceLevel.HIGH]
        med_conf = [d for d in result.probable_destinations if d.confidence_level == ConfidenceLevel.MEDIUM]
        cold_trails = [d for d in result.probable_destinations if d.trail_status == TrailStatus.COLD]

        if result.overall_privacy_score >= 70:
            return f"Good privacy detected. {len(cold_trails)} trail(s) went cold after CoinJoins. Found {len(high_conf)} high-confidence destination(s). WARNING: This tool cannot detect all attacks."
        elif result.overall_privacy_score >= 50:
            return f"Moderate privacy. Some trails obscured but {len(high_conf)} high-confidence and {len(med_conf)} medium-confidence destination(s) remain traceable."
        elif result.overall_privacy_score >= 30:
            return f"Poor privacy. Your funds can be traced with reasonable confidence to {len(high_conf)} address(es). Consider CoinJoin."
        else:
            return f"Very poor privacy. Your funds are easily traceable to {len(high_conf)} address(es) with high confidence. CRITICAL: Use CoinJoin immediately."
    
    def _categorize_risks(self, destinations: List[ProbableDestination], original_value: int) -> Dict:
        """
        Categorize findings into risk levels: CRITICAL, MEDIUM, POSITIVE.

        Args:
            destinations: List of probable destinations from trace
            original_value: Original withdrawal value in sats

        Returns:
            Dictionary with 'critical', 'medium', and 'positive' risk arrays
        """
        critical_risks = []
        medium_risks = []
        positive_factors = []

        # Check for exchange connections (CRITICAL)
        for dest in destinations:
            if not dest.address:
                continue

            entity_info = identify_entity(dest.address)
            if entity_info:
                # Found a known entity
                if entity_info.entity_type == "exchange":
                    critical_risks.append({
                        'type': 'exchange_connection',
                        'severity': 'CRITICAL',
                        'description': f"Destination is {entity_info.name} {entity_info.emoji}",
                        'detail': f"Address {dest.address[:10]}... is linked to {entity_info.name} ({entity_info.description})",
                        'address': dest.address,
                        'entity_name': entity_info.name,
                        'entity_type': entity_info.entity_type,
                        'confidence': dest.confidence_score,
                        'value_btc': dest.value_btc,
                        'recommendation': 'DO NOT spend directly to this address - use CoinJoin first'
                    })
                elif entity_info.entity_type in ["darknet_market", "gambling"]:
                    critical_risks.append({
                        'type': 'high_risk_entity',
                        'severity': 'CRITICAL',
                        'description': f"Connection to {entity_info.entity_type}: {entity_info.name}",
                        'detail': entity_info.description,
                        'address': dest.address,
                        'entity_name': entity_info.name,
                        'entity_type': entity_info.entity_type,
                        'confidence': dest.confidence_score,
                        'value_btc': dest.value_btc,
                        'recommendation': 'Extreme caution - this may attract regulatory attention'
                    })

        # Check for direct paths (no CoinJoins) - MEDIUM RISK
        for dest in destinations:
            if dest.coinjoins_passed == 0 and dest.confidence_level in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM]:
                value_percentage = (dest.value_sats / original_value * 100) if original_value > 0 else 0
                medium_risks.append({
                    'type': 'direct_path',
                    'severity': 'MEDIUM',
                    'description': 'Direct spending path exists (no mixing layer)',
                    'detail': f"Address {dest.address[:10] if dest.address else 'unknown'}... reachable in {dest.path_length} hop(s) with no CoinJoins",
                    'hops': dest.path_length,
                    'confidence': dest.confidence_score,
                    'value_percentage': round(value_percentage, 1),
                    'recommendation': 'Consider using CoinJoin before further transactions'
                })

        # Check for high-confidence unspent UTXOs - MEDIUM RISK
        unspent_high_conf = [d for d in destinations
                            if d.trail_status == TrailStatus.DEAD_END
                            and d.confidence_level == ConfidenceLevel.HIGH]
        if unspent_high_conf:
            total_value = sum(d.value_sats for d in unspent_high_conf)
            medium_risks.append({
                'type': 'high_confidence_utxos',
                'severity': 'MEDIUM',
                'description': f'{len(unspent_high_conf)} unspent UTXO(s) with high traceability',
                'detail': f"Total value: {total_value / 100_000_000:.8f} BTC easily linkable to your KYC identity",
                'count': len(unspent_high_conf),
                'total_value_btc': total_value / 100_000_000,
                'recommendation': 'Avoid consolidating these UTXOs without mixing first'
            })

        # Positive factors
        total_cj = sum(d.coinjoins_passed for d in destinations)
        if total_cj > 0:
            # Count unique CoinJoins (not total passes)
            unique_cj_count = len(set(
                node.txid for dest in destinations
                for node in dest.path
                if node.is_coinjoin
            ))

            positive_factors.append({
                'type': 'coinjoin_detected',
                'description': f'{unique_cj_count} CoinJoin transaction{"s" if unique_cj_count > 1 else ""} provide cover',
                'detail': f'Total {total_cj} CoinJoin passage{"s" if total_cj > 1 else ""} across all paths',
                'unique_coinjoins': unique_cj_count,
                'total_passages': total_cj,
                'impact': 'Reduces traceability significantly'
            })

        # Check for cold trails - POSITIVE
        cold_trails = [d for d in destinations if d.trail_status == TrailStatus.COLD]
        if cold_trails:
            cold_value = sum(d.value_sats for d in cold_trails)
            cold_percentage = (cold_value / original_value * 100) if original_value > 0 else 0
            positive_factors.append({
                'type': 'cold_trails',
                'description': f'{len(cold_trails)} trail(s) went cold (confidence < 5%)',
                'detail': f'{cold_percentage:.1f}% of original value is effectively untraceable',
                'count': len(cold_trails),
                'value_percentage': round(cold_percentage, 1),
                'value_btc': cold_value / 100_000_000,
                'impact': 'Strong privacy protection'
            })

        # Check for diverse path lengths - POSITIVE (if includes mixing)
        if destinations and total_cj > 0:
            avg_path_length = sum(d.path_length for d in destinations) / len(destinations)
            if avg_path_length > 3:
                positive_factors.append({
                    'type': 'path_complexity',
                    'description': f'Average path length: {avg_path_length:.1f} hops with mixing',
                    'detail': 'Longer paths with CoinJoins increase privacy',
                    'average_hops': round(avg_path_length, 1),
                    'impact': 'Moderate privacy improvement'
                })

        return {
            'critical': critical_risks,
            'medium': medium_risks,
            'positive': positive_factors,
            'summary': {
                'critical_count': len(critical_risks),
                'medium_count': len(medium_risks),
                'positive_count': len(positive_factors),
                'overall_risk_level': 'CRITICAL' if critical_risks else ('MEDIUM' if medium_risks else 'LOW')
            }
        }

    def _prioritize_recommendations(self, destinations: List[ProbableDestination], risk_analysis: Dict, result: KYCTraceResult) -> List[Dict]:
        """
        Prioritize recommendations as URGENT/IMPORTANT/BEST_PRACTICE.

        Args:
            destinations: List of probable destinations
            risk_analysis: Output from _categorize_risks
            result: Full KYCTraceResult for context

        Returns:
            List of prioritized recommendations
        """
        urgent = []
        important = []
        best_practice = []

        # URGENT: Exchange connections
        exchange_risks = [r for r in risk_analysis['critical'] if r['type'] == 'exchange_connection']
        if exchange_risks:
            for risk in exchange_risks:
                urgent.append({
                    'priority': 'URGENT',
                    'category': 'exchange_exposure',
                    'action': f"Address {risk['address'][:10]}... is linked to {risk['entity_name']}",
                    'recommendation': 'Use CoinJoin (Whirlpool/Wasabi) or atomic swap before ANY further transactions from this address',
                    'rationale': f"{risk['entity_name']} has your KYC info and can track this address",
                    'expected_improvement': '+30-40 privacy points',
                    'difficulty': 'MODERATE',
                    'time_estimate': '1-2 hours (CoinJoin mixing)',
                    'tools': ['Samourai Whirlpool', 'Wasabi Wallet', 'JoinMarket']
                })

        # URGENT: High-risk entities (darknet, gambling)
        high_risk_entities = [r for r in risk_analysis['critical'] if r['type'] == 'high_risk_entity']
        if high_risk_entities:
            for risk in high_risk_entities:
                urgent.append({
                    'priority': 'URGENT',
                    'category': 'high_risk_entity',
                    'action': f"Connection to {risk['entity_type']}: {risk['entity_name']}",
                    'recommendation': 'DO NOT link this to other wallets. Consider this chain permanently tainted.',
                    'rationale': 'Association with high-risk services may attract law enforcement attention',
                    'expected_improvement': 'Risk mitigation (not privacy improvement)',
                    'difficulty': 'N/A',
                    'time_estimate': 'Immediate action required',
                    'tools': ['Consult legal counsel']
                })

        # URGENT: No CoinJoins at all
        if result.coinjoins_encountered == 0:
            high_conf_count = len([d for d in destinations if d.confidence_level == ConfidenceLevel.HIGH])
            urgent.append({
                'priority': 'URGENT',
                'category': 'no_mixing',
                'action': f'No CoinJoins detected - {high_conf_count} destination(s) are trivially traceable',
                'recommendation': 'Implement CoinJoin mixing BEFORE spending these funds further',
                'rationale': 'Your funds are completely transparent on the blockchain',
                'expected_improvement': '+40-60 privacy points',
                'difficulty': 'MODERATE',
                'time_estimate': '2-4 hours (learn + mix)',
                'tools': ['Samourai Whirlpool', 'Wasabi Wallet', 'JoinMarket']
            })

        # IMPORTANT: Direct paths exist
        direct_path_risks = [r for r in risk_analysis['medium'] if r['type'] == 'direct_path']
        if direct_path_risks and len(direct_path_risks) >= 2:
            total_percentage = sum(r['value_percentage'] for r in direct_path_risks)
            important.append({
                'priority': 'IMPORTANT',
                'category': 'direct_paths',
                'action': f'{len(direct_path_risks)} destination(s) reachable via direct paths ({total_percentage:.1f}% of funds)',
                'recommendation': 'Use CoinJoin for future transactions from these addresses',
                'rationale': 'Direct paths make blockchain analysis trivial',
                'expected_improvement': '+20-30 privacy points',
                'difficulty': 'MODERATE',
                'time_estimate': '1-2 hours per mixing round',
                'tools': ['Samourai Whirlpool', 'Wasabi Wallet']
            })

        # IMPORTANT: High confidence unspent UTXOs
        high_conf_utxo_risks = [r for r in risk_analysis['medium'] if r['type'] == 'high_confidence_utxos']
        if high_conf_utxo_risks:
            for risk in high_conf_utxo_risks:
                important.append({
                    'priority': 'IMPORTANT',
                    'category': 'utxo_management',
                    'action': f"Avoid consolidating {risk['count']} high-confidence UTXO(s)",
                    'recommendation': 'Keep UTXOs separate or mix before consolidation',
                    'rationale': 'Consolidation creates common-input-ownership heuristic',
                    'expected_improvement': '+15-20 privacy points',
                    'difficulty': 'EASY',
                    'time_estimate': 'Ongoing practice',
                    'tools': ['UTXO coin control in wallet']
                })

        # IMPORTANT: Address reuse detection
        all_addresses = []
        for dest in destinations:
            for node in dest.path:
                if node.address:
                    all_addresses.append(node.address)

        if len(all_addresses) != len(set(all_addresses)):
            important.append({
                'priority': 'IMPORTANT',
                'category': 'address_reuse',
                'action': 'Address reuse detected in transaction history',
                'recommendation': 'Always use a fresh address for each transaction',
                'rationale': 'Address reuse links all transactions together',
                'expected_improvement': '+10-15 privacy points',
                'difficulty': 'EASY',
                'time_estimate': 'Immediate (change wallet settings)',
                'tools': ['HD wallet with auto-generation']
            })

        # BEST PRACTICE: Time-based privacy
        unspent_destinations = [d for d in destinations if d.trail_status == TrailStatus.DEAD_END]
        if unspent_destinations:
            best_practice.append({
                'priority': 'BEST_PRACTICE',
                'category': 'time_privacy',
                'action': 'Wait 30+ days before spending aged coins',
                'recommendation': 'Let coins "cool off" before next transaction',
                'rationale': 'Time increases anonymity set as blockchain grows',
                'expected_improvement': '+5-10 privacy points',
                'difficulty': 'EASY',
                'time_estimate': 'Passive (just wait)',
                'tools': ['Calendar reminder']
            })

        # BEST PRACTICE: Network privacy
        best_practice.append({
            'priority': 'BEST_PRACTICE',
            'category': 'network_privacy',
            'action': 'Use Tor when broadcasting transactions',
            'recommendation': 'Route Bitcoin Core through Tor or use Tor-enabled wallet',
            'rationale': 'Prevents IP address correlation with transactions',
            'expected_improvement': '+5 privacy points',
            'difficulty': 'EASY',
            'time_estimate': '15-30 minutes setup',
            'tools': ['Tor Browser', 'Whonix', 'Tails OS']
        })

        # BEST PRACTICE: Separate wallets
        if len(destinations) > 3:
            best_practice.append({
                'priority': 'BEST_PRACTICE',
                'category': 'wallet_separation',
                'action': 'Use separate wallets for different purposes',
                'recommendation': 'Keep "savings", "spending", and "identity-linked" wallets separate',
                'rationale': 'Prevents cross-contamination of transaction histories',
                'expected_improvement': '+10-15 privacy points',
                'difficulty': 'EASY',
                'time_estimate': '30 minutes (create new wallets)',
                'tools': ['Multiple HD wallet instances']
            })

        # BEST PRACTICE: Avoid dust
        best_practice.append({
            'priority': 'BEST_PRACTICE',
            'category': 'dust_attacks',
            'action': 'Enable "Do Not Spend Dust" in wallet settings',
            'recommendation': 'Reject or freeze dust transactions to prevent tracking',
            'rationale': 'Dust attacks send tiny amounts to track wallet activity',
            'expected_improvement': '+3-5 privacy points',
            'difficulty': 'EASY',
            'time_estimate': '5 minutes',
            'tools': ['Samourai "Do Not Spend"', 'Sparrow coin control']
        })

        # Combine and return in priority order
        return urgent + important + best_practice

    def _generate_recommendations(self, result: KYCTraceResult) -> List[str]:
        """Generate privacy improvement recommendations with critical warnings."""
        recs = []

        # CRITICAL WARNINGS FIRST
        recs.append("CRITICAL: This is heuristic analysis only - do NOT rely on this for operational security")
        recs.append("WARNING: This tool cannot detect timing correlation, Wasabi 2.0, network analysis, or sophisticated attacks")

        if result.coinjoins_encountered == 0:
            recs.append("URGENT: No CoinJoins detected - your funds are trivially traceable")
            recs.append("Consider using CoinJoin (Whirlpool, Wasabi 2.0, or JoinMarket) immediately")

        high_conf = [d for d in result.probable_destinations if d.confidence_level == ConfidenceLevel.HIGH]
        if high_conf:
            recs.append(f"You have {len(high_conf)} easily traceable destination(s) - these can be linked to your KYC identity")
        
        if result.overall_privacy_score < 60:
            recs.append("Avoid consolidating UTXOs from different sources without mixing first")
            recs.append("Use a new address for each transaction to prevent address clustering")
        
        if not result.electrs_enabled:
            recs.append("Enable Electrs for more accurate forward tracing analysis")
        
        # Check for address reuse in paths
        all_addresses = []
        for dest in result.probable_destinations:
            for node in dest.path:
                if node.address:
                    all_addresses.append(node.address)
        
        if len(all_addresses) != len(set(all_addresses)):
            recs.append("Address reuse detected in your transaction history - this hurts privacy")
        
        if not recs:
            recs.append("Your privacy practices look good! Continue using CoinJoin and avoiding address reuse")
        
        return recs
    
    @classmethod
    def get_depth_presets(cls) -> Dict:
        """Get available depth presets for UI."""
        return cls.DEPTH_PRESETS


# Singleton
_kyc_tracer_instance: Optional[KYCPrivacyTracer] = None


def get_kyc_tracer() -> KYCPrivacyTracer:
    """Get or create KYC tracer instance."""
    global _kyc_tracer_instance
    if _kyc_tracer_instance is None:
        _kyc_tracer_instance = KYCPrivacyTracer()
    return _kyc_tracer_instance
