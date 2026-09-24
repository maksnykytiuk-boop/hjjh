import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Eye, EyeOff, RefreshCw, Check } from "lucide-react";
import api, { apiErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useLang } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CoinIcon } from "@/components/common";

const FEE_COINS = ["USDT", "USDC", "BTC", "ETH", "BNB", "TRX", "SOL", "LTC"];

const COLORS = ["#94A3B8", "#1E3A5F", "#3B82F6", "#14B8A6", "#84CC16", "#2563EB",
  "#A855F7", "#EF4444", "#F87171", "#F59E0B", "#EAB308", "#92400E"];

export default function Settings() {
  const { t } = useLang();
  const { user } = useAuth();
  const [m, setM] = useState(null);
  const [showSecret, setShowSecret] = useState(false);

  useEffect(() => { api.get("/merchant").then((r) => setM(r.data.data)).catch(() => {}); }, []);
  if (!m) return <div className="text-slate-400">…</div>;

  const save = async () => {
    try {
      const { data } = await api.put("/merchant", {
        name: m.name, home_url: m.home_url, result_url: m.result_url,
        brand_color: m.brand_color, description: m.description,
        auto_swap: !!m.auto_swap, auto_swap_to: m.auto_swap_to || "USDT",
        fees: m.fees || {},
      });
      setM(data.data); toast.success(t("saved"));
    } catch (e) { toast.error(apiErr(e)); }
  };
  const regen = async () => {
    try { const { data } = await api.post("/merchant/regenerate"); setM(data.data); toast.success(t("regenerate")); }
    catch (e) { toast.error(apiErr(e)); }
  };
  const copy = (v) => { navigator.clipboard.writeText(v); toast.success(t("copied")); };

  const setFee = (iso, key, val) => {
    const fees = { ...(m.fees || {}) };
    fees[iso] = { ...(fees[iso] || {}), [key]: val === "" ? "" : Number(val) };
    setM({ ...m, fees });
  };
  const feeVal = (iso, key) => {
    const v = m.fees?.[iso]?.[key];
    return v === undefined || v === null ? "" : v;
  };

  return (
    <div className="space-y-6 oki-fade-up">
      <h1 className="text-2xl font-bold text-slate-900">{t("settings")}</h1>
      <div className="rounded-3xl bg-white p-6 shadow-sm border border-slate-100">
        <Tabs defaultValue="profile">
          <TabsList className="rounded-xl">
            <TabsTrigger value="profile" data-testid="tab-profile">{t("profile")}</TabsTrigger>
            <TabsTrigger value="merchant" data-testid="tab-merchant">{t("merchant")}</TabsTrigger>
            <TabsTrigger value="fees" data-testid="tab-fees">{t("fees")}</TabsTrigger>
          </TabsList>

          <TabsContent value="profile" className="pt-6">
            <div className="max-w-md space-y-4">
              <div><Label>{t("name")}</Label><Input value={user?.name || ""} disabled className="rounded-xl mt-1 bg-slate-50" /></div>
              <div><Label>{t("email")}</Label><Input value={user?.email || ""} disabled className="rounded-xl mt-1 bg-slate-50" /></div>
              <div className="text-xs text-slate-400">Провайдер входу: {user?.auth_provider || "password"}</div>
            </div>
          </TabsContent>

          <TabsContent value="merchant" className="pt-6">
            <div className="grid gap-8 lg:grid-cols-2">
              <div className="space-y-6">
                <div>
                  <div className="mb-3 text-lg font-bold text-slate-900">{t("merchant_info")}</div>
                  <div className="space-y-3">
                    <div><Label>{t("title")} *</Label><Input data-testid="merchant-name" value={m.name || ""} onChange={(e) => setM({ ...m, name: e.target.value })} className="rounded-xl mt-1" /></div>
                    <div><Label>{t("home_url")}</Label><Input data-testid="merchant-home" value={m.home_url || ""} onChange={(e) => setM({ ...m, home_url: e.target.value })} className="rounded-xl mt-1" placeholder="https://www.example.io" /></div>
                  </div>
                </div>
                <div>
                  <div className="mb-3 text-lg font-bold text-slate-900">{t("api_settings")}</div>
                  <div className="mb-2 text-xs text-slate-400">{t("api_key_note")}</div>
                  <div className="space-y-3">
                    <div><Label>{t("result_url")}</Label><Input data-testid="merchant-result-url" value={m.result_url || ""} onChange={(e) => setM({ ...m, result_url: e.target.value })} className="rounded-xl mt-1" placeholder="https://site.com/webhook" /></div>
                    <div><Label>{t("token")}</Label>
                      <div className="mt-1 flex items-center gap-2 rounded-xl border border-slate-200 p-2">
                        <code data-testid="merchant-token" className="flex-1 truncate text-xs">{m.token}</code>
                        <Button size="sm" variant="ghost" data-testid="copy-token" onClick={() => copy(m.token)}><Copy className="mr-1 h-3.5 w-3.5" />{t("copy")}</Button>
                      </div>
                    </div>
                    <div><Label>{t("secret")}</Label>
                      <div className="mt-1 flex items-center gap-2 rounded-xl border border-slate-200 p-2">
                        <code data-testid="merchant-secret" className="flex-1 truncate text-xs">{showSecret ? m.secret : "•".repeat(40)}</code>
                        <Button size="icon" variant="ghost" data-testid="toggle-secret" onClick={() => setShowSecret(!showSecret)}>{showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</Button>
                        <Button size="icon" variant="ghost" data-testid="copy-secret" onClick={() => copy(m.secret)}><Copy className="h-4 w-4" /></Button>
                      </div>
                    </div>
                    <Button data-testid="regen-btn" variant="outline" onClick={regen} className="rounded-full border-slate-300"><RefreshCw className="mr-2 h-4 w-4" />{t("regenerate")}</Button>
                  </div>
                </div>
              </div>

              <div>
                <div className="mb-3 text-lg font-bold text-slate-900">{t("branding")}</div>
                <Label>{t("color")}</Label>
                <div className="mt-2 flex flex-wrap gap-2">
                  {COLORS.map((c) => (
                    <button key={c} data-testid={`color-${c}`} onClick={() => setM({ ...m, brand_color: c })}
                      className="flex h-9 w-9 items-center justify-center rounded-full border-2 transition"
                      style={{ background: c, borderColor: m.brand_color === c ? "#0f172a" : "transparent" }}>
                      {m.brand_color === c && <Check className="h-4 w-4 text-white" />}
                    </button>
                  ))}
                </div>
                <div className="mt-6"><Label>{t("description")}</Label>
                  <Textarea data-testid="merchant-desc" value={m.description || ""} onChange={(e) => setM({ ...m, description: e.target.value })} className="rounded-xl mt-1" rows={4} placeholder="Зробіть назву вашого бізнесу зрозумілою для клієнтів" /></div>

                <div className="mt-8">
                  <div className="mb-3 text-lg font-bold text-slate-900">{t("auto_conv")}</div>
                  <div className="flex items-start justify-between rounded-2xl border border-slate-100 p-4">
                    <div className="pr-4">
                      <div className="font-semibold text-slate-800">{t("auto_swap")}</div>
                      <div className="text-xs text-slate-400">{t("auto_swap_desc")}</div>
                    </div>
                    <Switch data-testid="auto-swap-toggle" checked={!!m.auto_swap} onCheckedChange={(v) => setM({ ...m, auto_swap: v })} />
                  </div>
                  {m.auto_swap && (
                    <div className="mt-3 max-w-[220px]"><Label>{t("convert_to")}</Label>
                      <Select value={m.auto_swap_to || "USDT"} onValueChange={(v) => setM({ ...m, auto_swap_to: v })}>
                        <SelectTrigger data-testid="auto-swap-to" className="rounded-xl mt-1"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-white border border-slate-200">{["USDT", "USDC", "ETH", "BNB"].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="mt-8 flex justify-end">
              <Button data-testid="save-merchant" onClick={save} className="rounded-full bg-blue-600 hover:bg-blue-700 px-8">{t("save")}</Button>
            </div>
          </TabsContent>

          <TabsContent value="fees" className="pt-6">
            <div className="mb-4 max-w-2xl text-sm text-slate-500">{t("fees_desc")}</div>
            <div className="oki-scroll overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-400">
                    <th className="py-2">{t("currency")}</th>
                    <th className="text-center" colSpan={2}>{t("fee_in")}</th>
                    <th className="text-center" colSpan={2}>{t("fee_out")}</th>
                  </tr>
                  <tr className="text-left text-[11px] text-slate-300">
                    <th></th><th className="font-normal">{t("fee_pct")}</th><th className="font-normal">{t("fee_fixed")}</th>
                    <th className="font-normal">{t("fee_pct")}</th><th className="font-normal">{t("fee_fixed")}</th>
                  </tr>
                </thead>
                <tbody>
                  {FEE_COINS.map((iso) => (
                    <tr key={iso} data-testid={`fee-row-${iso}`} className="border-t border-slate-100">
                      <td className="py-2.5"><div className="flex items-center gap-2"><CoinIcon iso={iso} size={28} /><span className="font-semibold text-slate-700">{iso}</span></div></td>
                      <td className="pr-2"><Input data-testid={`fee-${iso}-in-pct`} type="number" step="0.01" value={feeVal(iso, "in_percent")} onChange={(e) => setFee(iso, "in_percent", e.target.value)} className="h-9 w-20 rounded-lg" placeholder="0" /></td>
                      <td className="pr-2"><Input data-testid={`fee-${iso}-in-fix`} type="number" step="0.0001" value={feeVal(iso, "in_fixed")} onChange={(e) => setFee(iso, "in_fixed", e.target.value)} className="h-9 w-24 rounded-lg" placeholder="0" /></td>
                      <td className="pr-2"><Input data-testid={`fee-${iso}-out-pct`} type="number" step="0.01" value={feeVal(iso, "out_percent")} onChange={(e) => setFee(iso, "out_percent", e.target.value)} className="h-9 w-20 rounded-lg" placeholder="0" /></td>
                      <td><Input data-testid={`fee-${iso}-out-fix`} type="number" step="0.0001" value={feeVal(iso, "out_fixed")} onChange={(e) => setFee(iso, "out_fixed", e.target.value)} className="h-9 w-24 rounded-lg" placeholder="0" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-8 flex justify-end">
              <Button data-testid="save-fees" onClick={save} className="rounded-full bg-blue-600 hover:bg-blue-700 px-8">{t("save")}</Button>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
