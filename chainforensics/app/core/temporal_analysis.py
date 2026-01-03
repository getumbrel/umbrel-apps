"""
ChainForensics - Temporal Correlation Analysis Module

Analyzes timing patterns in blockchain transactions to assess privacy risks:
- Timing correlation between transactions
- Spend velocity patterns (how quickly UTXOs are spent)
- Time-of-day clustering (timezone fingerprinting)
- Temporal gaps that enhance privacy

CRITICAL SECURITY WARNINGS:
- This is HEURISTIC ANALYSIS ONLY
- Timing correlation is a powerful deanonymization vector
- Network-level timing (Tor circuit timing, etc) is NOT detectable here
- This only analyzes blockchain timestamps (block times)
- Actual privacy may be worse than reported

Author: ChainForensics Team
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter
import statistics

logger = logging.getLogger("chainforensics.temporal_analysis")


class PrivacyBenefit(Enum):
    """Privacy benefit levels from temporal patterns."""
    NONE = "none"           # 0-1 hour: High correlation risk
    LOW = "low"             # 1 hour - 1 week: Some privacy
    MEDIUM = "medium"       # 1 week - 1 month: Moderate privacy
    HIGH = "high"           # 1+ month: Good temporal privacy
    EXCELLENT = "excellent" # 6+ months: Excellent temporal privacy


@dataclass
class TimingCorrelation:
    """Result of timing correlation analysis between two transactions."""
    tx1_time: datetime
    tx2_time: datetime
    gap_seconds: int
    gap_blocks: int
    gap_human: str  # Human-readable gap description
    correlation_risk: float  # 0.0-1.0 (higher = more risk)
    privacy_benefit: PrivacyBenefit
    score_impact: int  # Privacy score impact (-20 to +15)
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "tx1_time": self.tx1_time.isoformat() if self.tx1_time else None,
            "tx2_time": self.tx2_time.isoformat() if self.tx2_time else None,
            "gap_seconds": self.gap_seconds,
            "gap_blocks": self.gap_blocks,
            "gap_human": self.gap_human,
            "correlation_risk": round(self.correlation_risk, 3),
            "correlation_risk_percent": f"{self.correlation_risk * 100:.1f}%",
            "privacy_benefit": self.privacy_benefit.value,
            "score_impact": self.score_impact,
            "reasoning": self.reasoning
        }


@dataclass
class SpendVelocityAnalysis:
    """Analysis of how quickly a UTXO was spent."""
    creation_time: datetime
    spend_time: Optional[datetime]
    age_seconds: int
    age_blocks: int
    age_human: str
    velocity_category: str  # "instant", "fast", "normal", "slow", "very_slow", "unspent"
    privacy_score: int  # -15 to +15
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "creation_time": self.creation_time.isoformat() if self.creation_time else None,
            "spend_time": self.spend_time.isoformat() if self.spend_time else None,
            "age_seconds": self.age_seconds,
            "age_blocks": self.age_blocks,
            "age_human": self.age_human,
            "velocity_category": self.velocity_category,
            "privacy_score": self.privacy_score,
            "warnings": self.warnings,
            "recommendations": self.recommendations
        }


@dataclass
class TimezonePattern:
    """Detected timezone usage pattern."""
    most_active_hour_utc: int  # 0-23
    estimated_timezone: str  # e.g., "UTC+8", "UTC-5"
    confidence: float  # 0.0-1.0
    transaction_count: int
    hour_distribution: Dict[int, int]  # Hour -> Count
    fingerprint_risk: float  # 0.0-1.0
    score_impact: int  # -15 to 0

    def to_dict(self) -> Dict:
        return {
            "most_active_hour_utc": self.most_active_hour_utc,
            "estimated_timezone": self.estimated_timezone,
            "confidence": round(self.confidence, 3),
            "transaction_count": self.transaction_count,
            "hour_distribution": self.hour_distribution,
            "fingerprint_risk": round(self.fingerprint_risk, 3),
            "fingerprint_risk_percent": f"{self.fingerprint_risk * 100:.1f}%",
            "score_impact": self.score_impact,
            "interpretation": self._interpret()
        }

    def _interpret(self) -> str:
        if self.fingerprint_risk > 0.7:
            return f"HIGH RISK: Consistent activity pattern detected around {self.most_active_hour_utc}:00 UTC. This reveals your timezone/schedule."
        elif self.fingerprint_risk > 0.4:
            return f"MODERATE RISK: Some timing patterns detected. Try to randomize transaction times."
        else:
            return "LOW RISK: No strong timezone patterns detected."


@dataclass
class TemporalPrivacyScore:
    """Overall temporal privacy assessment for a transaction path."""
    path_length: int
    total_time_span_seconds: int
    average_hop_time_seconds: float
    time_variance: float  # Variance in hop times (high variance = better privacy)
    rapid_spends_count: int  # Spends within 1 hour
    score: int  # -30 to +20 temporal privacy contribution
    rating: str  # "poor", "fair", "good", "excellent"
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "path_length": self.path_length,
            "total_time_span_seconds": self.total_time_span_seconds,
            "total_time_span_human": self._humanize_seconds(self.total_time_span_seconds),
            "average_hop_time_seconds": round(self.average_hop_time_seconds, 1),
            "average_hop_time_human": self._humanize_seconds(int(self.average_hop_time_seconds)),
            "time_variance": round(self.time_variance, 2),
            "rapid_spends_count": self.rapid_spends_count,
            "score": self.score,
            "rating": self.rating,
            "warnings": self.warnings,
            "recommendations": self.recommendations
        }

    @staticmethod
    def _humanize_seconds(seconds: int) -> str:
        """Convert seconds to human-readable format."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''}"
        elif seconds < 2592000:
            weeks = seconds // 604800
            return f"{weeks} week{'s' if weeks != 1 else ''}"
        elif seconds < 31536000:
            months = seconds // 2592000
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            years = seconds // 31536000
            return f"{years} year{'s' if years != 1 else ''}"


class TemporalAnalyzer:
    """
    Analyzes temporal patterns in Bitcoin transactions for privacy assessment.

    Key Insights:
    - Fast spending (<6 blocks) creates strong timing correlation
    - Consistent timezone patterns are fingerprintable
    - Long delays between transactions enhance privacy
    - Variable timing is better than regular patterns
    """

    # Time thresholds (in seconds)
    INSTANT_THRESHOLD = 600          # < 10 minutes: Instant (likely automated/exchange)
    FAST_THRESHOLD = 3600            # < 1 hour: Fast (high correlation risk)
    NORMAL_THRESHOLD = 604800        # < 1 week: Normal
    SLOW_THRESHOLD = 2592000         # < 1 month: Slow (some privacy benefit)
    VERY_SLOW_THRESHOLD = 15552000   # < 6 months: Very slow (good privacy)
    # > 6 months: Excellent privacy

    # Block time estimate (10 minutes average)
    AVERAGE_BLOCK_TIME = 600

    def __init__(self):
        pass

    def analyze_timing_correlation(
        self,
        tx1_time: datetime,
        tx2_time: datetime
    ) -> TimingCorrelation:
        """
        Calculate timing correlation score between two transactions.

        Args:
            tx1_time: Timestamp of first transaction (earlier)
            tx2_time: Timestamp of second transaction (later)

        Returns:
            TimingCorrelation with risk assessment

        Risk Model:
        - < 10 min: 0.95 risk (extremely high - likely same session/automated)
        - 10 min - 1 hour: 0.85 risk (very high - same session likely)
        - 1 hour - 6 hours: 0.60 risk (high - possibly same session)
        - 6 hours - 1 day: 0.40 risk (moderate)
        - 1 day - 1 week: 0.25 risk (low-moderate)
        - 1 week - 1 month: 0.15 risk (low)
        - > 1 month: 0.05 risk (very low)
        """
        if not tx1_time or not tx2_time:
            return TimingCorrelation(
                tx1_time=tx1_time,
                tx2_time=tx2_time,
                gap_seconds=0,
                gap_blocks=0,
                gap_human="Unknown",
                correlation_risk=0.5,
                privacy_benefit=PrivacyBenefit.NONE,
                score_impact=0,
                reasoning=["Insufficient timestamp data"]
            )

        # Ensure tx1 is earlier
        if tx2_time < tx1_time:
            tx1_time, tx2_time = tx2_time, tx1_time

        gap = tx2_time - tx1_time
        gap_seconds = int(gap.total_seconds())
        gap_blocks = gap_seconds // self.AVERAGE_BLOCK_TIME

        # Calculate correlation risk
        reasoning = []

        if gap_seconds < self.INSTANT_THRESHOLD:
            correlation_risk = 0.95
            privacy_benefit = PrivacyBenefit.NONE
            score_impact = -20
            reasoning.append(f"CRITICAL: Transactions only {gap_seconds} seconds apart")
            reasoning.append("Extremely high timing correlation - likely same session or automated")
        elif gap_seconds < self.FAST_THRESHOLD:
            correlation_risk = 0.85
            privacy_benefit = PrivacyBenefit.NONE
            score_impact = -15
            reasoning.append(f"WARNING: Spent within {gap_seconds // 60} minutes")
            reasoning.append("Very high timing correlation risk")
        elif gap_seconds < 21600:  # 6 hours
            correlation_risk = 0.60
            privacy_benefit = PrivacyBenefit.LOW
            score_impact = -10
            reasoning.append(f"Spent within {gap_seconds // 3600} hours")
            reasoning.append("High timing correlation risk")
        elif gap_seconds < 86400:  # 1 day
            correlation_risk = 0.40
            privacy_benefit = PrivacyBenefit.LOW
            score_impact = -5
            reasoning.append("Spent within 1 day")
            reasoning.append("Moderate timing correlation risk")
        elif gap_seconds < self.NORMAL_THRESHOLD:  # 1 week
            correlation_risk = 0.25
            privacy_benefit = PrivacyBenefit.LOW
            score_impact = 0
            reasoning.append(f"Spent within {gap_seconds // 86400} days")
            reasoning.append("Some timing correlation possible")
        elif gap_seconds < self.SLOW_THRESHOLD:  # 1 month
            correlation_risk = 0.15
            privacy_benefit = PrivacyBenefit.MEDIUM
            score_impact = 5
            reasoning.append(f"Waited {gap_seconds // 86400} days before spending")
            reasoning.append("Good temporal privacy - reduces timing correlation")
        elif gap_seconds < self.VERY_SLOW_THRESHOLD:  # 6 months
            correlation_risk = 0.08
            privacy_benefit = PrivacyBenefit.HIGH
            score_impact = 10
            reasoning.append(f"Waited {gap_seconds // 2592000} months before spending")
            reasoning.append("Very good temporal privacy")
        else:  # > 6 months
            correlation_risk = 0.05
            privacy_benefit = PrivacyBenefit.EXCELLENT
            score_impact = 15
            reasoning.append(f"Waited {gap_seconds // 2592000} months before spending")
            reasoning.append("Excellent temporal privacy - minimal timing correlation")

        gap_human = TemporalPrivacyScore._humanize_seconds(gap_seconds)

        return TimingCorrelation(
            tx1_time=tx1_time,
            tx2_time=tx2_time,
            gap_seconds=gap_seconds,
            gap_blocks=gap_blocks,
            gap_human=gap_human,
            correlation_risk=correlation_risk,
            privacy_benefit=privacy_benefit,
            score_impact=score_impact,
            reasoning=reasoning
        )

    def analyze_spend_velocity(
        self,
        utxo_creation_time: datetime,
        spend_time: Optional[datetime] = None
    ) -> SpendVelocityAnalysis:
        """
        Analyze how quickly a UTXO was spent.

        Args:
            utxo_creation_time: When the UTXO was created
            spend_time: When it was spent (None if unspent)

        Returns:
            SpendVelocityAnalysis with privacy assessment
        """
        if not utxo_creation_time:
            return SpendVelocityAnalysis(
                creation_time=None,
                spend_time=spend_time,
                age_seconds=0,
                age_blocks=0,
                age_human="Unknown",
                velocity_category="unknown",
                privacy_score=0,
                warnings=["Missing creation timestamp"]
            )

        if spend_time is None:
            # UTXO is unspent - calculate age from now
            age = datetime.utcnow() - utxo_creation_time
        else:
            age = spend_time - utxo_creation_time

        age_seconds = int(age.total_seconds())
        age_blocks = age_seconds // self.AVERAGE_BLOCK_TIME
        age_human = TemporalPrivacyScore._humanize_seconds(age_seconds)

        warnings = []
        recommendations = []

        if spend_time is None:
            velocity_category = "unspent"
            privacy_score = 5  # Slight bonus for holding
            recommendations.append("UTXO is unspent - consider waiting longer before spending")
        elif age_seconds < self.INSTANT_THRESHOLD:
            velocity_category = "instant"
            privacy_score = -15
            warnings.append(f"CRITICAL: UTXO spent within {age_human} of creation")
            warnings.append("This creates extreme timing correlation risk")
            recommendations.append("Always wait at least 6 blocks (1 hour) before spending")
            recommendations.append("Consider waiting 24+ hours for better privacy")
        elif age_seconds < self.FAST_THRESHOLD:
            velocity_category = "fast"
            privacy_score = -10
            warnings.append(f"WARNING: UTXO spent quickly ({age_human})")
            warnings.append("High timing correlation risk")
            recommendations.append("Wait at least 24 hours before spending for better privacy")
        elif age_seconds < self.NORMAL_THRESHOLD:
            velocity_category = "normal"
            privacy_score = 0
            recommendations.append("Normal spend timing - consider waiting longer for enhanced privacy")
        elif age_seconds < self.SLOW_THRESHOLD:
            velocity_category = "slow"
            privacy_score = 5
            recommendations.append("Good temporal privacy from waiting period")
        elif age_seconds < self.VERY_SLOW_THRESHOLD:
            velocity_category = "very_slow"
            privacy_score = 10
            recommendations.append("Very good temporal privacy - long holding period")
        else:
            velocity_category = "aged"
            privacy_score = 15
            recommendations.append("Excellent temporal privacy - aged UTXO")

        return SpendVelocityAnalysis(
            creation_time=utxo_creation_time,
            spend_time=spend_time,
            age_seconds=age_seconds,
            age_blocks=age_blocks,
            age_human=age_human,
            velocity_category=velocity_category,
            privacy_score=privacy_score,
            warnings=warnings,
            recommendations=recommendations
        )

    def detect_timezone_patterns(
        self,
        transaction_times: List[datetime],
        min_transactions: int = 5
    ) -> Optional[TimezonePattern]:
        """
        Detect consistent time-of-day patterns (timezone fingerprinting).

        Args:
            transaction_times: List of transaction timestamps
            min_transactions: Minimum transactions needed for analysis

        Returns:
            TimezonePattern if detectable pattern found, None otherwise

        Privacy Risk:
        - If a user consistently transacts during specific hours (e.g., 9am-5pm in their timezone),
          this creates a fingerprint that can narrow down their location and identity.
        """
        if not transaction_times or len(transaction_times) < min_transactions:
            return None

        # Extract hour of day (UTC) for each transaction
        hours = [t.hour for t in transaction_times if t]

        if not hours:
            return None

        # Count transactions by hour
        hour_counts = Counter(hours)

        # Find most active hour
        most_active_hour = hour_counts.most_common(1)[0][0]
        most_active_count = hour_counts[most_active_hour]

        # Calculate concentration (how concentrated activity is)
        total_txs = len(hours)
        top_3_hours = sum(count for _, count in hour_counts.most_common(3))
        concentration = top_3_hours / total_txs if total_txs > 0 else 0

        # Estimate timezone based on most active hour
        # Assume most people transact during daytime (9am-5pm local time)
        # If most active hour is 14:00 UTC, and assuming 12:00 local time, offset = +2
        # This is a rough heuristic
        assumed_local_hour = 12  # Noon local time
        estimated_offset = most_active_hour - assumed_local_hour

        if estimated_offset > 12:
            estimated_offset -= 24
        elif estimated_offset < -12:
            estimated_offset += 24

        if estimated_offset >= 0:
            estimated_tz = f"UTC+{estimated_offset}"
        else:
            estimated_tz = f"UTC{estimated_offset}"

        # Calculate fingerprint risk based on concentration
        if concentration > 0.7:
            # Very concentrated - high fingerprint risk
            fingerprint_risk = 0.9
            score_impact = -15
            confidence = 0.8
        elif concentration > 0.5:
            # Moderately concentrated
            fingerprint_risk = 0.6
            score_impact = -10
            confidence = 0.6
        elif concentration > 0.3:
            # Some pattern
            fingerprint_risk = 0.3
            score_impact = -5
            confidence = 0.4
        else:
            # Well distributed - low risk
            fingerprint_risk = 0.1
            score_impact = 0
            confidence = 0.2

        return TimezonePattern(
            most_active_hour_utc=most_active_hour,
            estimated_timezone=estimated_tz,
            confidence=confidence,
            transaction_count=total_txs,
            hour_distribution=dict(hour_counts),
            fingerprint_risk=fingerprint_risk,
            score_impact=score_impact
        )

    def calculate_temporal_privacy_score(
        self,
        path_nodes: List[Dict]
    ) -> TemporalPrivacyScore:
        """
        Score the temporal privacy of an entire transaction path.

        Args:
            path_nodes: List of transaction nodes with block_time

        Returns:
            TemporalPrivacyScore with overall temporal assessment

        Factors:
        - Average time between hops (longer = better)
        - Variance in spending times (high variance = better, shows irregular pattern)
        - Number of rapid spends (< 1 hour)
        - Total time span
        """
        if not path_nodes or len(path_nodes) < 2:
            return TemporalPrivacyScore(
                path_length=len(path_nodes),
                total_time_span_seconds=0,
                average_hop_time_seconds=0,
                time_variance=0,
                rapid_spends_count=0,
                score=0,
                rating="unknown",
                warnings=["Insufficient path data for temporal analysis"]
            )

        # Extract timestamps
        times = []
        for node in path_nodes:
            if isinstance(node, dict):
                bt = node.get("block_time")
                if bt:
                    if isinstance(bt, str):
                        times.append(datetime.fromisoformat(bt.replace('Z', '+00:00')))
                    elif isinstance(bt, datetime):
                        times.append(bt)
            elif hasattr(node, 'block_time') and node.block_time:
                times.append(node.block_time)

        if len(times) < 2:
            return TemporalPrivacyScore(
                path_length=len(path_nodes),
                total_time_span_seconds=0,
                average_hop_time_seconds=0,
                time_variance=0,
                rapid_spends_count=0,
                score=0,
                rating="unknown",
                warnings=["Insufficient timestamp data"]
            )

        # Calculate hop times
        hop_times = []
        rapid_spends = 0

        for i in range(1, len(times)):
            hop = (times[i] - times[i-1]).total_seconds()
            hop_times.append(hop)
            if hop < 3600:  # < 1 hour
                rapid_spends += 1

        total_time_span = (times[-1] - times[0]).total_seconds()
        avg_hop_time = sum(hop_times) / len(hop_times) if hop_times else 0

        # Calculate variance
        if len(hop_times) > 1:
            time_variance = statistics.variance(hop_times)
        else:
            time_variance = 0

        # Score calculation
        score = 0
        warnings = []
        recommendations = []

        # Factor 1: Rapid spends (penalty)
        if rapid_spends > 0:
            penalty = min(rapid_spends * -10, -30)
            score += penalty
            warnings.append(f"Found {rapid_spends} rapid spend(s) (< 1 hour)")
            warnings.append("Fast spending creates timing correlation risk")

        # Factor 2: Average hop time (bonus for longer waits)
        if avg_hop_time > 2592000:  # > 1 month average
            score += 20
            recommendations.append("Excellent temporal privacy - long average wait times")
        elif avg_hop_time > 604800:  # > 1 week average
            score += 15
            recommendations.append("Very good temporal privacy")
        elif avg_hop_time > 86400:  # > 1 day average
            score += 10
            recommendations.append("Good temporal privacy")
        elif avg_hop_time > 3600:  # > 1 hour average
            score += 5
        else:
            score -= 10
            warnings.append(f"Average hop time is only {int(avg_hop_time/60)} minutes")
            recommendations.append("Increase time between transactions for better privacy")

        # Factor 3: Time variance (bonus for irregular patterns)
        if time_variance > 1000000:  # High variance (irregular timing)
            score += 5
            recommendations.append("Good timing irregularity - harder to fingerprint")

        # Factor 4: Total time span (bonus for very long spans)
        if total_time_span > 31536000:  # > 1 year
            score += 10
        elif total_time_span > 7776000:  # > 3 months
            score += 5

        # Clamp score to range
        score = max(-30, min(20, score))

        # Determine rating
        if score >= 15:
            rating = "excellent"
        elif score >= 5:
            rating = "good"
        elif score >= -5:
            rating = "fair"
        else:
            rating = "poor"

        if not recommendations:
            if score < 0:
                recommendations.append("Increase time delays between transactions")
                recommendations.append("Randomize transaction timing to avoid patterns")

        return TemporalPrivacyScore(
            path_length=len(path_nodes),
            total_time_span_seconds=int(total_time_span),
            average_hop_time_seconds=avg_hop_time,
            time_variance=time_variance,
            rapid_spends_count=rapid_spends,
            score=score,
            rating=rating,
            warnings=warnings,
            recommendations=recommendations
        )


# Singleton instance
_temporal_analyzer: Optional[TemporalAnalyzer] = None


def get_temporal_analyzer() -> TemporalAnalyzer:
    """Get or create the temporal analyzer singleton."""
    global _temporal_analyzer
    if _temporal_analyzer is None:
        _temporal_analyzer = TemporalAnalyzer()
    return _temporal_analyzer
