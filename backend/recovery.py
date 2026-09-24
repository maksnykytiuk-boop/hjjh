"""Live mainnet detection + sweep (wrong-network recovery) for EVM chains,
plus read-only detection for TRON and Bitcoin."""
import os
import requests
from web3 import Web3

from catalog import PRICES_USD

ALCHEMY_KEY = os.environ.get("ALCHEMY_KEY", "")
TRONGRID_KEY = os.environ.get("TRONGRID_KEY", "")
MEMPOOL_API = os.environ.get("MEMPOOL_API", "https://mempool.space/api")
TREASURY_EVM = os.environ.get("TREASURY_EVM", "")

# chain -> (alchemy subdomain, network_id, native symbol, chainId)
EVM = {
    "ethereum": ("eth-mainnet", 1, "ETH", 1),
    "polygon": ("polygon-mainnet", 6, "MATIC", 137),
    "bsc": ("bnb-mainnet", 4, "BNB", 56),
    "arbitrum": ("arb-mainnet", 7, "ETH", 42161),
}

# token contracts per chain: symbol -> (address, decimals)
TOKENS = {
    "ethereum": {
        "USDT": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
        "USDC": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
    },
    "polygon": {
        "USDT": ("0xc2132D05D31c914a87C6611C10748AEb04B58e8F", 6),
        "USDC": ("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
    },
    "bsc": {
        "USDT": ("0x55d398326f99059fF775485246999027B3197955", 18),
        "USDC": ("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 18),
    },
    "arbitrum": {
        "USDT": ("0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", 6),
        "USDC": ("0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
    },
}

NATIVE_USD = {"ETH": PRICES_USD["ETH"], "BNB": PRICES_USD["BNB"], "MATIC": 0.52}
TOKEN_USD = {"USDT": 1.0, "USDC": 1.0}

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
]


def _rpc_url(chain: str) -> str:
    sub = EVM[chain][0]
    return f"https://{sub}.g.alchemy.com/v2/{ALCHEMY_KEY}"


def _w3(chain: str) -> Web3:
    return Web3(Web3.HTTPProvider(_rpc_url(chain), request_kwargs={"timeout": 20}))


def scan_evm_address(address: str) -> list:
    """Scan a single 0x address across ALL EVM chains for native + token balances."""
    addr = Web3.to_checksum_address(address)
    out = []
    for chain, (sub, nid, native, chainid) in EVM.items():
        w3 = _w3(chain)
        try:
            wei = w3.eth.get_balance(addr)
        except Exception:
            continue
        if wei > 0:
            amt = wei / 1e18
            out.append({"address": address, "chain": chain, "network_id": nid,
                        "symbol": native, "kind": "native", "contract": None,
                        "decimals": 18, "amount": amt,
                        "usd": round(amt * NATIVE_USD.get(native, 0.0), 2)})
        for sym, (caddr, dec) in TOKENS.get(chain, {}).items():
            try:
                c = w3.eth.contract(address=Web3.to_checksum_address(caddr), abi=ERC20_ABI)
                raw = c.functions.balanceOf(addr).call()
            except Exception:
                continue
            if raw > 0:
                amt = raw / (10 ** dec)
                out.append({"address": address, "chain": chain, "network_id": nid,
                            "symbol": sym, "kind": "token", "contract": caddr,
                            "decimals": dec, "amount": amt,
                            "usd": round(amt * TOKEN_USD.get(sym, 0.0), 2)})
    return out


def scan_tron_address(address: str) -> list:
    """Read-only TRX + USDT (TRC-20) balance via TronGrid."""
    out = []
    h = {"TRON-PRO-API-KEY": TRONGRID_KEY} if TRONGRID_KEY else {}
    try:
        r = requests.get(f"https://api.trongrid.io/v1/accounts/{address}", headers=h, timeout=15)
        data = (r.json().get("data") or [{}])[0]
        trx = data.get("balance", 0) / 1e6
        if trx > 0:
            out.append({"address": address, "chain": "tron", "network_id": 2, "symbol": "TRX",
                        "kind": "native", "contract": None, "decimals": 6, "amount": trx,
                        "usd": round(trx * PRICES_USD["TRX"], 2)})
        for t in data.get("trc20", []):
            for caddr, bal in t.items():
                if caddr == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":  # USDT-TRC20
                    amt = int(bal) / 1e6
                    if amt > 0:
                        out.append({"address": address, "chain": "tron", "network_id": 2, "symbol": "USDT",
                                    "kind": "token", "contract": caddr, "decimals": 6, "amount": amt,
                                    "usd": round(amt, 2)})
    except Exception:
        pass
    return out


def scan_btc_address(address: str) -> list:
    try:
        r = requests.get(f"{MEMPOOL_API}/address/{address}", timeout=15)
        d = r.json()
        cs = d.get("chain_stats", {})
        sats = cs.get("funded_txo_sum", 0) - cs.get("spent_txo_sum", 0)
        amt = sats / 1e8
        if amt > 0:
            return [{"address": address, "chain": "bitcoin", "network_id": 0, "symbol": "BTC",
                     "kind": "native", "contract": None, "decimals": 8, "amount": amt,
                     "usd": round(amt * PRICES_USD["BTC"], 2)}]
    except Exception:
        pass
    return []


def sweep_evm(privkey: str, chain: str, kind: str, contract: str, to_address: str = None) -> dict:
    """Send full balance of an EVM asset to the treasury. Returns tx hash or error."""
    to_address = to_address or TREASURY_EVM
    if not to_address:
        return {"ok": False, "error": "Treasury address not configured"}
    _, nid, native, chainid = EVM[chain]
    w3 = _w3(chain)
    acct = w3.eth.account.from_key(privkey)
    frm = acct.address
    to_cs = Web3.to_checksum_address(to_address)
    gas_price = w3.eth.gas_price
    nonce = w3.eth.get_transaction_count(frm)
    try:
        if kind == "native":
            bal = w3.eth.get_balance(frm)
            fee = 21000 * gas_price
            value = bal - fee
            if value <= 0:
                return {"ok": False, "error": "Balance too low to cover gas"}
            tx = {"to": to_cs, "value": value, "gas": 21000, "gasPrice": gas_price,
                  "nonce": nonce, "chainId": chainid}
        else:
            c = w3.eth.contract(address=Web3.to_checksum_address(contract), abi=ERC20_ABI)
            raw = c.functions.balanceOf(frm).call()
            if raw <= 0:
                return {"ok": False, "error": "No token balance"}
            native_bal = w3.eth.get_balance(frm)
            tx = c.functions.transfer(to_cs, raw).build_transaction(
                {"from": frm, "nonce": nonce, "gasPrice": gas_price, "chainId": chainid})
            try:
                tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
            except Exception:
                tx["gas"] = 100000
            if native_bal < tx["gas"] * gas_price:
                return {"ok": False, "error": f"Not enough {native} for gas on this address. "
                        f"Send a little {native} to {frm} first, then retry."}
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.rawTransaction)
        return {"ok": True, "tx_hash": h.hex(), "from": frm, "to": to_cs, "chain": chain}
    except Exception as e:
        return {"ok": False, "error": str(e)}
