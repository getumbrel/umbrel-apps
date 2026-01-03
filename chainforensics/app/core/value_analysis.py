"""
ChainForensics - Value Fingerprinting and Subset Sum Analysis Module

Analyzes transaction amounts for privacy risks:
- Unique/fingerprintable amounts
- Subset sum leaks (input structure revelation)
- Amount correlation across CoinJoins
- Dust tracking detection
- Round number analysis

CRITICAL SECURITY WARNINGS:
- Amount correlation is a powerful deanonymization technique
- Unique amounts can be tracked across the entire blockchain
- Subset sum analysis can reveal input-output mappings
- This is HEURISTIC ANALYSIS ONLY

References:
- "An Analysis of Anonymity in Bitcoin Using P2P Network Traffic" (Koshy et al., 2014)
- "Deanonymisation of Clients in Bitcoin P2P Network" (Biryukov et al., 2014)

Author: ChainForensics Team
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
import itertools

logger = logging.getLogger("chainforensics.value_analysis")


@dataclass
class AmountUniqueness:
    """Result of amount uniqueness analysis."""
    amount_sats: int
    amount_btc: float
    is_unique: bool
    uniqueness_score: float  # 0.0-1.0 (higher = more unique/fingerprintable)
    precision_decimals: int  # Number of decimal places
    is_round: bool
    score_impact: int  # Privacy score impact (-15 to +5)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "amount_sats": self.amount_sats,
            "amount_btc": self.amount_btc,
            "is_unique": self.is_unique,
            "uniqueness_score": round(self.uniqueness_score, 3),
            "uniqueness_percent": f"{self.uniqueness_score * 100:.1f}%",
            "precision_decimals": self.precision_decimals,
            "is_round": self.is_round,
            "score_impact": self.score_impact,
            "warnings": self.warnings,
            "recommendations": self.recommendations
        }


@dataclass
class SubsetSumLeak:
    """Detected subset sum leak in a transaction."""
    input_indices: List[int]
    output_index: int
    input_sum_sats: int
    output_value_sats: int
    confidence: float  # 0.0-1.0
    explanation: str

    def to_dict(self) -> Dict:
        return {
            "input_indices": self.input_indices,
            "output_index": self.output_index,
            "input_sum_sats": self.input_sum_sats,
            "input_sum_btc": self.input_sum_sats / 100_000_000,
            "output_value_sats": self.output_value_sats,
            "output_value_btc": self.output_value_sats / 100_000_000,
            "confidence": round(self.confidence, 3),
            "confidence_percent": f"{self.confidence * 100:.1f}%",
            "explanation": self.explanation
        }


@dataclass
class SubsetSumAnalysis:
    """Complete subset sum analysis for a transaction."""
    has_leaks: bool
    leak_count: int
    leaks: List[SubsetSumLeak] = field(default_factory=list)
    score_impact: int = 0  # Privacy score impact (-20 to 0)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "has_leaks": self.has_leaks,
            "leak_count": self.leak_count,
            "leaks": [leak.to_dict() for leak in self.leaks],
            "score_impact": self.score_impact,
            "warnings": self.warnings,
            "recommendations": self.recommendations
        }


@dataclass
class AmountCorrelation:
    """Amount correlation analysis across CoinJoin or chain."""
    amount_before_sats: int
    amount_after_sats: int
    correlation_score: float  # 0.0-1.0 (higher = more correlated)
    is_exact_match: bool
    is_close_match: bool  # Within fee tolerance
    score_impact: int  # Privacy score impact (-20 to 0)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "amount_before_sats": self.amount_before_sats,
            "amount_before_btc": self.amount_before_sats / 100_000_000,
            "amount_after_sats": self.amount_after_sats,
            "amount_after_btc": self.amount_after_sats / 100_000_000,
            "correlation_score": round(self.correlation_score, 3),
            "correlation_percent": f"{self.correlation_score * 100:.1f}%",
            "is_exact_match": self.is_exact_match,
            "is_close_match": self.is_close_match,
            "score_impact": self.score_impact,
            "warnings": self.warnings
        }


@dataclass
class DustDetection:
    """Dust output detection (potential tracking pixels)."""
    output_index: int
    value_sats: int
    is_dust: bool
    dust_threshold_sats: int
    is_tracking_pixel: bool  # High confidence it's a tracker
    score_impact: int  # Privacy score impact (-10 to 0)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "output_index": self.output_index,
            "value_sats": self.value_sats,
            "value_btc": self.value_sats / 100_000_000,
            "is_dust": self.is_dust,
            "dust_threshold_sats": self.dust_threshold_sats,
            "is_tracking_pixel": self.is_tracking_pixel,
            "score_impact": self.score_impact,
            "warnings": self.warnings
        }


class ValueAnalyzer:
    """
    Analyzes Bitcoin transaction amounts for privacy risks.

    Key Insights:
    - Amounts with high precision (many decimals) are fingerprintable
    - Round amounts blend in better but may indicate exchanges
    - Subset sum can reveal input-output mappings
    - Amount correlation across CoinJoins defeats mixing
    - Dust outputs can be tracking pixels
    """

    # Dust threshold (below this is considered dust)
    DUST_THRESHOLD_SATS = 1000  # ~$0.30 at $30k BTC

    # Tracking pixel threshold (extremely small amounts likely to be trackers)
    TRACKING_PIXEL_THRESHOLD_SATS = 546  # Bitcoin dust limit

    # Fee tolerance for correlation analysis (typical fee range)
    FEE_TOLERANCE_SATS = 50000  # 0.0005 BTC (~$15 at $30k)

    # Precision thresholds
    LOW_PRECISION_DECIMALS = 3  # 0.001 BTC
    MEDIUM_PRECISION_DECIMALS = 5  # 0.00001 BTC
    HIGH_PRECISION_DECIMALS = 7  # Very fingerprintable

    def __init__(self):
        pass

    def is_amount_unique(
        self,
        amount_sats: int,
        tolerance_sats: int = 1000
    ) -> AmountUniqueness:
        """
        Check if an amount is unique/fingerprintable.

        Args:
            amount_sats: Amount in satoshis
            tolerance_sats: Tolerance for rounding (default 1000 = 0.00001 BTC)

        Returns:
            AmountUniqueness with assessment

        Uniqueness Factors:
        - High precision (many decimal places) = more unique
        - Round numbers = less unique (common)
        - Typical exchange amounts = less unique
        - Odd/specific amounts = more unique
        """
        amount_btc = amount_sats / 100_000_000

        # Calculate precision (number of significant decimal places)
        amount_str = f"{amount_btc:.8f}".rstrip('0')
        if '.' in amount_str:
            decimals = len(amount_str.split('.')[1])
        else:
            decimals = 0

        # Check if round number
        is_round = amount_sats % 100000 == 0  # Round to 0.001 BTC

        warnings = []
        recommendations = []
        score_impact = 0

        # Calculate uniqueness score
        uniqueness_score = 0.0

        # Factor 1: Precision (higher precision = more unique)
        if decimals >= self.HIGH_PRECISION_DECIMALS:
            uniqueness_score += 0.7
            warnings.append(f"CRITICAL: Amount has {decimals} decimal places - highly fingerprintable")
            warnings.append(f"This exact amount ({amount_btc:.8f} BTC) can be tracked across the blockchain")
            score_impact -= 15
            recommendations.append("Use round amounts (0.001, 0.01, 0.1 BTC) after mixing")
        elif decimals >= self.MEDIUM_PRECISION_DECIMALS:
            uniqueness_score += 0.4
            warnings.append(f"WARNING: Amount has {decimals} decimal places - fingerprintable")
            score_impact -= 10
            recommendations.append("Prefer rounder amounts for better privacy")
        elif decimals >= self.LOW_PRECISION_DECIMALS:
            uniqueness_score += 0.2
            score_impact -= 5

        # Factor 2: Round number (less unique is better)
        if is_round:
            uniqueness_score -= 0.3
            score_impact += 5
            recommendations.append("Round amount provides some privacy benefit")

        # Factor 3: Common exchange amounts (less unique)
        common_amounts = [
            100000000,    # 1.0 BTC
            50000000,     # 0.5 BTC
            10000000,     # 0.1 BTC
            5000000,      # 0.05 BTC
            1000000,      # 0.01 BTC
            100000,       # 0.001 BTC
        ]

        for common in common_amounts:
            if abs(amount_sats - common) < tolerance_sats:
                uniqueness_score -= 0.2
                break

        # Clamp to [0, 1]
        uniqueness_score = max(0.0, min(1.0, uniqueness_score))

        is_unique = uniqueness_score > 0.5

        if is_unique:
            warnings.append("Amount is highly unique - can be tracked")
        else:
            recommendations.append("Amount has reasonable privacy characteristics")

        return AmountUniqueness(
            amount_sats=amount_sats,
            amount_btc=amount_btc,
            is_unique=is_unique,
            uniqueness_score=uniqueness_score,
            precision_decimals=decimals,
            is_round=is_round,
            score_impact=score_impact,
            warnings=warnings,
            recommendations=recommendations
        )

    def detect_subset_sum_leak(
        self,
        inputs: List[Dict],
        outputs: List[Dict],
        max_subset_size: int = 3
    ) -> SubsetSumAnalysis:
        """
        Detect if output amounts reveal input structure (subset sum problem).

        Args:
            inputs: List of input dicts with 'value_sats'
            outputs: List of output dicts with 'value_sats'
            max_subset_size: Maximum input subset size to check

        Returns:
            SubsetSumAnalysis with detected leaks

        Leak Detection:
        If output amount matches sum of specific inputs (within fee tolerance),
        this reveals which inputs were used for that output.

        Example Leak:
        Inputs: 0.3 BTC, 0.2 BTC
        Outputs: 0.3 BTC (payment), 0.19... BTC (change)
        → The 0.3 BTC output reveals input[0] was used for payment
        """
        leaks = []
        warnings = []
        recommendations = []

        if not inputs or not outputs:
            return SubsetSumAnalysis(
                has_leaks=False,
                leak_count=0,
                leaks=[],
                warnings=["Insufficient input/output data"]
            )

        # Extract values
        input_values = []
        for i, inp in enumerate(inputs):
            value = inp.get('value_sats', 0)
            if value > 0:
                input_values.append((i, value))

        output_values = []
        for i, out in enumerate(outputs):
            value = out.get('value_sats', 0)
            if value > 0:
                output_values.append((i, value))

        # For each output, check if it matches subset sum of inputs
        for out_idx, out_value in output_values:
            # Try all subset sizes from 1 to max_subset_size
            for subset_size in range(1, min(max_subset_size + 1, len(input_values) + 1)):
                # Generate all subsets of this size
                for subset_indices in itertools.combinations(range(len(input_values)), subset_size):
                    subset_sum = sum(input_values[idx][1] for idx in subset_indices)

                    # Check if subset sum matches output (within fee tolerance)
                    diff = abs(subset_sum - out_value)

                    if diff < self.FEE_TOLERANCE_SATS:
                        # Potential leak detected!
                        confidence = 1.0 - (diff / self.FEE_TOLERANCE_SATS)

                        input_idx_list = [input_values[idx][0] for idx in subset_indices]

                        if diff == 0:
                            explanation = f"Output {out_idx} ({out_value} sats) EXACTLY matches sum of input(s) {input_idx_list}"
                        else:
                            explanation = f"Output {out_idx} ({out_value} sats) matches sum of input(s) {input_idx_list} within fee ({diff} sats difference)"

                        leaks.append(SubsetSumLeak(
                            input_indices=input_idx_list,
                            output_index=out_idx,
                            input_sum_sats=subset_sum,
                            output_value_sats=out_value,
                            confidence=confidence,
                            explanation=explanation
                        ))

                        # Only report the best match for each output
                        break

        # Remove duplicate leaks (same output matched by multiple subsets)
        seen_outputs = set()
        unique_leaks = []
        for leak in leaks:
            if leak.output_index not in seen_outputs:
                unique_leaks.append(leak)
                seen_outputs.add(leak.output_index)

        has_leaks = len(unique_leaks) > 0
        score_impact = 0

        if has_leaks:
            score_impact = min(len(unique_leaks) * -15, -30)  # Up to -30 points
            warnings.append(f"CRITICAL: {len(unique_leaks)} subset sum leak(s) detected")
            warnings.append("Output amounts reveal input structure - input-output mapping is exposed")
            recommendations.append("Use CoinJoin to break amount correlation")
            recommendations.append("Avoid sending amounts that match input subsets")
        else:
            recommendations.append("No obvious subset sum leaks detected")

        return SubsetSumAnalysis(
            has_leaks=has_leaks,
            leak_count=len(unique_leaks),
            leaks=unique_leaks,
            score_impact=score_impact,
            warnings=warnings,
            recommendations=recommendations
        )

    def calculate_amount_correlation(
        self,
        amount_before_sats: int,
        amount_after_sats: int,
        is_post_coinjoin: bool = False
    ) -> AmountCorrelation:
        """
        Check if amounts correlate across a transaction chain or CoinJoin.

        Args:
            amount_before_sats: Amount before (input or pre-mix)
            amount_after_sats: Amount after (output or post-mix)
            is_post_coinjoin: If True, applies stricter correlation checks

        Returns:
            AmountCorrelation with assessment

        Risk Model:
        - Exact match across CoinJoin: 1.0 correlation (defeats mixing)
        - Match within fee tolerance: 0.8-0.9 correlation (very high risk)
        - 10% difference: 0.5 correlation (moderate risk)
        - 30%+ difference: Low correlation
        """
        warnings = []
        score_impact = 0

        diff = abs(amount_before_sats - amount_after_sats)
        ratio = amount_after_sats / max(amount_before_sats, 1)

        # Check for exact match
        is_exact_match = (diff == 0)

        # Check for close match (within fee tolerance)
        is_close_match = (diff < self.FEE_TOLERANCE_SATS and diff > 0)

        # Calculate correlation score
        if is_exact_match:
            correlation_score = 1.0
            score_impact = -20
            warnings.append("CRITICAL: Exact amount match detected")
            if is_post_coinjoin:
                warnings.append("Amount correlation defeats CoinJoin anonymity")
        elif is_close_match:
            correlation_score = 0.9
            score_impact = -18
            warnings.append(f"CRITICAL: Amounts match within fee ({diff} sats)")
            if is_post_coinjoin:
                warnings.append("Near-exact amount correlation defeats CoinJoin")
        elif ratio > 0.9 and ratio < 1.1:
            # Within 10%
            correlation_score = 0.7
            score_impact = -12
            warnings.append(f"WARNING: Amounts are very similar ({ratio*100:.1f}% match)")
        elif ratio > 0.7 and ratio < 1.3:
            # Within 30%
            correlation_score = 0.4
            score_impact = -5
            warnings.append(f"Amounts are somewhat similar ({ratio*100:.1f}% match)")
        else:
            # Significant difference
            correlation_score = 0.2
            score_impact = 0

        return AmountCorrelation(
            amount_before_sats=amount_before_sats,
            amount_after_sats=amount_after_sats,
            correlation_score=correlation_score,
            is_exact_match=is_exact_match,
            is_close_match=is_close_match,
            score_impact=score_impact,
            warnings=warnings
        )

    def detect_dust_amounts(
        self,
        outputs: List[Dict]
    ) -> List[DustDetection]:
        """
        Identify dust outputs that may be tracking pixels.

        Args:
            outputs: List of output dicts with 'value_sats'

        Returns:
            List of DustDetection results

        Dust Attack:
        Attackers send tiny amounts (dust) to many addresses.
        When the victim spends this dust with their main coins,
        it links their addresses together.
        """
        detections = []

        for idx, output in enumerate(outputs):
            value_sats = output.get('value_sats', 0)

            if value_sats <= 0:
                continue

            is_dust = value_sats < self.DUST_THRESHOLD_SATS
            is_tracking_pixel = value_sats <= self.TRACKING_PIXEL_THRESHOLD_SATS

            warnings = []
            score_impact = 0

            if is_tracking_pixel:
                warnings.append(f"CRITICAL: Output {idx} is likely a tracking pixel ({value_sats} sats)")
                warnings.append("Do NOT spend this with other coins - it will link your addresses")
                score_impact = -10
            elif is_dust:
                warnings.append(f"WARNING: Output {idx} is dust ({value_sats} sats)")
                warnings.append("May be a tracking attempt - use caution when spending")
                score_impact = -5

            if is_dust:
                detections.append(DustDetection(
                    output_index=idx,
                    value_sats=value_sats,
                    is_dust=is_dust,
                    dust_threshold_sats=self.DUST_THRESHOLD_SATS,
                    is_tracking_pixel=is_tracking_pixel,
                    score_impact=score_impact,
                    warnings=warnings
                ))

        return detections


# Singleton instance
_value_analyzer: Optional[ValueAnalyzer] = None


def get_value_analyzer() -> ValueAnalyzer:
    """Get or create the value analyzer singleton."""
    global _value_analyzer
    if _value_analyzer is None:
        _value_analyzer = ValueAnalyzer()
    return _value_analyzer
