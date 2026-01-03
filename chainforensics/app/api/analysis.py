"""
ChainForensics - Analysis API
Endpoints for UTXO tracing and CoinJoin detection.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.core.tracer import UTXOTracer, get_tracer
from app.core.coinjoin import CoinJoinDetector, get_detector
from app.core.bitcoin_rpc import BitcoinRPC, BitcoinRPCError, get_rpc

logger = logging.getLogger("chainforensics.api.analysis")

router = APIRouter()


class TraceRequest(BaseModel):
    """Request model for trace operations."""
    txid: str
    vout: int = 0
    max_depth: int = 10


class PrivacyScoreResponse(BaseModel):
    """Privacy score response."""
    txid: str
    vout: int
    score: int
    factors: list
    recommendations: list


@router.get("/trace/forward")
async def trace_forward(
    txid: str,
    vout: int = Query(0, ge=0, description="Output index"),
    max_depth: int = Query(10, ge=1, le=50, description="Maximum trace depth")
):
    """
    Trace a UTXO forward through subsequent spends.
    
    Follows the UTXO until it reaches:
    - Unspent outputs (current endpoints)
    - Maximum depth limit
    
    Returns the trace graph with all intermediate transactions.
    """
    logger.info(f"=== API trace_forward CALLED === txid={txid[:16]}..., vout={vout}, max_depth={max_depth}")
    try:
        tracer = get_tracer()
        logger.info("API trace_forward: Calling tracer.trace_forward()...")
        result = await tracer.trace_forward(txid, vout, max_depth)
        
        logger.info(f"API trace_forward: Trace completed, converting to dict...")
        result_dict = result.to_dict()
        
        logger.info(f"API trace_forward: Returning response with {len(result_dict.get('nodes', []))} nodes")
        return result_dict
        
    except BitcoinRPCError as e:
        logger.error(f"API trace_forward: BitcoinRPCError: {e}")
        raise HTTPException(status_code=500, detail=f"Bitcoin RPC error: {e}")
    except Exception as e:
        logger.error(f"API trace_forward: EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"API trace_forward: Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/backward")
async def trace_backward(
    txid: str,
    max_depth: int = Query(10, ge=1, le=50, description="Maximum trace depth")
):
    """
    Trace a transaction backward through its inputs.
    
    Follows inputs until reaching:
    - Coinbase transactions (mining origins)
    - Maximum depth limit
    
    Returns the trace graph showing the origin of funds.
    """
    try:
        tracer = get_tracer()
        result = await tracer.trace_backward(txid, max_depth)
        
        return result.to_dict()
        
    except BitcoinRPCError as e:
        raise HTTPException(status_code=500, detail=f"Bitcoin RPC error: {e}")
    except Exception as e:
        logger.error(f"Error tracing backward {txid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/tree")
async def get_utxo_tree(
    txid: str,
    forward_depth: int = Query(5, ge=1, le=20, description="Forward trace depth"),
    backward_depth: int = Query(5, ge=1, le=20, description="Backward trace depth")
):
    """
    Get complete UTXO tree (both directions).
    
    Combines forward and backward traces to show full context
    of a transaction in the blockchain.
    """
    try:
        tracer = get_tracer()
        result = await tracer.get_utxo_tree(txid, forward_depth, backward_depth)
        
        return result
        
    except BitcoinRPCError as e:
        raise HTTPException(status_code=500, detail=f"Bitcoin RPC error: {e}")
    except Exception as e:
        logger.error(f"Error getting UTXO tree {txid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coinjoin/{txid}")
async def detect_coinjoin(txid: str):
    """
    Analyze a transaction for CoinJoin characteristics.
    
    Detects:
    - Whirlpool (Samourai)
    - Wasabi Wallet
    - JoinMarket
    - PayJoin (P2EP)
    - Generic equal-output patterns
    
    Returns confidence score and matched heuristics.
    """
    try:
        rpc = get_rpc()
        tx = await rpc.get_raw_transaction(txid, True)
        
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transaction not found: {txid}")
        
        detector = get_detector()
        result = detector.analyze_transaction(tx)
        
        response = result.to_dict()
        
        # Add transaction stats
        response["transaction_stats"] = {
            "input_count": len(tx.get("vin", [])),
            "output_count": len(tx.get("vout", [])),
            "total_output_btc": sum(out.get("value", 0) for out in tx.get("vout", []))
        }
        
        return response
        
    except BitcoinRPCError as e:
        raise HTTPException(status_code=500, detail=f"Bitcoin RPC error: {e}")
    except Exception as e:
        logger.error(f"Error analyzing CoinJoin {txid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coinjoin/history/{txid}")
async def get_coinjoin_history(
    txid: str,
    direction: str = Query("backward", regex="^(forward|backward|both)$"),
    max_depth: int = Query(10, ge=1, le=30)
):
    """
    Check if any transaction in a UTXO's history involved CoinJoin.
    
    Traces in specified direction and analyzes each transaction.
    NOTE: This can be slow for deep traces. Use the Trace buttons for quick results.
    """
    try:
        rpc = get_rpc()
        tracer = get_tracer()
        detector = get_detector()
        
        # Get trace
        transactions = []
        
        if direction in ["backward", "both"]:
            backward = await tracer.trace_backward(txid, max_depth)
            for node in backward.nodes:
                try:
                    tx = await rpc.get_raw_transaction(node.txid, True)
                    if tx:
                        transactions.append(tx)
                except Exception:
                    pass
        
        if direction in ["forward", "both"]:
            forward = await tracer.trace_forward(txid, 0, max_depth)
            for node in forward.nodes:
                try:
                    tx = await rpc.get_raw_transaction(node.txid, True)
                    if tx and tx.get("txid") not in [t.get("txid") for t in transactions]:
                        transactions.append(tx)
                except Exception:
                    pass
        
        # Analyze for CoinJoin
        history = detector.get_coinjoin_history(transactions)
        
        return {
            "start_txid": txid,
            "direction": direction,
            "max_depth": max_depth,
            **history
        }
        
    except Exception as e:
        logger.error(f"Error getting CoinJoin history {txid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/privacy-score")
async def calculate_privacy_score(
    txid: str,
    vout: int = Query(0, ge=0)
):
    """
    Calculate privacy score for a UTXO.
    
    Factors considered:
    - CoinJoin in current transaction
    - CoinJoin in immediate parent transactions (1 level only)
    - UTXO age
    - Round amounts
    - Consolidation patterns
    
    This is a QUICK analysis. For deep history, use the Trace features.
    """
    try:
        rpc = get_rpc()
        detector = get_detector()
        
        # Get transaction (1 RPC call)
        tx = await rpc.get_raw_transaction(txid, True)
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transaction not found: {txid}")
        
        score = 50  # Base score
        factors = []
        recommendations = []
        
        # Factor 1: CoinJoin in current transaction (no RPC call - just analysis)
        cj_result = detector.analyze_transaction(tx)
        if cj_result.score > 0.7:
            score += 30
            factors.append({
                "name": "coinjoin_current",
                "impact": "+30",
                "description": f"Transaction is a CoinJoin ({cj_result.protocol.value})"
            })
        elif cj_result.score > 0.4:
            score += 15
            factors.append({
                "name": "coinjoin_possible",
                "impact": "+15",
                "description": f"Transaction has CoinJoin characteristics ({cj_result.score*100:.0f}% confidence)"
            })
        
        # Factor 2: Check immediate parent transactions for CoinJoin
        # Limited to max 3 inputs to keep it fast
        coinjoin_in_history = False
        inputs_checked = 0
        max_inputs_to_check = 3
        
        for vin in tx.get("vin", []):
            if inputs_checked >= max_inputs_to_check:
                break
            if "coinbase" in vin:
                continue
            if "txid" in vin:
                try:
                    parent_tx = await rpc.get_raw_transaction(vin["txid"], True)
                    if parent_tx:
                        inputs_checked += 1
                        parent_cj = detector.analyze_transaction(parent_tx)
                        if parent_cj.score > 0.7:
                            coinjoin_in_history = True
                            break
                except Exception:
                    pass
        
        if coinjoin_in_history:
            score += 15
            factors.append({
                "name": "coinjoin_history",
                "impact": "+15",
                "description": "CoinJoin found in immediate parent transactions"
            })
        else:
            recommendations.append("Consider using CoinJoin to improve privacy")
        
        # Factor 3: UTXO age
        confirmations = tx.get("confirmations", 0)
        if confirmations > 52560:  # ~1 year
            score += 10
            factors.append({
                "name": "utxo_age",
                "impact": "+10",
                "description": "UTXO is over 1 year old"
            })
        elif confirmations > 4380:  # ~1 month
            score += 5
            factors.append({
                "name": "utxo_age",
                "impact": "+5",
                "description": "UTXO is over 1 month old"
            })
        
        # Factor 4: Round amount (negative)
        if vout < len(tx.get("vout", [])):
            value = tx["vout"][vout].get("value", 0)
            if value > 0 and value == round(value, 1):
                score -= 10
                factors.append({
                    "name": "round_amount",
                    "impact": "-10",
                    "description": f"Round amount ({value} BTC) may indicate exchange withdrawal"
                })
                recommendations.append("Avoid using round BTC amounts")
        
        # Factor 5: Consolidation (negative)
        input_count = len(tx.get("vin", []))
        if input_count > 10:
            score -= 20
            factors.append({
                "name": "consolidation_large",
                "impact": "-20",
                "description": f"Large consolidation transaction ({input_count} inputs)"
            })
            recommendations.append("Avoid consolidating many UTXOs from different sources")
        elif input_count > 5:
            score -= 10
            factors.append({
                "name": "consolidation",
                "impact": "-10",
                "description": f"Consolidation transaction ({input_count} inputs)"
            })
            recommendations.append("Consider the privacy implications of consolidating UTXOs")
        
        # Factor 6: Multiple outputs is good for ambiguity
        output_count = len(tx.get("vout", []))
        if output_count >= 5:
            score += 5
            factors.append({
                "name": "multiple_outputs",
                "impact": "+5",
                "description": f"Multiple outputs ({output_count}) adds ambiguity"
            })
        
        # Clamp score
        score = max(0, min(100, score))
        
        # Determine rating
        if score >= 70:
            rating = "good"
            summary = "This UTXO has good privacy characteristics"
        elif score >= 40:
            rating = "moderate"
            summary = "This UTXO has some privacy concerns"
        else:
            rating = "poor"
            summary = "This UTXO has significant privacy issues"
        
        return {
            "txid": txid,
            "vout": vout,
            "score": score,
            "rating": rating,
            "summary": summary,
            "factors": factors,
            "recommendations": recommendations,
            "analysis_depth": f"Checked current tx + {inputs_checked} parent transactions"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating privacy score {txid}:{vout}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/privacy-score/deep")
async def calculate_deep_privacy_score(
    txid: str,
    vout: int = Query(0, ge=0),
    depth: int = Query(3, ge=1, le=10, description="How many levels back to check")
):
    """
    Calculate DEEP privacy score with full backward trace.
    
    WARNING: This can be slow for transactions with many inputs.
    Use the regular /privacy-score for quick results.
    """
    try:
        rpc = get_rpc()
        tracer = get_tracer()
        detector = get_detector()
        
        # Get transaction
        tx = await rpc.get_raw_transaction(txid, True)
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transaction not found: {txid}")
        
        score = 50  # Base score
        factors = []
        recommendations = []
        
        # Factor 1: CoinJoin in current transaction
        cj_result = detector.analyze_transaction(tx)
        if cj_result.score > 0.7:
            score += 30
            factors.append({
                "name": "coinjoin_current",
                "impact": "+30",
                "description": f"Transaction is a CoinJoin ({cj_result.protocol.value})"
            })
        
        # Factor 2: Full backward trace for CoinJoin history
        backward = await tracer.trace_backward(txid, depth)
        
        coinjoin_count = len(backward.coinjoin_txids)
        if coinjoin_count > 0:
            bonus = min(20, coinjoin_count * 5)  # Up to +20 for multiple CoinJoins
            score += bonus
            factors.append({
                "name": "coinjoin_history",
                "impact": f"+{bonus}",
                "description": f"Found {coinjoin_count} CoinJoin transaction(s) in history"
            })
        else:
            recommendations.append("Consider using CoinJoin to improve privacy")
        
        # Factor 3: UTXO age
        confirmations = tx.get("confirmations", 0)
        if confirmations > 52560:
            score += 10
            factors.append({
                "name": "utxo_age",
                "impact": "+10",
                "description": "UTXO is over 1 year old"
            })
        elif confirmations > 4380:
            score += 5
            factors.append({
                "name": "utxo_age",
                "impact": "+5",
                "description": "UTXO is over 1 month old"
            })
        
        # Factor 4: Round amount
        if vout < len(tx.get("vout", [])):
            value = tx["vout"][vout].get("value", 0)
            if value > 0 and value == round(value, 1):
                score -= 10
                factors.append({
                    "name": "round_amount",
                    "impact": "-10",
                    "description": f"Round amount ({value} BTC) may indicate exchange withdrawal"
                })
        
        # Factor 5: Consolidation
        input_count = len(tx.get("vin", []))
        if input_count > 5:
            score -= 15
            factors.append({
                "name": "consolidation",
                "impact": "-15",
                "description": f"Consolidation transaction ({input_count} inputs)"
            })
        
        # Clamp score
        score = max(0, min(100, score))
        
        # Rating
        if score >= 70:
            rating = "good"
            summary = "This UTXO has good privacy characteristics"
        elif score >= 40:
            rating = "moderate"
            summary = "This UTXO has some privacy concerns"
        else:
            rating = "poor"
            summary = "This UTXO has significant privacy issues"
        
        return {
            "txid": txid,
            "vout": vout,
            "score": score,
            "rating": rating,
            "summary": summary,
            "factors": factors,
            "recommendations": recommendations,
            "trace_summary": {
                "depth_analyzed": depth,
                "transactions_scanned": backward.total_transactions,
                "coinjoins_found": coinjoin_count,
                "coinjoin_txids": backward.coinjoin_txids,
                "execution_time_ms": backward.execution_time_ms
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating deep privacy score {txid}:{vout}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dust-check/{address}")
async def check_dust_attack(address: str):
    """
    Check an address for potential dust attack UTXOs.
    
    Dust attacks send tiny amounts to track address clustering
    when the dust is spent with other UTXOs.
    
    Note: Requires Electrs for full address lookup.
    """
    return {
        "address": address,
        "status": "not_implemented",
        "message": "Full dust detection requires Electrs integration",
        "guidance": {
            "what_is_dust": "Tiny UTXOs (< 546 sats) sent by attackers to track your spending",
            "protection": [
                "Never consolidate unknown small UTXOs with main funds",
                "Use coin control to select specific UTXOs",
                "Consider CoinJoin before consolidating suspicious UTXOs"
            ]
        }
    }
