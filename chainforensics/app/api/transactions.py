"""
ChainForensics - Transactions API
Endpoints for transaction operations.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.bitcoin_rpc import BitcoinRPC, BitcoinRPCError, get_rpc

logger = logging.getLogger("chainforensics.api.transactions")

router = APIRouter()


class TransactionResponse(BaseModel):
    """Transaction response model."""
    txid: str
    block_hash: Optional[str] = None
    block_height: Optional[int] = None
    block_time: Optional[int] = None
    confirmations: Optional[int] = None
    size: int
    vsize: int
    weight: int
    version: int
    locktime: int
    inputs: list
    outputs: list
    fee_sats: Optional[int] = None
    is_coinbase: bool = False


class DecodeRequest(BaseModel):
    """Request to decode raw transaction."""
    hex: str


@router.get("/{txid}")
async def get_transaction(
    txid: str,
    resolve_inputs: bool = Query(False, description="Resolve input values from previous transactions")
):
    """
    Get transaction by txid.
    
    Requires txindex=1 on Bitcoin Core.
    """
    try:
        rpc = get_rpc()
        
        if resolve_inputs:
            tx = await rpc.get_transaction_with_inputs(txid)
        else:
            tx = await rpc.get_raw_transaction(txid, True)
        
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transaction not found: {txid}")
        
        # Format response
        inputs = []
        for vin in tx.get("vin", []):
            if "coinbase" in vin:
                inputs.append({
                    "type": "coinbase",
                    "coinbase": vin["coinbase"],
                    "sequence": vin.get("sequence")
                })
            else:
                inputs.append({
                    "txid": vin.get("txid"),
                    "vout": vin.get("vout"),
                    "value": vin.get("value"),  # Only present if resolve_inputs=True
                    "address": vin.get("address"),
                    "sequence": vin.get("sequence")
                })
        
        outputs = []
        for vout in tx.get("vout", []):
            script = vout.get("scriptPubKey", {})
            outputs.append({
                "n": vout.get("n"),
                "value_btc": vout.get("value"),
                "value_sats": int(vout.get("value", 0) * 100_000_000),
                "address": script.get("address"),
                "type": script.get("type"),
                "asm": script.get("asm"),
                "hex": script.get("hex")
            })
        
        return {
            "txid": tx.get("txid"),
            "hash": tx.get("hash"),
            "block_hash": tx.get("blockhash"),
            "block_height": tx.get("blockheight"),
            "block_time": tx.get("blocktime"),
            "confirmations": tx.get("confirmations"),
            "size": tx.get("size"),
            "vsize": tx.get("vsize"),
            "weight": tx.get("weight"),
            "version": tx.get("version"),
            "locktime": tx.get("locktime"),
            "inputs": inputs,
            "outputs": outputs,
            "input_count": len(inputs),
            "output_count": len(outputs),
            "total_output_btc": sum(o["value_btc"] for o in outputs),
            "total_output_sats": sum(o["value_sats"] for o in outputs),
            "fee_sats": tx.get("fee_sats"),
            "fee_btc": tx.get("fee"),
            "is_coinbase": any("coinbase" in vin for vin in tx.get("vin", []))
        }
        
    except BitcoinRPCError as e:
        if "txindex" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="Transaction index not available. Enable txindex=1 in Bitcoin Core."
            )
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching transaction {txid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decode")
async def decode_transaction(request: DecodeRequest):
    """Decode raw transaction hex."""
    try:
        rpc = get_rpc()
        tx = await rpc.decode_raw_transaction(request.hex)
        
        return {
            "txid": tx.get("txid"),
            "hash": tx.get("hash"),
            "version": tx.get("version"),
            "size": tx.get("size"),
            "vsize": tx.get("vsize"),
            "weight": tx.get("weight"),
            "locktime": tx.get("locktime"),
            "vin": tx.get("vin"),
            "vout": tx.get("vout")
        }
        
    except BitcoinRPCError as e:
        raise HTTPException(status_code=400, detail=f"Invalid transaction hex: {e}")
    except Exception as e:
        logger.error(f"Error decoding transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{txid}/utxo/{vout}")
async def check_utxo(txid: str, vout: int):
    """
    Check if a specific UTXO is spent or unspent.
    """
    try:
        rpc = get_rpc()
        utxo = await rpc.get_tx_out(txid, vout)
        
        if utxo:
            return {
                "txid": txid,
                "vout": vout,
                "status": "unspent",
                "value_btc": utxo.get("value"),
                "value_sats": int(utxo.get("value", 0) * 100_000_000),
                "confirmations": utxo.get("confirmations"),
                "script_type": utxo.get("scriptPubKey", {}).get("type"),
                "address": utxo.get("scriptPubKey", {}).get("address")
            }
        else:
            return {
                "txid": txid,
                "vout": vout,
                "status": "spent",
                "message": "This UTXO has been spent"
            }
            
    except BitcoinRPCError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error checking UTXO {txid}:{vout}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{txid}/context")
async def get_transaction_context(txid: str):
    """
    Get contextual information about a transaction.
    Includes block info, fee analysis, timing.
    """
    try:
        rpc = get_rpc()
        tx = await rpc.get_transaction_with_inputs(txid)
        
        if not tx:
            raise HTTPException(status_code=404, detail=f"Transaction not found: {txid}")
        
        context = {
            "txid": txid,
            "confirmations": tx.get("confirmations", 0),
            "in_mempool": tx.get("confirmations", 0) == 0
        }
        
        # Block context
        if tx.get("blockhash"):
            block = await rpc.get_block(tx["blockhash"], 1)
            block_txids = block.get("tx", [])
            
            context["block"] = {
                "hash": tx["blockhash"],
                "height": block.get("height"),
                "time": block.get("time"),
                "tx_count": len(block_txids),
                "position_in_block": block_txids.index(txid) if txid in block_txids else None
            }
        
        # Fee context
        if tx.get("fee_sats") and tx.get("vsize"):
            fee_rate = tx["fee_sats"] / tx["vsize"]
            context["fee"] = {
                "total_sats": tx["fee_sats"],
                "rate_sat_vbyte": round(fee_rate, 2)
            }
        
        # Size context
        context["size"] = {
            "bytes": tx.get("size"),
            "vbytes": tx.get("vsize"),
            "weight": tx.get("weight")
        }
        
        return context
        
    except BitcoinRPCError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transaction context {txid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
