import os
import asyncio
import logging
import random
import string
import time
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Body
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from core import (
    db, hash_password, verify_password, create_access_token, set_auth_cookie,
    set_session_cookie, clear_auth_cookies, get_current_user, exchange_emergent_session,
    make_signature, new_token, new_secret,
)
import catalog
from catalog import (
    CURRENCIES, NETWORKS, FIAT_CURRENCIES, FIAT_RATES_USD, PRICES_USD, PRICE_CHANGE,
    STATUS_MAP, STATUS_NAME_TO_ID, networks_for, commission_for,
)
from hd_wallet import generate_mnemonic, seed_from_mnemonic, derive_address
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("okipays")

app = FastAPI(title="OKIPAYS Clone API")
_seed = {"bytes": None}


# ============================ helpers ============================
def now_ts() -> int:
    return int(time.time())


def gen_id(n=8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


async def next_index(chain: str) -> int:
    doc = await db.counters.find_one_and_update(
        {"_id": chain}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return doc["seq"]


async def ensure_seed():
    if _seed["bytes"] is not None:
        return
    env_m = os.environ.get("WALLET_MNEMONIC", "").strip()
    if env_m:
        mnemonic = env_m
    else:
        sysdoc = await db.system.find_one({"_id": "wallet"})
        if sysdoc and sysdoc.get("mnemonic"):
            mnemonic = sysdoc["mnemonic"]
        else:
            mnemonic = generate_mnemonic()
            await db.system.update_one({"_id": "wallet"},
                                       {"$set": {"mnemonic": mnemonic}}, upsert=True)
            logger.warning("Generated new HD wallet mnemonic (stored in DB). "
                           "Set WALLET_MNEMONIC in .env for production.")
    _seed["bytes"] = seed_from_mnemonic(mnemonic)


async def allocate_address(user_id: str, iso: str, network_id: int, invoice_id=None) -> dict:
    await ensure_seed()
    net = NETWORKS.get(network_id)
    if not net:
        raise HTTPException(400, "Network not found")
    chain = net["chain"]
    if invoice_id is None:
        existing = await db.addresses.find_one(
            {"user_id": user_id, "iso": iso, "network_id": network_id, "invoice_id": None},
            {"_id": 0})
        if existing:
            return existing
    idx = await next_index(chain)
    d = derive_address(_seed["bytes"], chain, idx)
    doc = {"user_id": user_id, "iso": iso, "network_id": network_id, "chain": chain,
           "index": idx, "address": d["address"], "path": d["path"],
           "invoice_id": invoice_id, "time_create": now_ts()}
    await db.addresses.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def credit_balance(user_id: str, iso: str, amount: float, available: bool = True):
    inc = {"balance": amount}
    if available:
        inc["balance_available"] = amount
    await db.wallets.update_one(
        {"user_id": user_id, "iso": iso}, {"$inc": inc}, upsert=True)


async def get_balance(user_id: str, iso: str) -> dict:
    w = await db.wallets.find_one({"user_id": user_id, "iso": iso}, {"_id": 0})
    if not w:
        return {"iso": iso, "balance": 0.0, "balance_available": 0.0}
    return {"iso": iso, "balance": round(w.get("balance", 0.0), 8),
            "balance_available": round(w.get("balance_available", 0.0), 8)}


async def add_transaction(user_id: str, ttype: str, iso: str, network_id, amount,
                          status="Done", address=None, txid=None, description="",
                          order_id=None, invoice_id=None, usd=None):
    tx = {
        "tx_id": uuid.uuid4().hex[:12], "user_id": user_id, "type": ttype, "iso": iso,
        "network_id": network_id, "amount": round(float(amount), 8),
        "usd_value": usd if usd is not None else catalog.usd_value(iso, amount),
        "status": status, "address": address, "txid": txid, "description": description,
        "order_id": order_id, "invoice_id": invoice_id, "created_ts": now_ts(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.transactions.insert_one(dict(tx))
    tx.pop("_id", None)
    return tx


async def get_merchant(user_id: str) -> dict:
    m = await db.merchants.find_one({"user_id": user_id}, {"_id": 0})
    if not m:
        m = {
            "merchant_id": int(now_ts()), "user_id": user_id, "name": "My Merchant",
            "home_url": "", "result_url": "", "token": new_token(), "secret": new_secret(),
            "brand_color": "#2563EB", "logo_url": "", "description": "", "is_default": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.merchants.insert_one(dict(m))
        m.pop("_id", None)
    return m


def invoice_public(inv: dict) -> dict:
    return {k: inv.get(k) for k in [
        "id", "order_id", "status", "status_id", "price", "payment_currency_iso",
        "include_commission", "description", "link", "currencies", "redirect_url",
        "time_create", "time_expired", "pay_info", "amount_paid", "usd_value"]}


async def send_webhook(merchant: dict, inv: dict, cur_iso=None, amount=0.0):
    url = merchant.get("result_url")
    if not url:
        return
    rate = PRICES_USD.get(cur_iso, 0.0) if cur_iso else 0.0
    payload = {
        "id": inv["id"], "order_id": inv["order_id"], "currency": cur_iso or "",
        "payment_currency": inv["payment_currency_iso"], "status": inv["status"],
        "amount": amount, "amount_send": amount, "price": inv["price"],
        "price_send": round(amount * rate, 2), "rate": rate,
        "total_sum_price": round(amount * rate, 2), "commission": 0,
        "address": (inv.get("pay_info") or {}).get("address", ""),
        "network_type": (inv.get("pay_info") or {}).get("network", ""),
        "time_create": inv["time_create"], "time_update": now_ts(),
        "time_done": now_ts() if inv["status"] in ("Paid", "Completed") else None,
        "time_expired": inv.get("time_expired"), "time_send": now_ts(),
        "time_receive": None, "include_commission": inv.get("include_commission", 0),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(url, json=payload)
    except Exception as e:
        logger.info(f"webhook send failed: {e}")


# ============================ auth router ============================
auth_router = APIRouter(prefix="/api/auth")


class RegisterIn(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


@auth_router.post("/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user = {"user_id": user_id, "email": email, "name": payload.name or email.split("@")[0],
            "password_hash": hash_password(payload.password), "auth_provider": "password",
            "picture": "", "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(dict(user))
    await get_merchant(user_id)
    token = create_access_token(user_id, email)
    set_auth_cookie(response, token)
    user.pop("password_hash", None)
    return {"user": user, "access_token": token}


@auth_router.post("/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Невірний email або пароль")
    token = create_access_token(user["user_id"], email)
    set_auth_cookie(response, token)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return {"user": user, "access_token": token}


class SessionIn(BaseModel):
    session_id: str


@auth_router.post("/google/session")
async def google_session(payload: SessionIn, response: Response):
    data = await exchange_emergent_session(payload.session_id)
    email = data["email"].lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {"user_id": user_id, "email": email, "name": data.get("name", ""),
                "picture": data.get("picture", ""), "auth_provider": "google",
                "created_at": datetime.now(timezone.utc).isoformat()}
        await db.users.insert_one(dict(user))
        await get_merchant(user_id)
    else:
        user_id = user["user_id"]
    stoken = data["session_token"]
    await db.user_sessions.update_one(
        {"session_token": stoken},
        {"$set": {"user_id": user_id, "session_token": stoken,
                  "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                  "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    set_session_cookie(response, stoken)
    user.pop("password_hash", None)
    return {"user": user}


@auth_router.get("/me")
async def me(request: Request):
    return await get_current_user(request)


@auth_router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"status": "ok"}


# ============================ cabinet router ============================
cab = APIRouter(prefix="/api")


@cab.get("/prices")
async def prices():
    return {"status": True, "data": [
        {"iso": iso, "name": CURRENCIES[iso]["name"], "color": CURRENCIES[iso]["color"],
         "price": PRICES_USD[iso], "change": PRICE_CHANGE.get(iso, 0.0)}
        for iso in CURRENCIES]}


@cab.get("/me/summary")
async def summary(request: Request):
    user = await get_current_user(request)
    uid = user["user_id"]
    wallets = await db.wallets.find({"user_id": uid}, {"_id": 0}).to_list(100)
    assets, total, available = [], 0.0, 0.0
    for iso in CURRENCIES:
        w = next((x for x in wallets if x["iso"] == iso), None)
        bal = w.get("balance", 0.0) if w else 0.0
        avail = w.get("balance_available", 0.0) if w else 0.0
        usd = catalog.usd_value(iso, bal)
        total += usd
        available += catalog.usd_value(iso, avail)
        assets.append({"iso": iso, "name": CURRENCIES[iso]["name"], "color": CURRENCIES[iso]["color"],
                       "balance": round(bal, 8), "balance_available": round(avail, 8),
                       "price": PRICES_USD[iso], "usd_value": usd})
    txs = await db.transactions.find({"user_id": uid}, {"_id": 0}).sort("created_ts", -1).to_list(10)
    # 30-day chart from cumulative tx usd flow (demo-friendly)
    chart = []
    base = round(total, 2)
    v = base
    for i in range(29, -1, -1):
        v = max(0, v - random.uniform(-40, 60))
        chart.append({"t": (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%d.%m"),
                      "value": round(v, 2)})
    chart.append({"t": "now", "value": base})
    return {"status": True, "total_usd": round(total, 2), "available_usd": round(available, 2),
            "assets": assets, "recent": txs, "chart": chart}


@cab.get("/transactions")
async def transactions(request: Request):
    user = await get_current_user(request)
    txs = await db.transactions.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_ts", -1).to_list(200)
    return {"status": True, "data": txs}


@cab.get("/wallet")
async def wallet(request: Request):
    user = await get_current_user(request)
    uid = user["user_id"]
    out = []
    for iso, cur in CURRENCIES.items():
        b = await get_balance(uid, iso)
        out.append({"iso": iso, "name": cur["name"], "color": cur["color"],
                    "price": PRICES_USD[iso], "balance": b["balance"],
                    "balance_available": b["balance_available"],
                    "usd_value": catalog.usd_value(iso, b["balance"]),
                    "networks": networks_for(iso)})
    return {"status": True, "data": out}


class DepositAddrIn(BaseModel):
    currency: str
    network_id: int


@cab.post("/wallet/deposit-address")
async def deposit_address(request: Request, payload: DepositAddrIn):
    user = await get_current_user(request)
    iso = payload.currency.upper()
    if iso not in CURRENCIES or payload.network_id not in CURRENCIES[iso]["networks"]:
        raise HTTPException(400, "Currency/network not available")
    addr = await allocate_address(user["user_id"], iso, payload.network_id)
    net = NETWORKS[payload.network_id]
    return {"status": True, "data": {"address": addr["address"], "currency": iso,
            "network_id": payload.network_id, "network": net["name"], "network_iso": net["iso"]}}


class WithdrawIn(BaseModel):
    currency: str
    network_id: int
    amount: float
    address: str


@cab.post("/wallet/withdraw")
async def withdraw(request: Request, payload: WithdrawIn):
    user = await get_current_user(request)
    uid = user["user_id"]
    iso = payload.currency.upper()
    if iso not in CURRENCIES:
        raise HTTPException(400, "Currency not available")
    bal = await get_balance(uid, iso)
    comm = commission_for(iso, payload.network_id)["withdraw"]
    fee = max(comm["fixed"] + payload.amount * comm["percent"] / 100, comm["min_fee"])
    if payload.amount <= 0:
        raise HTTPException(400, "Invalid amount")
    if payload.amount > bal["balance_available"]:
        raise HTTPException(400, "Недостатньо коштів на балансі")
    await credit_balance(uid, iso, -payload.amount)
    tx = await add_transaction(uid, "withdraw", iso, payload.network_id, payload.amount,
                               status="Pending", address=payload.address,
                               description=f"Withdraw {iso}")
    return {"status": True, "data": tx, "commission": round(fee, 8)}


class ExchangeIn(BaseModel):
    from_iso: str
    to_iso: str
    amount: float


@cab.post("/wallet/exchange")
async def exchange(request: Request, payload: ExchangeIn):
    user = await get_current_user(request)
    uid = user["user_id"]
    fi, ti = payload.from_iso.upper(), payload.to_iso.upper()
    if fi not in CURRENCIES or ti not in CURRENCIES or fi == ti:
        raise HTTPException(400, "Invalid pair")
    bal = await get_balance(uid, fi)
    if payload.amount <= 0 or payload.amount > bal["balance_available"]:
        raise HTTPException(400, "Недостатньо коштів на балансі")
    usd = payload.amount * PRICES_USD[fi]
    fee_usd = usd * 0.004  # 0.4% swap fee
    received = (usd - fee_usd) / PRICES_USD[ti]
    await credit_balance(uid, fi, -payload.amount)
    await credit_balance(uid, ti, received)
    await add_transaction(uid, "exchange", fi, None, payload.amount, status="Done",
                          description=f"Exchange {fi} → {ti}", usd=round(usd, 2))
    tx = await add_transaction(uid, "exchange", ti, None, received, status="Done",
                               description=f"Received {ti} from {fi}")
    return {"status": True, "data": {"received": round(received, 8), "rate": round(PRICES_USD[fi]/PRICES_USD[ti], 8),
            "fee_usd": round(fee_usd, 2), "tx": tx}}


# ---------- invoices (cabinet) ----------
class InvoiceIn(BaseModel):
    order_id: str = ""
    payment_currency_iso: str = "USD"
    price: float = 0
    include_commission: int = 1
    description: str = ""
    currencies: list = []
    time_expired: int = 0
    redirect_url: str = ""


async def _create_invoice(user, merchant, data: dict) -> dict:
    inv_id = gen_id()
    curs = data.get("currencies") or []
    if not curs:
        curs = []
        for iso, c in CURRENCIES.items():
            for nid in c["networks"]:
                curs.append({"iso": iso, "network": nid})
    order_id = data.get("order_id") or gen_id(6)
    frontend = os.environ.get("FRONTEND_URL", "")
    inv = {
        "id": inv_id, "user_id": user["user_id"], "merchant_id": merchant["merchant_id"],
        "order_id": str(order_id), "payment_currency_iso": data.get("payment_currency_iso", "USD"),
        "price": float(data.get("price", 0)), "include_commission": int(data.get("include_commission", 1)),
        "description": data.get("description", ""), "status_id": 0, "status": "Created",
        "currencies": curs, "link": f"{frontend}/checkout/{inv_id}",
        "redirect_url": data.get("redirect_url", ""),
        "time_create": now_ts(),
        "time_expired": int(data.get("time_expired")) if data.get("time_expired") else now_ts() + 3600,
        "pay_info": None, "amount_paid": 0.0, "usd_value": 0.0,
    }
    await db.invoices.insert_one(dict(inv))
    inv.pop("_id", None)
    return inv


@cab.get("/invoices")
async def list_invoices(request: Request):
    user = await get_current_user(request)
    invs = await db.invoices.find({"user_id": user["user_id"]}, {"_id": 0}).sort("time_create", -1).to_list(200)
    return {"status": True, "data": [invoice_public(i) for i in invs]}


@cab.post("/invoices")
async def create_invoice_cab(request: Request, payload: InvoiceIn):
    user = await get_current_user(request)
    merchant = await get_merchant(user["user_id"])
    inv = await _create_invoice(user, merchant, payload.model_dump())
    return {"status": True, "data": invoice_public(inv)}


@cab.post("/invoices/{inv_id}/cancel")
async def cancel_invoice(request: Request, inv_id: str):
    user = await get_current_user(request)
    inv = await db.invoices.find_one({"id": inv_id, "user_id": user["user_id"]})
    if not inv:
        raise HTTPException(404, "Not found")
    await db.invoices.update_one({"id": inv_id}, {"$set": {"status": "Cancelled", "status_id": 3}})
    return {"status": True}


# ---------- contacts ----------
class ContactIn(BaseModel):
    name: str
    address: str
    network_id: int
    currency: str = ""


@cab.get("/contacts")
async def list_contacts(request: Request):
    user = await get_current_user(request)
    cs = await db.contacts.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"status": True, "data": cs}


@cab.post("/contacts")
async def add_contact(request: Request, payload: ContactIn):
    user = await get_current_user(request)
    c = {"contact_id": uuid.uuid4().hex[:10], "user_id": user["user_id"], "name": payload.name,
         "address": payload.address, "network_id": payload.network_id, "currency": payload.currency.upper(),
         "network": NETWORKS.get(payload.network_id, {}).get("name", ""),
         "created_at": datetime.now(timezone.utc).isoformat()}
    await db.contacts.insert_one(dict(c))
    c.pop("_id", None)
    return {"status": True, "data": c}


@cab.delete("/contacts/{cid}")
async def del_contact(request: Request, cid: str):
    user = await get_current_user(request)
    await db.contacts.delete_one({"contact_id": cid, "user_id": user["user_id"]})
    return {"status": True}


# ---------- merchant settings ----------
class MerchantIn(BaseModel):
    name: str = None
    home_url: str = None
    result_url: str = None
    brand_color: str = None
    logo_url: str = None
    description: str = None


@cab.get("/merchant")
async def merchant_get(request: Request):
    user = await get_current_user(request)
    return {"status": True, "data": await get_merchant(user["user_id"])}


@cab.put("/merchant")
async def merchant_update(request: Request, payload: MerchantIn):
    user = await get_current_user(request)
    await get_merchant(user["user_id"])
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    if upd:
        await db.merchants.update_one({"user_id": user["user_id"]}, {"$set": upd})
    return {"status": True, "data": await get_merchant(user["user_id"])}


@cab.post("/merchant/regenerate")
async def merchant_regen(request: Request):
    user = await get_current_user(request)
    await get_merchant(user["user_id"])
    await db.merchants.update_one({"user_id": user["user_id"]},
                                  {"$set": {"token": new_token(), "secret": new_secret()}})
    return {"status": True, "data": await get_merchant(user["user_id"])}


# ---------- public checkout ----------
@cab.get("/checkout/{inv_id}")
async def checkout_get(inv_id: str):
    inv = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    merchant = await db.merchants.find_one({"merchant_id": inv["merchant_id"]}, {"_id": 0})
    return {"status": True, "data": {
        **invoice_public(inv),
        "merchant": {"name": merchant.get("name", ""), "brand_color": merchant.get("brand_color", "#2563EB"),
                     "logo_url": merchant.get("logo_url", "")} if merchant else {},
        "currency_meta": {iso: {"name": CURRENCIES[iso]["name"], "color": CURRENCIES[iso]["color"]} for iso in CURRENCIES},
        "network_meta": {str(k): v for k, v in NETWORKS.items()},
    }}


class CheckoutSelectIn(BaseModel):
    iso: str
    network_id: int


@cab.post("/checkout/{inv_id}/select")
async def checkout_select(inv_id: str, payload: CheckoutSelectIn):
    inv = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv["status"] in ("Paid", "Completed", "Cancelled", "Expired"):
        raise HTTPException(400, "Invoice not payable")
    iso = payload.iso.upper()
    if iso not in CURRENCIES or payload.network_id not in CURRENCIES[iso]["networks"]:
        raise HTTPException(400, "Currency/network not available")
    addr = await allocate_address(inv["user_id"], iso, payload.network_id, invoice_id=inv_id)
    usd = inv["price"] * FIAT_RATES_USD.get(inv["payment_currency_iso"], 1.0)
    amount = usd / PRICES_USD[iso]
    comm = commission_for(iso, payload.network_id)["refill"]
    fee = max(comm["fixed"] + amount * comm["percent"] / 100, comm["min_fee"])
    amount_to_pay = amount + (fee if inv["include_commission"] == 0 else 0)
    net = NETWORKS[payload.network_id]
    pay_info = {"amount": round(amount, 8), "commission": round(fee, 8),
                "amount_to_pay": round(amount_to_pay, 8), "address": addr["address"],
                "currency": iso, "network": net["name"], "network_id": payload.network_id,
                "network_iso": net["iso"], "rate": PRICES_USD[iso]}
    await db.invoices.update_one({"id": inv_id}, {"$set": {"pay_info": pay_info, "status": "In Process", "status_id": 6}})
    return {"status": True, "data": pay_info}


@cab.post("/checkout/{inv_id}/simulate-pay")
async def checkout_simulate(inv_id: str):
    """DEMO: simulate a confirmed on-chain payment for the selected currency."""
    inv = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if not inv.get("pay_info"):
        raise HTTPException(400, "Select a payment currency first")
    if inv["status"] in ("Paid", "Completed"):
        return {"status": True, "data": invoice_public(inv)}
    pi = inv["pay_info"]
    iso, nid, amount = pi["currency"], pi["network_id"], pi["amount"]
    await credit_balance(inv["user_id"], iso, amount)
    await add_transaction(inv["user_id"], "deposit", iso, nid, amount, status="Done",
                          address=pi["address"], txid="0x" + uuid.uuid4().hex,
                          description=f"Deposit Invoice #{inv['id']}", invoice_id=inv_id,
                          order_id=inv["order_id"])
    await db.invoices.update_one({"id": inv_id}, {"$set": {
        "status": "Paid", "status_id": 8, "amount_paid": amount,
        "usd_value": round(amount * PRICES_USD[iso], 2)}})
    inv["status"] = "Paid"
    merchant = await db.merchants.find_one({"merchant_id": inv["merchant_id"]}, {"_id": 0})
    if merchant:
        await send_webhook(merchant, inv, iso, amount)
    inv2 = await db.invoices.find_one({"id": inv_id}, {"_id": 0})
    return {"status": True, "data": invoice_public(inv2)}


# ============================ public okipays API ============================
pub = APIRouter(prefix="/api/v1/public")


@pub.get("/currency-list")
async def currency_list():
    return {"status": True, "data": FIAT_CURRENCIES}


@pub.get("/currency-network-list")
async def currency_network_list():
    return {"status": True, "data": [
        {"name": CURRENCIES[iso]["name"], "iso3": iso, "icon": "",
         "networks": networks_for(iso)} for iso in CURRENCIES]}


# ============================ private okipays API (signature) ============================
priv = APIRouter(prefix="/api/v1")


async def auth_merchant(request: Request):
    token = request.headers.get("X-Auth-Token")
    if not token:
        raise HTTPException(401, "Your request was made with invalid credentials.NONE headers")
    merchant = await db.merchants.find_one({"token": token}, {"_id": 0})
    if not merchant:
        raise HTTPException(401, "Your request was made with invalid credentials.NONE headers")
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
        sign = request.headers.get("X-Auth-Sign", "")
        expected = make_signature(body, merchant["secret"])
        if sign != expected:
            raise HTTPException(400, "Signature is invalid")
    user = await db.users.find_one({"user_id": merchant["user_id"]}, {"_id": 0})
    return merchant, user, body


def coins_payload():
    data = {}
    for iso, c in CURRENCIES.items():
        nets = {}
        for nid in c["networks"]:
            net = NETWORKS[nid]
            comm = commission_for(iso, nid)
            nets[net["name"]] = {
                "name": net["name"], "network_id": nid, "network_iso": net["iso"],
                "in": 1, "out": 1,
                "withdraw": {"commission": {"fixed": comm["withdraw"]["fixed"],
                                            "percent": comm["withdraw"]["percent"],
                                            "min_fee": comm["withdraw"]["min_fee"]},
                             "min": comm["withdraw"]["min"]},
                "refill": {"commission": {"fixed": comm["refill"]["fixed"],
                                          "percent": comm["refill"]["percent"],
                                          "min_fee": comm["refill"]["min_fee"]},
                           "min": comm["refill"]["min"]},
            }
        data[iso] = {"id": c["id"], "name": c["name"], "iso3": iso, "networks": nets}
    return data


@priv.get("/private/coins")
async def private_coins(request: Request):
    merchant, _, _ = await auth_merchant(request)
    return {"status": True, "data": coins_payload(), "token": merchant["token"]}


@priv.post("/private/get-address")
async def private_get_address(request: Request):
    merchant, user, body = await auth_merchant(request)
    iso = str(body.get("currency", "")).upper()
    net_in = body.get("network")
    nid = _resolve_network(iso, net_in)
    if iso not in CURRENCIES or nid is None:
        return {"status": False, "error": "Currency not found", "token": merchant["token"]}
    addr = await allocate_address(user["user_id"], iso, nid)
    return {"status": True, "message": "", "data": {
        "address": addr["address"], "time_create": addr["time_create"],
        "network": NETWORKS[nid]["name"], "currency": {"iso": iso, "name": CURRENCIES[iso]["name"]}},
        "token": merchant["token"]}


def _resolve_network(iso, net_in):
    if iso not in CURRENCIES:
        return None
    allowed = CURRENCIES[iso]["networks"]
    if isinstance(net_in, int):
        return net_in if net_in in allowed else None
    if isinstance(net_in, str):
        for nid in allowed:
            if NETWORKS[nid]["name"].lower() == net_in.lower() or NETWORKS[nid]["iso"].lower() == net_in.lower():
                return nid
    if len(allowed) == 1:
        return allowed[0]
    return None


@priv.post("/order/create")
async def order_create(request: Request):
    merchant, user, body = await auth_merchant(request)
    if not body.get("order_id"):
        raise HTTPException(400, "order_id required")
    curs = []
    for c in body.get("currencies", []) or []:
        curs.append({"iso": str(c.get("iso", "")).upper(), "network": c.get("network")})
    data = {"order_id": body.get("order_id"), "payment_currency_iso": body.get("payment_currency_iso", "USD"),
            "price": body.get("price", 0), "include_commission": body.get("include_commission", 1),
            "description": body.get("description", ""), "currencies": curs,
            "time_expired": body.get("time_expired", 0), "redirect_url": body.get("redirect_url", "")}
    inv = await _create_invoice(user, merchant, data)
    return {"status": True, "message": "Success send request to create order.",
            "data": invoice_public(inv), "token": merchant["token"]}


@priv.post("/order/get")
async def order_get(request: Request):
    merchant, user, body = await auth_merchant(request)
    q = {"user_id": user["user_id"]}
    if body.get("order_id"):
        q["order_id"] = str(body["order_id"])
    inv = await db.invoices.find_one(q, {"_id": 0}, sort=[("time_create", -1)])
    if not inv:
        raise HTTPException(400, "Order not found")
    return {"status": True, "message": "Success get order data.",
            "data": invoice_public(inv), "token": merchant["token"]}


@priv.post("/merchant/balance")
async def merchant_balance(request: Request):
    merchant, user, body = await auth_merchant(request)
    iso = str(body.get("currency", "")).upper()
    if iso not in CURRENCIES:
        raise HTTPException(400, "Currency not available")
    b = await get_balance(user["user_id"], iso)
    return {"status": True, "message": "", "data": {
        "balance": str(b["balance"]), "balance_available": str(b["balance_available"]),
        "currency": {"iso3": iso, "name": CURRENCIES[iso]["name"]}}, "token": merchant["token"]}


@priv.post("/merchant/pay-in")
async def merchant_pay_in(request: Request):
    """Create Pay-in v2 — returns pay_info with deposit address immediately."""
    merchant, user, body = await auth_merchant(request)
    iso = str(body.get("currency", "")).upper()
    nid = _resolve_network(iso, body.get("network"))
    if iso not in CURRENCIES or nid is None:
        raise HTTPException(400, "Currency not available")
    amount = float(body.get("amount", 0))
    data = {"order_id": body.get("order_id") or gen_id(6), "payment_currency_iso": iso,
            "price": amount, "include_commission": body.get("include_commission", 0),
            "description": body.get("description", ""),
            "currencies": [{"iso": iso, "network": nid}],
            "redirect_url": body.get("redirect_url", "")}
    inv = await _create_invoice(user, merchant, data)
    addr = await allocate_address(user["user_id"], iso, nid, invoice_id=inv["id"])
    comm = commission_for(iso, nid)["refill"]
    fee = max(comm["fixed"] + amount * comm["percent"] / 100, comm["min_fee"])
    amount_to_pay = amount + (fee if inv["include_commission"] == 0 else 0)
    net = NETWORKS[nid]
    pay_info = {"commission": round(fee, 8), "amount_to_pay": round(amount_to_pay, 8),
                "amount": round(amount, 8), "address": addr["address"],
                "currency": net["iso"], "network": net["name"], "network_id": nid, "rate": PRICES_USD[iso]}
    await db.invoices.update_one({"id": inv["id"]}, {"$set": {"pay_info": pay_info, "status": "In Process", "status_id": 6}})
    inv = await db.invoices.find_one({"id": inv["id"]}, {"_id": 0})
    return {"status": True, "message": "Success send request to create order.",
            "data": invoice_public(inv), "token": merchant["token"]}


# ============================ startup / worker ============================
async def expire_worker():
    while True:
        try:
            ts = now_ts()
            cur = db.invoices.find({"status": {"$in": ["Created", "In Process"]},
                                    "time_expired": {"$lt": ts}}, {"_id": 0})
            async for inv in cur:
                await db.invoices.update_one({"id": inv["id"]}, {"$set": {"status": "Expired", "status_id": 7}})
                merchant = await db.merchants.find_one({"merchant_id": inv["merchant_id"]}, {"_id": 0})
                if merchant:
                    inv["status"] = "Expired"
                    await send_webhook(merchant, inv)
        except Exception as e:
            logger.info(f"worker error: {e}")
        await asyncio.sleep(30)


async def seed_demo():
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if existing:
        if existing.get("password_hash") and not verify_password(admin_pw, existing["password_hash"]):
            await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_pw)}})
        return existing["user_id"]
    uid = f"user_{uuid.uuid4().hex[:12]}"
    await db.users.insert_one({"user_id": uid, "email": admin_email, "name": "Merchant Demo",
                               "password_hash": hash_password(admin_pw), "auth_provider": "password",
                               "picture": "", "role": "admin",
                               "created_at": datetime.now(timezone.utc).isoformat()})
    merchant = await get_merchant(uid)
    await db.merchants.update_one({"user_id": uid}, {"$set": {
        "name": "EWEX", "home_url": "https://www.ewex.io", "description": "Crypto exchange service"}})
    # demo balances
    for iso, amt in [("USDT", 1049.0), ("BNB", 2.1), ("BTC", 0.0032), ("ETH", 0.15), ("TRX", 300.0)]:
        await credit_balance(uid, iso, amt)
    # demo transactions
    demo = [
        ("withdraw", "USDT", 1, 200.70, "Pending", "0xf8f...61d84"),
        ("withdraw", "USDT", 2, 40.35, "Pending", "GEmn7...AsTqT"),
        ("deposit", "USDT", 1, 1049.0, "Done", "Invoice #G2WGYW6P"),
        ("withdraw", "BNB", 4, 2.10, "Done", "0x848...73553"),
        ("deposit", "BNB", 4, 2.09, "Done", "Invoice #A1B2C3"),
        ("deposit", "BTC", 0, 0.0032, "Done", "Invoice #BTC001"),
    ]
    for t, iso, nid, amt, st, desc in demo:
        await add_transaction(uid, t, iso, nid, amt, status=st, description=desc)
        await asyncio.sleep(0)
    # demo invoices
    for oid, price, st, sid in [("1001", 15, "Paid", 8), ("1002", 49.99, "Created", 0), ("1003", 120, "Expired", 7)]:
        inv = await _create_invoice({"user_id": uid}, merchant, {"order_id": oid, "price": price,
              "payment_currency_iso": "USD", "description": f"Order {oid}"})
        await db.invoices.update_one({"id": inv["id"]}, {"$set": {"status": st, "status_id": sid}})
    logger.info(f"Seeded demo merchant {admin_email}")
    return uid


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id")
    await db.merchants.create_index("token")
    await db.merchants.create_index("user_id")
    await db.addresses.create_index([("chain", 1), ("index", 1)], unique=True)
    await db.invoices.create_index("id", unique=True)
    await db.transactions.create_index([("user_id", 1), ("created_ts", -1)])
    await db.user_sessions.create_index("session_token")
    await ensure_seed()
    uid = await seed_demo()
    merchant = await db.merchants.find_one({"user_id": uid}, {"_id": 0})
    try:
        from pathlib import Path as _P
        _P("/app/memory/test_credentials.md").write_text(
            "# Test Credentials\n\n"
            f"## Merchant cabinet (email/password)\n- Email: {os.environ['ADMIN_EMAIL']}\n"
            f"- Password: {os.environ['ADMIN_PASSWORD']}\n- Role: admin\n\n"
            "## Merchant API keys (for private /api/v1 endpoints)\n"
            f"- X-Auth-Token: {merchant['token']}\n- Secret: {merchant['secret']}\n\n"
            "## Auth endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n"
            "- POST /api/auth/google/session\n- GET /api/auth/me\n- POST /api/auth/logout\n")
    except Exception as e:
        logger.info(f"cred write failed: {e}")
    asyncio.create_task(expire_worker())


@app.on_event("shutdown")
async def shutdown():
    from core import client as _c
    _c.close()


@app.get("/api/")
async def root():
    return {"message": "OKIPAYS clone API", "status": True}


for r in (auth_router, cab, pub, priv):
    app.include_router(r)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[os.environ.get("FRONTEND_URL", "*")] if os.environ.get("FRONTEND_URL") else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
