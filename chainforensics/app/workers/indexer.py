"""
ChainForensics - Background Indexer
Continuously indexes blockchain data for faster analysis.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.config import settings
from app.core.bitcoin_rpc import get_rpc, BitcoinRPCError
from app.database import get_db, Transaction, TransactionOutput

logger = logging.getLogger("chainforensics.worker.indexer")


class BackgroundIndexer:
    """
    Background worker that indexes blockchain data.
    
    This enables faster queries by pre-caching transaction data
    and building a local spending index.
    """
    
    def __init__(self):
        self.running = False
        self.last_indexed_height = 0
        self.indexed_count = 0
    
    async def start(self):
        """Start the background indexer."""
        if self.running:
            logger.warning("Indexer already running")
            return
        
        self.running = True
        logger.info("Background indexer starting...")
        
        while self.running:
            try:
                await self._index_cycle()
            except Exception as e:
                logger.error(f"Indexer cycle error: {e}")
            
            # Wait before next cycle
            await asyncio.sleep(60)  # Check every minute
    
    def stop(self):
        """Stop the background indexer."""
        self.running = False
        logger.info("Background indexer stopped")
    
    async def _index_cycle(self):
        """Single indexing cycle."""
        try:
            rpc = get_rpc()
            
            # Get current block height
            blockchain_info = await rpc.get_blockchain_info()
            current_height = blockchain_info.get("blocks", 0)
            
            if current_height <= self.last_indexed_height:
                return  # No new blocks
            
            # Index new blocks (limit to prevent overload)
            blocks_to_index = min(10, current_height - self.last_indexed_height)
            
            for i in range(blocks_to_index):
                height = self.last_indexed_height + i + 1
                await self._index_block(height)
                self.last_indexed_height = height
            
            logger.debug(f"Indexed up to block {self.last_indexed_height}")
            
        except BitcoinRPCError as e:
            logger.warning(f"RPC error during indexing: {e}")
        except Exception as e:
            logger.error(f"Indexing error: {e}")
    
    async def _index_block(self, height: int):
        """Index a single block."""
        try:
            rpc = get_rpc()
            
            # Get block
            block_hash = await rpc.get_block_hash(height)
            block = await rpc.get_block(block_hash, 2)  # Verbosity 2 = full tx data
            
            if not block:
                return
            
            block_time = block.get("time")
            
            # Index transactions
            for tx in block.get("tx", []):
                await self._index_transaction(tx, height, block_hash, block_time)
                self.indexed_count += 1
            
        except Exception as e:
            logger.error(f"Error indexing block {height}: {e}")
    
    async def _index_transaction(
        self,
        tx: dict,
        block_height: int,
        block_hash: str,
        block_time: int
    ):
        """Index a single transaction."""
        try:
            txid = tx.get("txid")
            if not txid:
                return
            
            # Check if already indexed
            async with get_db() as db:
                existing = await db.get(Transaction, txid)
                if existing:
                    return
                
                # Calculate values
                vins = tx.get("vin", [])
                vouts = tx.get("vout", [])
                is_coinbase = any("coinbase" in vin for vin in vins)
                total_output = sum(int(out.get("value", 0) * 100_000_000) for out in vouts)
                
                # Create transaction record
                tx_record = Transaction(
                    txid=txid,
                    block_hash=block_hash,
                    block_height=block_height,
                    block_time=datetime.utcfromtimestamp(block_time) if block_time else None,
                    size=tx.get("size", 0),
                    vsize=tx.get("vsize", 0),
                    weight=tx.get("weight", 0),
                    version=tx.get("version", 0),
                    locktime=tx.get("locktime", 0),
                    input_count=len(vins),
                    output_count=len(vouts),
                    total_output_sats=total_output,
                    is_coinbase=is_coinbase
                )
                
                db.add(tx_record)
                
                # Index outputs
                for vout in vouts:
                    script = vout.get("scriptPubKey", {})
                    output = TransactionOutput(
                        txid=txid,
                        vout_index=vout.get("n", 0),
                        value_sats=int(vout.get("value", 0) * 100_000_000),
                        address=script.get("address"),
                        script_type=script.get("type", "unknown"),
                        script_hex=script.get("hex"),
                        is_spent=False
                    )
                    db.add(output)
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Error indexing transaction: {e}")


# Global indexer instance
_indexer: Optional[BackgroundIndexer] = None


def get_indexer() -> BackgroundIndexer:
    """Get or create indexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = BackgroundIndexer()
    return _indexer


async def start_background_indexer():
    """Start the background indexer task."""
    indexer = get_indexer()
    await indexer.start()
