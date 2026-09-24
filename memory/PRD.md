# MaksPAY — Crypto Payment Gateway (OKIPAYS-style)

## Original problem statement
Build a fully working crypto payment gateway similar to okipays.com (API docs: docs.okipays.com). No landing page. Merchant cabinet + working crypto acceptance & exchange + full client API. HD wallets (BIP-44), multi-chain tracking, auto-conversion, wrong-network fund recovery. Brand: **MaksPAY**.

## User choices
- Blockchain: MAINNET (real keys provided). DEMO simulation acceptable for incoming-deposit detection until websocket worker is wired.
- Auth: email+password (JWT) AND Emergent Google login.
- Currencies: USDT (ETH/BSC/Polygon/Arbitrum/TRON), USDC, BTC, ETH, BNB, TRX, SOL, LTC.
- Languages: Ukrainian + English (switcher).

## Architecture
- Backend: FastAPI + MongoDB (motor). Modules: core.py (auth/security/signature), catalog.py (currencies/networks/fees/prices), hd_wallet.py (BIP-44 derivation), recovery.py (live EVM/TRON/BTC scan + EVM sweep), server.py (routers + worker + seed).
- Frontend: React (CRA/craco), Tailwind + shadcn/ui, recharts, sonner, i18n (uk/en), axios (cookie + Bearer).
- HD Wallet: single BIP-39 mnemonic (env WALLET_MNEMONIC). EVM chains share one 0x address per index; TRON/BTC/LTC/SOL derived per coin.

## Integrations (LIVE mainnet keys in backend/.env)
- Alchemy (ALCHEMY_KEY): eth/polygon/arb/bnb RPC — verified working.
- TronGrid (TRONGRID_KEY): TRON reads — verified.
- Mempool.space: BTC reads (no key).
- 1inch (ONEINCH_KEY): stored, swap engine not yet wired (cabinet exchange uses internal rates).
- TREASURY_EVM: sweep destination (= HD index 1 address of provided seed).

## Implemented (2026-06 / iteration 1-2)
- Auth: register/login (JWT), Emergent Google session, /auth/me, logout. Admin seed: merchant@okipays.dev / Merchant123!
- Cabinet: Dashboard (balance card, live tickers, balance chart, recent tx), Wallet (balances, deposit address+QR, withdraw, exchange/swap, tx table), Payment Requests (create/list/cancel invoices + checkout link), Contacts (CRUD), Settings (Profile + Merchant: token/secret copy+regen, branding color, description), API Docs page (live examples with merchant token), Fund Recovery page.
- Public checkout page (/checkout/:id): select currency+network → real deposit address + QR → simulate payment → Paid + webhook.
- Client API (OKIPAYS-compatible): public currency-list / currency-network-list; private (X-Auth-Token + X-Auth-Sign sha256): coins, get-address, order/create, order/get, merchant/balance, merchant/pay-in. Signature verified; bad sign → 400.
- HD address generation: REAL BIP-44 (verified TRON/BTC/EVM).
- **Fund recovery (LIVE mainnet)**: scan all HD addresses across ETH/Polygon/BSC/Arbitrum (native + USDT/USDC) + TRON + BTC; sweep EVM balances to treasury (signs & broadcasts). Private-key↔address guard.
- Worker: expires overdue invoices + webhook.
- Bilingual UI, mobile-responsive (overflow verified at 390px), MaksPAY branding.

## Testing
- Backend: 34/34 pytest passed (iteration_1). Recovery live scan verified (EVM:3/TRON:5/BTC:1, empty balances). Mobile overflow fixed.
- Frontend: login→dashboard, nav, wallet, invoices, checkout, settings, api-docs, recovery verified via screenshots.

## Backlog / remaining
- P0: Wire LIVE incoming-deposit detection (Alchemy websockets / TronGrid / Mempool polling) to auto-credit merchant balance & fire webhook, replacing simulate-pay.
- P1: Live 1inch auto-swap on received deposits (EVM) + cross-chain (FixedFloat/ChangeNOW) for BTC/TRON.
- P1: Gas-station auto-funding for ERC-20/BEP-20 token sweeps (fund native gas before transfer).
- P2: TRON/BTC sweep execution (currently EVM sweep only; TRON/BTC detection-only).
- P2: Webhook signature/HMAC + retry queue; invoice status "Completed" on merchant ack.
- P2: Rotate seed to secure custody (provided seed considered compromised).

## Notes / MOCKED
- Incoming invoice payment confirmation is **SIMULATED** via POST /api/checkout/{id}/simulate-pay (DEMO). Address generation, price/RPC reads, and fund-recovery sweep are LIVE mainnet.
- EVM sweep sends real on-chain transactions; not exercised with real funds (test addresses empty).
