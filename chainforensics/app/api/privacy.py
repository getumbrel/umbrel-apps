"""
ChainForensics - Privacy Analysis API Endpoints
Provides endpoints for:
- Cluster Detection
- Exchange Proximity Analysis
- UTXO Privacy Rating
- Enhanced Privacy Analysis (ALL HEURISTICS)
"""
from fastapi import APIRouter, HTTPException, Query, Depends
import logging

from app.core.privacy_analysis import (
    get_privacy_analyzer,
    PrivacyAnalyzer,
    ClusterResult,
    ExchangeProximityResult,
    UTXOPrivacyResult
)

# Import enhanced response model
from app.api.models import EnhancedPrivacyScore

logger = logging.getLogger("chainforensics.api.privacy")

router = APIRouter(tags=["privacy"])


@router.get("/cluster/{address}")
async def detect_cluster(
    address: str,
    max_depth: int = Query(3, ge=1, le=5, description="Maximum depth to search for linked addresses")
):
    """
    Detect address cluster using Common Input Ownership Heuristic (CIOH).
    
    When multiple addresses are used as inputs in the same transaction,
    they are likely controlled by the same entity. This endpoint identifies
    all addresses that can be linked to the given address.
    
    **Privacy Implications:**
    - Linked addresses can be attributed to the same owner
    - An observer can track total holdings across the cluster
    - Exchange compliance can identify all related addresses
    
    **Parameters:**
    - address: The Bitcoin address to analyze
    - max_depth: How many hops to follow (1-5, default 3)
    
    **Returns:**
    - cluster_size: Number of linked addresses found
    - linked_addresses: List of addresses linked through common inputs
    - risk_level: low/medium/high/critical based on cluster size
    - recommendations: Suggested actions to improve privacy
    """
    try:
        analyzer = get_privacy_analyzer()
        result = await analyzer.detect_cluster(address, max_depth)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error in cluster detection for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/{address}/advanced")
async def detect_cluster_advanced(
    address: str,
    max_depth: int = Query(3, ge=1, le=5, description="Maximum depth to search for linked addresses"),
    include_change_heuristic: bool = Query(True, description="Include change address detection heuristic"),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold for links")
):
    """
    Advanced cluster detection using Union-Find algorithm with graph analysis.

    This endpoint provides enhanced clustering capabilities over the basic
    cluster detection, including:

    **Improvements over Basic Clustering:**
    - Uses efficient Union-Find algorithm for cluster management
    - Optionally includes change address detection heuristic
    - Provides detailed graph metrics (density, average degree)
    - Tracks individual edges (connections) between addresses
    - Shows heuristic breakdown (common input vs change detection)
    - Includes metadata for each address (tx count, value, first seen)

    **Heuristics Used:**
    1. Common Input Ownership (CIOH): High confidence (95%)
       - Addresses spent together in the same transaction
    2. Change Address Detection: Medium confidence (60%)
       - Identifies likely change addresses in 2-output transactions

    **Graph Metrics:**
    - Graph Density: Ratio of actual connections to maximum possible
    - Average Degree: Average number of connections per address
    - Edge Count: Total number of detected links

    **Privacy Implications:**
    - All addresses in a cluster can be attributed to the same owner
    - Higher graph density = more address reuse = worse privacy
    - Change detection can reveal additional linked addresses
    - Large clusters indicate poor UTXO management

    **Parameters:**
    - address: The Bitcoin address to analyze
    - max_depth: How many hops to follow (1-5, default 3)
    - include_change_heuristic: Apply change detection (default true)
    - min_confidence: Only include links above this threshold (0.0-1.0, default 0.5)

    **Returns:**
    - cluster_size: Number of linked addresses
    - cluster_members: Detailed info for each address
    - edges: Individual connections between addresses
    - graph_metrics: Network analysis statistics
    - heuristic_breakdown: Count by detection method
    - recommendations: Privacy improvement suggestions
    """
    try:
        analyzer = get_privacy_analyzer()
        result = await analyzer.detect_cluster_advanced(
            address,
            max_depth,
            include_change_heuristic,
            min_confidence
        )
        return result
    except Exception as e:
        logger.error(f"Error in advanced cluster detection for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exchange-proximity/{address}")
async def analyze_exchange_proximity(
    address: str,
    max_hops: int = Query(6, ge=1, le=10, description="Maximum hops to search for exchange connections")
):
    """
    Analyze how close an address is to known exchange addresses.
    
    Traces both incoming and outgoing transactions to find the
    shortest path to a known exchange (Binance, Coinbase, Kraken, etc.).
    
    **Privacy Implications:**
    - Addresses close to exchanges are easily KYC-linked
    - Chain analysis firms can trace funds back to verified identities
    - Even 2-3 hops provides limited privacy
    
    **Parameters:**
    - address: The Bitcoin address to analyze
    - max_hops: Maximum hops to search (1-10, default 6)
    
    **Returns:**
    - nearest_exchange: Name of the closest exchange found
    - hops_to_exchange: Number of transactions between address and exchange
    - direction: Whether funds were received_from or sent_to exchange
    - proximity_score: 0-100 score (100 = directly connected)
    - risk_level: critical/high/medium/low
    - path_to_exchange: The transaction path connecting to the exchange
    """
    try:
        analyzer = get_privacy_analyzer()
        result = await analyzer.analyze_exchange_proximity(address, max_hops)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error in exchange proximity analysis for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/utxo-rating/{address}")
async def analyze_utxo_privacy(
    address: str
):
    """
    Analyze privacy rating for all UTXOs at an address.
    
    Rates each UTXO as Red/Yellow/Green based on multiple factors:
    - Exchange proximity (how close to KYC)
    - CoinJoin history (was it mixed?)
    - Cluster size (how many linked addresses?)
    - Age (mature UTXOs are slightly better)
    - Value patterns (round numbers suggest exchange withdrawals)
    
    **Privacy Implications:**
    - Red UTXOs should never be spent with private coins
    - Yellow UTXOs need caution when spending
    - Green UTXOs have reasonable privacy
    
    **Parameters:**
    - address: The Bitcoin address to analyze
    
    **Returns:**
    - overall_rating: red/yellow/green for the address
    - overall_score: 0-100 privacy score
    - rating_breakdown: Count of red/yellow/green UTXOs
    - utxos: Detailed analysis for each UTXO
    - recommendations: Suggested actions to improve privacy
    """
    try:
        analyzer = get_privacy_analyzer()
        result = await analyzer.analyze_utxo_privacy(address)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Error in UTXO privacy analysis for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/known-exchanges")
async def list_known_exchanges():
    """
    List all known exchange addresses in the database.
    
    This is useful for transparency - users can see what exchanges
    are being tracked and verify the address list.
    
    **Returns:**
    - exchanges: Dictionary of exchange names and their known addresses
    - total_addresses: Total number of tracked addresses
    """
    from app.core.privacy_analysis import KNOWN_EXCHANGE_ADDRESSES
    
    # Group by exchange
    exchanges = {}
    for addr, info in KNOWN_EXCHANGE_ADDRESSES.items():
        exchange_name = info["exchange"]
        if exchange_name not in exchanges:
            exchanges[exchange_name] = {"addresses": [], "types": set()}
        exchanges[exchange_name]["addresses"].append({
            "address": addr,
            "type": info["type"]
        })
        exchanges[exchange_name]["types"].add(info["type"])
    
    # Convert sets to lists for JSON
    for ex in exchanges.values():
        ex["types"] = list(ex["types"])
        ex["address_count"] = len(ex["addresses"])
    
    return {
        "exchanges": exchanges,
        "total_addresses": len(KNOWN_EXCHANGE_ADDRESSES),
        "exchange_count": len(exchanges)
    }


@router.get("/privacy-score/enhanced", response_model=EnhancedPrivacyScore)
async def get_enhanced_privacy_score(
    txid: str = Query(..., description="Transaction ID"),
    vout: int = Query(..., description="Output index"),
    max_depth: int = Query(10, ge=1, le=50, description="Maximum trace depth")
):
    """
    **ENHANCED PRIVACY ANALYSIS** with all sophisticated heuristics.

    This endpoint provides commercial-grade blockchain analysis combining:

    **Temporal Analysis:**
    - Timing correlation detection (fast spends = high risk)
    - Spend velocity patterns
    - Timezone fingerprinting
    - Path-level temporal scoring

    **Value Analysis:**
    - Amount uniqueness/fingerprinting (unique amounts = trackable)
    - Subset sum leak detection (reveals input-output mapping)
    - Amount correlation across CoinJoins
    - Dust/tracking pixel detection

    **Wallet Fingerprinting:**
    - Script type patterns
    - BIP-69 output ordering detection
    - Fee calculation strategies
    - Change position patterns

    **Advanced Pattern Detection:**
    - Peeling chain identification
    - Unnecessary input heuristic
    - Common input ownership

    **Existing Analysis:**
    - Exchange proximity (hops to known exchanges)
    - CoinJoin detection (Whirlpool, Wasabi, JoinMarket)
    - UTXO tracing (forward/backward)

    **Returns:**
    - Overall privacy score (0-100) with color-coded rating
    - Natural language summary
    - Privacy factors organized by category
    - Critical risks and warnings with remediation
    - Attack surface analysis with specific vectors
    - Actionable recommendations prioritized by impact
    - Comparative privacy context (benchmarks)
    - Assessment confidence and limitations

    **Example:**
    ```
    GET /api/v1/privacy-score/enhanced?txid=abc123...&vout=0&max_depth=10
    ```

    **CRITICAL WARNINGS:**
    - This is HEURISTIC ANALYSIS ONLY
    - Cannot detect: network analysis, off-chain data, advanced protocols
    - Do NOT use for operational security decisions
    - Privacy scores are conservative estimates
    - Consult security professionals for critical applications
    """
    try:
        logger.info(f"Enhanced privacy analysis requested: txid={txid[:16]}..., vout={vout}, depth={max_depth}")

        # Get analyzer instance
        analyzer = get_privacy_analyzer()

        # Run enhanced analysis
        result = await analyzer.analyze_utxo_privacy_enhanced(txid, vout, max_depth)

        logger.info(f"Enhanced analysis complete: score={result.overall_score}, rating={result.rating.value}")

        return result

    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid input: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Enhanced privacy analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Privacy analysis failed: {str(e)}"
        )
