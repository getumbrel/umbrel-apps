"""
ChainForensics - Jobs API
Endpoints for managing background analysis jobs.
"""
import logging
import uuid
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select

from app.database import get_db, AnalysisJob
from app.core.tracer import get_tracer
from app.core.coinjoin import get_detector
from app.core.bitcoin_rpc import get_rpc

logger = logging.getLogger("chainforensics.api.jobs")

router = APIRouter()


class JobCreateRequest(BaseModel):
    """Request to create a new analysis job."""
    job_type: str  # 'trace_forward', 'trace_backward', 'full_analysis', 'cluster'
    target_txid: Optional[str] = None
    target_address: Optional[str] = None
    parameters: Optional[dict] = None


class JobResponse(BaseModel):
    """Job status response."""
    id: str
    job_type: str
    status: str
    progress: int
    target_txid: Optional[str]
    target_address: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]


async def run_trace_job(job_id: str, txid: str, direction: str, max_depth: int):
    """Background task to run trace analysis."""
    async with get_db() as db:
        try:
            # Update job status to running
            job = await db.get(AnalysisJob, job_id)
            if not job:
                return
            
            job.status = "running"
            job.started_at = datetime.utcnow()
            await db.commit()
            
            # Run trace
            tracer = get_tracer()
            
            async def progress_callback(tx_count, visited, depth):
                job.progress = min(95, int((visited / max(max_depth * 10, 1)) * 100))
                await db.commit()
            
            if direction == "forward":
                result = await tracer.trace_forward(txid, 0, max_depth, progress_callback)
            else:
                result = await tracer.trace_backward(txid, max_depth, progress_callback)
            
            # Save result
            job.status = "completed"
            job.progress = 100
            job.result = json.dumps(result.to_dict())
            job.completed_at = datetime.utcnow()
            await db.commit()
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            job = await db.get(AnalysisJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                await db.commit()


async def run_full_analysis_job(job_id: str, txid: str, params: dict):
    """Background task to run full UTXO analysis."""
    async with get_db() as db:
        try:
            job = await db.get(AnalysisJob, job_id)
            if not job:
                return
            
            job.status = "running"
            job.started_at = datetime.utcnow()
            await db.commit()
            
            tracer = get_tracer()
            detector = get_detector()
            rpc = get_rpc()
            
            result = {
                "txid": txid,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Step 1: Get transaction details (10%)
            job.progress = 5
            await db.commit()
            
            tx = await rpc.get_transaction_with_inputs(txid)
            result["transaction"] = {
                "inputs": len(tx.get("vin", [])),
                "outputs": len(tx.get("vout", [])),
                "fee_sats": tx.get("fee_sats")
            }
            
            # Step 2: CoinJoin analysis (20%)
            job.progress = 20
            await db.commit()
            
            cj_result = detector.analyze_transaction(tx)
            result["coinjoin"] = cj_result.to_dict()
            
            # Step 3: Forward trace (50%)
            job.progress = 30
            await db.commit()
            
            forward_depth = params.get("forward_depth", 10)
            forward = await tracer.trace_forward(txid, 0, forward_depth)
            result["forward_trace"] = {
                "nodes": len(forward.nodes),
                "unspent_endpoints": len(forward.unspent_endpoints),
                "coinjoin_txids": forward.coinjoin_txids
            }
            
            job.progress = 50
            await db.commit()
            
            # Step 4: Backward trace (80%)
            backward_depth = params.get("backward_depth", 10)
            backward = await tracer.trace_backward(txid, backward_depth)
            result["backward_trace"] = {
                "nodes": len(backward.nodes),
                "coinbase_origins": len(backward.coinbase_origins),
                "coinjoin_txids": backward.coinjoin_txids
            }
            
            job.progress = 80
            await db.commit()
            
            # Step 5: Summary (100%)
            all_coinjoins = list(set(forward.coinjoin_txids + backward.coinjoin_txids))
            result["summary"] = {
                "total_transactions_analyzed": forward.total_transactions + backward.total_transactions,
                "unique_coinjoin_transactions": len(all_coinjoins),
                "coinjoin_txids": all_coinjoins,
                "unspent_outputs": len(forward.unspent_endpoints),
                "coinbase_origins": len(backward.coinbase_origins)
            }
            
            job.status = "completed"
            job.progress = 100
            job.result = json.dumps(result)
            job.completed_at = datetime.utcnow()
            await db.commit()
            
        except Exception as e:
            logger.error(f"Full analysis job {job_id} failed: {e}")
            job = await db.get(AnalysisJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                await db.commit()


@router.post("/")
async def create_job(request: JobCreateRequest, background_tasks: BackgroundTasks):
    """
    Create a new background analysis job.
    
    Supported job types:
    - trace_forward: Trace UTXO forward
    - trace_backward: Trace inputs backward
    - full_analysis: Complete analysis (forward + backward + coinjoin)
    - cluster: Address clustering (requires Electrs)
    """
    job_id = str(uuid.uuid4())
    
    # Validate request
    if request.job_type not in ["trace_forward", "trace_backward", "full_analysis", "cluster"]:
        raise HTTPException(status_code=400, detail=f"Invalid job type: {request.job_type}")
    
    if request.job_type in ["trace_forward", "trace_backward", "full_analysis"] and not request.target_txid:
        raise HTTPException(status_code=400, detail="target_txid required for trace jobs")
    
    if request.job_type == "cluster" and not request.target_address:
        raise HTTPException(status_code=400, detail="target_address required for cluster jobs")
    
    # Create job record
    async with get_db() as db:
        job = AnalysisJob(
            id=job_id,
            job_type=request.job_type,
            status="queued",
            target_txid=request.target_txid,
            target_address=request.target_address,
            parameters=json.dumps(request.parameters) if request.parameters else None,
            progress=0
        )
        db.add(job)
        await db.commit()
    
    # Schedule background task
    params = request.parameters or {}
    
    if request.job_type == "trace_forward":
        background_tasks.add_task(
            run_trace_job,
            job_id,
            request.target_txid,
            "forward",
            params.get("max_depth", 10)
        )
    elif request.job_type == "trace_backward":
        background_tasks.add_task(
            run_trace_job,
            job_id,
            request.target_txid,
            "backward",
            params.get("max_depth", 10)
        )
    elif request.job_type == "full_analysis":
        background_tasks.add_task(
            run_full_analysis_job,
            job_id,
            request.target_txid,
            params
        )
    elif request.job_type == "cluster":
        # Clustering requires Electrs - mark as not implemented
        async with get_db() as db:
            job = await db.get(AnalysisJob, job_id)
            job.status = "failed"
            job.error_message = "Address clustering requires Electrs integration"
            await db.commit()
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job created successfully",
        "poll_url": f"/api/v1/jobs/{job_id}"
    }


@router.get("/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific job."""
    async with get_db() as db:
        job = await db.get(AnalysisJob, job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        
        response = {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "target_txid": job.target_txid,
            "target_address": job.target_address,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message
        }
        
        # Include result if completed
        if job.status == "completed" and job.result:
            response["result"] = json.loads(job.result)
        
        return response


@router.get("/")
async def list_jobs(
    status: Optional[str] = Query(None, regex="^(queued|running|completed|failed|cancelled)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List all jobs with optional filtering."""
    async with get_db() as db:
        query = select(AnalysisJob).order_by(AnalysisJob.created_at.desc())
        
        if status:
            query = query.where(AnalysisJob.status == status)
        
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        return {
            "jobs": [
                {
                    "id": job.id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "progress": job.progress,
                    "target_txid": job.target_txid,
                    "created_at": job.created_at.isoformat() if job.created_at else None
                }
                for job in jobs
            ],
            "count": len(jobs),
            "offset": offset,
            "limit": limit
        }


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a queued or running job."""
    async with get_db() as db:
        job = await db.get(AnalysisJob, job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        
        if job.status in ["completed", "failed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job with status: {job.status}"
            )
        
        job.status = "cancelled"
        job.completed_at = datetime.utcnow()
        await db.commit()
        
        return {"message": "Job cancelled", "job_id": job_id}
