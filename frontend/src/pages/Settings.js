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
      });
      setM(data.data); toast.success(t("saved"));
    } catch (e) { toast.error(apiErr(e)); }
  };
  const regen = async () => {
    try { const { data } = await api.post("/merchant/regenerate"); setM(data.data); toast.success(t("regenerate")); }
    catch (e) { toast.error(apiErr(e)); }
  };
  const copy = (v) => { navigator.clipboard.writeText(v); toast.success(t("copied")); };

  return (
    <div className="space-y-6 oki-fade-up">
      <h1 className="text-2xl font-bold text-slate-900">{t("settings")}</h1>
      <div className="rounded-3xl bg-white p-6 shadow-sm border border-slate-100">
        <Tabs defaultValue="profile">
          <TabsList className="rounded-xl">
            <TabsTrigger value="profile" data-testid="tab-profile">{t("profile")}</TabsTrigger>
            <TabsTrigger value="merchant" data-testid="tab-merchant">{t("merchant")}</TabsTrigger>
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
              </div>
            </div>
            <div className="mt-8 flex justify-end">
              <Button data-testid="save-merchant" onClick={save} className="rounded-full bg-blue-600 hover:bg-blue-700 px-8">{t("save")}</Button>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
