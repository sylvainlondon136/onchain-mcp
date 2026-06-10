# onchain-mcp

A **Model Context Protocol (MCP)** server that gives any MCP client — Claude
Desktop, Claude Code, Cursor, etc. — live, read-only access to **Solana
on-chain data**. Ask natural-language questions like *"what SPL tokens does this
wallet hold?"* or *"what's the USD price of this mint?"* and the model answers
from real Solana mainnet RPC + Jupiter, no API key required.

## Tools

| Tool | What it does |
|------|--------------|
| `get_sol_balance(address)` | Native SOL balance of an account |
| `get_token_holdings(address)` | Non-zero SPL token balances of a wallet |
| `get_token_price(mint)` | USD price of a token mint (via Jupiter) |
| `get_transaction(signature)` | Parsed transaction summary (slot, fee, logs, success) |
| `get_account_info(address)` | Owner program, lamports, executable flag |
| `get_token_supply(mint)` | Total on-chain supply of a token mint |
| `get_recent_signatures(address)` | Recent transaction signatures for an account |
| `get_epoch_info()` | Current epoch / slot / block height / progress |

All endpoints are public. Point at a private RPC by setting `SOLANA_RPC_URL`
(and optionally `JUPITER_PRICE_API`).

## Run

```bash
# Run the server over stdio (what an MCP client launches):
uv run --with "mcp>=1.2" --with httpx onchain_mcp.py
```

### Use with Claude Desktop / Claude Code

Add to your MCP config (`claude_desktop_config.json` or `.mcp.json`):

```json
{
  "mcpServers": {
    "onchain": {
      "command": "uv",
      "args": ["run", "--with", "mcp>=1.2", "--with", "httpx",
               "/absolute/path/to/onchain-mcp/onchain_mcp.py"]
    }
  }
}
```

Then ask, e.g.: *"Using the onchain tools, what's the USDC price and how much
SOL does `<address>` hold?"*

## Test

Live smoke tests against mainnet (asserts USDC ≈ $1, the SPL Token program is
executable, balance/holdings shapes):

```bash
uv run --python 3.12 --with "mcp>=1.2" --with httpx \
  --with pytest --with pytest-asyncio pytest test_onchain_mcp.py -q
```

## Notes

- Read-only: the server never signs or sends transactions — it only queries
  public chain state, so it is safe to expose to an LLM.
- Default RPC is `api.mainnet-beta.solana.com` (rate-limited); use a dedicated
  RPC for heavy use.

## License

MIT
