"""onchain-mcp — a Model Context Protocol (MCP) server exposing live Solana
on-chain data to any MCP client (Claude Desktop, Claude Code, Cursor, …).

It turns natural-language questions like "what's the USDC balance of this
wallet?" into real Solana mainnet RPC + Jupiter price queries. No API key
required — it uses public endpoints (override with SOLANA_RPC_URL for a
private RPC).

Tools:
  - get_sol_balance(address)        native SOL balance
  - get_token_holdings(address)     non-zero SPL token balances
  - get_token_price(mint)           USD price via Jupiter
  - get_transaction(signature)      parsed transaction summary
  - get_account_info(address)       owner / lamports / executable

Run as an MCP server (stdio):  uv run onchain_mcp.py
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

SOLANA_RPC_URL = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
JUPITER_PRICE_API = os.environ.get("JUPITER_PRICE_API", "https://lite-api.jup.ag/price/v3")
SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
LAMPORTS_PER_SOL = 1_000_000_000
_TIMEOUT = httpx.Timeout(20.0)

mcp = FastMCP("onchain-mcp")


async def _rpc(method: str, params: list[Any]) -> Any:
    """Call a Solana JSON-RPC method and return its `result`, raising on error."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            SOLANA_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        resp.raise_for_status()
        payload = resp.json()
    if "error" in payload:
        raise RuntimeError(f"Solana RPC error for {method}: {payload['error']}")
    return payload["result"]


@mcp.tool()
async def get_sol_balance(address: str) -> dict:
    """Get the native SOL balance of a Solana account.

    Args:
        address: Base58-encoded account/wallet address.

    Returns a dict with the raw `lamports` and human-readable `sol`.
    """
    result = await _rpc("getBalance", [address])
    lamports = int(result["value"])
    return {"address": address, "lamports": lamports, "sol": lamports / LAMPORTS_PER_SOL}


@mcp.tool()
async def get_token_holdings(address: str) -> dict:
    """List the non-zero SPL token balances held by a Solana wallet.

    Args:
        address: Base58-encoded wallet address.

    Returns a dict with a `tokens` list of {mint, amount, decimals, ui_amount}.
    """
    result = await _rpc(
        "getTokenAccountsByOwner",
        [address, {"programId": SPL_TOKEN_PROGRAM}, {"encoding": "jsonParsed"}],
    )
    tokens = []
    for acc in result.get("value", []):
        info = acc["account"]["data"]["parsed"]["info"]
        amount = info["tokenAmount"]
        if int(amount["amount"]) == 0:
            continue
        tokens.append(
            {
                "mint": info["mint"],
                "amount": amount["amount"],
                "decimals": amount["decimals"],
                "ui_amount": amount["uiAmount"],
            }
        )
    return {"address": address, "token_count": len(tokens), "tokens": tokens}


@mcp.tool()
async def get_token_price(mint: str) -> dict:
    """Get the USD price of an SPL token by its mint address (via Jupiter).

    Args:
        mint: Base58-encoded token mint (e.g. the USDC or SOL mint).

    Returns {mint, price_usd, found}.
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(JUPITER_PRICE_API, params={"ids": mint})
        resp.raise_for_status()
        data = resp.json()
    # Jupiter price v3 returns a flat object keyed by mint: {<mint>: {"usdPrice": ...}}
    entry = data.get(mint) if isinstance(data, dict) else None
    if not entry or entry.get("usdPrice") is None:
        return {"mint": mint, "price_usd": None, "found": False}
    return {"mint": mint, "price_usd": float(entry["usdPrice"]), "found": True}


@mcp.tool()
async def get_transaction(signature: str) -> dict:
    """Summarize a Solana transaction by its signature.

    Args:
        signature: Base58-encoded transaction signature.

    Returns slot, block_time, fee, error status, and log messages.
    """
    result = await _rpc(
        "getTransaction",
        [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
    )
    if result is None:
        return {"signature": signature, "found": False}
    meta = result.get("meta") or {}
    return {
        "signature": signature,
        "found": True,
        "slot": result.get("slot"),
        "block_time": result.get("blockTime"),
        "fee_lamports": meta.get("fee"),
        "succeeded": meta.get("err") is None,
        "err": meta.get("err"),
        "log_messages": meta.get("logMessages"),
    }


@mcp.tool()
async def get_account_info(address: str) -> dict:
    """Get basic on-chain info for an account: owner program, lamports, executable flag."""
    result = await _rpc("getAccountInfo", [address, {"encoding": "base64"}])
    value = result.get("value")
    if value is None:
        return {"address": address, "exists": False}
    return {
        "address": address,
        "exists": True,
        "owner": value["owner"],
        "lamports": int(value["lamports"]),
        "executable": value["executable"],
        "rent_epoch": value.get("rentEpoch"),
    }


@mcp.tool()
async def get_token_supply(mint: str) -> dict:
    """Get the total on-chain supply of an SPL token mint.

    Args:
        mint: Base58-encoded token mint address.

    Returns {mint, amount (raw), decimals, ui_amount}.
    """
    result = await _rpc("getTokenSupply", [mint])
    v = result["value"]
    return {
        "mint": mint,
        "amount": v["amount"],
        "decimals": v["decimals"],
        "ui_amount": v["uiAmount"],
    }


@mcp.tool()
async def get_recent_signatures(address: str, limit: int = 10) -> dict:
    """List the most recent transaction signatures touching an account.

    Args:
        address: Base58-encoded account/wallet address.
        limit: Max number of signatures (1-100, default 10).

    Returns {address, count, signatures: [{signature, slot, block_time, succeeded}]}.
    """
    limit = max(1, min(int(limit), 100))
    result = await _rpc("getSignaturesForAddress", [address, {"limit": limit}])
    sigs = [
        {
            "signature": s["signature"],
            "slot": s.get("slot"),
            "block_time": s.get("blockTime"),
            "succeeded": s.get("err") is None,
        }
        for s in result
    ]
    return {"address": address, "count": len(sigs), "signatures": sigs}


@mcp.tool()
async def get_epoch_info() -> dict:
    """Get current Solana network epoch/slot info (epoch, slot, block height, progress)."""
    result = await _rpc("getEpochInfo", [])
    slots_in_epoch = result.get("slotsInEpoch") or 0
    slot_index = result.get("slotIndex") or 0
    return {
        "epoch": result.get("epoch"),
        "absolute_slot": result.get("absoluteSlot"),
        "block_height": result.get("blockHeight"),
        "slot_index": slot_index,
        "slots_in_epoch": slots_in_epoch,
        "epoch_progress": (slot_index / slots_in_epoch) if slots_in_epoch else None,
    }


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
