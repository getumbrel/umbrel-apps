"""
ChainForensics - Addresses API
Endpoints for address operations, lookups, and labeling.
Now with full Fulcrum integration!
"""
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.database import get_db, AddressLabel
from app.core.bitcoin_rpc import get_rpc, BitcoinRPCError
from app.core.fulcrum import get_fulcrum, check_fulcrum_connection, FulcrumError

logger = logging.getLogger("chainforensics.api.addresses")

router = APIRouter()


class AddressLabelRequest(BaseModel):
    """Request to create/update address label."""
    address: str
    label: str
    category: str = "other"  # 'exchange', 'personal', 'merchant', 'mixer', 'other'
    notes: Optional[str] = None


class AddressLabelResponse(BaseModel):
    """Address label response."""
    address: str
    label: str
    category: str
    notes: Optional[str]
    created_at: str
    updated_at: str


@router.get("/fulcrum/status")
async def get_fulcrum_status():
    """
    Check Fulcrum connection status.

    Returns connection info and server details if connected.
    """
    status = await check_fulcrum_connection()
    return status


@router.get("/{address}/validate")
async def validate_address(address: str):
    """
    Validate a Bitcoin address and identify its type.
    
    Returns:
    - Validity status
    - Address type (P2PKH, P2SH, P2WPKH, P2WSH, P2TR)
    - Network (mainnet, testnet)
    """
    try:
        rpc = get_rpc()
        result = await rpc.validate_address(address)
        
        # Determine address type from prefix
        addr_type = "unknown"
        network = "mainnet"
        
        if address.startswith("1"):
            addr_type = "P2PKH (Legacy)"
        elif address.startswith("3"):
            addr_type = "P2SH (Script Hash)"
        elif address.startswith("bc1q"):
            if len(address) == 42:
                addr_type = "P2WPKH (Native SegWit)"
            else:
                addr_type = "P2WSH (Native SegWit Script)"
        elif address.startswith("bc1p"):
            addr_type = "P2TR (Taproot)"
        elif address.startswith("m") or address.startswith("n") or address.startswith("2"):
            network = "testnet"
            addr_type = "Testnet address"
        elif address.startswith("tb1"):
            network = "testnet"
            addr_type = "Testnet SegWit"
        
        return {
            "address": address,
            "is_valid": result.get("isvalid", False),
            "type": addr_type,
            "network": network,
            "script_pubkey": result.get("scriptPubKey"),
            "is_witness": result.get("iswitness"),
            "witness_version": result.get("witness_version"),
            "witness_program": result.get("witness_program")
        }
        
    except BitcoinRPCError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error validating address {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{address}/info")
async def get_address_info(address: str):
    """
    Get comprehensive information about an address.

    Uses Fulcrum for balance, transaction history, and UTXOs.
    Falls back to basic validation if Fulcrum unavailable.
    """
    try:
        # Validate address first
        rpc = get_rpc()
        validation = await rpc.validate_address(address)

        if not validation.get("isvalid"):
            raise HTTPException(status_code=400, detail="Invalid Bitcoin address")

        # Get stored label
        label_data = None
        async with get_db() as db:
            result = await db.execute(
                select(AddressLabel).where(AddressLabel.address == address)
            )
            label = result.scalar_one_or_none()
            if label:
                label_data = {
                    "label": label.label,
                    "category": label.category,
                    "notes": label.notes,
                    "created_at": label.created_at.isoformat() if label.created_at else None
                }

        # Try to get Fulcrum data
        fulcrum_data = None
        fulcrum_status = "not_available"

        try:
            fulcrum = get_fulcrum()
            if fulcrum.is_configured:
                info = await fulcrum.get_address_info(address)
                fulcrum_data = info
                fulcrum_status = "connected"
        except FulcrumError as e:
            logger.warning(f"Fulcrum error for {address}: {e}")
            fulcrum_status = f"error: {e.message}"
        except Exception as e:
            logger.warning(f"Could not get Fulcrum data for {address}: {e}")
            fulcrum_status = f"error: {str(e)}"

        response = {
            "address": address,
            "is_valid": True,
            "label": label_data,
            "fulcrum_status": fulcrum_status
        }

        if fulcrum_data:
            response.update({
                "balance": fulcrum_data.get("balance"),
                "transaction_count": fulcrum_data.get("transaction_count"),
                "utxo_count": fulcrum_data.get("utxo_count"),
                "first_seen_height": fulcrum_data.get("first_seen_height"),
                "last_seen_height": fulcrum_data.get("last_seen_height"),
                "total_received_btc": fulcrum_data.get("total_received_btc"),
                "total_sent_btc": fulcrum_data.get("total_sent_btc"),
                "total_received_sats": fulcrum_data.get("total_received_sats"),
                "total_sent_sats": fulcrum_data.get("total_sent_sats"),
                "totals_complete": fulcrum_data.get("totals_complete", True),
                "transactions": fulcrum_data.get("transactions"),
                "utxos": fulcrum_data.get("utxos"),
                "warnings": fulcrum_data.get("warnings", []),
                "history_truncated": fulcrum_data.get("history_truncated", False),
                "utxos_truncated": fulcrum_data.get("utxos_truncated", False)
            })

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting address info {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{address}/balance")
async def get_address_balance(address: str):
    """
    Get balance for an address.

    Requires Fulcrum integration.
    """
    try:
        fulcrum = get_fulcrum()

        if not fulcrum.is_configured:
            raise HTTPException(
                status_code=503,
                detail="Fulcrum not configured. Set FULCRUM_HOST in environment."
            )

        balance = await fulcrum.get_balance(address)
        return balance.to_dict()

    except FulcrumError as e:
        raise HTTPException(status_code=500, detail=f"Fulcrum error: {e.message}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting balance for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{address}/history")
async def get_address_history(
    address: str,
    limit: int = Query(50, ge=1, le=500, description="Maximum transactions to return")
):
    """
    Get transaction history for an address.

    Requires Fulcrum integration.
    """
    try:
        fulcrum = get_fulcrum()

        if not fulcrum.is_configured:
            raise HTTPException(
                status_code=503,
                detail="Fulcrum not configured. Set FULCRUM_HOST in environment."
            )

        history = await fulcrum.get_history(address)

        # Sort by height descending (newest first)
        history.sort(key=lambda x: x.height if x.height > 0 else float('inf'), reverse=True)

        return {
            "address": address,
            "transaction_count": len(history),
            "transactions": [tx.to_dict() for tx in history[:limit]]
        }

    except FulcrumError as e:
        raise HTTPException(status_code=500, detail=f"Fulcrum error: {e.message}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting history for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{address}/utxos")
async def get_address_utxos(address: str):
    """
    Get unspent transaction outputs (UTXOs) for an address.

    Requires Fulcrum integration.
    """
    try:
        fulcrum = get_fulcrum()

        if not fulcrum.is_configured:
            raise HTTPException(
                status_code=503,
                detail="Fulcrum not configured. Set FULCRUM_HOST in environment."
            )

        utxos = await fulcrum.get_utxos(address)

        # Sort by value descending
        utxos.sort(key=lambda x: x.value_sats, reverse=True)

        total_value = sum(u.value_sats for u in utxos)

        return {
            "address": address,
            "utxo_count": len(utxos),
            "total_value_sats": total_value,
            "total_value_btc": total_value / 100_000_000,
            "utxos": [utxo.to_dict() for utxo in utxos]
        }

    except FulcrumError as e:
        raise HTTPException(status_code=500, detail=f"Fulcrum error: {e.message}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting UTXOs for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{address}/dust-check")
async def check_address_dust(
    address: str,
    threshold_sats: int = Query(1000, ge=1, le=100000, description="Dust threshold in satoshis")
):
    """
    Check an address for potential dust attack UTXOs.

    Dust attacks send tiny amounts to track address clustering
    when the dust is spent with other UTXOs.

    Requires Fulcrum integration.
    """
    try:
        fulcrum = get_fulcrum()

        if not fulcrum.is_configured:
            raise HTTPException(
                status_code=503,
                detail="Fulcrum not configured. Set FULCRUM_HOST in environment."
            )

        result = await fulcrum.check_dust_attack(address, threshold_sats)
        return result

    except FulcrumError as e:
        raise HTTPException(status_code=500, detail=f"Fulcrum error: {e.message}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking dust for {address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/labels")
async def create_or_update_label(request: AddressLabelRequest):
    """
    Create or update a label for an address.
    
    Categories:
    - exchange: Known exchange address
    - personal: Your own address
    - merchant: Known merchant/service
    - mixer: Known mixing service
    - other: Other/unknown
    """
    try:
        # Validate address first
        rpc = get_rpc()
        validation = await rpc.validate_address(request.address)
        
        if not validation.get("isvalid"):
            raise HTTPException(status_code=400, detail="Invalid Bitcoin address")
        
        async with get_db() as db:
            # Check if label exists
            result = await db.execute(
                select(AddressLabel).where(AddressLabel.address == request.address)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update
                existing.label = request.label
                existing.category = request.category
                existing.notes = request.notes
                existing.updated_at = datetime.utcnow()
                action = "updated"
            else:
                # Create
                label = AddressLabel(
                    address=request.address,
                    label=request.label,
                    category=request.category,
                    notes=request.notes
                )
                db.add(label)
                action = "created"
            
            await db.commit()
        
        return {
            "message": f"Label {action} successfully",
            "address": request.address,
            "label": request.label,
            "category": request.category
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating label for {request.address}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/labels")
async def list_labels(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """List all stored address labels."""
    async with get_db() as db:
        query = select(AddressLabel).order_by(AddressLabel.updated_at.desc())
        
        if category:
            query = query.where(AddressLabel.category == category)
        
        if search:
            query = query.where(
                AddressLabel.label.ilike(f"%{search}%") |
                AddressLabel.address.ilike(f"%{search}%")
            )
        
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        labels = result.scalars().all()
        
        return {
            "labels": [
                {
                    "address": l.address,
                    "label": l.label,
                    "category": l.category,
                    "notes": l.notes,
                    "created_at": l.created_at.isoformat() if l.created_at else None,
                    "updated_at": l.updated_at.isoformat() if l.updated_at else None
                }
                for l in labels
            ],
            "count": len(labels),
            "offset": offset,
            "limit": limit
        }


@router.delete("/labels/{address}")
async def delete_label(address: str):
    """Delete a label for an address."""
    async with get_db() as db:
        result = await db.execute(
            select(AddressLabel).where(AddressLabel.address == address)
        )
        label = result.scalar_one_or_none()
        
        if not label:
            raise HTTPException(status_code=404, detail="Label not found")
        
        await db.delete(label)
        await db.commit()
        
        return {"message": "Label deleted", "address": address}


@router.get("/{address}/label")
async def get_address_label(address: str):
    """Get label for a specific address."""
    async with get_db() as db:
        result = await db.execute(
            select(AddressLabel).where(AddressLabel.address == address)
        )
        label = result.scalar_one_or_none()
        
        if not label:
            return {"address": address, "label": None}
        
        return {
            "address": address,
            "label": label.label,
            "category": label.category,
            "notes": label.notes,
            "created_at": label.created_at.isoformat() if label.created_at else None,
            "updated_at": label.updated_at.isoformat() if label.updated_at else None
        }
