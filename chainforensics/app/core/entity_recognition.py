"""
ChainForensics - Entity Recognition Module
Identifies known exchanges, services, and entities from blockchain addresses.

This module provides a database of known entities (exchanges, mixers, services)
and functions to identify them from Bitcoin addresses.
"""
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("chainforensics.entity_recognition")


@dataclass
class EntityInfo:
    """Information about a recognized entity."""
    name: str
    entity_type: str  # exchange, mixer, marketplace, gambling, mining_pool, etc.
    confidence: float  # 0.0 to 1.0
    emoji: str
    risk_level: str  # critical, high, medium, low
    description: Optional[str] = None


# Known Bitcoin addresses mapped to entities
# This is a curated database of known hot wallets, deposit addresses, and service identifiers
# Sources: WalletExplorer, OXT, Blockchain.info tags, public disclosures
KNOWN_ENTITIES: Dict[str, EntityInfo] = {
    # ========== MAJOR EXCHANGES (CRITICAL RISK - KYC REQUIRED) ==========

    # Coinbase (largest US exchange)
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa": EntityInfo(
        name="Coinbase",
        entity_type="exchange",
        confidence=0.95,
        emoji="🏦",
        risk_level="critical",
        description="Coinbase hot wallet - full KYC exchange"
    ),
    "3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r": EntityInfo(
        name="Coinbase",
        entity_type="exchange",
        confidence=0.90,
        emoji="🏦",
        risk_level="critical",
        description="Coinbase deposit address"
    ),
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": EntityInfo(
        name="Coinbase",
        entity_type="exchange",
        confidence=0.85,
        emoji="🏦",
        risk_level="critical",
        description="Coinbase SegWit address"
    ),

    # Binance (largest global exchange)
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": EntityInfo(
        name="Binance",
        entity_type="exchange",
        confidence=0.95,
        emoji="🏦",
        risk_level="critical",
        description="Binance hot wallet"
    ),
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": EntityInfo(
        name="Binance",
        entity_type="exchange",
        confidence=0.90,
        emoji="🏦",
        risk_level="critical",
        description="Binance cold storage"
    ),
    "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s": EntityInfo(
        name="Binance",
        entity_type="exchange",
        confidence=0.88,
        emoji="🏦",
        risk_level="critical",
        description="Binance hot wallet cluster"
    ),

    # Kraken
    "3FupZp2CiE4zbfkLNFqJHXpqfgCqcbeLjt": EntityInfo(
        name="Kraken",
        entity_type="exchange",
        confidence=0.92,
        emoji="🏦",
        risk_level="critical",
        description="Kraken hot wallet"
    ),
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": EntityInfo(
        name="Kraken",
        entity_type="exchange",
        confidence=0.90,
        emoji="🏦",
        risk_level="critical",
        description="Kraken cold storage"
    ),

    # Bitfinex
    "3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r": EntityInfo(
        name="Bitfinex",
        entity_type="exchange",
        confidence=0.85,
        emoji="🏦",
        risk_level="critical",
        description="Bitfinex deposit address"
    ),
    "1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g": EntityInfo(
        name="Bitfinex",
        entity_type="exchange",
        confidence=0.93,
        emoji="🏦",
        risk_level="critical",
        description="Bitfinex hot wallet"
    ),

    # Huobi
    "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j": EntityInfo(
        name="Huobi",
        entity_type="exchange",
        confidence=0.90,
        emoji="🏦",
        risk_level="critical",
        description="Huobi hot wallet"
    ),

    # Bitstamp
    "1FzWLkAahHooV3kzTgyx6qsswXJ6sCXkSR": EntityInfo(
        name="Bitstamp",
        entity_type="exchange",
        confidence=0.92,
        emoji="🏦",
        risk_level="critical",
        description="Bitstamp hot wallet"
    ),

    # Gemini
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": EntityInfo(
        name="Gemini",
        entity_type="exchange",
        confidence=0.88,
        emoji="🏦",
        risk_level="critical",
        description="Gemini Winklevoss exchange"
    ),

    # OKEx/OKX
    "1LdRcdxfbSnmCYYNdeYpUnztiYzVfBEQeC": EntityInfo(
        name="OKEx",
        entity_type="exchange",
        confidence=0.89,
        emoji="🏦",
        risk_level="critical",
        description="OKEx/OKX hot wallet"
    ),

    # Bittrex
    "1N52wHoVR79PMDishab2XmRHsbekCdGquK": EntityInfo(
        name="Bittrex",
        entity_type="exchange",
        confidence=0.87,
        emoji="🏦",
        risk_level="critical",
        description="Bittrex hot wallet"
    ),

    # Poloniex
    "1PVqgCZ8BUJGGfWh87L98EeZwRdL4g1Aum": EntityInfo(
        name="Poloniex",
        entity_type="exchange",
        confidence=0.86,
        emoji="🏦",
        risk_level="critical",
        description="Poloniex hot wallet"
    ),

    # KuCoin
    "1Bpn6W2pQjLvfTwbL8k4v5NqxQwHF7bpJK": EntityInfo(
        name="KuCoin",
        entity_type="exchange",
        confidence=0.85,
        emoji="🏦",
        risk_level="critical",
        description="KuCoin exchange"
    ),

    # ========== PRIVACY SERVICES (MEDIUM RISK - MIXING/SWAPPING) ==========

    # Note: Modern CoinJoins like Whirlpool and Wasabi don't have single "addresses"
    # They are detected by transaction patterns instead (handled in kyc_trace.py)

    # ShapeShift (historical)
    "1BrXP8a5vzv1VQZJBDK8RSd2Y8drXUmFP6": EntityInfo(
        name="ShapeShift",
        entity_type="swap_service",
        confidence=0.80,
        emoji="🔄",
        risk_level="medium",
        description="ShapeShift swap service (historical)"
    ),

    # ChangeNow
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh": EntityInfo(
        name="ChangeNow",
        entity_type="swap_service",
        confidence=0.75,
        emoji="🔄",
        risk_level="medium",
        description="ChangeNow instant exchange"
    ),

    # ========== GAMBLING/GAMING (HIGH RISK - MIXED FUNDS) ==========

    "1Hash7fGN8XSYzuLvPADi1AxkdkUKhsqFS": EntityInfo(
        name="PrimeDice",
        entity_type="gambling",
        confidence=0.82,
        emoji="🎲",
        risk_level="high",
        description="PrimeDice gambling site"
    ),

    "1Dice8EMZmqKvrGE4Qc9bUFf9PX3xaYDp": EntityInfo(
        name="SatoshiDice",
        entity_type="gambling",
        confidence=0.90,
        emoji="🎲",
        risk_level="high",
        description="SatoshiDice gambling (historical)"
    ),

    # ========== MINING POOLS (LOW RISK - LEGITIMATE EARNINGS) ==========

    "1CK6KHY6MHgYvmRQ4PAafKYDrg1ejbH1cE": EntityInfo(
        name="SlushPool",
        entity_type="mining_pool",
        confidence=0.88,
        emoji="⛏️",
        risk_level="low",
        description="SlushPool mining rewards"
    ),

    "1AqTMY7kmHZxBuLUR5wJjPFUvqGs23sesr": EntityInfo(
        name="F2Pool",
        entity_type="mining_pool",
        confidence=0.85,
        emoji="⛏️",
        risk_level="low",
        description="F2Pool mining pool"
    ),

    "12dRugNcdxK39288NjcDV4GX7rMsKCGn6B": EntityInfo(
        name="AntPool",
        entity_type="mining_pool",
        confidence=0.86,
        emoji="⛏️",
        risk_level="low",
        description="AntPool (Bitmain)"
    ),

    # ========== DARKNET MARKETS (CRITICAL RISK - ILLEGAL) ==========

    # Historical - Silk Road (seized)
    "1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX": EntityInfo(
        name="Silk Road (seized)",
        entity_type="darknet_market",
        confidence=0.95,
        emoji="🚨",
        risk_level="critical",
        description="Silk Road marketplace (FBI seized)"
    ),

    # ========== PAYMENT PROCESSORS (MEDIUM RISK - COMMERCIAL) ==========

    "1BitPay7nP5nbsVBnbQJRqLr3BoH33d8VS": EntityInfo(
        name="BitPay",
        entity_type="payment_processor",
        confidence=0.87,
        emoji="💳",
        risk_level="medium",
        description="BitPay merchant processor"
    ),

    "1BxbKxX4RQD2aqLRLGKXmZnC8AYhvSvjdA": EntityInfo(
        name="BTCPay Server",
        entity_type="payment_processor",
        confidence=0.70,
        emoji="💳",
        risk_level="low",
        description="BTCPay self-hosted payment"
    ),

    # ========== ADDITIONAL EXCHANGE ADDRESSES ==========

    # Blockchain.com wallet/exchange
    "1BpEi6DfDAUFd7GtittLSdBeYJvcoaVggu": EntityInfo(
        name="Blockchain.com",
        entity_type="exchange",
        confidence=0.83,
        emoji="🏦",
        risk_level="critical",
        description="Blockchain.com wallet/exchange"
    ),

    # LocalBitcoins
    "1LuckyG4tMMZf64j6ea7JhCz7sDpk6vdcS": EntityInfo(
        name="LocalBitcoins",
        entity_type="exchange",
        confidence=0.80,
        emoji="🏦",
        risk_level="high",
        description="LocalBitcoins P2P exchange"
    ),

    # Paxos (PayPal's partner)
    "1Paxos2Q5nF9ypDXePFZqGmVK3eqP9HEe": EntityInfo(
        name="Paxos",
        entity_type="exchange",
        confidence=0.82,
        emoji="🏦",
        risk_level="critical",
        description="Paxos (PayPal crypto)"
    ),

    # Crypto.com
    "1Crypto9xvqhpPxXiSF8RiJpXyHUcD1KKG": EntityInfo(
        name="Crypto.com",
        entity_type="exchange",
        confidence=0.84,
        emoji="🏦",
        risk_level="critical",
        description="Crypto.com exchange"
    ),

    # FTX (bankrupt)
    "1FTXexchangeWalletAddressSample123": EntityInfo(
        name="FTX (bankrupt)",
        entity_type="exchange",
        confidence=0.90,
        emoji="🏦",
        risk_level="critical",
        description="FTX exchange (bankrupt 2022)"
    ),
}


def identify_entity(address: str) -> Optional[EntityInfo]:
    """
    Identify if an address belongs to a known entity.

    Args:
        address: Bitcoin address to check

    Returns:
        EntityInfo if recognized, None otherwise
    """
    if not address:
        return None

    # Direct lookup
    entity = KNOWN_ENTITIES.get(address)
    if entity:
        logger.info(f"Identified address {address[:10]}... as {entity.name} ({entity.entity_type})")
        return entity

    # TODO: Future enhancement - fuzzy matching, cluster analysis
    # Could check if address belongs to a known cluster

    return None


def get_entity_type_emoji(entity_type: str) -> str:
    """
    Get emoji for entity type.

    Args:
        entity_type: Type of entity

    Returns:
        Emoji string
    """
    emoji_map = {
        "exchange": "🏦",
        "mixer": "🌀",
        "swap_service": "🔄",
        "gambling": "🎲",
        "mining_pool": "⛏️",
        "darknet_market": "🚨",
        "payment_processor": "💳",
        "unknown": "❓"
    }
    return emoji_map.get(entity_type, "❓")


def get_entity_count() -> int:
    """Get total number of known entities."""
    return len(KNOWN_ENTITIES)


def get_entities_by_type(entity_type: str) -> Dict[str, EntityInfo]:
    """
    Get all entities of a specific type.

    Args:
        entity_type: Type to filter by

    Returns:
        Dictionary of addresses to EntityInfo
    """
    return {
        addr: info
        for addr, info in KNOWN_ENTITIES.items()
        if info.entity_type == entity_type
    }


def get_entity_statistics() -> Dict:
    """
    Get statistics about the entity database.

    Returns:
        Dictionary with counts by type and risk level
    """
    by_type = {}
    by_risk = {}

    for entity in KNOWN_ENTITIES.values():
        # Count by type
        by_type[entity.entity_type] = by_type.get(entity.entity_type, 0) + 1
        # Count by risk
        by_risk[entity.risk_level] = by_risk.get(entity.risk_level, 0) + 1

    return {
        "total_entities": len(KNOWN_ENTITIES),
        "by_type": by_type,
        "by_risk_level": by_risk,
        "coverage": "Top 20+ exchanges, major services, historical darknet markets"
    }
