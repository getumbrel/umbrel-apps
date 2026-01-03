"""
ChainForensics - Fulcrum Client
Full Electrum protocol implementation for address lookups.
Optimized for Fulcrum's high-performance capabilities.
"""
import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

from app.config import settings

logger = logging.getLogger("chainforensics.fulcrum")


class FulcrumHealthTracker:
    """Tracks Fulcrum operational health over time."""

    FAILURE_WINDOW_SECONDS = 300  # Track failures for 5 minutes
    CLEAR_AFTER_SECONDS = 180  # Clear warning after 3 minutes of no failures

    def __init__(self):
        self._failures: deque = deque()  # List of failure timestamps
        self._last_success: Optional[float] = None
        self._lock = asyncio.Lock()

    async def record_failure(self, error_msg: str = ""):
        """Record a Fulcrum operation failure."""
        async with self._lock:
            now = time.time()
            self._failures.append((now, error_msg))
            self._cleanup_old_failures()

    async def record_success(self):
        """Record a successful Fulcrum operation."""
        async with self._lock:
            self._last_success = time.time()

    def _cleanup_old_failures(self):
        """Remove failures older than the tracking window."""
        cutoff = time.time() - self.FAILURE_WINDOW_SECONDS
        while self._failures and self._failures[0][0] < cutoff:
            self._failures.popleft()

    async def get_status(self) -> Dict:
        """Get current Fulcrum health status."""
        async with self._lock:
            self._cleanup_old_failures()
            now = time.time()

            failure_count = len(self._failures)
            recent_errors = [err for ts, err in list(self._failures)[-5:]]  # Last 5 errors

            # Calculate time since last failure
            time_since_last_failure = None
            if self._failures:
                time_since_last_failure = now - self._failures[-1][0]

            # Determine if we should show a warning
            # Show warning if there are failures in the window
            # Clear warning if no failures for CLEAR_AFTER_SECONDS
            show_warning = False
            if failure_count > 0:
                if time_since_last_failure is not None and time_since_last_failure < self.CLEAR_AFTER_SECONDS:
                    show_warning = True

            return {
                "failure_count_5min": failure_count,
                "last_success": self._last_success,
                "time_since_last_failure": time_since_last_failure,
                "show_warning": show_warning,
                "recent_errors": recent_errors,
                "warning_message": "Fulcrum experiencing issues - you may need to restart the Fulcrum app" if show_warning else None
            }


# Global health tracker instance
_health_tracker: Optional[FulcrumHealthTracker] = None


def get_health_tracker() -> FulcrumHealthTracker:
    """Get or create the health tracker instance."""
    global _health_tracker
    if _health_tracker is None:
        _health_tracker = FulcrumHealthTracker()
    return _health_tracker


class FulcrumError(Exception):
    """Fulcrum client error."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Fulcrum Error {code}: {message}")


@dataclass
class AddressBalance:
    """Address balance information."""
    address: str
    confirmed_sats: int
    unconfirmed_sats: int

    @property
    def confirmed_btc(self) -> float:
        return self.confirmed_sats / 100_000_000

    @property
    def unconfirmed_btc(self) -> float:
        return self.unconfirmed_sats / 100_000_000

    @property
    def total_sats(self) -> int:
        return self.confirmed_sats + self.unconfirmed_sats

    @property
    def total_btc(self) -> float:
        return self.total_sats / 100_000_000

    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "confirmed_sats": self.confirmed_sats,
            "confirmed_btc": self.confirmed_btc,
            "unconfirmed_sats": self.unconfirmed_sats,
            "unconfirmed_btc": self.unconfirmed_btc,
            "total_sats": self.total_sats,
            "total_btc": self.total_btc
        }


@dataclass
class AddressUTXO:
    """UTXO belonging to an address."""
    txid: str
    vout: int
    value_sats: int
    height: int  # 0 if unconfirmed

    @property
    def value_btc(self) -> float:
        return self.value_sats / 100_000_000

    @property
    def is_confirmed(self) -> bool:
        return self.height > 0

    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "value_sats": self.value_sats,
            "value_btc": self.value_btc,
            "height": self.height,
            "is_confirmed": self.is_confirmed
        }


@dataclass
class AddressTransaction:
    """Transaction involving an address."""
    txid: str
    height: int  # 0 if unconfirmed
    fee: Optional[int] = None

    @property
    def is_confirmed(self) -> bool:
        return self.height > 0

    def to_dict(self) -> Dict:
        return {
            "txid": self.txid,
            "height": self.height,
            "is_confirmed": self.is_confirmed,
            "fee": self.fee
        }


class FulcrumClient:
    """
    Full Electrum protocol client for Fulcrum.

    Implements the Electrum protocol over TCP for address-based queries.
    Optimized for Fulcrum's high-performance capabilities.
    Reference: https://electrumx.readthedocs.io/en/latest/protocol-methods.html
    """

    # Fulcrum is much more performant - reduce retries and delays
    MAX_RETRIES = 2
    RETRY_DELAY = 0.5  # seconds (reduced from 1.0)

    def __init__(self, host: str = None, port: int = None):
        self.host = host or settings.FULCRUM_HOST
        self.port = port or settings.FULCRUM_PORT
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._connected = False
        self._handshake_complete = False
        self._server_version_info: Optional[Dict] = None
        self._last_successful_call = None

    @property
    def is_configured(self) -> bool:
        """Check if Fulcrum is configured."""
        return bool(self.host and self.port)

    async def connect(self, force_reconnect: bool = False) -> bool:
        """Connect to Fulcrum server."""
        if not self.is_configured:
            logger.warning("Fulcrum not configured (FULCRUM_HOST not set)")
            return False

        # Check if we need to reconnect
        if not force_reconnect and self._connected and self._writer and not self._writer.is_closing():
            return True

        # Close existing connection if any
        if self._writer:
            await self.disconnect()

        try:
            # Use large buffer limit (64MB) - Fulcrum can handle much larger responses than Electrs
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port, limit=64*1024*1024),
                timeout=10.0
            )
            self._connected = True
            logger.info(f"Connected to Fulcrum at {self.host}:{self.port}")
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to Fulcrum at {self.host}:{self.port}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Fulcrum: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from Fulcrum server."""
        logger.debug("Fulcrum: Disconnecting...")
        self._connected = False
        self._handshake_complete = False
        self._server_version_info = None
        if self._writer:
            try:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Fulcrum: Timeout waiting for writer to close")
            except Exception as e:
                logger.debug(f"Fulcrum: Error closing writer: {e}")
        self._reader = None
        self._writer = None
        logger.debug("Fulcrum: Disconnected")

    async def _perform_handshake(self) -> bool:
        """
        Perform Electrum protocol handshake (server.version).
        MUST only be called once per connection - Electrum protocol requirement.
        Returns True if handshake successful, False otherwise.
        """
        if self._handshake_complete:
            logger.debug("Fulcrum: Handshake already complete, skipping")
            return True

        try:
            logger.debug("Fulcrum: Performing handshake (server.version)")
            # Call server.version directly without going through _call to avoid recursion
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "server.version",
                "params": ["ChainForensics", "1.4"]
            }

            request_line = json.dumps(request) + "\n"
            self._writer.write(request_line.encode())
            await self._writer.drain()

            response_line = await asyncio.wait_for(
                self._reader.readline(),
                timeout=10.0
            )

            if not response_line:
                raise FulcrumError(-1, "Empty response during handshake")

            response = json.loads(response_line.decode())

            if "error" in response and response["error"]:
                error = response["error"]
                raise FulcrumError(
                    error.get("code", -1),
                    error.get("message", "Unknown error")
                )

            result = response.get("result")
            self._server_version_info = {
                "server_software": result[0] if isinstance(result, list) else result,
                "protocol_version": result[1] if isinstance(result, list) and len(result) > 1 else "1.4"
            }

            self._handshake_complete = True
            logger.debug(f"Fulcrum: Handshake complete - server={self._server_version_info.get('server_software')}")
            return True

        except Exception as e:
            logger.error(f"Fulcrum: Handshake failed: {e}")
            return False

    async def _call(self, method: str, params: List = None) -> Any:
        """Make JSON-RPC call to Fulcrum with automatic retry."""
        if params is None:
            params = []

        last_error = None
        tracker = get_health_tracker()

        for attempt in range(self.MAX_RETRIES):
            try:
                result = await self._call_once(method, params)
                # Record success
                await tracker.record_success()
                return result
            except FulcrumError as e:
                last_error = e
                logger.warning(f"Fulcrum call failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")

                # Disconnect and wait before retry
                await self.disconnect()

                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))

        # All retries failed - record failure
        error_msg = str(last_error) if last_error else "All retries failed"
        await tracker.record_failure(error_msg)
        raise last_error or FulcrumError(-1, "All retries failed")

    async def _call_once(self, method: str, params: List) -> Any:
        """Make a single JSON-RPC call to Fulcrum."""
        async with self._lock:
            # Ensure connected
            if not await self.connect():
                raise FulcrumError(-1, "Not connected to Fulcrum")

            # Perform handshake if not done yet (but only once per connection)
            if not self._handshake_complete:
                if not await self._perform_handshake():
                    raise FulcrumError(-1, "Handshake failed")

            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params
            }

            try:
                # Send request
                request_line = json.dumps(request) + "\n"
                self._writer.write(request_line.encode())
                await self._writer.drain()

                # Read response - Fulcrum is much faster, increased timeout for very large responses
                response_line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=120.0  # Increased from 60s for large address histories
                )

                if not response_line:
                    raise FulcrumError(-1, "Empty response from Fulcrum")

                response = json.loads(response_line.decode())

                if "error" in response and response["error"]:
                    error = response["error"]
                    raise FulcrumError(
                        error.get("code", -1),
                        error.get("message", "Unknown error")
                    )

                self._last_successful_call = asyncio.get_event_loop().time()
                return response.get("result")

            except asyncio.TimeoutError:
                await self.disconnect()
                raise FulcrumError(-1, "Request timed out")
            except json.JSONDecodeError as e:
                await self.disconnect()
                raise FulcrumError(-1, f"Invalid JSON response: {e}")
            except Exception as e:
                if isinstance(e, FulcrumError):
                    raise
                await self.disconnect()
                raise FulcrumError(-1, f"Request failed: {e}")

    # ============== Address Conversion ==============

    @staticmethod
    def address_to_scripthash(address: str) -> str:
        """
        Convert a Bitcoin address to an Electrum scripthash.

        The scripthash is the SHA256 hash of the scriptPubKey, reversed.
        This is what Electrum protocol uses for address lookups.
        """
        import hashlib

        # Decode address to get scriptPubKey
        script_pubkey = FulcrumClient._address_to_script_pubkey(address)

        # SHA256 hash
        sha256_hash = hashlib.sha256(script_pubkey).digest()

        # Reverse bytes (Electrum uses little-endian)
        reversed_hash = sha256_hash[::-1]

        return reversed_hash.hex()

    @staticmethod
    def _address_to_script_pubkey(address: str) -> bytes:
        """Convert Bitcoin address to scriptPubKey bytes."""

        # P2PKH (Legacy) - starts with 1
        if address.startswith('1'):
            pubkey_hash = FulcrumClient._base58_decode_check(address)[1:]  # Remove version byte
            # OP_DUP OP_HASH160 <20 bytes> OP_EQUALVERIFY OP_CHECKSIG
            return bytes([0x76, 0xa9, 0x14]) + pubkey_hash + bytes([0x88, 0xac])

        # P2SH (Script Hash) - starts with 3
        elif address.startswith('3'):
            script_hash = FulcrumClient._base58_decode_check(address)[1:]  # Remove version byte
            # OP_HASH160 <20 bytes> OP_EQUAL
            return bytes([0xa9, 0x14]) + script_hash + bytes([0x87])

        # P2WPKH (Native SegWit) - starts with bc1q, 42 chars
        elif address.startswith('bc1q') and len(address) == 42:
            _, data = FulcrumClient._bech32_decode(address)
            witness_program = FulcrumClient._convert_bits(data[1:], 5, 8, False)
            # OP_0 <20 bytes>
            return bytes([0x00, 0x14]) + bytes(witness_program)

        # P2WSH (Native SegWit Script) - starts with bc1q, 62 chars
        elif address.startswith('bc1q') and len(address) == 62:
            _, data = FulcrumClient._bech32_decode(address)
            witness_program = FulcrumClient._convert_bits(data[1:], 5, 8, False)
            # OP_0 <32 bytes>
            return bytes([0x00, 0x20]) + bytes(witness_program)

        # P2TR (Taproot) - starts with bc1p
        elif address.startswith('bc1p'):
            _, data = FulcrumClient._bech32m_decode(address)
            witness_program = FulcrumClient._convert_bits(data[1:], 5, 8, False)
            # OP_1 <32 bytes>
            return bytes([0x51, 0x20]) + bytes(witness_program)

        # Testnet addresses
        elif address.startswith(('m', 'n')):
            pubkey_hash = FulcrumClient._base58_decode_check(address)[1:]
            return bytes([0x76, 0xa9, 0x14]) + pubkey_hash + bytes([0x88, 0xac])

        elif address.startswith('2'):
            script_hash = FulcrumClient._base58_decode_check(address)[1:]
            return bytes([0xa9, 0x14]) + script_hash + bytes([0x87])

        elif address.startswith('tb1q'):
            _, data = FulcrumClient._bech32_decode(address)
            witness_program = FulcrumClient._convert_bits(data[1:], 5, 8, False)
            if len(witness_program) == 20:
                return bytes([0x00, 0x14]) + bytes(witness_program)
            else:
                return bytes([0x00, 0x20]) + bytes(witness_program)

        elif address.startswith('tb1p'):
            _, data = FulcrumClient._bech32m_decode(address)
            witness_program = FulcrumClient._convert_bits(data[1:], 5, 8, False)
            return bytes([0x51, 0x20]) + bytes(witness_program)

        else:
            raise ValueError(f"Unsupported address format: {address}")

    @staticmethod
    def _base58_decode_check(address: str) -> bytes:
        """Decode Base58Check encoded address."""
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

        # Decode base58
        num = 0
        for char in address:
            num = num * 58 + alphabet.index(char)

        # Convert to bytes
        combined = num.to_bytes(25, 'big')

        # Verify checksum
        checksum = combined[-4:]
        payload = combined[:-4]

        hash1 = hashlib.sha256(payload).digest()
        hash2 = hashlib.sha256(hash1).digest()

        if hash2[:4] != checksum:
            raise ValueError("Invalid checksum")

        return payload

    @staticmethod
    def _bech32_decode(address: str) -> Tuple[str, List[int]]:
        """Decode Bech32 address."""
        CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

        # Find separator
        pos = address.rfind('1')
        if pos < 1 or pos + 7 > len(address):
            raise ValueError("Invalid bech32 address")

        hrp = address[:pos].lower()
        data_part = address[pos + 1:].lower()

        # Decode data
        data = []
        for c in data_part:
            if c not in CHARSET:
                raise ValueError(f"Invalid character: {c}")
            data.append(CHARSET.index(c))

        # Verify checksum (simplified - just return data without checksum)
        return hrp, data[:-6]

    @staticmethod
    def _bech32m_decode(address: str) -> Tuple[str, List[int]]:
        """Decode Bech32m address (for Taproot)."""
        # Same structure as bech32, different checksum constant
        return FulcrumClient._bech32_decode(address)

    @staticmethod
    def _convert_bits(data: List[int], from_bits: int, to_bits: int, pad: bool = True) -> List[int]:
        """Convert between bit sizes."""
        acc = 0
        bits = 0
        result = []
        maxv = (1 << to_bits) - 1

        for value in data:
            acc = (acc << from_bits) | value
            bits += from_bits
            while bits >= to_bits:
                bits -= to_bits
                result.append((acc >> bits) & maxv)

        if pad and bits:
            result.append((acc << (to_bits - bits)) & maxv)

        return result

    # ============== Server Methods ==============

    async def server_version(self) -> Dict:
        """
        Get server version information.
        Returns cached version info from the handshake.
        """
        async with self._lock:
            # Ensure we're connected and handshake is done
            if not self._handshake_complete:
                if not await self.connect():
                    raise FulcrumError(-1, "Not connected to Fulcrum")
                if not await self._perform_handshake():
                    raise FulcrumError(-1, "Handshake failed")

            return self._server_version_info

    async def server_banner(self) -> str:
        """Get server banner message."""
        return await self._call("server.banner")

    async def server_ping(self) -> bool:
        """Ping the server."""
        try:
            await self._call("server.ping")
            return True
        except Exception:
            return False

    # ============== Blockchain Methods ==============

    async def get_block_header(self, height: int) -> str:
        """Get block header at height (hex)."""
        return await self._call("blockchain.block.header", [height])

    async def get_block_headers(self, start_height: int, count: int) -> Dict:
        """Get multiple block headers."""
        return await self._call("blockchain.block.headers", [start_height, count])

    async def estimate_fee(self, blocks: int = 6) -> float:
        """Estimate fee rate (BTC/kB) for confirmation in n blocks."""
        return await self._call("blockchain.estimatefee", [blocks])

    async def get_tip(self) -> Dict:
        """Get current blockchain tip."""
        result = await self._call("blockchain.headers.subscribe")
        # Result can be a dict or sometimes just the header info
        if isinstance(result, dict):
            return {
                "height": result.get("height"),
                "hex": result.get("hex")
            }
        elif isinstance(result, list) and len(result) > 0:
            # Some servers return [{"height": ..., "hex": ...}]
            first = result[0] if isinstance(result[0], dict) else {}
            return {
                "height": first.get("height"),
                "hex": first.get("hex")
            }
        else:
            return {"height": None, "hex": None}

    # ============== Address/ScriptHash Methods ==============

    async def get_balance(self, address: str) -> AddressBalance:
        """Get balance for an address."""
        scripthash = self.address_to_scripthash(address)
        result = await self._call("blockchain.scripthash.get_balance", [scripthash])

        return AddressBalance(
            address=address,
            confirmed_sats=result.get("confirmed", 0),
            unconfirmed_sats=result.get("unconfirmed", 0)
        )

    async def get_history(self, address: str) -> List[AddressTransaction]:
        """Get transaction history for an address."""
        scripthash = self.address_to_scripthash(address)
        logger.info(f"get_history: Calling Fulcrum for address {address[:20]}... (connected={self._connected})")

        try:
            result = await self._call("blockchain.scripthash.get_history", [scripthash])
        except Exception as e:
            logger.warning(f"get_history: _call failed with {type(e).__name__}: {e}")
            return []

        # Handle None or invalid result
        if not result or not isinstance(result, list):
            logger.warning(f"get_history: Got invalid result: {type(result).__name__}")
            return []

        logger.info(f"get_history: Got {len(result)} transactions")

        transactions = []
        for item in result:
            if not isinstance(item, dict):
                continue
            transactions.append(AddressTransaction(
                txid=item.get("tx_hash"),
                height=item.get("height", 0),
                fee=item.get("fee")
            ))

        return transactions

    async def get_mempool(self, address: str) -> List[AddressTransaction]:
        """Get unconfirmed transactions for an address."""
        scripthash = self.address_to_scripthash(address)
        result = await self._call("blockchain.scripthash.get_mempool", [scripthash])

        # Handle None or invalid result
        if not result or not isinstance(result, list):
            return []

        transactions = []
        for item in result:
            if not isinstance(item, dict):
                continue
            transactions.append(AddressTransaction(
                txid=item.get("tx_hash"),
                height=0,
                fee=item.get("fee")
            ))

        return transactions

    async def get_utxos(self, address: str) -> List[AddressUTXO]:
        """Get unspent outputs for an address."""
        scripthash = self.address_to_scripthash(address)
        result = await self._call("blockchain.scripthash.listunspent", [scripthash])

        # Handle None or invalid result
        if not result or not isinstance(result, list):
            return []

        utxos = []
        for item in result:
            if not isinstance(item, dict):
                continue
            utxos.append(AddressUTXO(
                txid=item.get("tx_hash"),
                vout=item.get("tx_pos"),
                value_sats=item.get("value"),
                height=item.get("height", 0)
            ))

        return utxos

    # ============== Transaction Methods ==============

    async def get_transaction(self, txid: str, verbose: bool = True) -> Optional[Dict]:
        """Get raw transaction."""
        try:
            result = await self._call("blockchain.transaction.get", [txid, verbose])
        except Exception as e:
            logger.warning(f"get_transaction: _call failed: {e}")
            return None

        # Validate response is a dict (not a hex string)
        if isinstance(result, dict):
            return result
        elif isinstance(result, str):
            # Fulcrum returned hex string - verbose mode may not be supported
            logger.warning(f"Fulcrum returned hex string for {txid}, verbose mode may not be supported")
            return None
        return result

    async def broadcast_transaction(self, raw_tx_hex: str) -> str:
        """Broadcast a raw transaction. Returns txid."""
        return await self._call("blockchain.transaction.broadcast", [raw_tx_hex])

    async def get_merkle_proof(self, txid: str, height: int) -> Dict:
        """Get merkle proof for a transaction."""
        return await self._call("blockchain.transaction.get_merkle", [txid, height])

    async def get_tx_from_position(self, height: int, tx_pos: int, merkle: bool = False) -> str:
        """Get transaction hash from block position."""
        return await self._call("blockchain.transaction.id_from_pos", [height, tx_pos, merkle])

    # ============== High-Level Methods ==============

    async def get_address_info(self, address: str) -> Dict:
        """
        Get comprehensive address information.
        Optimized for Fulcrum's high performance - much more aggressive than Electrs version.
        """
        warnings = []

        # Get balance first (usually fast)
        balance = None
        try:
            balance = await asyncio.wait_for(self.get_balance(address), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning(f"get_address_info: Balance lookup timed out for {address}")
            warnings.append("Balance lookup timed out")
        except Exception as e:
            logger.warning(f"get_address_info: Balance lookup failed: {e}")
            warnings.append(f"Balance lookup failed: {str(e)[:50]}")

        # Get history - Fulcrum handles large histories much better
        history = []
        history_truncated = False
        try:
            # Increased timeout - Fulcrum can handle it
            history = await asyncio.wait_for(self.get_history(address), timeout=180.0)
            if len(history) > 10000:
                warnings.append(f"Address has {len(history)} transactions - showing last 100")
                history_truncated = True
        except asyncio.TimeoutError:
            logger.warning(f"get_address_info: History lookup timed out for {address}")
            warnings.append("Transaction history too large to fetch")
            await self.disconnect()
        except Exception as e:
            logger.warning(f"get_address_info: History lookup failed: {e}")
            warnings.append(f"History lookup failed: {str(e)[:50]}")
            await self.disconnect()

        # Get UTXOs
        utxos = []
        utxos_truncated = False
        try:
            # Increased timeout for large UTXO sets
            utxos = await asyncio.wait_for(self.get_utxos(address), timeout=180.0)
            if len(utxos) > 5000:
                warnings.append(f"Address has {len(utxos)} UTXOs - display may be limited")
                utxos_truncated = True
        except asyncio.TimeoutError:
            logger.warning(f"get_address_info: UTXO lookup timed out for {address}")
            warnings.append("UTXO lookup timed out")
            await self.disconnect()
        except Exception as e:
            logger.warning(f"get_address_info: UTXO lookup failed: {e}")
            warnings.append(f"UTXO lookup failed: {str(e)[:50]}")
            await self.disconnect()

        # Calculate stats from what we got
        first_seen = None
        last_seen = None
        if history:
            heights = [h.height for h in history if h.height > 0]
            if heights:
                first_seen = min(heights)
                last_seen = max(heights)

        # Calculate total received and sent - Fulcrum is fast enough to handle more
        total_received_sats = 0
        total_sent_sats = 0
        totals_complete = True
        totals_calculated = False

        # Increased limit for Fulcrum - it can handle much more
        MAX_TXS_FOR_TOTALS = 500
        if history and len(history) <= MAX_TXS_FOR_TOTALS:
            try:
                txs_to_process = history
                logger.info(f"get_address_info: Calculating totals from {len(txs_to_process)} transactions")

                processed = 0
                for hist_tx in txs_to_process:
                    try:
                        # Increased timeout per transaction
                        tx = await asyncio.wait_for(
                            self.get_transaction(hist_tx.txid, verbose=True),
                            timeout=10.0
                        )
                        if not tx or not isinstance(tx, dict):
                            continue

                        # Check outputs - if this address received
                        for vout in tx.get("vout", []):
                            script = vout.get("scriptPubKey", {})
                            out_addr = script.get("address")
                            if out_addr == address:
                                value_sats = int(vout.get("value", 0) * 100_000_000)
                                total_received_sats += value_sats

                        # Check inputs - if this address sent
                        for vin in tx.get("vin", []):
                            if "coinbase" in vin:
                                continue
                            prev_txid = vin.get("txid")
                            prev_vout = vin.get("vout")
                            if prev_txid and prev_vout is not None:
                                try:
                                    prev_tx = await asyncio.wait_for(
                                        self.get_transaction(prev_txid, verbose=True),
                                        timeout=5.0
                                    )
                                    if prev_tx and isinstance(prev_tx, dict):
                                        prev_outputs = prev_tx.get("vout", [])
                                        if prev_vout < len(prev_outputs):
                                            prev_out = prev_outputs[prev_vout]
                                            prev_script = prev_out.get("scriptPubKey", {})
                                            prev_addr = prev_script.get("address")
                                            if prev_addr == address:
                                                value_sats = int(prev_out.get("value", 0) * 100_000_000)
                                                total_sent_sats += value_sats
                                except:
                                    pass

                        processed += 1
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        continue

                totals_calculated = True
                logger.info(f"get_address_info: Calculated totals - received={total_received_sats}, sent={total_sent_sats}")

            except Exception as e:
                logger.warning(f"get_address_info: Error calculating totals: {e}")
                totals_complete = False
        elif history and len(history) > MAX_TXS_FOR_TOTALS:
            warnings.append(f"Total received/sent calculated from last {MAX_TXS_FOR_TOTALS} of {len(history)} transactions")
            totals_complete = False
            # Calculate from limited set
            try:
                limited_history = sorted(history, key=lambda x: x.height if x.height > 0 else float('inf'), reverse=True)[:MAX_TXS_FOR_TOTALS]

                for hist_tx in limited_history:
                    try:
                        tx = await asyncio.wait_for(
                            self.get_transaction(hist_tx.txid, verbose=True),
                            timeout=10.0
                        )
                        if not tx or not isinstance(tx, dict):
                            continue

                        # Check outputs
                        for vout in tx.get("vout", []):
                            script = vout.get("scriptPubKey", {})
                            out_addr = script.get("address")
                            if out_addr == address:
                                value_sats = int(vout.get("value", 0) * 100_000_000)
                                total_received_sats += value_sats

                        # Check inputs
                        for vin in tx.get("vin", []):
                            if "coinbase" in vin:
                                continue
                            prev_txid = vin.get("txid")
                            prev_vout = vin.get("vout")
                            if prev_txid and prev_vout is not None:
                                try:
                                    prev_tx = await asyncio.wait_for(
                                        self.get_transaction(prev_txid, verbose=True),
                                        timeout=5.0
                                    )
                                    if prev_tx and isinstance(prev_tx, dict):
                                        prev_outputs = prev_tx.get("vout", [])
                                        if prev_vout < len(prev_outputs):
                                            prev_out = prev_outputs[prev_vout]
                                            prev_script = prev_out.get("scriptPubKey", {})
                                            prev_addr = prev_script.get("address")
                                            if prev_addr == address:
                                                value_sats = int(prev_out.get("value", 0) * 100_000_000)
                                                total_sent_sats += value_sats
                                except:
                                    pass
                    except:
                        continue

                totals_calculated = True
            except Exception as e:
                logger.warning(f"get_address_info: Error calculating limited totals: {e}")

        return {
            "address": address,
            "balance": balance.to_dict() if balance else {"confirmed": 0, "unconfirmed": 0, "total": 0},
            "transaction_count": len(history),
            "utxo_count": len(utxos),
            "first_seen_height": first_seen,
            "last_seen_height": last_seen,
            "total_received_sats": total_received_sats if totals_calculated else None,
            "total_sent_sats": total_sent_sats if totals_calculated else None,
            "total_received_btc": total_received_sats / 100_000_000 if totals_calculated else None,
            "total_sent_btc": total_sent_sats / 100_000_000 if totals_calculated else None,
            "totals_complete": totals_complete,
            "transactions": [tx.to_dict() for tx in history[-100:]],  # Last 100 transactions (increased from 50)
            "utxos": [utxo.to_dict() for utxo in utxos[:5000]],  # Limit to 5000 UTXOs (increased from 1000)
            "warnings": warnings,
            "history_truncated": history_truncated or len(history) > 100,
            "utxos_truncated": utxos_truncated or len(utxos) > 5000
        }

    async def find_spending_tx(self, txid: str, vout: int) -> Optional[str]:
        """
        Find the transaction that spent a specific output.

        This is the key feature that Bitcoin Core RPC cannot do without txindex!
        Optimized for Fulcrum's performance.
        """
        logger.info(f"find_spending_tx: START txid={txid[:16]}..., vout={vout}, connected={self._connected}")

        # First, get the transaction to find the output address
        logger.info(f"find_spending_tx: Getting source transaction...")
        tx = await self.get_transaction(txid, verbose=True)

        # Validate tx is a dict with expected structure
        if not tx or not isinstance(tx, dict) or "vout" not in tx:
            logger.warning(f"find_spending_tx: Source tx invalid or not found (tx={type(tx).__name__})")
            return None

        if vout >= len(tx["vout"]):
            logger.warning(f"find_spending_tx: vout {vout} out of range (tx has {len(tx['vout'])} outputs)")
            return None

        output = tx["vout"][vout]
        script_pubkey = output.get("scriptPubKey", {})
        address = script_pubkey.get("address")

        if not address:
            logger.warning(f"find_spending_tx: No address found for output")
            return None

        logger.info(f"find_spending_tx: Output address is {address[:20]}...")

        # Get all transactions for this address
        logger.info(f"find_spending_tx: Getting address history...")
        history = await self.get_history(address)

        # Check if history is valid
        if not history:
            logger.warning(f"find_spending_tx: No history returned for address (history={history})")
            return None

        logger.info(f"find_spending_tx: Address has {len(history)} transactions in history")

        # Fulcrum can handle much larger address histories - increased limit significantly
        MAX_HISTORY_CHECK = 1000  # Increased from 200
        if len(history) > MAX_HISTORY_CHECK:
            logger.warning(f"find_spending_tx: Address has {len(history)} txs, limiting check to most recent {MAX_HISTORY_CHECK}")
            history = sorted(history, key=lambda x: x.height if x.height > 0 else float('inf'), reverse=True)[:MAX_HISTORY_CHECK]

        # Look for a transaction that spends this output
        checked_count = 0
        for hist_tx in history:
            if hist_tx.txid == txid:
                continue  # Skip the original transaction

            checked_count += 1
            if checked_count % 50 == 0:
                logger.debug(f"find_spending_tx: Checked {checked_count}/{len(history)} transactions...")

            try:
                full_tx = await self.get_transaction(hist_tx.txid, verbose=True)
                # Validate response is a dict
                if not full_tx or not isinstance(full_tx, dict):
                    continue

                for vin in full_tx.get("vin", []):
                    if vin.get("txid") == txid and vin.get("vout") == vout:
                        logger.debug(f"find_spending_tx: FOUND spending tx {hist_tx.txid[:16]}... after checking {checked_count} txs")
                        return hist_tx.txid
            except Exception as e:
                logger.debug(f"find_spending_tx: Error checking tx {hist_tx.txid[:16]}...: {e}")
                continue

        logger.debug(f"find_spending_tx: No spending tx found after checking {checked_count} transactions")
        return None  # Output is unspent or spending tx not found

    async def check_dust_attack(self, address: str, dust_threshold_sats: int = 1000) -> Dict:
        """
        Check an address for potential dust attack UTXOs.

        Dust attacks send tiny amounts to track spending patterns.
        """
        utxos = await self.get_utxos(address)
        history = await self.get_history(address)

        dust_utxos = []
        suspicious_utxos = []

        for utxo in utxos:
            if utxo.value_sats <= dust_threshold_sats:
                dust_utxos.append(utxo.to_dict())

                # Check if this could be a dust attack
                # (received from unknown source, tiny amount)
                if utxo.value_sats <= 546:  # Bitcoin dust limit
                    suspicious_utxos.append({
                        **utxo.to_dict(),
                        "warning": "Below dust limit - likely dust attack",
                        "recommendation": "Do NOT spend with other UTXOs"
                    })
                elif utxo.value_sats <= dust_threshold_sats:
                    suspicious_utxos.append({
                        **utxo.to_dict(),
                        "warning": "Small UTXO - potential dust attack",
                        "recommendation": "Verify source before spending"
                    })

        return {
            "address": address,
            "dust_threshold_sats": dust_threshold_sats,
            "total_utxos": len(utxos),
            "dust_utxos_count": len(dust_utxos),
            "suspicious_count": len(suspicious_utxos),
            "dust_utxos": dust_utxos,
            "suspicious_utxos": suspicious_utxos,
            "total_dust_value_sats": sum(u["value_sats"] for u in dust_utxos),
            "recommendation": (
                "DANGER: Dust UTXOs detected! Do not consolidate these with your main UTXOs."
                if suspicious_utxos else
                "No suspicious dust UTXOs detected."
            )
        }


# Singleton instance
_fulcrum_instance: Optional[FulcrumClient] = None


def get_fulcrum() -> FulcrumClient:
    """Get or create Fulcrum client instance."""
    global _fulcrum_instance
    if _fulcrum_instance is None:
        _fulcrum_instance = FulcrumClient()
    return _fulcrum_instance


async def check_fulcrum_connection() -> Dict:
    """Check if Fulcrum is available and return status."""
    client = get_fulcrum()

    if not client.is_configured:
        return {
            "status": "not_configured",
            "message": "FULCRUM_HOST not set in environment"
        }

    try:
        # Connect and perform handshake (only if not already done)
        if not await client.connect():
            return {
                "status": "disconnected",
                "host": client.host,
                "port": client.port,
                "message": "Failed to connect"
            }

        # Get version info from handshake (cached, won't call server.version again)
        version = await client.server_version()

        # Use blockchain.headers.subscribe for health check (idempotent, safe to call multiple times)
        tip = await client.get_tip()

        # Functional probe: Test if verbose transaction fetching works
        # Use a well-known old transaction (Satoshi's first transaction to Hal Finney)
        probe_txid = "f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16"
        verbose_works = False
        try:
            # Direct call to test verbose mode
            probe_result = await client._call("blockchain.transaction.get", [probe_txid, True])
            if isinstance(probe_result, dict):
                # Check if we got verbose response (has vout)
                if "vout" in probe_result:
                    verbose_works = True
                else:
                    logger.warning("Fulcrum health check: verbose mode not working")
                    verbose_works = False
        except Exception as e:
            logger.warning(f"Fulcrum health check: probe failed: {e}")
            verbose_works = False

        status_result = {
            "status": "connected" if verbose_works else "degraded",
            "host": client.host,
            "port": client.port,
            "server": version.get("server_software") if isinstance(version, dict) else str(version),
            "protocol": version.get("protocol_version") if isinstance(version, dict) else "1.4",
            "tip_height": tip.get("height") if isinstance(tip, dict) else None,
            "verbose_mode_working": verbose_works
        }

        if not verbose_works:
            status_result["warning"] = "Fulcrum connected but verbose mode not working - may need restart"
            # Force disconnect to trigger reconnection on next use
            await client.disconnect()

        return status_result
    except Exception as e:
        logger.error(f"Fulcrum connection check failed: {e}")
        return {
            "status": "error",
            "host": client.host,
            "port": client.port,
            "error": str(e)
        }

    return {
        "status": "disconnected",
        "host": client.host,
        "port": client.port
    }
