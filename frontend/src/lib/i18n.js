import React, { createContext, useContext, useState, useCallback } from "react";

const dict = {
  uk: {
    login: "Вхід", register: "Реєстрація", email: "Email", password: "Пароль", name: "Ім'я",
    login_title: "Вхід в кабінет", login_sub: "Керуйте крипто-платежами MaksPAY",
    login_btn: "Увійти", register_btn: "Створити акаунт", google_btn: "Увійти через Google",
    logout: "Вийти", dashboard: "Панель керування", wallet: "Гаманець",
    requests: "Платіжні запити", contacts: "Контакти", settings: "Налаштування",
    commissions: "Комісії", api_docs: "API Документація", about: "Про нас",
    total_balance: "Загальний баланс", available: "Доступно", receive: "Отримати",
    send: "Відправити", exchange: "Обмін", balance_chart: "Графік балансу",
    recent_tx: "Останні транзакції", create_invoice: "Створити рахунок",
    all_tx: "Усі транзакції", details: "Деталі", amount: "Сума", status: "Статус",
    profile: "Профіль", merchant: "Мерчант", merchant_info: "Інформація про Мерчанта",
    api_settings: "API-налаштування", branding: "Брендинг", title: "Назва",
    home_url: "Домашній URL", result_url: "Result URL", token: "Токен", secret: "Секрет",
    copy: "Скопіювати", copied: "Скопійовано", regenerate: "Регенерувати",
    color: "Колір", description: "Опис", save: "Зберегти", saved: "Збережено",
    deposit: "Поповнення", withdraw: "Виведення", swap: "Обмін валют",
    deposit_address: "Адреса для поповнення", generate: "Згенерувати адресу",
    network: "Мережа", currency: "Валюта", withdraw_address: "Адреса отримувача",
    withdraw_btn: "Вивести кошти", you_get: "Ви отримаєте", from: "З", to: "На",
    add_contact: "Додати контакт", contact_name: "Ім'я контакту", address: "Адреса",
    delete: "Видалити", no_data: "Немає даних", price: "Сума", client: "Опис",
    callback: "Callback URL", create: "Створити", pay_link: "Посилання на оплату",
    invoice: "Рахунок", pay: "Оплатити", select_currency: "Оберіть валюту оплати",
    scan_qr: "Відскануйте QR або скопіюйте адресу", simulate_pay: "Симулювати оплату",
    paid: "Оплачено", waiting: "Очікування оплати", pick_pair: "Оберіть пару",
    save_contact: "Зберегти", welcome: "Ласкаво просимо", cancel: "Скасувати",
    balance: "Баланс", value: "Вартість", empty_tx: "Транзакцій ще немає",
    api_key_note: "Ключі для доступу до приватного API",
  },
  en: {
    login: "Login", register: "Sign up", email: "Email", password: "Password", name: "Name",
    login_title: "Sign in to cabinet", login_sub: "Manage MaksPAY crypto payments",
    login_btn: "Sign in", register_btn: "Create account", google_btn: "Continue with Google",
    logout: "Log out", dashboard: "Dashboard", wallet: "Wallet",
    requests: "Payment requests", contacts: "Contacts", settings: "Settings",
    commissions: "Fees", api_docs: "API Docs", about: "About",
    total_balance: "Total balance", available: "Available", receive: "Receive",
    send: "Send", exchange: "Exchange", balance_chart: "Balance chart",
    recent_tx: "Recent transactions", create_invoice: "Create invoice",
    all_tx: "All transactions", details: "Details", amount: "Amount", status: "Status",
    profile: "Profile", merchant: "Merchant", merchant_info: "Merchant information",
    api_settings: "API settings", branding: "Branding", title: "Name",
    home_url: "Home URL", result_url: "Result URL", token: "Token", secret: "Secret",
    copy: "Copy", copied: "Copied", regenerate: "Regenerate",
    color: "Color", description: "Description", save: "Save", saved: "Saved",
    deposit: "Deposit", withdraw: "Withdraw", swap: "Swap",
    deposit_address: "Deposit address", generate: "Generate address",
    network: "Network", currency: "Currency", withdraw_address: "Recipient address",
    withdraw_btn: "Withdraw", you_get: "You get", from: "From", to: "To",
    add_contact: "Add contact", contact_name: "Contact name", address: "Address",
    delete: "Delete", no_data: "No data", price: "Amount", client: "Description",
    callback: "Callback URL", create: "Create", pay_link: "Payment link",
    invoice: "Invoice", pay: "Pay", select_currency: "Select payment currency",
    scan_qr: "Scan QR or copy the address", simulate_pay: "Simulate payment",
    paid: "Paid", waiting: "Waiting for payment", pick_pair: "Select pair",
    save_contact: "Save", welcome: "Welcome", cancel: "Cancel",
    balance: "Balance", value: "Value", empty_tx: "No transactions yet",
    api_key_note: "Keys to access the private API",
  },
};

const LangCtx = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(localStorage.getItem("oki_lang") || "uk");
  const change = useCallback((l) => { setLang(l); localStorage.setItem("oki_lang", l); }, []);
  const t = useCallback((k) => (dict[lang] && dict[lang][k]) || dict.uk[k] || k, [lang]);
  return <LangCtx.Provider value={{ lang, setLang: change, t }}>{children}</LangCtx.Provider>;
}

export const useLang = () => useContext(LangCtx);
