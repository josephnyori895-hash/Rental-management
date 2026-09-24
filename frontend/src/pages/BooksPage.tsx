import { useEffect, useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  DollarSign, CreditCard, AlertTriangle, TrendingUp, TrendingDown,
  FileText, Search, Download, Building2, Loader2, Wallet, Scale,
  BookOpen, Receipt, ArrowUpRight, ArrowDownRight, Calendar, X,
} from "lucide-react";
import { getBoard, getInvoices, getPaymentHistory, getBooksBundle, exportBooks, downloadCSV } from "../lib/api";
import { Card, AnimatedNumber, money } from "../components/ui";

type Tab = "pnl" | "balance" | "trial" | "invoices" | "payments" | "expenses";

const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: "pnl",       label: "Profit & Loss",   icon: <TrendingUp className="w-3.5 h-3.5" /> },
  { key: "balance",   label: "Balance Sheet",   icon: <Scale className="w-3.5 h-3.5" /> },
  { key: "trial",     label: "Trial Balance",   icon: <BookOpen className="w-3.5 h-3.5" /> },
  { key: "invoices",  label: "Invoices",        icon: <FileText className="w-3.5 h-3.5" /> },
  { key: "payments",  label: "Payments",        icon: <CreditCard className="w-3.5 h-3.5" /> },
  { key: "expenses",  label: "Expenses",        icon: <Receipt className="w-3.5 h-3.5" /> },
];

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};
const item = {
  hidden: { y: 12, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { type: "spring" as const, stiffness: 200, damping: 22 } },
};

export default function BooksPage() {
  const [board, setBoard] = useState<any>(null);
  const [bundle, setBundle] = useState<any>(null);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [payments, setPayments] = useState<any[]>([]);
  const [tab, setTab] = useState<Tab>("pnl");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [search, setSearch] = useState("");
  const [invFilter, setInvFilter] = useState("all");
  const [downloading, setDownloading] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    setFromDate(firstDay.toISOString().slice(0, 10));
    setToDate(today.toISOString().slice(0, 10));
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [b, inv, pay] = await Promise.all([
          getBoard(),
          getInvoices(),
          getPaymentHistory(),
        ]);
        setBoard(b);
        setInvoices(inv.invoices || []);
        setPayments(pay.payments || []);
      } catch (e) {
        console.error(e);
      }
    })();
  }, []);

  useEffect(() => {
    if (!fromDate || !toDate) return;
    setLoading(true);
    getBooksBundle(fromDate, toDate)
      .then((d) => { setBundle(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [fromDate, toDate]);

  const handleExport = async () => {
    setDownloading(true);
    try {
      await exportBooks(fromDate, toDate);
    } catch (e) {
      console.error(e);
    } finally {
      setDownloading(false);
    }
  };

  const handleExportTab = (currentTab: Tab) => {
    if (!bundle) return;
    const rows: (string | number)[][] = [];
    if (currentTab === "pnl") {
      rows.push(["PROFIT & LOSS STATEMENT"]);
      rows.push([`Period: ${fromDate} to ${toDate}`]);
      rows.push([]);
      rows.push(["INCOME"]);
      rows.push(["Code", "Account", "Balance"]);
      bundle.profit_loss.income.forEach((a: any) => rows.push([a.code, a.name, a.balance.toFixed(2)]));
      rows.push(["", "Total Income", bundle.profit_loss.total_income.toFixed(2)]);
      rows.push([]);
      rows.push(["EXPENSES"]);
      rows.push(["Code", "Account", "Balance"]);
      bundle.profit_loss.expenses.forEach((a: any) => rows.push([a.code, a.name, a.balance.toFixed(2)]));
      rows.push(["", "Total Expenses", bundle.profit_loss.total_expenses.toFixed(2)]);
      rows.push(["", "NET PROFIT", bundle.profit_loss.net_profit.toFixed(2)]);
    } else if (currentTab === "balance") {
      rows.push(["BALANCE SHEET"]);
      rows.push([`As at: ${toDate}`]);
      rows.push([]);
      rows.push(["ASSETS"]);
      rows.push(["Code", "Account", "Balance"]);
      bundle.balance_sheet.assets.forEach((a: any) => rows.push([a.code, a.name, a.balance.toFixed(2)]));
      rows.push(["", "Total Assets", bundle.balance_sheet.total_assets.toFixed(2)]);
      rows.push([]);
      rows.push(["LIABILITIES"]);
      bundle.balance_sheet.liabilities.forEach((a: any) => rows.push([a.code, a.name, a.balance.toFixed(2)]));
      rows.push(["", "Total Liabilities", bundle.balance_sheet.total_liabilities.toFixed(2)]);
      rows.push([]);
      rows.push(["EQUITY"]);
      bundle.balance_sheet.equity.forEach((a: any) => rows.push([a.code, a.name, a.balance.toFixed(2)]));
      rows.push(["", "Total Equity", bundle.balance_sheet.total_equity.toFixed(2)]);
      rows.push(["", "Net Assets", bundle.balance_sheet.net_assets.toFixed(2)]);
    } else if (currentTab === "trial") {
      rows.push(["TRIAL BALANCE"]);
      rows.push([`As at: ${toDate}`]);
      rows.push([]);
      rows.push(["Code", "Account", "Type", "Debit", "Credit", "Balance"]);
      bundle.trial_balance.forEach((a: any) => rows.push([a.code, a.name, a.type, a.debit.toFixed(2), a.credit.toFixed(2), a.balance.toFixed(2)]));
    } else if (currentTab === "invoices") {
      rows.push(["INVOICES"]);
      rows.push(["Invoice #", "Date", "Tenant", "Unit", "Type", "Amount", "Paid", "Balance", "Status", "Due Date"]);
      bundle.invoices.forEach((i: any) => rows.push([i.invoice_number, i.date, i.tenant, i.unit, i.type, i.amount, i.paid, i.balance, i.status, i.due_date]));
    } else if (currentTab === "payments") {
      rows.push(["PAYMENTS"]);
      rows.push(["Date", "Tenant", "Unit", "Amount", "Method", "Reference", "Status"]);
      bundle.payments.forEach((p: any) => rows.push([p.date, p.tenant, p.unit, p.amount, p.method, p.reference, p.status]));
    } else if (currentTab === "expenses") {
      rows.push(["EXPENSES"]);
      rows.push(["Date", "Category", "Description", "Amount", "Vendor"]);
      bundle.expenses.forEach((e: any) => rows.push([e.date, e.category, e.description, e.amount, e.vendor]));
    }
    downloadCSV(`${currentTab}_${fromDate}_to_${toDate}.csv`, rows);
  };

  if (!board) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
    </div>
  );

  const t = board.totals;
  const collectionRate = t.expected > 0 ? Math.round((t.collected / t.expected) * 100) : 0;

  const filteredInvoices = invoices.filter((inv: any) => {
    if (invFilter !== "all" && inv.status !== invFilter) return false;
    if (search && !inv.tenant_name?.toLowerCase().includes(search.toLowerCase()) && !inv.unit_number?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-4">

      <motion.div variants={item} className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-sky-400 bg-clip-text text-transparent">
            Books of Accounts
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {bundle ? `${bundle.trial_balance.length} accounts · ${bundle.invoices.length} invoices · ${bundle.payments.length} payments · ${bundle.expenses.length} expenses` : "Loading..."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 bg-slate-900/60 border border-white/[0.06] rounded-lg px-3 py-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-500" />
            <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
              className="bg-transparent text-xs text-slate-300 outline-none" />
            <span className="text-slate-600 text-xs">→</span>
            <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
              className="bg-transparent text-xs text-slate-300 outline-none" />
          </div>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleExport}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 hover:bg-emerald-500/25 transition text-xs font-medium disabled:opacity-50"
          >
            {downloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            {downloading ? "Exporting..." : "Export Books (CSV)"}
          </motion.button>
        </div>
      </motion.div>

      <motion.div variants={item} className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard icon={<DollarSign className="w-4 h-4" />} label="Expected Revenue" value={`KES ${money(t.expected)}`} color="text-emerald-400" bg="bg-emerald-500/10" delay={0} />
        <SummaryCard icon={<CreditCard className="w-4 h-4" />} label="Collected" value={`KES ${money(t.collected)}`} color="text-green-400" bg="bg-green-500/10" delay={0.05} />
        <SummaryCard icon={<AlertTriangle className="w-4 h-4" />} label="Outstanding" value={`KES ${money(t.outstanding)}`} color="text-rose-400" bg="bg-rose-500/10" delay={0.1} />
        <SummaryCard icon={<TrendingUp className="w-4 h-4" />} label="Collection Rate" value={`${collectionRate}%`} color={collectionRate > 70 ? "text-emerald-400" : "text-amber-400"} bg="bg-sky-500/10" delay={0.15} />
      </motion.div>

      <motion.div variants={item} className="flex items-center gap-1 overflow-x-auto scrollbar-thin pb-1">
        {TABS.map((tb) => (
          <button key={tb.key} onClick={() => setTab(tb.key)}
            className={`relative flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition whitespace-nowrap ${
              tab === tb.key
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/25"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent"
            }`}>
            {tb.icon}
            {tb.label}
          </button>
        ))}
        <button onClick={() => handleExportTab(tab)}
          className="ml-auto flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-[10px] font-medium text-slate-400 hover:text-emerald-300 hover:bg-slate-800/50 transition whitespace-nowrap">
          <Download className="w-3 h-3" />
          Export this tab
        </button>
      </motion.div>

      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
            </div>
          ) : (
            <>
              {tab === "pnl" && bundle && <PLStatement data={bundle.profit_loss} />}
              {tab === "balance" && bundle && <BalanceSheet data={bundle.balance_sheet} />}
              {tab === "trial" && bundle && <TrialBalance data={bundle.trial_balance} />}
              {tab === "invoices" && (
                <InvoiceTable invoices={filteredInvoices} search={search} setSearch={setSearch}
                  filter={invFilter} setFilter={setInvFilter} />
              )}
              {tab === "payments" && <PaymentTable payments={payments} />}
              {tab === "expenses" && bundle && <ExpenseTable expenses={bundle.expenses} />}
            </>
          )}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

function SummaryCard({ icon, label, value, color, bg, delay }: { icon: React.ReactNode; label: string; value: string; color: string; bg: string; delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: "spring", stiffness: 200, damping: 22 }}
      whileHover={{ y: -2 }}
      className={`rounded-xl ${bg} border border-white/[0.06] p-3 backdrop-blur`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wider text-slate-400">{label}</span>
        <span className={color}>{icon}</span>
      </div>
      <div className={`text-lg font-bold ${color}`}>{value}</div>
    </motion.div>
  );
}

function PLStatement({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      <Card className="p-4" hover={false}>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-white">Profit & Loss Statement</h2>
          <span className="text-[10px] text-slate-500 ml-auto">{data.period?.from} → {data.period?.to}</span>
        </div>

        <SectionHeader title="Income" />
        <div className="space-y-1 mb-4">
          {data.income.length === 0 && <EmptyRow text="No income recorded" />}
          {data.income.map((a: any, i: number) => (
            <AccountRow key={i} code={a.code} name={a.name} balance={a.balance} positive />
          ))}
          <TotalRow label="Total Income" value={data.total_income} color="text-emerald-400" />
        </div>

        <SectionHeader title="Expenses" />
        <div className="space-y-1 mb-4">
          {data.expenses.length === 0 && <EmptyRow text="No expenses recorded" />}
          {data.expenses.map((a: any, i: number) => (
            <AccountRow key={i} code={a.code} name={a.name} balance={a.balance} positive />
          ))}
          <TotalRow label="Total Expenses" value={data.total_expenses} color="text-rose-400" />
        </div>

        <div className="border-t border-white/[0.06] pt-3 mt-3">
          <div className="flex items-center justify-between px-3 py-3 rounded-xl bg-gradient-to-r from-emerald-500/10 to-transparent">
            <div className="flex items-center gap-2">
              <Wallet className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-semibold text-white">Net Profit</span>
            </div>
            <span className={`text-xl font-bold ${data.net_profit >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              KES <AnimatedNumber value={money(Math.abs(data.net_profit))} />
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}

function BalanceSheet({ data }: { data: any }) {
  return (
    <div className="space-y-4">
      <Card className="p-4" hover={false}>
        <div className="flex items-center gap-2 mb-4">
          <Scale className="w-4 h-4 text-sky-400" />
          <h2 className="text-sm font-semibold text-white">Balance Sheet</h2>
          <span className="text-[10px] text-slate-500 ml-auto">As at {data.as_at}</span>
        </div>

        <SectionHeader title="Assets" />
        <div className="space-y-1 mb-4">
          {data.assets.length === 0 && <EmptyRow text="No assets recorded" />}
          {data.assets.map((a: any, i: number) => (
            <AccountRow key={i} code={a.code} name={a.name} balance={a.balance} positive />
          ))}
          <TotalRow label="Total Assets" value={data.total_assets} color="text-emerald-400" />
        </div>

        <SectionHeader title="Liabilities" />
        <div className="space-y-1 mb-4">
          {data.liabilities.length === 0 && <EmptyRow text="No liabilities recorded" />}
          {data.liabilities.map((a: any, i: number) => (
            <AccountRow key={i} code={a.code} name={a.name} balance={a.balance} positive />
          ))}
          <TotalRow label="Total Liabilities" value={data.total_liabilities} color="text-rose-400" />
        </div>

        <SectionHeader title="Equity" />
        <div className="space-y-1 mb-4">
          {data.equity.length === 0 && <EmptyRow text="No equity recorded" />}
          {data.equity.map((a: any, i: number) => (
            <AccountRow key={i} code={a.code} name={a.name} balance={a.balance} positive />
          ))}
          <TotalRow label="Total Equity" value={data.total_equity} color="text-sky-400" />
        </div>

        <div className="border-t border-white/[0.06] pt-3">
          <div className="flex items-center justify-between px-3 py-3 rounded-xl bg-gradient-to-r from-sky-500/10 to-transparent">
            <span className="text-sm font-semibold text-white">Net Assets (Assets - Liabilities)</span>
            <span className="text-xl font-bold text-sky-400">KES <AnimatedNumber value={money(data.net_assets)} /></span>
          </div>
        </div>
      </Card>
    </div>
  );
}

function TrialBalance({ data }: { data: any }) {
  const totalDebit = data.reduce((s: number, a: any) => s + a.debit, 0);
  const totalCredit = data.reduce((s: number, a: any) => s + a.credit, 0);
  return (
    <Card className="p-4" hover={false}>
      <div className="flex items-center gap-2 mb-4">
        <BookOpen className="w-4 h-4 text-violet-400" />
        <h2 className="text-sm font-semibold text-white">Trial Balance</h2>
        <span className="text-[10px] text-slate-500 ml-auto">{data.length} accounts</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Code</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Account</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Type</th>
              <th className="text-right py-2 px-2 text-slate-500 font-medium">Debit</th>
              <th className="text-right py-2 px-2 text-slate-500 font-medium">Credit</th>
              <th className="text-right py-2 px-2 text-slate-500 font-medium">Balance</th>
            </tr>
          </thead>
          <tbody>
            {data.map((a: any, i: number) => (
              <motion.tr key={i}
                initial={{ opacity: 0, x: -5 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.02 }}
                className="border-b border-white/[0.02] hover:bg-white/[0.02] transition"
              >
                <td className="py-2 px-2 font-mono text-slate-500">{a.code}</td>
                <td className="py-2 px-2 text-slate-200">{a.name}</td>
                <td className="py-2 px-2 text-slate-500 capitalize">{a.type.replace("_", " ")}</td>
                <td className="py-2 px-2 text-right text-slate-300 font-mono">{a.debit > 0 ? money(a.debit) : "—"}</td>
                <td className="py-2 px-2 text-right text-slate-300 font-mono">{a.credit > 0 ? money(a.credit) : "—"}</td>
                <td className={`py-2 px-2 text-right font-mono font-medium ${a.balance >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {money(Math.abs(a.balance))}
                </td>
              </motion.tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-emerald-500/20">
              <td colSpan={3} className="py-3 px-2 text-sm font-semibold text-white">TOTALS</td>
              <td className="py-3 px-2 text-right font-mono font-bold text-emerald-400">{money(totalDebit)}</td>
              <td className="py-3 px-2 text-right font-mono font-bold text-rose-400">{money(totalCredit)}</td>
              <td className="py-3 px-2 text-right text-slate-500">—</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Card>
  );
}

function InvoiceTable({ invoices, search, setSearch, filter, setFilter }: any) {
  return (
    <Card className="p-4" hover={false}>
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-semibold text-white">Invoices</h2>
          <span className="text-[10px] text-slate-500">{invoices.length} shown</span>
        </div>
        <div className="flex gap-1 ml-auto">
          {["all", "paid", "pending", "overdue"].map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-medium transition ${
                filter === f ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "text-slate-400 hover:bg-slate-800 border border-transparent"
              }`}>{f.charAt(0).toUpperCase() + f.slice(1)}</button>
          ))}
        </div>
      </div>
      <div className="relative mb-3">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input className="w-full bg-slate-800/50 border border-white/[0.06] rounded-lg pl-8 pr-3 py-2 text-xs outline-none focus:border-emerald-500/50 placeholder:text-slate-500"
          placeholder="Search by tenant or room..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <div className="overflow-x-auto max-h-[500px] overflow-y-auto scrollbar-thin">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-slate-900/95 backdrop-blur">
            <tr className="border-b border-white/[0.06]">
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Invoice #</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Tenant</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Unit</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Type</th>
              <th className="text-right py-2 px-2 text-slate-500 font-medium">Amount</th>
              <th className="text-right py-2 px-2 text-slate-500 font-medium">Paid</th>
              <th className="text-right py-2 px-2 text-slate-500 font-medium">Balance</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Status</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Due</th>
            </tr>
          </thead>
          <tbody>
            {invoices.length === 0 && (
              <tr><td colSpan={9} className="text-center py-8 text-slate-500">No invoices found</td></tr>
            )}
            {invoices.map((inv: any, i: number) => (
              <motion.tr key={inv.id}
                initial={{ opacity: 0, x: -5 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.01 }}
                className="border-b border-white/[0.02] hover:bg-white/[0.02] transition cursor-pointer"
              >
                <td className="py-2 px-2 font-mono text-slate-500">{inv.invoice_number || inv.id.slice(0, 8)}</td>
                <td className="py-2 px-2 text-slate-200 truncate max-w-[120px]">{inv.tenant_name}</td>
                <td className="py-2 px-2 text-slate-400 font-mono">{inv.unit_number}</td>
                <td className="py-2 px-2 text-slate-500 capitalize">{inv.invoice_type}</td>
                <td className="py-2 px-2 text-right text-slate-300 font-mono">{money(inv.amount)}</td>
                <td className="py-2 px-2 text-right text-emerald-400 font-mono">{money(inv.paid_amount || 0)}</td>
                <td className="py-2 px-2 text-right text-rose-400 font-mono">{money(inv.balance || 0)}</td>
                <td className="py-2 px-2">
                  <StatusBadge status={inv.status} />
                </td>
                <td className="py-2 px-2 text-slate-500">{inv.due_date?.slice(0, 10) || "—"}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function PaymentTable({ payments }: { payments: any[] }) {
  return (
    <Card className="p-4" hover={false}>
      <div className="flex items-center gap-2 mb-3">
        <CreditCard className="w-4 h-4 text-emerald-400" />
        <h2 className="text-sm font-semibold text-white">Payment History</h2>
        <span className="text-[10px] text-slate-500">{payments.length} transactions</span>
      </div>
      <div className="overflow-x-auto max-h-[500px] overflow-y-auto scrollbar-thin">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-slate-900/95 backdrop-blur">
            <tr className="border-b border-white/[0.06]">
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Date</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Tenant</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Unit</th>
              <th className="text-right py-2 px-2 text-slate-500 font-medium">Amount</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Method</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Reference</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {payments.length === 0 && (
              <tr><td colSpan={7} className="text-center py-8 text-slate-500">No payments recorded</td></tr>
            )}
            {payments.map((p: any, i: number) => (
              <motion.tr key={p.id || i}
                initial={{ opacity: 0, x: -5 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.01 }}
                className="border-b border-white/[0.02] hover:bg-white/[0.02] transition"
              >
                <td className="py-2 px-2 text-slate-500">{p.paid_at?.slice(0, 10) || "—"}</td>
                <td className="py-2 px-2 text-slate-200 truncate max-w-[120px]">{p.tenant_name || "—"}</td>
                <td className="py-2 px-2 text-slate-400 font-mono">{p.unit_number || "—"}</td>
                <td className="py-2 px-2 text-right text-emerald-400 font-mono">{money(p.amount)}</td>
                <td className="py-2 px-2 text-slate-300 capitalize">{p.method || "—"}</td>
                <td className="py-2 px-2 text-slate-500 font-mono text-[10px]">{p.reference || "—"}</td>
                <td className="py-2 px-2">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    p.status === "completed" ? "bg-emerald-500/15 text-emerald-300" :
                    p.status === "pending" ? "bg-amber-500/15 text-amber-300" :
                    "bg-slate-500/15 text-slate-400"
                  }`}>{p.status}</span>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ExpenseTable({ expenses }: { expenses: any[] }) {
  const total = expenses.reduce((s: number, e: any) => s + e.amount, 0);
  return (
    <Card className="p-4" hover={false}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Receipt className="w-4 h-4 text-rose-400" />
          <h2 className="text-sm font-semibold text-white">Expenses</h2>
          <span className="text-[10px] text-slate-500">{expenses.length} entries</span>
        </div>
        <div className="text-right">
          <span className="text-[10px] text-slate-500 uppercase tracking-wider">Total</span>
          <div className="text-lg font-bold text-rose-400">KES <AnimatedNumber value={money(total)} /></div>
        </div>
      </div>
      <div className="overflow-x-auto max-h-[500px] overflow-y-auto scrollbar-thin">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-slate-900/95 backdrop-blur">
            <tr className="border-b border-white/[0.06]">
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Date</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Category</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Description</th>
              <th className="text-left py-2 px-2 text-slate-500 font-medium">Vendor</th>
              <th className="text-right py-2 px-2 text-slate-500 font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {expenses.length === 0 && (
              <tr><td colSpan={5} className="text-center py-8 text-slate-500">No expenses recorded</td></tr>
            )}
            {expenses.map((e: any, i: number) => (
              <motion.tr key={i}
                initial={{ opacity: 0, x: -5 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.01 }}
                className="border-b border-white/[0.02] hover:bg-white/[0.02] transition"
              >
                <td className="py-2 px-2 text-slate-500">{e.date}</td>
                <td className="py-2 px-2"><span className="text-[10px] px-1.5 py-0.5 rounded-full bg-rose-500/10 text-rose-300 capitalize">{e.category}</span></td>
                <td className="py-2 px-2 text-slate-300 truncate max-w-[200px]">{e.description || "—"}</td>
                <td className="py-2 px-2 text-slate-400">{e.vendor || "—"}</td>
                <td className="py-2 px-2 text-right text-rose-400 font-mono">{money(e.amount)}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-2 mb-2 mt-2">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">{title}</h3>
      <div className="flex-1 h-px bg-white/[0.04]" />
    </div>
  );
}

function AccountRow({ code, name, balance, positive }: { code: string; name: string; balance: number; positive?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -5 }}
      animate={{ opacity: 1, x: 0 }}
      whileHover={{ x: 2 }}
      className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/[0.02] transition"
    >
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] text-slate-600 w-10">{code}</span>
        <span className="text-xs text-slate-200">{name}</span>
      </div>
      <span className={`text-xs font-mono font-medium ${balance >= 0 ? "text-slate-300" : "text-rose-400"}`}>
        KES {money(Math.abs(balance))}
      </span>
    </motion.div>
  );
}

function TotalRow({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center justify-between px-3 py-2.5 mt-1 rounded-lg bg-white/[0.03] border border-white/[0.04]">
      <span className="text-xs font-semibold text-white">{label}</span>
      <span className={`text-sm font-bold font-mono ${color}`}>KES {money(value)}</span>
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return <div className="text-center py-3 text-xs text-slate-600">{text}</div>;
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    paid: "bg-emerald-500/15 text-emerald-300",
    pending: "bg-amber-500/15 text-amber-300",
    overdue: "bg-rose-500/15 text-rose-300",
    partial: "bg-sky-500/15 text-sky-300",
  };
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium uppercase ${map[status] || "bg-slate-500/15 text-slate-400"}`}>{status}</span>;
}
