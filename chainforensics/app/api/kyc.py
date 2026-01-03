"""
ChainForensics - KYC Privacy Check API
Endpoints for analyzing privacy of KYC exchange withdrawals.
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.kyc_trace import get_kyc_tracer, KYCPrivacyTracer
from app.core.entity_recognition import identify_entity
from app.core.bitcoin_rpc import get_rpc

logger = logging.getLogger("chainforensics.api.kyc")

router = APIRouter()


# ========== Helper Functions ==========

async def estimate_block_time(block_height: int) -> Optional[str]:
    """
    Estimate the timestamp of a block based on its height.

    Args:
        block_height: Block height to estimate

    Returns:
        ISO format timestamp string or None
    """
    try:
        rpc = get_rpc()
        block_hash = await rpc.get_block_hash(block_height)
        block_header = await rpc.get_block_header(block_hash, verbose=True)

        if block_header and 'time' in block_header:
            timestamp = datetime.utcfromtimestamp(block_header['time'])
            return timestamp.isoformat()
    except Exception as e:
        logger.warning(f"Failed to get block time for height {block_height}: {e}")

    return None


async def calculate_age_days(block_height: int) -> Optional[float]:
    """
    Calculate the age of a block in days.

    Args:
        block_height: Block height to calculate age for

    Returns:
        Age in days or None
    """
    try:
        rpc = get_rpc()

        # Get current block height
        current_height = await rpc.get_block_count()

        # Calculate block difference
        block_diff = current_height - block_height

        # Estimate days (average 10 minutes per block)
        days = (block_diff * 10) / (60 * 24)

        return round(days, 2)
    except Exception as e:
        logger.warning(f"Failed to calculate age for block {block_height}: {e}")

    return None


async def enrich_destination_with_metadata(destination: dict) -> dict:
    """
    Enrich a destination with entity recognition and timestamp data.

    Args:
        destination: Destination dictionary from trace results

    Returns:
        Enriched destination dictionary
    """
    # Add entity recognition
    address = destination.get('address')
    if address:
        entity_info = identify_entity(address)
        if entity_info:
            destination['entity_name'] = entity_info.name
            destination['entity_type'] = entity_info.entity_type
            destination['entity_confidence'] = entity_info.confidence
            destination['entity_emoji'] = entity_info.emoji
            destination['entity_risk_level'] = entity_info.risk_level
            destination['entity_description'] = entity_info.description

    # Add timestamp and age for the final node in the path
    if destination.get('path') and len(destination['path']) > 0:
        final_node = destination['path'][-1]

        # Use existing block_time from the path node
        block_time_str = final_node.get('block_time')
        if block_time_str:
            try:
                # Parse the ISO timestamp
                from datetime import datetime, timezone
                block_time = datetime.fromisoformat(block_time_str.replace('Z', '+00:00'))

                # Add timestamp
                destination['timestamp'] = block_time_str

                # Calculate age in days from current time
                now = datetime.now(timezone.utc)
                age_delta = now - block_time.replace(tzinfo=timezone.utc if block_time.tzinfo is None else block_time.tzinfo)
                age_days = age_delta.total_seconds() / (60 * 60 * 24)

                destination['age_days'] = round(age_days, 2)

                # Add human-readable age
                if age_days < 1:
                    destination['age_human'] = f"{age_days * 24:.1f} hours"
                elif age_days < 30:
                    destination['age_human'] = f"{age_days:.1f} days"
                elif age_days < 365:
                    destination['age_human'] = f"{age_days / 30:.1f} months"
                else:
                    destination['age_human'] = f"{age_days / 365:.1f} years"
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse block_time {block_time_str}: {e}")

    return destination


class KYCTraceRequest(BaseModel):
    """Request model for KYC privacy trace."""
    exchange_txid: str = Field(..., description="Transaction ID of the exchange withdrawal")
    destination_address: str = Field(..., description="Address that received the withdrawal")
    depth_preset: str = Field("standard", description="Depth preset: quick, standard, deep, or thorough")


@router.get("/presets")
async def get_depth_presets():
    """
    Get available depth presets for KYC privacy tracing.
    
    Returns the available scan depth options with descriptions.
    """
    return {
        "presets": KYCPrivacyTracer.DEPTH_PRESETS,
        "default": "standard",
        "description": "Choose a depth preset based on how thorough you want the analysis"
    }


@router.post("/trace")
async def trace_kyc_withdrawal(request: KYCTraceRequest):
    """
    Trace a KYC exchange withdrawal to analyze privacy.

    This endpoint helps you understand what an adversary who knows your
    exchange withdrawal details could potentially discover about your
    current Bitcoin holdings.

    **Input:**
    - `exchange_txid`: The transaction ID from your exchange withdrawal
    - `destination_address`: The address you withdrew to
    - `depth_preset`: How deep to search (quick/standard/deep/thorough)

    **Output:**
    - List of probable current destinations with confidence scores
    - Overall privacy score (0-100, higher = more private)
    - Risk intelligence (CRITICAL/MEDIUM/POSITIVE findings)
    - Prioritized recommendations (URGENT/IMPORTANT/BEST_PRACTICE)
    - Entity recognition for known exchanges/services
    - Timestamps and age for each destination
    """
    tracer = get_kyc_tracer()

    # Validate depth preset
    if request.depth_preset not in KYCPrivacyTracer.DEPTH_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid depth preset. Choose from: {list(KYCPrivacyTracer.DEPTH_PRESETS.keys())}"
        )

    try:
        result = await tracer.trace_kyc_withdrawal(
            exchange_txid=request.exchange_txid,
            destination_address=request.destination_address,
            depth_preset=request.depth_preset
        )

        # Convert to dict
        result_dict = result.to_dict()

        # Enrich each destination with entity recognition and timestamps
        if 'probable_destinations' in result_dict:
            enriched_destinations = []
            for dest in result_dict['probable_destinations']:
                enriched_dest = await enrich_destination_with_metadata(dest)
                enriched_destinations.append(enriched_dest)
            result_dict['probable_destinations'] = enriched_destinations

        # Add risk intelligence categorization
        risk_intelligence = tracer._categorize_risks(
            result.probable_destinations,
            result.original_value_sats
        )
        result_dict['risk_intelligence'] = risk_intelligence

        # Add prioritized recommendations
        recommendations_prioritized = tracer._prioritize_recommendations(
            result.probable_destinations,
            risk_intelligence,
            result
        )
        result_dict['recommendations_prioritized'] = recommendations_prioritized

        # Add enhanced flag
        result_dict['enhanced'] = True
        result_dict['phase'] = 'Phase 1 MVP'
        result_dict['features'] = [
            'Entity Recognition',
            'Risk Intelligence',
            'Timestamps',
            'Prioritized Recommendations'
        ]

        return result_dict

    except Exception as e:
        logger.error(f"KYC trace error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace")
async def trace_kyc_withdrawal_get(
    exchange_txid: str = Query(..., description="Transaction ID of the exchange withdrawal"),
    destination_address: str = Query(..., description="Address that received the withdrawal"),
    depth_preset: str = Query("standard", description="Depth preset: quick, standard, deep, thorough")
):
    """
    Trace a KYC exchange withdrawal to analyze privacy (GET version).

    Same as POST /trace but using query parameters for easier testing.

    **Enhanced with Phase 1 MVP features:**
    - Entity recognition for known exchanges/services
    - Risk intelligence categorization (CRITICAL/MEDIUM/POSITIVE)
    - Timestamps and age calculation for destinations
    - Prioritized recommendations (URGENT/IMPORTANT/BEST_PRACTICE)
    """
    tracer = get_kyc_tracer()

    # Validate depth preset
    if depth_preset not in KYCPrivacyTracer.DEPTH_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid depth preset. Choose from: {list(KYCPrivacyTracer.DEPTH_PRESETS.keys())}"
        )

    try:
        result = await tracer.trace_kyc_withdrawal(
            exchange_txid=exchange_txid,
            destination_address=destination_address,
            depth_preset=depth_preset
        )

        # Convert to dict
        result_dict = result.to_dict()

        # Enrich each destination with entity recognition and timestamps
        if 'probable_destinations' in result_dict:
            enriched_destinations = []
            for dest in result_dict['probable_destinations']:
                enriched_dest = await enrich_destination_with_metadata(dest)
                enriched_destinations.append(enriched_dest)
            result_dict['probable_destinations'] = enriched_destinations

        # Add risk intelligence categorization
        risk_intelligence = tracer._categorize_risks(
            result.probable_destinations,
            result.original_value_sats
        )
        result_dict['risk_intelligence'] = risk_intelligence

        # Add prioritized recommendations
        recommendations_prioritized = tracer._prioritize_recommendations(
            result.probable_destinations,
            risk_intelligence,
            result
        )
        result_dict['recommendations_prioritized'] = recommendations_prioritized

        # Add enhanced flag
        result_dict['enhanced'] = True
        result_dict['phase'] = 'Phase 1 MVP'
        result_dict['features'] = [
            'Entity Recognition',
            'Risk Intelligence',
            'Timestamps',
            'Prioritized Recommendations'
        ]

        return result_dict

    except Exception as e:
        logger.error(f"KYC trace error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick-check")
async def quick_privacy_check(
    exchange_txid: str = Query(..., description="Transaction ID of the exchange withdrawal"),
    destination_address: str = Query(..., description="Address that received the withdrawal")
):
    """
    Quick privacy check with minimal depth.
    
    Use this for a fast initial assessment. For thorough analysis, use /trace.
    """
    tracer = get_kyc_tracer()
    
    try:
        result = await tracer.trace_kyc_withdrawal(
            exchange_txid=exchange_txid,
            destination_address=destination_address,
            depth_preset="quick"
        )
        
        # Return simplified result
        return {
            "privacy_score": result.overall_privacy_score,
            "privacy_rating": result.privacy_rating,
            "summary": result.summary,
            "high_confidence_destinations": result.to_dict()["high_confidence_destinations"],
            "coinjoins_encountered": result.coinjoins_encountered,
            "recommendations": result.recommendations[:3] if result.recommendations else [],
            "full_analysis_available": True,
            "message": "Use /trace endpoint with higher depth for detailed analysis"
        }
        
    except Exception as e:
        logger.error(f"Quick check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
