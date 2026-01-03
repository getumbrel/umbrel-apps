"""
ChainForensics - Wallet Fingerprinting Module

Identifies wallet software through transaction patterns:
- Script type consistency (P2PKH, P2WPKH, P2SH, etc.)
- Output ordering patterns (BIP-69 vs random)
- Fee calculation strategies
- Change output position patterns
- nSequence and nLockTime usage

CRITICAL SECURITY WARNINGS:
- This is HEURISTIC ANALYSIS ONLY
- Wallet fingerprinting can link transactions from the same software/user
- Modern wallets may implement countermeasures
- False positives are possible

References:
- "Bitcoin Wallet Privacy" (Goldfeder et al.)
- BIP-69: Lexicographical Indexing of Transaction Inputs and Outputs
- "Wallet Fingerprinting: Privacy Analysis of Bitcoin Wallets" (Various)

Author: ChainForensics Team
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import Counter
import statistics

logger = logging.getLogger("chainforensics.wallet_fingerprint")


@dataclass
class ScriptTypePattern:
    """Analysis of script type usage patterns."""
    transactions_analyzed: int
    script_types_used: Dict[str, int]  # Script type -> count
    consistency_score: float  # 0.0-1.0 (higher = more consistent)
    dominant_type: Optional[str]
    is_consistent: bool
    score_impact: int  # Privacy score impact (-20 to +5)
    warnings: List[str] = field(default_factory=list)
    interpretation: str = ""

    def to_dict(self) -> Dict:
        return {
            "transactions_analyzed": self.transactions_analyzed,
            "script_types_used": self.script_types_used,
            "consistency_score": round(self.consistency_score, 3),
            "consistency_percent": f"{self.consistency_score * 100:.1f}%",
            "dominant_type": self.dominant_type,
            "is_consistent": self.is_consistent,
            "score_impact": self.score_impact,
            "warnings": self.warnings,
            "interpretation": self.interpretation
        }


@dataclass
class OutputOrderingPattern:
    """Analysis of output ordering (BIP-69 detection)."""
    transactions_analyzed: int
    bip69_compliant_count: int
    bip69_compliance_ratio: float
    is_likely_bip69: bool
    random_ordering_count: int
    pattern_detected: str  # "bip69", "random", "consistent_non_bip69", "unknown"
    score_impact: int  # Privacy score impact (-10 to 0)
    warnings: List[str] = field(default_factory=list)
    interpretation: str = ""

    def to_dict(self) -> Dict:
        return {
            "transactions_analyzed": self.transactions_analyzed,
            "bip69_compliant_count": self.bip69_compliant_count,
            "bip69_compliance_ratio": round(self.bip69_compliance_ratio, 3),
            "bip69_compliance_percent": f"{self.bip69_compliance_ratio * 100:.1f}%",
            "is_likely_bip69": self.is_likely_bip69,
            "random_ordering_count": self.random_ordering_count,
            "pattern_detected": self.pattern_detected,
            "score_impact": self.score_impact,
            "warnings": self.warnings,
            "interpretation": self.interpretation
        }


@dataclass
class FeePattern:
    """Analysis of fee calculation patterns."""
    transactions_analyzed: int
    fees_sats_per_vbyte: List[float]
    average_fee_rate: float
    fee_rate_stddev: float
    uses_round_fees: bool  # Always round sat/vB (1, 5, 10, 20, etc)
    fee_pattern: str  # "round", "precise", "variable", "unknown"
    score_impact: int  # Privacy score impact (-15 to 0)
    warnings: List[str] = field(default_factory=list)
    interpretation: str = ""

    def to_dict(self) -> Dict:
        return {
            "transactions_analyzed": self.transactions_analyzed,
            "average_fee_rate": round(self.average_fee_rate, 2),
            "fee_rate_stddev": round(self.fee_rate_stddev, 2),
            "uses_round_fees": self.uses_round_fees,
            "fee_pattern": self.fee_pattern,
            "score_impact": self.score_impact,
            "warnings": self.warnings,
            "interpretation": self.interpretation
        }


@dataclass
class ChangePositionPattern:
    """Analysis of change output position patterns."""
    transactions_analyzed: int
    change_positions: List[int]  # List of change position indices
    position_counter: Dict[int, int]  # Position -> count
    most_common_position: Optional[int]
    position_consistency: float  # 0.0-1.0
    always_last: bool
    always_first: bool
    is_consistent: bool
    score_impact: int  # Privacy score impact (-15 to 0)
    warnings: List[str] = field(default_factory=list)
    interpretation: str = ""

    def to_dict(self) -> Dict:
        return {
            "transactions_analyzed": self.transactions_analyzed,
            "most_common_position": self.most_common_position,
            "position_consistency": round(self.position_consistency, 3),
            "position_consistency_percent": f"{self.position_consistency * 100:.1f}%",
            "always_last": self.always_last,
            "always_first": self.always_first,
            "is_consistent": self.is_consistent,
            "score_impact": self.score_impact,
            "warnings": self.warnings,
            "interpretation": self.interpretation
        }


@dataclass
class WalletFingerprintResult:
    """Overall wallet fingerprint assessment."""
    transactions_analyzed: int
    fingerprint_strength: float  # 0.0-1.0 (how identifiable is this wallet?)
    detected_patterns: List[str]
    likely_wallet_software: Optional[str]  # Guess at wallet type
    confidence: float  # 0.0-1.0 confidence in wallet identification
    total_score_impact: int  # Total privacy score impact (-60 to 0)
    script_type_pattern: Optional[ScriptTypePattern] = None
    output_ordering: Optional[OutputOrderingPattern] = None
    fee_pattern: Optional[FeePattern] = None
    change_position: Optional[ChangePositionPattern] = None
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        result = {
            "transactions_analyzed": self.transactions_analyzed,
            "fingerprint_strength": round(self.fingerprint_strength, 3),
            "fingerprint_strength_percent": f"{self.fingerprint_strength * 100:.1f}%",
            "detected_patterns": self.detected_patterns,
            "likely_wallet_software": self.likely_wallet_software,
            "confidence": round(self.confidence, 3),
            "confidence_percent": f"{self.confidence * 100:.1f}%",
            "total_score_impact": self.total_score_impact,
            "warnings": self.warnings,
            "recommendations": self.recommendations
        }

        if self.script_type_pattern:
            result["script_type_pattern"] = self.script_type_pattern.to_dict()
        if self.output_ordering:
            result["output_ordering"] = self.output_ordering.to_dict()
        if self.fee_pattern:
            result["fee_pattern"] = self.fee_pattern.to_dict()
        if self.change_position:
            result["change_position"] = self.change_position.to_dict()

        return result


class WalletFingerprinter:
    """
    Identifies wallet software through transaction patterns.

    Privacy Impact:
    - Consistent patterns allow linking transactions
    - Wallet fingerprints can reveal user identity
    - Mixing wallet types improves privacy
    """

    # Known wallet patterns (simplified - real implementation would be more comprehensive)
    KNOWN_WALLETS = {
        "electrum": {
            "script_types": ["p2wpkh", "p2sh-p2wpkh"],
            "uses_bip69": False,
            "typical_fees": "variable",
            "change_position": "random"
        },
        "wasabi": {
            "script_types": ["p2wpkh"],
            "uses_bip69": True,
            "typical_fees": "round",
            "change_position": "random"
        },
        "samourai": {
            "script_types": ["p2wpkh", "p2pkh"],
            "uses_bip69": False,
            "typical_fees": "variable",
            "change_position": "first"  # Often change is first output
        },
        "bitcoin_core": {
            "script_types": ["p2wpkh", "p2pkh", "p2sh"],
            "uses_bip69": False,
            "typical_fees": "variable",
            "change_position": "random"
        },
        "ledger": {
            "script_types": ["p2sh-p2wpkh", "p2wpkh"],
            "uses_bip69": False,
            "typical_fees": "round",
            "change_position": "last"
        }
    }

    def __init__(self):
        pass

    def analyze_script_type_patterns(
        self,
        transactions: List[Dict]
    ) -> ScriptTypePattern:
        """
        Identify wallet by consistent script type usage.

        Args:
            transactions: List of transaction dicts

        Returns:
            ScriptTypePattern analysis
        """
        if not transactions:
            return ScriptTypePattern(
                transactions_analyzed=0,
                script_types_used={},
                consistency_score=0.0,
                dominant_type=None,
                is_consistent=False,
                score_impact=0,
                warnings=["No transactions to analyze"]
            )

        script_types = []

        for tx in transactions:
            # Check output script types
            for vout in tx.get("vout", []):
                script_pubkey = vout.get("scriptPubKey", {})
                script_type = script_pubkey.get("type", "unknown")
                if script_type and script_type != "unknown":
                    script_types.append(script_type)

        if not script_types:
            return ScriptTypePattern(
                transactions_analyzed=len(transactions),
                script_types_used={},
                consistency_score=0.0,
                dominant_type=None,
                is_consistent=False,
                score_impact=0,
                warnings=["No script types found"]
            )

        type_counts = Counter(script_types)
        dominant_type, dominant_count = type_counts.most_common(1)[0]
        consistency_score = dominant_count / len(script_types)

        is_consistent = consistency_score > 0.8

        warnings = []
        score_impact = 0
        interpretation = ""

        if is_consistent:
            warnings.append(f"Consistent script type usage detected ({dominant_type})")
            warnings.append("This creates a wallet fingerprint - transactions are linkable")
            score_impact = -20
            interpretation = f"STRONG FINGERPRINT: {int(consistency_score*100)}% of outputs use {dominant_type}. This wallet can be tracked."
        elif consistency_score > 0.6:
            warnings.append(f"Frequent use of {dominant_type} ({int(consistency_score*100)}%)")
            score_impact = -10
            interpretation = f"MODERATE FINGERPRINT: Preference for {dominant_type} detected."
        else:
            score_impact = 5
            interpretation = f"GOOD: Mixed script types reduce wallet fingerprinting."

        return ScriptTypePattern(
            transactions_analyzed=len(transactions),
            script_types_used=dict(type_counts),
            consistency_score=consistency_score,
            dominant_type=dominant_type,
            is_consistent=is_consistent,
            score_impact=score_impact,
            warnings=warnings,
            interpretation=interpretation
        )

    def detect_output_ordering_pattern(
        self,
        transactions: List[Dict]
    ) -> OutputOrderingPattern:
        """
        Detect if wallet uses BIP-69 (deterministic ordering) or random.

        Args:
            transactions: List of transaction dicts

        Returns:
            OutputOrderingPattern analysis

        BIP-69 Detection:
        - Outputs sorted by amount (ascending), then by scriptPubKey (lexicographical)
        - Consistent BIP-69 usage is a fingerprint
        """
        if not transactions:
            return OutputOrderingPattern(
                transactions_analyzed=0,
                bip69_compliant_count=0,
                bip69_compliance_ratio=0.0,
                is_likely_bip69=False,
                random_ordering_count=0,
                pattern_detected="unknown",
                score_impact=0,
                warnings=["No transactions to analyze"]
            )

        bip69_compliant = 0
        total_analyzed = 0

        for tx in transactions:
            vouts = tx.get("vout", [])
            if len(vouts) < 2:
                continue  # Can't determine ordering with <2 outputs

            total_analyzed += 1

            # Check if outputs are sorted by value
            values = [int(vout.get("value", 0) * 100_000_000) for vout in vouts]
            is_sorted_by_value = values == sorted(values)

            if is_sorted_by_value:
                bip69_compliant += 1

        if total_analyzed == 0:
            return OutputOrderingPattern(
                transactions_analyzed=0,
                bip69_compliant_count=0,
                bip69_compliance_ratio=0.0,
                is_likely_bip69=False,
                random_ordering_count=0,
                pattern_detected="unknown",
                score_impact=0,
                warnings=["Not enough multi-output transactions"]
            )

        compliance_ratio = bip69_compliant / total_analyzed
        is_likely_bip69 = compliance_ratio > 0.8

        warnings = []
        score_impact = 0
        pattern_detected = "unknown"
        interpretation = ""

        if is_likely_bip69:
            pattern_detected = "bip69"
            warnings.append(f"BIP-69 ordering detected ({int(compliance_ratio*100)}% compliance)")
            warnings.append("Deterministic output ordering creates a wallet fingerprint")
            score_impact = -10
            interpretation = "FINGERPRINT: BIP-69 usage detected. Transactions are linkable."
        elif compliance_ratio < 0.2:
            pattern_detected = "random"
            interpretation = "GOOD: Random output ordering improves privacy."
        else:
            pattern_detected = "mixed"
            score_impact = -5
            interpretation = "MODERATE: Inconsistent ordering pattern detected."

        return OutputOrderingPattern(
            transactions_analyzed=total_analyzed,
            bip69_compliant_count=bip69_compliant,
            bip69_compliance_ratio=compliance_ratio,
            is_likely_bip69=is_likely_bip69,
            random_ordering_count=total_analyzed - bip69_compliant,
            pattern_detected=pattern_detected,
            score_impact=score_impact,
            warnings=warnings,
            interpretation=interpretation
        )

    def analyze_fee_patterns(
        self,
        transactions: List[Dict]
    ) -> FeePattern:
        """
        Identify wallet by fee calculation strategy.

        Args:
            transactions: List of transaction dicts

        Returns:
            FeePattern analysis
        """
        if not transactions:
            return FeePattern(
                transactions_analyzed=0,
                fees_sats_per_vbyte=[],
                average_fee_rate=0.0,
                fee_rate_stddev=0.0,
                uses_round_fees=False,
                fee_pattern="unknown",
                score_impact=0,
                warnings=["No transactions to analyze"]
            )

        fee_rates = []

        for tx in transactions:
            # Calculate fee rate (sat/vB)
            # Note: vsize may not be in tx dict - we'd need to calculate it
            # For now, use a simplified approach

            # Get total input value
            total_in = 0
            for vin in tx.get("vin", []):
                # This would require looking up previous transactions
                # Simplified: skip if not available
                pass

            # Get total output value
            total_out = sum(int(vout.get("value", 0) * 100_000_000) for vout in tx.get("vout", []))

            # For demonstration, we'll use tx.get("fee") if available
            fee_sats = tx.get("fee")
            vsize = tx.get("vsize") or tx.get("size", 250)  # Approximate

            if fee_sats and vsize:
                fee_rate = fee_sats / vsize
                fee_rates.append(fee_rate)

        if not fee_rates:
            return FeePattern(
                transactions_analyzed=len(transactions),
                fees_sats_per_vbyte=[],
                average_fee_rate=0.0,
                fee_rate_stddev=0.0,
                uses_round_fees=False,
                fee_pattern="unknown",
                score_impact=0,
                warnings=["Fee data not available"]
            )

        avg_fee = statistics.mean(fee_rates)
        stddev = statistics.stdev(fee_rates) if len(fee_rates) > 1 else 0.0

        # Check if fees are round numbers (1, 5, 10, 20, 50, etc)
        round_fees_count = 0
        for fee_rate in fee_rates:
            if fee_rate in [1, 2, 5, 10, 20, 50, 100, 200]:
                round_fees_count += 1

        uses_round_fees = (round_fees_count / len(fee_rates)) > 0.7

        warnings = []
        score_impact = 0
        interpretation = ""

        if uses_round_fees:
            fee_pattern = "round"
            warnings.append("Consistent round fee rates detected")
            warnings.append("This is a wallet fingerprint")
            score_impact = -15
            interpretation = "FINGERPRINT: Always uses round sat/vB fees. Wallet is identifiable."
        elif stddev < 5:
            fee_pattern = "consistent"
            warnings.append("Consistent fee calculation detected")
            score_impact = -10
            interpretation = "MODERATE FINGERPRINT: Consistent fee strategy."
        else:
            fee_pattern = "variable"
            interpretation = "GOOD: Variable fee rates reduce wallet fingerprinting."

        return FeePattern(
            transactions_analyzed=len(transactions),
            fees_sats_per_vbyte=fee_rates,
            average_fee_rate=avg_fee,
            fee_rate_stddev=stddev,
            uses_round_fees=uses_round_fees,
            fee_pattern=fee_pattern,
            score_impact=score_impact,
            warnings=warnings,
            interpretation=interpretation
        )

    def detect_change_position_pattern(
        self,
        transactions: List[Dict],
        change_outputs: List[Tuple[str, int]]  # List of (txid, vout_index) for known change
    ) -> ChangePositionPattern:
        """
        Some wallets always put change in position 0 or position 1.

        Args:
            transactions: List of transaction dicts
            change_outputs: List of (txid, vout) tuples for identified change outputs

        Returns:
            ChangePositionPattern analysis
        """
        if not change_outputs:
            return ChangePositionPattern(
                transactions_analyzed=0,
                change_positions=[],
                position_counter={},
                most_common_position=None,
                position_consistency=0.0,
                always_last=False,
                always_first=False,
                is_consistent=False,
                score_impact=0,
                warnings=["No change outputs identified"]
            )

        positions = []

        # Build a lookup dict for change outputs
        change_lookup = {(txid, vout): True for txid, vout in change_outputs}

        for tx in transactions:
            txid = tx.get("txid")
            vouts = tx.get("vout", [])

            for idx, vout in enumerate(vouts):
                if (txid, idx) in change_lookup:
                    positions.append(idx)

        if not positions:
            return ChangePositionPattern(
                transactions_analyzed=len(transactions),
                change_positions=[],
                position_counter={},
                most_common_position=None,
                position_consistency=0.0,
                always_last=False,
                always_first=False,
                is_consistent=False,
                score_impact=0,
                warnings=["Could not map change outputs"]
            )

        position_counts = Counter(positions)
        most_common_pos, most_common_count = position_counts.most_common(1)[0]
        consistency = most_common_count / len(positions)

        always_first = all(p == 0 for p in positions)
        always_last = False  # Would need to check against output count

        is_consistent = consistency > 0.8

        warnings = []
        score_impact = 0
        interpretation = ""

        if is_consistent:
            warnings.append(f"Change always in position {most_common_pos} ({int(consistency*100)}%)")
            warnings.append("This is a strong wallet fingerprint")
            score_impact = -15
            interpretation = f"STRONG FINGERPRINT: Change consistently at position {most_common_pos}."
        elif consistency > 0.6:
            warnings.append(f"Change often in position {most_common_pos} ({int(consistency*100)}%)")
            score_impact = -8
            interpretation = "MODERATE FINGERPRINT: Preferred change position detected."
        else:
            interpretation = "GOOD: Randomized change position improves privacy."

        return ChangePositionPattern(
            transactions_analyzed=len(transactions),
            change_positions=positions,
            position_counter=dict(position_counts),
            most_common_position=most_common_pos,
            position_consistency=consistency,
            always_last=always_last,
            always_first=always_first,
            is_consistent=is_consistent,
            score_impact=score_impact,
            warnings=warnings,
            interpretation=interpretation
        )

    def calculate_wallet_fingerprint_score(
        self,
        transactions: List[Dict],
        change_outputs: Optional[List[Tuple[str, int]]] = None
    ) -> WalletFingerprintResult:
        """
        Overall fingerprint detectability score.

        Args:
            transactions: List of transaction dicts
            change_outputs: Optional list of (txid, vout) for change outputs

        Returns:
            WalletFingerprintResult with comprehensive assessment
        """
        if not transactions:
            return WalletFingerprintResult(
                transactions_analyzed=0,
                fingerprint_strength=0.0,
                detected_patterns=[],
                likely_wallet_software=None,
                confidence=0.0,
                total_score_impact=0,
                warnings=["No transactions to analyze"]
            )

        # Run all analyses
        script_pattern = self.analyze_script_type_patterns(transactions)
        ordering_pattern = self.detect_output_ordering_pattern(transactions)
        fee_pattern = self.analyze_fee_patterns(transactions)

        change_pattern = None
        if change_outputs:
            change_pattern = self.detect_change_position_pattern(transactions, change_outputs)

        # Calculate overall fingerprint strength
        fingerprint_scores = []

        if script_pattern.consistency_score > 0.8:
            fingerprint_scores.append(0.9)
        elif script_pattern.consistency_score > 0.6:
            fingerprint_scores.append(0.6)

        if ordering_pattern.is_likely_bip69:
            fingerprint_scores.append(0.7)

        if fee_pattern.uses_round_fees:
            fingerprint_scores.append(0.8)

        if change_pattern and change_pattern.is_consistent:
            fingerprint_scores.append(0.8)

        fingerprint_strength = max(fingerprint_scores) if fingerprint_scores else 0.3

        # Detect patterns
        detected_patterns = []

        if script_pattern.is_consistent:
            detected_patterns.append(f"Consistent script type: {script_pattern.dominant_type}")

        if ordering_pattern.is_likely_bip69:
            detected_patterns.append("BIP-69 output ordering")

        if fee_pattern.uses_round_fees:
            detected_patterns.append("Round fee rates")

        if change_pattern and change_pattern.is_consistent:
            detected_patterns.append(f"Consistent change position: {change_pattern.most_common_position}")

        # Guess wallet software
        likely_wallet = None
        confidence = 0.0

        # Simple heuristic matching (real implementation would be more sophisticated)
        if ordering_pattern.is_likely_bip69 and script_pattern.dominant_type == "witness_v0_keyhash":
            likely_wallet = "wasabi"
            confidence = 0.7
        elif change_pattern and change_pattern.always_first:
            likely_wallet = "samourai"
            confidence = 0.6

        # Calculate total score impact
        total_score_impact = script_pattern.score_impact + ordering_pattern.score_impact + fee_pattern.score_impact
        if change_pattern:
            total_score_impact += change_pattern.score_impact

        # Generate warnings and recommendations
        warnings = []
        recommendations = []

        if fingerprint_strength > 0.7:
            warnings.append("STRONG wallet fingerprint detected")
            warnings.append("Your transactions are easily linkable")
            recommendations.append("Consider using multiple wallet types")
            recommendations.append("Randomize transaction patterns when possible")
        elif fingerprint_strength > 0.4:
            warnings.append("Moderate wallet fingerprint detected")
            recommendations.append("Improve privacy by varying wallet behavior")

        if not detected_patterns:
            recommendations.append("Good wallet privacy hygiene - no strong fingerprints detected")

        return WalletFingerprintResult(
            transactions_analyzed=len(transactions),
            fingerprint_strength=fingerprint_strength,
            detected_patterns=detected_patterns,
            likely_wallet_software=likely_wallet,
            confidence=confidence,
            total_score_impact=total_score_impact,
            script_type_pattern=script_pattern,
            output_ordering=ordering_pattern,
            fee_pattern=fee_pattern,
            change_position=change_pattern,
            warnings=warnings,
            recommendations=recommendations
        )


# Singleton instance
_wallet_fingerprinter: Optional[WalletFingerprinter] = None


def get_wallet_fingerprinter() -> WalletFingerprinter:
    """Get or create the wallet fingerprinter singleton."""
    global _wallet_fingerprinter
    if _wallet_fingerprinter is None:
        _wallet_fingerprinter = WalletFingerprinter()
    return _wallet_fingerprinter
