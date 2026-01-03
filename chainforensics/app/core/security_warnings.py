"""
Security warnings module for critical privacy vulnerabilities.

This module detects and warns users about known security vulnerabilities:
- WabiSabi coordinator attacks (Dec 2024 research)
- Lightning Network linkability (43.7% of nodes)
- RPC timing correlation attacks

Author: ChainForensics Team
Version: 1.3.0
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

from app.api.models import RiskSeverity

logger = logging.getLogger("chainforensics.security_warnings")


@dataclass
class WabiSabiWarning:
    """WabiSabi CoinJoin coordinator attack warning."""
    detected: bool
    coordinator_known: bool
    coordinator_name: Optional[str]
    anonymity_set_size: int
    warning_level: RiskSeverity
    explanation: str
    remediation: str


@dataclass
class LightningPrivacyWarning:
    """Lightning Network privacy risk warning."""
    ln_channels_detected: bool
    linkability_risk: float  # Research: 43.7% of LN nodes linkable
    affected_utxos: List[str]
    warning: str
    remediation: str


class SecurityWarnings:
    """
    Security warnings for critical privacy vulnerabilities.

    Based on latest research (Dec 2024):
    - WabiSabi coordinator attacks can deanonymize all participants
    - 43.7% of Lightning Network nodes linkable to on-chain addresses
    - RPC timing correlation can leak transaction patterns
    """

    # Trusted WabiSabi coordinators (Dec 2024)
    TRUSTED_COORDINATORS = {
        "zkSNACKs": {
            "url": "https://wasabiwallet.io",
            "confidence": 0.95,
            "description": "Official Wasabi Wallet coordinator"
        },
        "Official Wasabi": {
            "url": "https://wasabiwallet.io",
            "confidence": 0.95,
            "description": "zkSNACKs official coordinator"
        }
    }

    def check_wabisabi_risks(
        self,
        tx: Dict,
        coinjoin_result
    ) -> Optional[WabiSabiWarning]:
        """
        Check for WabiSabi coordinator attack risk.

        CRITICAL RESEARCH (Dec 2024):
        Malicious coordinators can deanonymize ALL participants in WabiSabi CoinJoins.

        Unlike Whirlpool (fixed equal outputs), WabiSabi uses variable amounts,
        giving coordinators complete control over transaction construction.

        Args:
            tx: Transaction data dict
            coinjoin_result: DetectionResult from coinjoin.py

        Returns:
            WabiSabiWarning if WabiSabi detected, None otherwise
        """
        # Only warn for WabiSabi (Wasabi v2)
        if not coinjoin_result or coinjoin_result.protocol.value != "wasabi_v2":
            return None

        logger.info(f"WabiSabi CoinJoin detected in tx {tx.get('txid', 'unknown')[:16]}...")

        # Extract anonymity set size from detection details
        anonymity_set_size = coinjoin_result.details.get("inputs", 10)

        # Check if coordinator is known/trusted
        # In full implementation, would analyze transaction metadata
        # for coordinator identification (output patterns, known coordinator addresses)
        coordinator_known = False
        coordinator_name = None

        # For now, mark as unknown (conservative approach)
        # Real implementation would check:
        # 1. Known coordinator addresses in outputs
        # 2. Coordinator fee patterns
        # 3. Community-maintained coordinator database

        if not coordinator_known:
            logger.warning(
                f"WabiSabi detected with UNKNOWN coordinator - "
                f"anonymity set: {anonymity_set_size}"
            )

            return WabiSabiWarning(
                detected=True,
                coordinator_known=False,
                coordinator_name=None,
                anonymity_set_size=anonymity_set_size,
                warning_level=RiskSeverity.CRITICAL,
                explanation=(
                    "CRITICAL: WabiSabi CoinJoin detected with UNKNOWN coordinator. "
                    "Malicious coordinators can compromise ALL participant privacy by "
                    "controlling transaction construction (Dec 2024 research). "
                    "Unlike Whirlpool with fixed outputs, WabiSabi uses variable amounts, "
                    "making coordinator attacks undetectable. The coordinator can link "
                    "all input-output pairs and deanonymize every participant."
                ),
                remediation=(
                    "ONLY use CoinJoins from TRUSTED sources:\n"
                    "✅ zkSNACKs (Official Wasabi Wallet coordinator)\n"
                    "✅ Whirlpool (Samourai - fixed denominations, no coordinator control)\n"
                    "✅ JoinMarket (no coordinator - fully decentralized)\n"
                    "❌ NEVER use unknown WabiSabi coordinators\n"
                    "❌ Affected anonymity set: {anonymity_set_size} participants"
                ).format(anonymity_set_size=anonymity_set_size)
            )

        # If coordinator is known and trusted, low severity
        return WabiSabiWarning(
            detected=True,
            coordinator_known=True,
            coordinator_name=coordinator_name,
            anonymity_set_size=anonymity_set_size,
            warning_level=RiskSeverity.LOW,
            explanation=(
                f"WabiSabi CoinJoin with trusted coordinator: {coordinator_name}. "
                f"Anonymity set: {anonymity_set_size} participants."
            ),
            remediation="Continue using trusted coordinators for privacy."
        )

    def check_lightning_privacy(
        self,
        trace_result
    ) -> Optional[LightningPrivacyWarning]:
        """
        Check for Lightning Network privacy issues.

        RESEARCH FINDING (2024):
        43.7% of Lightning Network nodes are linkable to 26.3% of on-chain addresses.

        Detection:
        - 2-of-2 multisig outputs (Lightning channel funding)
        - Specific value patterns (common channel sizes)
        - Anchor outputs (CPFP for fee bumping)

        Args:
            trace_result: TraceResult from tracer.py

        Returns:
            LightningPrivacyWarning if LN channels detected, None otherwise
        """
        if not trace_result or not trace_result.nodes:
            return None

        # Detect Lightning channel patterns
        ln_channel_utxos = []

        for node in trace_result.nodes:
            if self._is_lightning_channel(node):
                utxo_id = f"{node.txid}:{node.vout}"
                ln_channel_utxos.append(utxo_id)
                logger.debug(f"Lightning channel detected: {utxo_id}")

        if not ln_channel_utxos:
            return None

        logger.warning(
            f"Lightning Network activity detected: {len(ln_channel_utxos)} channel(s)"
        )

        return LightningPrivacyWarning(
            ln_channels_detected=True,
            linkability_risk=0.437,  # 43.7% from research
            affected_utxos=ln_channel_utxos,
            warning=(
                f"Lightning Network channels detected ({len(ln_channel_utxos)} UTXO(s)). "
                "Research shows 43.7% of LN nodes can be linked to on-chain addresses. "
                "Channel opens/closes may reveal your identity through:\n"
                "- Channel capacity analysis (links node to funding transaction)\n"
                "- Channel close patterns (cooperative vs force-close reveals relationship)\n"
                "- Timing correlation (opening channels correlates with on-chain activity)\n"
                "- Balance probing (attackers can probe channel balances in <1 minute)"
            ),
            remediation=(
                "To improve Lightning privacy:\n"
                "✅ Use separate on-chain identity for channel funding\n"
                "✅ Fund channels through CoinJoin outputs\n"
                "✅ Wait random delays between on-chain tx and channel opens\n"
                "✅ Use multiple small channels instead of one large channel\n"
                "✅ Close channels cooperatively to avoid force-close patterns\n"
                "❌ Avoid funding channels directly from KYC exchanges"
            )
        )

    def _is_lightning_channel(self, node) -> bool:
        """
        Detect Lightning channel funding patterns.

        Lightning channels have specific characteristics:
        - 2-of-2 multisig (P2WSH)
        - Common value ranges (0.001 - 0.5 BTC typical)
        - Witness v0 script hash

        Args:
            node: UTXONode from tracer.py

        Returns:
            True if likely Lightning channel, False otherwise
        """
        # Check for P2WSH (witness v0 script hash)
        if node.script_type != "witness_v0_scripthash":
            return False

        # Check for common channel sizes
        # Most LN channels: 0.001 - 0.5 BTC
        value_btc = node.value_sats / 100_000_000
        if not (0.001 <= value_btc <= 1.0):
            return False

        # Additional heuristics could include:
        # - Output script pattern analysis (2-of-2 multisig)
        # - Spending patterns (anchor outputs, HTLC transactions)
        # - Timing (channels often spent within weeks/months)

        # For now, use conservative detection
        # Real implementation would check script details

        return True

    def check_rpc_timing_correlation(
        self,
        nodes: List
    ) -> Optional[Dict]:
        """
        Warn about RPC timing correlation risks.

        VULNERABILITY (CVE-2025-43968):
        RPC queries can be correlated with on-chain transactions.
        Even over Tor, timing patterns reveal:
        - Which addresses/transactions user is interested in
        - Transaction creation timing (mempool → block)
        - Wallet scanning patterns

        Args:
            nodes: List of UTXONode objects

        Returns:
            Warning dict if rapid consecutive spends detected, None otherwise
        """
        if not nodes or len(nodes) < 2:
            return None

        # Check for rapid consecutive spends (< 10 blocks apart)
        rapid_spends = []

        for i in range(len(nodes) - 1):
            current = nodes[i]
            next_node = nodes[i + 1]

            # Both must have block height data
            if not current.block_height or not next_node.block_height:
                continue

            block_diff = abs(current.block_height - next_node.block_height)

            # Rapid spend: < 10 blocks (~100 minutes)
            if block_diff < 10 and block_diff > 0:
                rapid_spends.append({
                    "utxo_1": f"{current.txid[:16]}...:{current.vout}",
                    "utxo_2": f"{next_node.txid[:16]}...:{next_node.vout}",
                    "block_gap": block_diff,
                    "time_estimate_minutes": block_diff * 10
                })

        if not rapid_spends:
            return None

        logger.warning(
            f"RPC timing correlation risk: {len(rapid_spends)} rapid spend pair(s)"
        )

        return {
            "detected": True,
            "risk_level": RiskSeverity.MEDIUM,
            "rapid_spend_count": len(rapid_spends),
            "rapid_spends": rapid_spends,
            "explanation": (
                f"Found {len(rapid_spends)} pairs of UTXOs spent within 10 blocks. "
                "Even over Tor, timing patterns can be correlated by:\n"
                "- ISP logging RPC request timestamps\n"
                "- Tor circuit timing analysis (traffic correlation)\n"
                "- Network-level surveillance (packet timing)\n"
                "- Mempool monitoring (transaction broadcast timing)\n"
                "\n"
                "This reveals which transactions belong to same entity."
            ),
            "remediation": (
                "Recommended timing privacy practices:\n"
                "✅ Wait 24+ hours between receiving and spending funds\n"
                "✅ Use random delays to break timing patterns\n"
                "✅ Batch transactions instead of spending immediately\n"
                "✅ Run own Bitcoin Core node (you already are!)\n"
                "✅ Use Tor for ALL RPC connections\n"
                "✅ Consider using multiple wallets with different timing patterns\n"
                "❌ Avoid spending UTXOs immediately after receiving"
            )
        }

    def get_all_warnings(
        self,
        tx: Dict,
        coinjoin_result,
        trace_result
    ) -> Dict[str, any]:
        """
        Run all security checks and return comprehensive warnings.

        Args:
            tx: Transaction data dict
            coinjoin_result: DetectionResult from coinjoin.py
            trace_result: TraceResult from tracer.py

        Returns:
            Dict with all detected warnings
        """
        warnings = {
            "wabisabi": None,
            "lightning": None,
            "rpc_timing": None,
            "has_critical": False,
            "has_warnings": False
        }

        # Check WabiSabi
        wabisabi_warning = self.check_wabisabi_risks(tx, coinjoin_result)
        if wabisabi_warning:
            warnings["wabisabi"] = wabisabi_warning
            if wabisabi_warning.warning_level == RiskSeverity.CRITICAL:
                warnings["has_critical"] = True
            else:
                warnings["has_warnings"] = True

        # Check Lightning
        ln_warning = self.check_lightning_privacy(trace_result)
        if ln_warning:
            warnings["lightning"] = ln_warning
            warnings["has_warnings"] = True

        # Check RPC timing
        if trace_result and trace_result.nodes:
            timing_warning = self.check_rpc_timing_correlation(trace_result.nodes)
            if timing_warning:
                warnings["rpc_timing"] = timing_warning
                warnings["has_warnings"] = True

        return warnings


# Singleton instance
_security_warnings_instance = None


def get_security_warnings() -> SecurityWarnings:
    """Get singleton SecurityWarnings instance."""
    global _security_warnings_instance
    if _security_warnings_instance is None:
        _security_warnings_instance = SecurityWarnings()
        logger.info("SecurityWarnings initialized")
    return _security_warnings_instance
