"""
ChainForensics - Bitcoin Core RPC Client
Async client for communicating with local Bitcoin Core node.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from decimal import Decimal

import httpx

from app.config import settings

logger = logging.getLogger("chainforensics.rpc")


class BitcoinRPCError(Exception):
    """Bitcoin RPC error."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"RPC Error {code}: {message}")


class BitcoinRPC:
    """Async Bitcoin Core RPC client."""
    
    def __init__(self):
        self.url = settings.bitcoin_rpc_url
        self.timeout = settings.BITCOIN_RPC_TIMEOUT
        self._request_id = 0
    
    async def _call(self, method: str, params: List = None) -> Any:
        """Make RPC call to Bitcoin Core."""
        if params is None:
            params = []
        
        self._request_id += 1
        payload = {
            "jsonrpc": "1.0",
            "id": f"chainforensics-{self._request_id}",
            "method": method,
            "params": params
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 401:
                    raise BitcoinRPCError(-1, "Authentication failed - check RPC credentials")
                
                result = response.json()
                
                if "error" in result and result["error"]:
                    raise BitcoinRPCError(
                        result["error"].get("code", -1),
                        result["error"].get("message", "Unknown error")
                    )
                
                return result.get("result")
                
            except httpx.ConnectError as e:
                raise BitcoinRPCError(-1, f"Connection failed: {e}")
            except httpx.TimeoutException:
                raise BitcoinRPCError(-1, f"Request timed out after {self.timeout}s")
    
    # ============== Blockchain Info ==============
    
    async def get_blockchain_info(self) -> Dict:
        """Get blockchain information."""
        return await self._call("getblockchaininfo")
    
    async def get_block_count(self) -> int:
        """Get current block height."""
        return await self._call("getblockcount")
    
    async def get_block_hash(self, height: int) -> str:
        """Get block hash at height."""
        return await self._call("getblockhash", [height])
    
    async def get_block(self, block_hash: str, verbosity: int = 1) -> Dict:
        """Get block by hash."""
        return await self._call("getblock", [block_hash, verbosity])
    
    async def get_block_header(self, block_hash: str, verbose: bool = True) -> Dict:
        """Get block header."""
        return await self._call("getblockheader", [block_hash, verbose])
    
    # ============== Transaction Methods ==============
    
    async def get_raw_transaction(self, txid: str, verbose: bool = True) -> Dict:
        """Get transaction by txid. Requires txindex=1."""
        return await self._call("getrawtransaction", [txid, verbose])
    
    async def decode_raw_transaction(self, hex_string: str) -> Dict:
        """Decode raw transaction hex."""
        return await self._call("decoderawtransaction", [hex_string])
    
    async def get_tx_out(self, txid: str, vout: int, include_mempool: bool = True) -> Optional[Dict]:
        """Get UTXO. Returns None if spent."""
        return await self._call("gettxout", [txid, vout, include_mempool])
    
    async def get_tx_out_set_info(self) -> Dict:
        """Get UTXO set statistics."""
        return await self._call("gettxoutsetinfo")
    
    # ============== Mempool Methods ==============
    
    async def get_mempool_info(self) -> Dict:
        """Get mempool statistics."""
        return await self._call("getmempoolinfo")
    
    async def get_raw_mempool(self, verbose: bool = False) -> Any:
        """Get all mempool transaction IDs or details."""
        return await self._call("getrawmempool", [verbose])
    
    async def get_mempool_entry(self, txid: str) -> Dict:
        """Get mempool entry for specific transaction."""
        return await self._call("getmempoolentry", [txid])
    
    # ============== Address Methods ==============
    
    async def validate_address(self, address: str) -> Dict:
        """Validate a Bitcoin address."""
        return await self._call("validateaddress", [address])
    
    async def get_address_info(self, address: str) -> Dict:
        """Get address information (wallet addresses only)."""
        return await self._call("getaddressinfo", [address])
    
    # ============== Utility Methods ==============
    
    async def estimate_smart_fee(self, conf_target: int = 6) -> Dict:
        """Estimate fee rate for confirmation target."""
        return await self._call("estimatesmartfee", [conf_target])
    
    async def get_network_info(self) -> Dict:
        """Get network information."""
        return await self._call("getnetworkinfo")
    
    # ============== Batch Methods ==============
    
    async def batch_get_transactions(self, txids: List[str]) -> List[Dict]:
        """Get multiple transactions efficiently."""
        tasks = [self.get_raw_transaction(txid, True) for txid in txids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        transactions = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to fetch tx {txids[i]}: {result}")
                transactions.append(None)
            else:
                transactions.append(result)
        
        return transactions
    
    async def is_utxo_spent(self, txid: str, vout: int) -> bool:
        """Check if a UTXO is spent."""
        result = await self.get_tx_out(txid, vout)
        return result is None
    
    async def get_transaction_with_inputs(self, txid: str) -> Dict:
        """Get transaction with input values resolved."""
        tx = await self.get_raw_transaction(txid, True)
        
        if not tx:
            return None
        
        # Resolve input values
        total_input = 0
        for vin in tx.get("vin", []):
            if "coinbase" in vin:
                vin["value"] = None
                vin["address"] = None
                continue
            
            try:
                prev_tx = await self.get_raw_transaction(vin["txid"], True)
                if prev_tx and vin["vout"] < len(prev_tx["vout"]):
                    prev_out = prev_tx["vout"][vin["vout"]]
                    vin["value"] = prev_out["value"]
                    vin["address"] = prev_out.get("scriptPubKey", {}).get("address")
                    total_input += int(prev_out["value"] * 100_000_000)
            except Exception as e:
                logger.warning(f"Could not resolve input {vin['txid']}:{vin['vout']}: {e}")
                vin["value"] = None
                vin["address"] = None
        
        # Calculate fee
        total_output = sum(int(out["value"] * 100_000_000) for out in tx.get("vout", []))
        if total_input > 0:
            tx["fee"] = (total_input - total_output) / 100_000_000
            tx["fee_sats"] = total_input - total_output
        
        return tx


# ============== Electrs Client (for address lookups) ==============

class ElectrsClient:
    """Client for Electrs/Fulcrum Electrum protocol server."""
    
    def __init__(self):
        self.host = settings.ELECTRS_HOST
        self.port = settings.ELECTRS_PORT
        self.connected = False
    
    async def connect(self):
        """Connect to Electrs server."""
        if not self.host:
            raise Exception("Electrs not configured")
        
        # Electrum protocol uses JSON-RPC over TCP
        # Implementation would use asyncio streams
        # For now, using HTTP if Electrs exposes REST API
        pass
    
    async def get_address_history(self, address: str) -> List[Dict]:
        """Get transaction history for address."""
        # This would use blockchain.scripthash.get_history
        # Requires converting address to scripthash
        raise NotImplementedError("Electrs integration pending")
    
    async def get_address_balance(self, address: str) -> Dict:
        """Get address balance."""
        raise NotImplementedError("Electrs integration pending")
    
    async def get_address_utxos(self, address: str) -> List[Dict]:
        """Get UTXOs for address."""
        raise NotImplementedError("Electrs integration pending")


# Singleton instances
_rpc_instance: Optional[BitcoinRPC] = None
_electrs_instance: Optional[ElectrsClient] = None


def get_rpc() -> BitcoinRPC:
    """Get or create RPC instance."""
    global _rpc_instance
    if _rpc_instance is None:
        _rpc_instance = BitcoinRPC()
    return _rpc_instance


def get_electrs() -> ElectrsClient:
    """Get or create Electrs instance."""
    global _electrs_instance
    if _electrs_instance is None:
        _electrs_instance = ElectrsClient()
    return _electrs_instance
