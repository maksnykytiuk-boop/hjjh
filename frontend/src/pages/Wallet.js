import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, ArrowUpRight, ArrowDownLeft, RefreshCw } from "lucide-react";
import api, { apiErr } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { CoinIcon, StatusBadge, fmtUsd, fmtCrypto } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

function NetSelect({ networks, value, onChange, testid }) {
  return (
    <Select value={value != null ? String(value) : ""} onValueChange={(v) => onChange(Number(v))}>
      <SelectTrigger data-testid={testid} className="rounded-xl"><SelectValue placeholder="—" /></SelectTrigger>
      <SelectContent className="bg-white border border-slate-200">
        {networks.map((n) => (
          <SelectItem key={n.network_id} value={String(n.network_id)}>{n.name} ({n.network_iso})</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export default function Wallet() {
  const { t } = useLang();
  const [assets, setAssets] = useState([]);
  const [txs, setTxs] = useState([]);

  const load = () => {
    api.get("/wallet").then((r) => setAssets(r.data.data)).catch(() => {});
    api.get("/transactions").then((r) => setTxs(r.data.data)).catch(() => {});
  };
  useEffect(load, []);

  // deposit
  const [dCur, setDCur] = useState("USDT");
  const [dNet, setDNet] = useState(null);
  const [dAddr, setDAddr] = useState("");
  const depAsset = assets.find((a) => a.iso === dCur);
  const genAddr = async () => {
    try {
      const { data } = await api.post("/wallet/deposit-address", { currency: dCur, network_id: dNet });
      setDAddr(data.data.address);
    } catch (e) { toast.error(apiErr(e)); }
  };

  // withdraw
  const [wCur, setWCur] = useState("USDT");
  const [wNet, setWNet] = useState(null);
  const [wAmt, setWAmt] = useState("");
  const [wAddr, setWAddr] = useState("");
  const wdAsset = assets.find((a) => a.iso === wCur);
  const doWithdraw = async () => {
    try {
      await api.post("/wallet/withdraw", { currency: wCur, network_id: wNet, amount: Number(wAmt), address: wAddr });
      toast.success("Заявку на виведення створено");
      setWAmt(""); setWAddr(""); load();
    } catch (e) { toast.error(apiErr(e)); }
  };

  // exchange
  const [fFrom, setFFrom] = useState("USDT");
  const [fTo, setFTo] = useState("BTC");
  const [fAmt, setFAmt] = useState("");
  const doExchange = async () => {
    try {
      const { data } = await api.post("/wallet/exchange", { from_iso: fFrom, to_iso: fTo, amount: Number(fAmt) });
      toast.success(`${t("you_get")} ${fmtCrypto(data.data.received)} ${fTo}`);
      setFAmt(""); load();
    } catch (e) { toast.error(apiErr(e)); }
  };
  const fromAsset = assets.find((a) => a.iso === fFrom);

  const copy = (v) => { navigator.clipboard.writeText(v); toast.success(t("copied")); };

  return (
    <div className="space-y-6 oki-fade-up">
      <h1 className="text-2xl font-bold text-slate-900">{t("wallet")}</h1>
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Assets */}
        <div className="rounded-3xl bg-white p-5 shadow-sm border border-slate-100 lg:col-span-2">
          <div className="mb-3 text-lg font-bold text-slate-900">{t("balance")}</div>
          <div className="space-y-1">
            {assets.map((a) => (
              <div key={a.iso} data-testid={`asset-${a.iso}`} className="flex items-center gap-3 rounded-xl px-2 py-2.5 hover:bg-slate-50">
                <CoinIcon iso={a.iso} />
                <div className="flex-1">
                  <div className="text-sm font-semibold text-slate-800">{a.name}</div>
                  <div className="text-xs text-slate-400">{a.iso} • {fmtUsd(a.price)}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-slate-800">{fmtCrypto(a.balance)}</div>
                  <div className="text-xs text-slate-400">{fmtUsd(a.usd_value)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="rounded-3xl bg-white p-5 shadow-sm border border-slate-100 lg:col-span-3">
          <Tabs defaultValue="deposit">
            <TabsList className="grid w-full grid-cols-3 rounded-xl">
              <TabsTrigger value="deposit" data-testid="tab-deposit"><ArrowDownLeft className="mr-1 h-4 w-4" />{t("deposit")}</TabsTrigger>
              <TabsTrigger value="withdraw" data-testid="tab-withdraw"><ArrowUpRight className="mr-1 h-4 w-4" />{t("withdraw")}</TabsTrigger>
              <TabsTrigger value="swap" data-testid="tab-swap"><RefreshCw className="mr-1 h-4 w-4" />{t("swap")}</TabsTrigger>
            </TabsList>

            <TabsContent value="deposit" className="space-y-4 pt-4">
              <div className="grid grid-cols-2 gap-3">
                <div><Label>{t("currency")}</Label>
                  <Select value={dCur} onValueChange={(v) => { setDCur(v); setDNet(null); setDAddr(""); }}>
                    <SelectTrigger data-testid="dep-currency" className="rounded-xl mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-white border border-slate-200">{assets.map((a) => <SelectItem key={a.iso} value={a.iso}>{a.iso}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label>{t("network")}</Label><div className="mt-1"><NetSelect testid="dep-network" networks={depAsset?.networks || []} value={dNet} onChange={(v) => { setDNet(v); setDAddr(""); }} /></div></div>
              </div>
              <Button data-testid="gen-address-btn" disabled={dNet == null} onClick={genAddr} className="w-full rounded-full bg-blue-600 hover:bg-blue-700">{t("generate")}</Button>
              {dAddr && (
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4 text-center">
                  <img alt="qr" src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(dAddr)}`} className="mx-auto rounded-xl bg-white p-2" />
                  <div className="mt-3 text-xs text-slate-500">{t("scan_qr")}</div>
                  <div data-testid="dep-address" className="mt-2 flex items-center gap-2 rounded-xl bg-white p-2">
                    <code className="flex-1 break-all text-xs text-slate-700">{dAddr}</code>
                    <Button size="icon" variant="ghost" data-testid="copy-address" onClick={() => copy(dAddr)}><Copy className="h-4 w-4" /></Button>
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="withdraw" className="space-y-4 pt-4">
              <div className="grid grid-cols-2 gap-3">
                <div><Label>{t("currency")}</Label>
                  <Select value={wCur} onValueChange={(v) => { setWCur(v); setWNet(null); }}>
                    <SelectTrigger data-testid="wd-currency" className="rounded-xl mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-white border border-slate-200">{assets.map((a) => <SelectItem key={a.iso} value={a.iso}>{a.iso}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label>{t("network")}</Label><div className="mt-1"><NetSelect testid="wd-network" networks={wdAsset?.networks || []} value={wNet} onChange={setWNet} /></div></div>
              </div>
              <div><Label>{t("amount")} <span className="text-slate-400">({t("available")}: {fmtCrypto(wdAsset?.balance_available)} {wCur})</span></Label>
                <Input data-testid="wd-amount" type="number" value={wAmt} onChange={(e) => setWAmt(e.target.value)} className="rounded-xl mt-1" placeholder="0.00" /></div>
              <div><Label>{t("withdraw_address")}</Label><Input data-testid="wd-address" value={wAddr} onChange={(e) => setWAddr(e.target.value)} className="rounded-xl mt-1" placeholder="0x… / T… / bc1…" /></div>
              <Button data-testid="withdraw-btn" disabled={wNet == null || !wAmt || !wAddr} onClick={doWithdraw} className="w-full rounded-full bg-blue-600 hover:bg-blue-700">{t("withdraw_btn")}</Button>
            </TabsContent>

            <TabsContent value="swap" className="space-y-4 pt-4">
              <div className="grid grid-cols-2 gap-3">
                <div><Label>{t("from")}</Label>
                  <Select value={fFrom} onValueChange={setFFrom}>
                    <SelectTrigger data-testid="ex-from" className="rounded-xl mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-white border border-slate-200">{assets.map((a) => <SelectItem key={a.iso} value={a.iso}>{a.iso}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label>{t("to")}</Label>
                  <Select value={fTo} onValueChange={setFTo}>
                    <SelectTrigger data-testid="ex-to" className="rounded-xl mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-white border border-slate-200">{assets.map((a) => <SelectItem key={a.iso} value={a.iso}>{a.iso}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div><Label>{t("amount")} <span className="text-slate-400">({t("available")}: {fmtCrypto(fromAsset?.balance_available)} {fFrom})</span></Label>
                <Input data-testid="ex-amount" type="number" value={fAmt} onChange={(e) => setFAmt(e.target.value)} className="rounded-xl mt-1" placeholder="0.00" /></div>
              <Button data-testid="exchange-btn" disabled={!fAmt || fFrom === fTo} onClick={doExchange} className="w-full rounded-full bg-blue-600 hover:bg-blue-700">{t("exchange")}</Button>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {/* Transactions */}
      <div className="rounded-3xl bg-white p-5 shadow-sm border border-slate-100">
        <div className="mb-3 text-lg font-bold text-slate-900">{t("all_tx")}</div>
        <div className="oki-scroll overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-400">
              <th className="py-2">{t("details")}</th><th>{t("amount")}</th><th>{t("value")}</th><th className="text-right">{t("status")}</th>
            </tr></thead>
            <tbody>
              {txs.map((tx) => (
                <tr key={tx.tx_id} data-testid={`wtx-${tx.tx_id}`} className="border-t border-slate-100">
                  <td className="py-3"><div className="flex items-center gap-3"><CoinIcon iso={tx.iso} size={32} />
                    <div><div className="font-semibold capitalize text-slate-800">{tx.type}</div><div className="text-xs text-slate-400">{tx.description}</div></div></div></td>
                  <td className={tx.type === "withdraw" ? "text-rose-500 font-semibold" : "text-emerald-600 font-semibold"}>{tx.type === "withdraw" ? "-" : "+"}{fmtCrypto(tx.amount)} {tx.iso}</td>
                  <td className="text-slate-500">{fmtUsd(tx.usd_value)}</td>
                  <td className="text-right"><StatusBadge status={tx.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {txs.length === 0 && <div className="py-8 text-center text-sm text-slate-400">{t("empty_tx")}</div>}
        </div>
      </div>
    </div>
  );
}
