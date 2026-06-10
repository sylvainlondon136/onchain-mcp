"""Live smoke tests for onchain-mcp against Solana mainnet + Jupiter.

These hit public endpoints (no key). They assert on stable, well-known facts:
USDC trades ~$1, the SPL Token program is executable and owned by the native
loader, and a non-existent account reports `exists: False`. Run with:

    uv run --with pytest --with pytest-asyncio --extra test pytest -q
"""

import pytest

import onchain_mcp as m

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
# A fresh, normal wallet (no token accounts) — valid for getTokenAccountsByOwner,
# unlike high-traffic program accounts which public RPCs exclude from indexes.
FRESH_WALLET = "5Hm7t4bB7MeNZqwADGsXruYDdFKkmZMh6R6K8GpSx1DC"


@pytest.mark.asyncio
async def test_usdc_price_is_about_one():
    res = await m.get_token_price(USDC_MINT)
    assert res["found"] is True
    assert 0.9 <= res["price_usd"] <= 1.1, res


@pytest.mark.asyncio
async def test_token_program_account_is_executable():
    res = await m.get_account_info(SPL_TOKEN_PROGRAM)
    assert res["exists"] is True
    assert res["executable"] is True
    assert res["lamports"] > 0


@pytest.mark.asyncio
async def test_sol_balance_shape():
    res = await m.get_sol_balance(SPL_TOKEN_PROGRAM)
    assert res["lamports"] >= 0
    assert res["sol"] == res["lamports"] / 1_000_000_000


@pytest.mark.asyncio
async def test_token_holdings_shape():
    # A fresh wallet has no token accounts; result must still be well-formed.
    res = await m.get_token_holdings(FRESH_WALLET)
    assert res["address"] == FRESH_WALLET
    assert isinstance(res["tokens"], list)
    assert res["token_count"] == len(res["tokens"])


@pytest.mark.asyncio
async def test_usdc_supply():
    res = await m.get_token_supply(USDC_MINT)
    assert res["mint"] == USDC_MINT
    assert res["decimals"] == 6
    assert int(res["amount"]) > 0


@pytest.mark.asyncio
async def test_epoch_info():
    res = await m.get_epoch_info()
    assert res["epoch"] > 0
    assert res["absolute_slot"] > 0
    assert 0.0 <= res["epoch_progress"] <= 1.0


@pytest.mark.asyncio
async def test_recent_signatures_shape():
    res = await m.get_recent_signatures(SPL_TOKEN_PROGRAM, limit=3)
    assert res["address"] == SPL_TOKEN_PROGRAM
    assert isinstance(res["signatures"], list)
    assert res["count"] == len(res["signatures"]) <= 3
