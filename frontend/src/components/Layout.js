import React, { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Wallet, Receipt, Users, Settings, LogOut,
  ChevronDown, MessageCircle, Menu, X,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useLang } from "@/lib/i18n";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const NAV = [
  { key: "dashboard", path: "/dashboard", icon: LayoutDashboard },
  { key: "wallet", path: "/wallet", icon: Wallet },
  { key: "requests", path: "/requests", icon: Receipt },
  { key: "contacts", path: "/contacts", icon: Users },
  { key: "settings", path: "/settings", icon: Settings },
];

function Logo() {
  return (
    <div className="flex items-center gap-2.5" data-testid="oki-logo">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white font-extrabold shadow-md">
        M
      </div>
      <span className="text-xl font-extrabold tracking-tight text-slate-900">MaksPAY</span>
    </div>
  );
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useLang();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const initials = (user?.name || user?.email || "M").slice(0, 2).toUpperCase();

  const topLinks = [
    { key: "commissions", path: "/commissions" },
    { key: "api_docs", path: "/docs" },
    { key: "about", path: "/about" },
  ];

  return (
    <div className="min-h-screen bg-[#F4F5F7]">
      {/* Topbar */}
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
        <div className="flex items-center gap-8">
          <button className="lg:hidden" onClick={() => setOpen(!open)} data-testid="sidebar-toggle">
            {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
          <Logo />
          <nav className="hidden items-center gap-6 md:flex">
            {topLinks.map((l) => (
              <NavLink key={l.key} to={l.path} data-testid={`top-${l.key}`}
                className="text-sm font-semibold text-slate-600 transition-colors hover:text-blue-600">
                {t(l.key)}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid="lang-switch" className="flex items-center gap-1 rounded-full px-2 py-1 text-sm font-semibold text-slate-600 hover:bg-slate-100">
                {lang.toUpperCase()} <ChevronDown className="h-4 w-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-white border border-slate-200">
              <DropdownMenuItem onClick={() => setLang("uk")} data-testid="lang-uk">UK · Українська</DropdownMenuItem>
              <DropdownMenuItem onClick={() => setLang("en")} data-testid="lang-en">EN · English</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid="user-menu" className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-600 text-sm font-bold text-white shadow">
                {initials}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-white border border-slate-200 w-56">
              <div className="px-2 py-1.5 text-xs text-slate-500">{user?.email}</div>
              <DropdownMenuItem onClick={() => { logout(); navigate("/login"); }} data-testid="logout-btn" className="text-rose-600 focus:text-rose-600">
                <LogOut className="mr-2 h-4 w-4" /> {t("logout")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className={`fixed inset-y-16 left-0 z-20 w-64 transform border-r border-slate-200 bg-white p-4 transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
          <nav className="space-y-1.5">
            {NAV.map((n) => {
              const Icon = n.icon;
              return (
                <NavLink key={n.key} to={n.path} onClick={() => setOpen(false)} data-testid={`nav-${n.key}`}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition-all ${
                      isActive ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-md" : "text-slate-600 hover:bg-slate-100"
                    }`}>
                  <Icon className="h-5 w-5" /> {t(n.key)}
                </NavLink>
              );
            })}
          </nav>
        </aside>

        <main className="min-h-[calc(100vh-4rem)] w-full min-w-0 flex-1 overflow-x-hidden p-4 sm:p-6 lg:p-8">{children}</main>
      </div>

      {/* Support bubble */}
      <button data-testid="support-bubble" className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-xl transition-transform hover:scale-110">
        <MessageCircle className="h-6 w-6" />
      </button>
    </div>
  );
}
