import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  Bot,
  Building2,
  Calculator,
  CheckCircle2,
  FileCheck2,
  LogOut,
  Printer,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserCheck,
  UserX,
  Users
} from 'lucide-react';
import SignInPage from './components/SignInPage';

const STORAGE_KEY = 'hr_payroll_recon_agent05_user';
const THEME_STORAGE_KEY = 'hr_payroll_recon_theme';

const APPEARANCE_THEMES = [
  { id: 'daylight', label: 'Daylight', title: 'Studio Daylight', swatch: '#F5F5F7' },
  { id: 'sand', label: 'Sand', title: 'Warm Sand (Default)', swatch: '#F7F5F0' },
  { id: 'dusk', label: 'Dusk', title: 'Quiet Dusk', swatch: '#1C1E26' },
  { id: 'midnight', label: 'Midnight', title: 'Midnight OLED', swatch: '#0B0C10' }
];

function formatKES(val) {
  const num = Number(val || 0);
  return `KES ${num.toLocaleString('en-KE', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;
}

export default function App() {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [theme, setTheme] = useState(() => {
    try {
      const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
      if (savedTheme && ['daylight', 'sand', 'dusk', 'midnight'].includes(savedTheme)) {
        return savedTheme;
      }
    } catch {
      // ignore storage errors
    }
    return 'sand';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.classList.toggle('dark', theme === 'dusk' || theme === 'midnight');
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // ignore storage errors
    }
  }, [theme]);

  const [activeTab, setActiveTab] = useState('bridge'); // 'bridge' | 'audit' | 'agent' | 'certificate'
  const [employees, setEmployees] = useState([]);
  const [kpis, setKpis] = useState(null);
  const [selectedId, setSelectedId] = useState('EMP-KE-102');
  const [filterMode, setFilterMode] = useState('ALL'); // 'ALL' | 'EXCEPTIONS' | 'BANK' | 'SALARY_GHOST' | 'STATUTORY' | 'VERIFIED'
  const [loading, setLoading] = useState(false);
  const [bannerMessage, setBannerMessage] = useState('');

  // Editable parameters for live what-if payroll adjustment & verification
  const [simBasicPay, setSimBasicPay] = useState(0);
  const [simHouseAllowance, setSimHouseAllowance] = useState(0);
  const [simTransportAllowance, setSimTransportAllowance] = useState(0);
  const [simBonusOvertime, setSimBonusOvertime] = useState(0);
  const [simApplyStatutory, setSimApplyStatutory] = useState(true);
  const [simRevertBank, setSimRevertBank] = useState(false);
  const [simRemoveExited, setSimRemoveExited] = useState(false);
  const [simVerifyTaxPin, setSimVerifyTaxPin] = useState(false);
  const [simAuthorizeSalary, setSimAuthorizeSalary] = useState(false);

  // Ask Payroll Agent Q&A state
  const [question, setQuestion] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [askingAgent, setAskingAgent] = useState(false);

  const selectedEmployee =
    employees.find((e) => e.employee_id === selectedId) || employees[0] || null;

  const fetchPayroll = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/payroll');
      const data = await res.json();
      setEmployees(data.employees || []);
      setKpis(data.kpis || null);
    } catch (err) {
      console.error('Failed to load payroll records:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchPayroll();
    }
  }, [user]);

  useEffect(() => {
    if (selectedEmployee) {
      setSimBasicPay(selectedEmployee.current_basic_pay);
      setSimHouseAllowance(selectedEmployee.current_house_allowance);
      setSimTransportAllowance(selectedEmployee.current_transport_allowance);
      setSimBonusOvertime(selectedEmployee.current_bonus_overtime);
      setSimApplyStatutory(true);
      setSimRevertBank(false);
      setSimRemoveExited(false);
      setSimVerifyTaxPin(false);
      setSimAuthorizeSalary(false);
    }
  }, [selectedEmployee?.employee_id]);

  const handleSignInSuccess = (authenticatedUser) => {
    setUser(authenticatedUser);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(authenticatedUser));
    } catch {
      // ignore storage errors
    }
  };

  const handleSignOut = () => {
    setUser(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  };

  const handleSimulatePayroll = async (e) => {
    e.preventDefault();
    if (!selectedEmployee) return;
    setLoading(true);
    setBannerMessage('');
    try {
      const res = await fetch('/api/payroll/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          employee_id: selectedEmployee.employee_id,
          current_basic_pay: Number(simBasicPay),
          current_house_allowance: Number(simHouseAllowance),
          current_transport_allowance: Number(simTransportAllowance),
          current_bonus_overtime: Number(simBonusOvertime),
          apply_statutory_rates: simApplyStatutory,
          revert_bank_to_verified: simRevertBank,
          remove_exited_employee: simRemoveExited,
          verify_tax_pin: simVerifyTaxPin,
          authorize_salary_change: simAuthorizeSalary
        })
      });
      const data = await res.json();
      if (res.ok) {
        setEmployees((prev) =>
          prev.map((item) =>
            item.employee_id === data.employee.employee_id ? data.employee : item
          )
        );
        setKpis(data.kpis);
        setBannerMessage(data.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleApproveEmployee = async (empId, resolveExceptions = false) => {
    setLoading(true);
    setBannerMessage('');
    try {
      const res = await fetch(`/api/payroll/${empId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved_by: user?.name || 'Head of Payroll',
          resolve_exceptions: resolveExceptions
        })
      });
      const data = await res.json();
      if (res.ok) {
        setEmployees((prev) =>
          prev.map((item) =>
            item.employee_id === data.employee.employee_id ? data.employee : item
          )
        );
        setKpis(data.kpis);
        setBannerMessage(data.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAllVerified = async () => {
    setLoading(true);
    setBannerMessage('');
    try {
      const res = await fetch('/api/payroll/approve-all-verified', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved_by: user?.name || 'Head of Payroll',
          resolve_exceptions: false
        })
      });
      const data = await res.json();
      if (res.ok) {
        setEmployees(data.employees || []);
        setKpis(data.kpis);
        setBannerMessage(data.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResetDemo = async () => {
    setLoading(true);
    setBannerMessage('');
    try {
      const res = await fetch('/api/payroll/reset', {
        method: 'POST'
      });
      const data = await res.json();
      if (res.ok) {
        setEmployees(data.employees || []);
        setKpis(data.kpis);
        setBannerMessage(data.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAskPayrollAgent = async (customPrompt) => {
    const q = (customPrompt ?? question).trim();
    if (!q || !selectedEmployee) return;
    setAskingAgent(true);
    setQuestion('');
    setChatHistory((prev) => [
      ...prev,
      {
        role: 'user',
        text: q,
        employee_id: selectedEmployee.employee_id
      }
    ]);
    try {
      const res = await fetch('/api/agent/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          employee_id: selectedEmployee.employee_id
        })
      });
      const data = await res.json();
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.answer || 'No response received.',
          model: data.model || 'Payroll Reconciliation Agent'
        }
      ]);
    } catch (err) {
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Unable to reach Payroll Reconciliation Agent: ${err.message}`,
          model: 'Payroll Reconciliation Agent'
        }
      ]);
    } finally {
      setAskingAgent(false);
    }
  };

  const filteredEmployees = employees.filter((emp) => {
    if (filterMode === 'EXCEPTIONS') return emp.has_exceptions;
    if (filterMode === 'BANK') return emp.bank_account_changed;
    if (filterMode === 'SALARY_GHOST')
      return (
        emp.exception_codes?.includes('UNEXPLAINED_PAY_JUMP') ||
        emp.exception_codes?.includes('GHOST_WORKER')
      );
    if (filterMode === 'STATUTORY')
      return emp.exception_codes?.includes('STATUTORY_VARIANCE');
    if (filterMode === 'VERIFIED') return !emp.has_exceptions;
    return true;
  });

  if (!user) {
    return <SignInPage onSuccess={handleSignInSuccess} theme={theme} onThemeChange={setTheme} />;
  }

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)] flex flex-col">
      {/* Top Frosted-Glass Apple Navigation Bar (Hidden when printing Sign-Off Sheet) */}
      <header className="print:hidden sticky top-0 z-30 apple-glass">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#0071E3] flex items-center justify-center text-white shadow-sm">
              <Calculator className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200">
                  HR Agent #05 • Payroll &amp; Statutory Reconciliation
                </span>
                <span className="text-xs text-gray-500 hidden md:inline">
                  October 2026 Draft Payroll vs. September 2026 &amp; HR Master
                </span>
              </div>
              <h1 className="text-base sm:text-lg font-bold text-[#1D1D1F] tracking-tight">
                Payroll Variance, Statutory Compliance &amp; Payslip Recon Agent
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Compact 4-Dot Apple Appearance Switcher */}
            <div
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-[var(--bg-card)] border border-[var(--border-subtle)] shadow-2xs"
              role="group"
              aria-label="Reading Appearance Theme"
            >
              {APPEARANCE_THEMES.map((t) => {
                const isActive = theme === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTheme(t.id)}
                    title={`${t.label} — ${t.title}`}
                    aria-label={`${t.label} appearance`}
                    className={`w-5 h-5 rounded-full transition-all flex items-center justify-center cursor-pointer ${
                      isActive
                        ? 'ring-2 ring-[#0071E3] ring-offset-1 scale-110'
                        : 'opacity-80 hover:opacity-100 hover:scale-105'
                    }`}
                    style={{
                      backgroundColor: t.swatch,
                      border: '1px solid rgba(128,128,128,0.35)'
                    }}
                  />
                );
              })}
            </div>

            <div className="text-right hidden sm:block">
              <div className="text-xs font-semibold text-[#1D1D1F]">{user.name}</div>
              <div className="text-[11px] text-gray-500">{user.email}</div>
            </div>
            <button
              onClick={handleResetDemo}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-xs font-medium text-gray-700 cursor-pointer"
              title="Reset demo payroll records"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Reset Demo</span>
            </button>
            <button
              onClick={handleSignOut}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-xs font-medium text-gray-700 cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>

        {/* 4-Tab Bar */}
        <div className="max-w-7xl mx-auto px-6 flex items-center gap-2 overflow-x-auto pb-2.5">
          {[
            {
              id: 'bridge',
              label: '1. Monthly Payroll Bridge & Exception Queue',
              icon: Banknote
            },
            {
              id: 'audit',
              label: '2. Employee Payslip Audit & Statutory Calculator',
              icon: Calculator
            },
            {
              id: 'agent',
              label: '3. Ask Payroll Agent',
              icon: Bot
            },
            {
              id: 'certificate',
              label: '4. 1-Page CFO / CHRO Payroll Sign-Off Certificate',
              icon: FileCheck2
            }
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition cursor-pointer ${
                  active
                    ? 'bg-[#0071E3] text-white shadow-sm'
                    : 'bg-gray-100/90 text-gray-700 hover:bg-gray-200/70'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Container */}
      <main className="max-w-7xl mx-auto w-full px-6 py-6 flex-1 space-y-6">
        {/* Top Executive KPI Strip (Hidden on print) */}
        {kpis && (
          <section className="print:hidden grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="bg-white rounded-2xl p-4 border border-gray-200/90 shadow-xs">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Oct 2026 Draft Gross Payroll
              </div>
              <div className="text-lg font-bold text-[#1D1D1F] mt-1">
                {formatKES(kpis.current_total_gross)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Sep 2026: {formatKES(kpis.prior_total_gross)} ({kpis.gross_variance >= 0 ? '+' : ''}
                {formatKES(kpis.gross_variance)})
              </div>
            </div>

            <div className="bg-white rounded-2xl p-4 border border-gray-200/90 shadow-xs">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Statutory Taxes &amp; Levies
              </div>
              <div className="text-lg font-bold text-[#0071E3] mt-1">
                {formatKES(kpis.total_statutory)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                PAYE: {formatKES(kpis.total_paye)} • SHIF+AHL+NSSF
              </div>
            </div>

            <div className="bg-white rounded-2xl p-4 border border-gray-200/90 shadow-xs">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Net Salaries to Disburse
              </div>
              <div className="text-lg font-bold text-[#34C759] mt-1">
                {formatKES(kpis.current_total_net)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {kpis.active_paid_headcount} active paid staff • {kpis.new_hires_count} new hire
              </div>
            </div>

            <div className="bg-white rounded-2xl p-4 border border-gray-200/90 shadow-xs">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Exceptions Caught Before Payout
              </div>
              <div
                className={`text-lg font-bold mt-1 ${
                  kpis.flagged_count > 0 ? 'text-[#FF3B30]' : 'text-[#34C759]'
                }`}
              >
                {kpis.flagged_count} Flagged Records
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {kpis.ghost_worker_count} Exited • {kpis.bank_swap_count} Bank Swap •{' '}
                {kpis.pay_jump_count} Pay Jump
              </div>
            </div>

            <div className="bg-white rounded-2xl p-4 border border-gray-200/90 shadow-xs">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Payroll Funds Protected
              </div>
              <div className="text-lg font-bold text-[#FF9500] mt-1">
                {formatKES(kpis.total_amount_protected)}
              </div>
              <div className="text-xs text-emerald-700 font-medium mt-1">
                {kpis.approved_count} of {kpis.total_records} records approved
              </div>
            </div>
          </section>
        )}

        {bannerMessage && (
          <div className="print:hidden rounded-2xl bg-emerald-50 border border-[#34C759]/40 px-4 py-3 flex items-center justify-between text-xs text-emerald-950 font-medium">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#34C759] shrink-0" />
              <span>{bannerMessage}</span>
            </div>
            <button
              onClick={() => setBannerMessage('')}
              className="text-emerald-800 hover:underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* TAB 1: Monthly Payroll Bridge & Exception Queue */}
        {activeTab === 'bridge' && (
          <div className="space-y-5">
            <div className="bg-white rounded-3xl p-6 border border-gray-200/90 shadow-xs space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-base font-bold text-[#1D1D1F]">
                    October 2026 Monthly Payroll Reconciliation &amp; Exception Queue
                  </h2>
                  <p className="text-xs text-gray-500">
                    Compare September 2026 vs. October 2026 draft salaries, inspect flagged bank
                    account changes or exited staff, and approve verified employee payslips.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={handleApproveAllVerified}
                    disabled={loading}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#34C759] hover:bg-emerald-600 text-xs font-semibold text-white cursor-pointer"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Approve All Verified Records</span>
                  </button>
                  <button
                    onClick={fetchPayroll}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-xs font-semibold text-gray-700 cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    <span>Refresh</span>
                  </button>
                </div>
              </div>

              {/* Filter Pills */}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {[
                  { id: 'ALL', label: `All Employees (${employees.length})` },
                  {
                    id: 'EXCEPTIONS',
                    label: `Needs Review / Exceptions (${employees.filter((e) => e.has_exceptions).length})`
                  },
                  {
                    id: 'SALARY_GHOST',
                    label: `Salary Jumps & Exited Staff (${
                      employees.filter(
                        (e) =>
                          e.exception_codes?.includes('UNEXPLAINED_PAY_JUMP') ||
                          e.exception_codes?.includes('GHOST_WORKER')
                      ).length
                    })`
                  },
                  {
                    id: 'BANK',
                    label: `Bank Account Changes (${employees.filter((e) => e.bank_account_changed).length})`
                  },
                  {
                    id: 'STATUTORY',
                    label: `Statutory Tax Alerts (${
                      employees.filter((e) => e.exception_codes?.includes('STATUTORY_VARIANCE'))
                        .length
                    })`
                  },
                  {
                    id: 'VERIFIED',
                    label: `Verified & Ready (${employees.filter((e) => !e.has_exceptions).length})`
                  }
                ].map((pill) => (
                  <button
                    key={pill.id}
                    onClick={() => setFilterMode(pill.id)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                      filterMode === pill.id
                        ? 'bg-[#1D1D1F] text-white'
                        : 'bg-[#F5F5F7] text-gray-700 hover:bg-gray-200/80'
                    }`}
                  >
                    {pill.label}
                  </button>
                ))}
              </div>

              {/* Employee Reconciliation Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-gray-200 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                      <th className="py-3 px-3">Employee &amp; Role</th>
                      <th className="py-3 px-3">HR Status &amp; Bank</th>
                      <th className="py-3 px-3 text-right">Sep 2026 Gross</th>
                      <th className="py-3 px-3 text-right">Oct 2026 Draft Gross</th>
                      <th className="py-3 px-3 text-right">PAYE + NSSF + SHIF + AHL</th>
                      <th className="py-3 px-3 text-right">Oct 2026 Net Pay</th>
                      <th className="py-3 px-3">Audit Finding</th>
                      <th className="py-3 px-3">Sign-Off Status</th>
                      <th className="py-3 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-xs">
                    {filteredEmployees.map((emp) => {
                      const isSelected = emp.employee_id === selectedId;
                      return (
                        <tr
                          key={emp.employee_id}
                          onClick={() => setSelectedId(emp.employee_id)}
                          className={`transition cursor-pointer ${
                            isSelected ? 'bg-blue-50/60' : 'hover:bg-gray-50'
                          }`}
                        >
                          <td className="py-3.5 px-3">
                            <div className="font-semibold text-[#1D1D1F]">
                              {emp.full_name}{' '}
                              <span className="font-mono text-[11px] text-gray-500">
                                ({emp.employee_id})
                              </span>
                            </div>
                            <div className="text-[11px] text-gray-500">
                              {emp.job_title} • {emp.department}
                            </div>
                          </td>

                          <td className="py-3.5 px-3">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                                  emp.employment_status === 'Exited'
                                    ? 'bg-red-100 text-[#FF3B30]'
                                    : emp.employment_status === 'New Hire'
                                    ? 'bg-blue-100 text-[#0071E3]'
                                    : 'bg-gray-100 text-gray-700'
                                }`}
                              >
                                {emp.employment_status}
                              </span>
                              {emp.bank_account_changed && (
                                <span
                                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                                    emp.bank_change_authorized
                                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                      : 'bg-red-50 text-[#FF3B30] border border-red-200'
                                  }`}
                                >
                                  {emp.bank_change_authorized
                                    ? 'Bank Change Verified'
                                    : 'Unverified Bank Swap'}
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-gray-500 mt-0.5">
                              {emp.current_bank_name} • {emp.current_bank_account}
                            </div>
                          </td>

                          <td className="py-3.5 px-3 text-right font-mono text-gray-600">
                            {formatKES(emp.prior_gross_pay)}
                          </td>

                          <td className="py-3.5 px-3 text-right font-mono font-bold text-[#1D1D1F]">
                            <div>{formatKES(emp.current_gross_pay)}</div>
                            {emp.gross_variance !== 0 && (
                              <div
                                className={`text-[10px] font-semibold ${
                                  emp.has_exceptions ? 'text-[#FF3B30]' : 'text-[#0071E3]'
                                }`}
                              >
                                {emp.gross_variance > 0 ? '+' : ''}
                                {formatKES(emp.gross_variance)}
                              </div>
                            )}
                          </td>

                          <td className="py-3.5 px-3 text-right font-mono text-gray-700">
                            <div>-{formatKES(emp.draft_total_statutory)}</div>
                            {Math.abs(emp.statutory_discrepancy) > 1 && (
                              <div className="text-[10px] text-[#FF9500] font-semibold">
                                Shortfall: {formatKES(emp.statutory_discrepancy)}
                              </div>
                            )}
                          </td>

                          <td className="py-3.5 px-3 text-right font-mono font-bold text-[#0071E3]">
                            {formatKES(emp.draft_net_pay)}
                          </td>

                          <td className="py-3.5 px-3 max-w-xs">
                            {emp.risk_level === 'CRITICAL' ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-red-50 text-[#FF3B30] border border-red-200 font-semibold text-[11px]">
                                <ShieldAlert className="w-3 h-3 shrink-0" />
                                {emp.exceptions[0]?.title || 'Critical Exception'}
                              </span>
                            ) : emp.risk_level === 'WARNING' ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-50 text-[#FF9500] border border-amber-200 font-semibold text-[11px]">
                                <AlertTriangle className="w-3 h-3 shrink-0" />
                                {emp.exceptions[0]?.title || 'Statutory Alert'}
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-[#34C759] border border-emerald-200 font-semibold text-[11px]">
                                <CheckCircle2 className="w-3 h-3 shrink-0" />
                                Verified &amp; Matched
                              </span>
                            )}
                            <div className="text-[11px] text-gray-500 mt-1 line-clamp-1">
                              {emp.hr_reference_note}
                            </div>
                          </td>

                          <td className="py-3.5 px-3">
                            {emp.approval_status === 'APPROVED' ? (
                              <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold text-[11px]">
                                APPROVED
                              </span>
                            ) : emp.has_exceptions ? (
                              <span className="px-2.5 py-0.5 rounded-full bg-red-100 text-[#FF3B30] font-semibold text-[11px]">
                                HOLD • FLAGGED
                              </span>
                            ) : (
                              <span className="px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] font-semibold text-[11px]">
                                READY TO APPROVE
                              </span>
                            )}
                          </td>

                          <td className="py-3.5 px-3 text-right">
                            <div className="inline-flex items-center gap-1.5">
                              {emp.has_exceptions && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleApproveEmployee(emp.employee_id, true);
                                  }}
                                  className="px-2.5 py-1.5 rounded-lg bg-[#34C759] text-white font-semibold hover:bg-emerald-600 cursor-pointer"
                                  title="Apply HR Master verified fix and approve"
                                >
                                  Resolve &amp; Approve
                                </button>
                              )}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedId(emp.employee_id);
                                  setActiveTab('audit');
                                }}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#0071E3] text-white font-semibold hover:bg-[#0077ED] cursor-pointer"
                              >
                                <span>Inspect Payslip</span>
                                <ArrowRight className="w-3 h-3" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: Employee Payslip Audit & Statutory Calculator */}
        {activeTab === 'audit' && selectedEmployee && (
          <div className="space-y-6">
            {/* Employee Selector Bar */}
            <div className="bg-white rounded-2xl p-4 border border-gray-200/90 flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-gray-500">Select Employee:</span>
                {employees.map((e) => (
                  <button
                    key={e.employee_id}
                    onClick={() => setSelectedId(e.employee_id)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
                      e.employee_id === selectedEmployee.employee_id
                        ? 'bg-[#0071E3] text-white'
                        : e.has_exceptions
                        ? 'bg-red-50 text-[#FF3B30] border border-red-200 hover:bg-red-100'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    <span>{e.full_name.split(' ')[0]}</span>
                    {e.has_exceptions && <span className="w-2 h-2 rounded-full bg-[#FF3B30]" />}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab('certificate')}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-gray-300 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-700 cursor-pointer"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>View Sign-Off Certificate</span>
                </button>
                <button
                  onClick={() =>
                    handleApproveEmployee(
                      selectedEmployee.employee_id,
                      selectedEmployee.has_exceptions
                    )
                  }
                  disabled={loading || selectedEmployee.approval_status === 'APPROVED'}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#34C759] hover:bg-emerald-600 disabled:opacity-50 text-white text-xs font-semibold shadow-xs cursor-pointer"
                >
                  <UserCheck className="w-3.5 h-3.5" />
                  <span>
                    {selectedEmployee.approval_status === 'APPROVED'
                      ? `Approved (${selectedEmployee.approved_by})`
                      : selectedEmployee.has_exceptions
                      ? 'Resolve Exception & Approve Payslip'
                      : 'Approve Employee Payslip'}
                  </span>
                </button>
              </div>
            </div>

            {/* Exception Banner or Verified Banner */}
            {selectedEmployee.has_exceptions ? (
              <div className="rounded-3xl bg-red-50 border border-red-200 p-6 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#FF3B30]">
                    <ShieldAlert className="w-4 h-4" />
                    Pre-Disbursement Exception Alert • {selectedEmployee.full_name} (
                    {selectedEmployee.employee_id})
                  </span>
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-[#FF3B30] text-white">
                    HOLD FOR HR &amp; PAYROLL REVIEW
                  </span>
                </div>
                <div className="space-y-2">
                  {selectedEmployee.exceptions.map((ex, idx) => (
                    <div
                      key={idx}
                      className="bg-white/90 rounded-2xl p-3.5 border border-red-200 text-xs"
                    >
                      <div className="font-bold text-[#1D1D1F]">{ex.title}</div>
                      <div className="text-gray-700 mt-0.5">{ex.detail}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="rounded-3xl bg-[#1D1D1F] text-white p-6 flex flex-wrap items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="text-xs font-semibold uppercase tracking-wider text-[#34C759]">
                    100% Reconciled &amp; Statutory Compliant • {selectedEmployee.employee_id}
                  </div>
                  <div className="text-base font-bold">
                    {selectedEmployee.full_name} — {selectedEmployee.job_title} (
                    {selectedEmployee.department})
                  </div>
                  <div className="text-xs text-gray-300">{selectedEmployee.hr_reference_note}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-400">Verified Net Take-Home Pay</div>
                  <div className="text-xl font-bold text-[#34C759]">
                    {formatKES(selectedEmployee.draft_net_pay)}
                  </div>
                </div>
              </div>
            )}

            {/* 2-Column Split: Payslip Comparison & Statutory Breakdown + Interactive What-If Calculator */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left 7/12: Month-over-Month & Statutory Breakdown */}
              <div className="lg:col-span-7 bg-white rounded-3xl p-6 border border-gray-200/90 space-y-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-[#1D1D1F]">
                      Side-by-Side Payslip &amp; Statutory Tax Audit
                    </h3>
                    <p className="text-xs text-gray-500">
                      Compares September 2026 Prior Payslip, October 2026 Draft Payslip, and
                      Official Statutory Formula.
                    </p>
                  </div>
                  <span className="text-xs font-mono font-semibold text-[#0071E3]">
                    KRA PIN: {selectedEmployee.kra_pin}
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-gray-200 text-[11px] uppercase text-gray-400">
                        <th className="py-2.5 px-2">Payslip Component</th>
                        <th className="py-2.5 px-2 text-right">Sep 2026 (Prior)</th>
                        <th className="py-2.5 px-2 text-right">Oct 2026 (Draft)</th>
                        <th className="py-2.5 px-2 text-right">Agent Verified Math</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      <tr>
                        <td className="py-2.5 px-2 font-medium text-gray-800">Basic Pay</td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          {formatKES(selectedEmployee.prior_basic_pay)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono font-semibold text-[#1D1D1F]">
                          {formatKES(selectedEmployee.current_basic_pay)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-emerald-700 font-semibold">
                          {formatKES(selectedEmployee.hr_approved_basic_pay)} (HR Master)
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2.5 px-2 font-medium text-gray-800">House Allowance</td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          {formatKES(selectedEmployee.prior_house_allowance)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-[#1D1D1F]">
                          {formatKES(selectedEmployee.current_house_allowance)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          {formatKES(selectedEmployee.current_house_allowance)}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2.5 px-2 font-medium text-gray-800">
                          Transport Allowance
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          {formatKES(selectedEmployee.prior_transport_allowance)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-[#1D1D1F]">
                          {formatKES(selectedEmployee.current_transport_allowance)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          {formatKES(selectedEmployee.current_transport_allowance)}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2.5 px-2 font-medium text-gray-800">
                          Bonus / Overtime Pay
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          {formatKES(selectedEmployee.prior_bonus_overtime)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-[#1D1D1F]">
                          {formatKES(selectedEmployee.current_bonus_overtime)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          {formatKES(selectedEmployee.current_bonus_overtime)}
                        </td>
                      </tr>
                      <tr className="bg-gray-50 font-bold">
                        <td className="py-2.5 px-2 text-[#1D1D1F]">Gross Monthly Pay</td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-700">
                          {formatKES(selectedEmployee.prior_gross_pay)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-[#1D1D1F]">
                          {formatKES(selectedEmployee.current_gross_pay)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-[#0071E3]">
                          {formatKES(selectedEmployee.current_gross_pay)}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2.5 px-2 text-gray-700">
                          NSSF Pension (Tier I &amp; II • 6% capped at 4,320)
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          -{formatKES(selectedEmployee.prior_nssf)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-800">
                          -{formatKES(selectedEmployee.draft_nssf)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-emerald-700 font-semibold">
                          -{formatKES(selectedEmployee.expected_nssf)}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2.5 px-2 text-gray-700">
                          SHIF Health Fund (2.75% of Gross Pay)
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          -{formatKES(selectedEmployee.prior_shif)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-800">
                          -{formatKES(selectedEmployee.draft_shif)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-emerald-700 font-semibold">
                          -{formatKES(selectedEmployee.expected_shif)}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2.5 px-2 text-gray-700">
                          Affordable Housing Levy (1.5% of Gross Pay)
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          -{formatKES(selectedEmployee.prior_housing_levy)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-800">
                          -{formatKES(selectedEmployee.draft_housing_levy)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-emerald-700 font-semibold">
                          -{formatKES(selectedEmployee.expected_housing_levy)}
                        </td>
                      </tr>
                      <tr>
                        <td className="py-2.5 px-2 text-gray-700">
                          KRA PAYE Tax (after KES 2,400 Personal Relief)
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-600">
                          -{formatKES(selectedEmployee.prior_paye)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-gray-800">
                          -{formatKES(selectedEmployee.draft_paye)}
                        </td>
                        <td className="py-2.5 px-2 text-right font-mono text-emerald-700 font-semibold">
                          -{formatKES(selectedEmployee.expected_paye)}
                        </td>
                      </tr>
                      <tr className="bg-blue-50/50 font-bold text-sm">
                        <td className="py-3 px-2 text-[#1D1D1F]">Net Take-Home Salary</td>
                        <td className="py-3 px-2 text-right font-mono text-gray-700">
                          {formatKES(selectedEmployee.prior_net_pay)}
                        </td>
                        <td className="py-3 px-2 text-right font-mono text-[#0071E3]">
                          {formatKES(selectedEmployee.draft_net_pay)}
                        </td>
                        <td className="py-3 px-2 text-right font-mono text-[#34C759]">
                          {formatKES(selectedEmployee.expected_net_pay)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Bank Account & Employment Status Verification Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                  <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/80 space-y-1">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                      Bank Account Disbursement Check
                    </div>
                    <div className="text-xs font-bold text-[#1D1D1F]">
                      Draft: {selectedEmployee.current_bank_name} •{' '}
                      {selectedEmployee.current_bank_account}
                    </div>
                    <div className="text-xs text-gray-500">
                      HR Master Verified: {selectedEmployee.hr_verified_bank_name} •{' '}
                      {selectedEmployee.hr_verified_bank_account}
                    </div>
                  </div>

                  <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/80 space-y-1">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                      HR Master Employment &amp; Statutory IDs
                    </div>
                    <div className="text-xs font-bold text-[#1D1D1F]">
                      Status: {selectedEmployee.employment_status}{' '}
                      {selectedEmployee.exit_date ? `(Exited ${selectedEmployee.exit_date})` : ''}
                    </div>
                    <div className="text-xs text-gray-500">
                      NSSF: {selectedEmployee.nssf_no} • SHIF: {selectedEmployee.shif_no}
                    </div>
                  </div>
                </div>
              </div>

              {/* Right 5/12: Interactive What-If Payroll Adjustment & Statutory Verifier */}
              <div className="lg:col-span-5 bg-white rounded-3xl p-6 border border-gray-200/90 space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-[#1D1D1F]">
                    Interactive Payroll Adjustment &amp; Verification
                  </h3>
                  <p className="text-xs text-gray-500">
                    Adjust salary or allowance amounts or apply HR Master controls to recalculate
                    statutory PAYE, NSSF, SHIF, and Housing Levy automatically.
                  </p>
                </div>

                <form onSubmit={handleSimulatePayroll} className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-1">
                        Basic Pay (KES)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={simBasicPay}
                        onChange={(e) => setSimBasicPay(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl border border-gray-300 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-1">
                        House Allowance (KES)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={simHouseAllowance}
                        onChange={(e) => setSimHouseAllowance(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl border border-gray-300 text-xs font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-1">
                        Transport Allowance (KES)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={simTransportAllowance}
                        onChange={(e) => setSimTransportAllowance(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl border border-gray-300 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-1">
                        Bonus / Overtime (KES)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={simBonusOvertime}
                        onChange={(e) => setSimBonusOvertime(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl border border-gray-300 text-xs font-mono"
                      />
                    </div>
                  </div>

                  {/* Quick Control Checkboxes */}
                  <div className="rounded-2xl bg-[#F5F5F7] p-3.5 space-y-2 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={simApplyStatutory}
                        onChange={(e) => setSimApplyStatutory(e.target.checked)}
                        className="rounded text-[#0071E3]"
                      />
                      <span className="font-medium text-gray-800">
                        Apply Official Statutory PAYE, NSSF, SHIF &amp; Housing Levy Rates
                      </span>
                    </label>

                    {selectedEmployee.bank_account_changed &&
                      !selectedEmployee.bank_change_authorized && (
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={simRevertBank}
                            onChange={(e) => setSimRevertBank(e.target.checked)}
                            className="rounded text-[#0071E3]"
                          />
                          <span className="font-medium text-[#FF3B30]">
                            Revert Bank Account to HR Master Verified Account
                          </span>
                        </label>
                      )}

                    {selectedEmployee.employment_status === 'Exited' && (
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={simRemoveExited}
                          onChange={(e) => setSimRemoveExited(e.target.checked)}
                          className="rounded text-[#0071E3]"
                        />
                        <span className="font-medium text-[#FF3B30]">
                          Remove Exited Employee from October Payroll Run (KES 0 Payout)
                        </span>
                      </label>
                    )}

                    {!selectedEmployee.tax_pin_verified && (
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={simVerifyTaxPin}
                          onChange={(e) => setSimVerifyTaxPin(e.target.checked)}
                          className="rounded text-[#0071E3]"
                        />
                        <span className="font-medium text-amber-800">
                          Mark KRA Tax PIN &amp; SHIF Registration as Verified
                        </span>
                      </label>
                    )}

                    {selectedEmployee.exception_codes?.includes('UNEXPLAINED_PAY_JUMP') && (
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={simAuthorizeSalary}
                          onChange={(e) => setSimAuthorizeSalary(e.target.checked)}
                          className="rounded text-[#0071E3]"
                        />
                        <span className="font-medium text-gray-800">
                          Record Signed CHRO Salary Increment Approval for Current Basic Pay
                        </span>
                      </label>
                    )}
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-xs font-semibold cursor-pointer"
                  >
                    Recalculate &amp; Verify Payslip
                  </button>
                </form>

                {/* Employer Cost Summary */}
                <div className="pt-3 border-t border-gray-100 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Taxable Monthly Pay (Gross − NSSF):</span>
                    <span className="font-mono font-semibold text-[#1D1D1F]">
                      {formatKES(selectedEmployee.expected_taxable_pay)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Employer Matching NSSF + Housing Levy:</span>
                    <span className="font-mono font-semibold text-gray-700">
                      +
                      {formatKES(
                        selectedEmployee.employer_nssf + selectedEmployee.employer_housing_levy
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between pt-2 border-t border-gray-200">
                    <span className="font-semibold text-[#1D1D1F]">
                      Total Monthly Company Cost-to-Company:
                    </span>
                    <span className="font-mono font-bold text-[#0071E3]">
                      {formatKES(selectedEmployee.total_employer_cost)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: Ask Payroll Agent */}
        {activeTab === 'agent' && selectedEmployee && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-4 bg-white rounded-3xl p-6 border border-gray-200/90 space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-[#0071E3] text-white flex items-center justify-center">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#1D1D1F]">Ask Payroll Agent</h3>
                  <p className="text-[11px] text-gray-500">
                    Plain-English Payroll &amp; Statutory Assistant
                  </p>
                </div>
              </div>

              <p className="text-xs text-gray-600 leading-relaxed">
                Select any question below or ask your own question about salary variances, bank
                account changes, exited staff, or statutory tax calculations.
              </p>

              <div className="space-y-2">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                  Suggested HR &amp; Payroll Questions
                </div>
                {[
                  `Why is ${selectedEmployee.full_name} (${selectedEmployee.employee_id}) flagged or verified on the October 2026 payroll?`,
                  'Which employees had bank account changes this month, and which ones are unverified?',
                  'Are there any exited or offboarded employees still listed on the October draft payroll?',
                  `Show the exact PAYE, NSSF, SHIF, and Housing Levy calculation for ${selectedEmployee.full_name}.`
                ].map((qText, i) => (
                  <button
                    key={i}
                    onClick={() => handleAskPayrollAgent(qText)}
                    disabled={askingAgent}
                    className="w-full text-left p-3 rounded-2xl bg-[#F5F5F7] hover:bg-blue-50/70 border border-gray-200/80 text-xs text-gray-800 font-medium transition cursor-pointer"
                  >
                    {qText}
                  </button>
                ))}
              </div>
            </div>

            <div className="lg:col-span-8 bg-white rounded-3xl p-6 border border-gray-200/90 flex flex-col justify-between min-h-[480px]">
              <div className="space-y-4 overflow-y-auto max-h-[380px] pr-1">
                {chatHistory.length === 0 ? (
                  <div className="rounded-2xl bg-[#F5F5F7] p-6 text-center space-y-2">
                    <Sparkles className="w-6 h-6 text-[#0071E3] mx-auto" />
                    <div className="text-sm font-bold text-[#1D1D1F]">
                      Ask Payroll Agent About Any Payslip or Statutory Deduction
                    </div>
                    <p className="text-xs text-gray-500 max-w-md mx-auto">
                      Click one of the suggested questions on the left or type a question below to
                      get an instant plain-English explanation.
                    </p>
                  </div>
                ) : (
                  chatHistory.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-2xl text-xs leading-relaxed whitespace-pre-line ${
                        msg.role === 'user'
                          ? 'bg-[#0071E3] text-white ml-12'
                          : 'bg-[#F5F5F7] text-[#1D1D1F] border border-gray-200/80 mr-6'
                      }`}
                    >
                      {msg.role === 'assistant' && (
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-[#0071E3] mb-1">
                          {msg.model || 'Payroll Reconciliation Agent'}
                        </div>
                      )}
                      {msg.text}
                    </div>
                  ))
                )}
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAskPayrollAgent();
                }}
                className="pt-4 border-t border-gray-100 flex items-center gap-2"
              >
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={`Ask Payroll Agent about ${selectedEmployee.full_name} or October 2026 payroll...`}
                  className="flex-1 px-4 py-2.5 rounded-xl border border-gray-300 text-xs focus:outline-none focus:ring-2 focus:ring-[#0071E3]"
                />
                <button
                  type="submit"
                  disabled={askingAgent || !question.trim()}
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] disabled:opacity-50 text-white text-xs font-semibold cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{askingAgent ? 'Asking...' : 'Ask Agent'}</span>
                </button>
              </form>
            </div>
          </div>
        )}

        {/* TAB 4: 1-Page CFO / CHRO Payroll Reconciliation Sign-Off Certificate */}
        {activeTab === 'certificate' && kpis && (
          <div className="space-y-4">
            <div className="print:hidden flex flex-wrap items-center justify-between gap-4 bg-white rounded-2xl p-4 border border-gray-200/90">
              <div>
                <h2 className="text-sm font-bold text-[#1D1D1F]">
                  1-Page CFO &amp; CHRO Payroll Reconciliation Sign-Off Certificate
                </h2>
                <p className="text-xs text-gray-500">
                  Official monthly payroll variance, headcount bridge, and statutory tax remittance
                  approval sheet ready for printing or PDF export.
                </p>
              </div>
              <button
                onClick={() => window.print()}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-xs font-semibold shadow-xs cursor-pointer"
              >
                <Printer className="w-4 h-4" />
                <span>Print 1-Page Sign-Off Certificate</span>
              </button>
            </div>

            {/* Printable 1-Page Certificate */}
            <div className="bg-white rounded-3xl p-8 border border-gray-300 shadow-xs space-y-6 print:border-0 print:shadow-none print:p-2">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-gray-200 pb-4">
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-wider text-[#0071E3]">
                    Enterprise People &amp; Finance Governance • HR Agent #05
                  </div>
                  <h2 className="text-xl font-bold text-[#1D1D1F] mt-0.5">
                    Monthly Payroll Reconciliation &amp; Statutory Compliance Certificate
                  </h2>
                  <p className="text-xs text-gray-500">
                    Payroll Period: <strong>{kpis.payroll_period}</strong> (Compared Against{' '}
                    {kpis.prior_period})
                  </p>
                </div>
                <div className="text-right text-xs">
                  <div className="font-bold text-[#1D1D1F]">Certificate Ref: PAY-REC-2026-10</div>
                  <div className="text-gray-500">Prepared By: {user.name}</div>
                  <div
                    className={`inline-block mt-1 px-2.5 py-0.5 rounded-full font-semibold ${
                      kpis.ready_for_cfo_signoff
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-amber-100 text-amber-900'
                    }`}
                  >
                    {kpis.ready_for_cfo_signoff
                      ? 'ALL EXCEPTIONS RESOLVED • CLEARED FOR BANK PAYOUT'
                      : `${kpis.flagged_count} EXCEPTION(S) PENDING RESOLUTION`}
                  </div>
                </div>
              </div>

              {/* Section 1: Headcount & Gross-to-Net Monthly Bridge */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200 space-y-2">
                  <div className="text-xs font-bold uppercase tracking-wider text-gray-500">
                    1. Monthly Headcount Reconciliation Bridge
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="text-gray-600">September 2026 Paid Staff:</div>
                    <div className="text-right font-mono font-semibold">
                      {kpis.prior_headcount} Employees
                    </div>
                    <div className="text-gray-600">+ October 2026 New Hires (Agent #03):</div>
                    <div className="text-right font-mono font-semibold text-[#0071E3]">
                      +{kpis.new_hires_count} Employee
                    </div>
                    <div className="text-gray-600">− Exited / Offboarded Staff (Agent #04):</div>
                    <div className="text-right font-mono font-semibold text-[#FF3B30]">
                      −{kpis.exited_count} Employee
                    </div>
                    <div className="font-bold text-[#1D1D1F] pt-1 border-t border-gray-200">
                      October 2026 Active Paid Headcount:
                    </div>
                    <div className="text-right font-mono font-bold text-[#1D1D1F] pt-1 border-t border-gray-200">
                      {kpis.active_paid_headcount} Employees
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200 space-y-2">
                  <div className="text-xs font-bold uppercase tracking-wider text-gray-500">
                    2. Statutory Remittance Schedule (October 2026)
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="text-gray-600">KRA PAYE Income Tax (Due 9th Nov):</div>
                    <div className="text-right font-mono font-semibold">
                      {formatKES(kpis.total_paye)}
                    </div>
                    <div className="text-gray-600">NSSF Pension Tier I &amp; II (Employee):</div>
                    <div className="text-right font-mono font-semibold">
                      {formatKES(kpis.total_nssf)}
                    </div>
                    <div className="text-gray-600">SHIF Social Health Insurance (2.75%):</div>
                    <div className="text-right font-mono font-semibold">
                      {formatKES(kpis.total_shif)}
                    </div>
                    <div className="text-gray-600">Affordable Housing Levy (1.5%):</div>
                    <div className="text-right font-mono font-semibold">
                      {formatKES(kpis.total_housing_levy)}
                    </div>
                    <div className="font-bold text-[#1D1D1F] pt-1 border-t border-gray-200">
                      Total Employee Statutory Deductions:
                    </div>
                    <div className="text-right font-mono font-bold text-[#0071E3] pt-1 border-t border-gray-200">
                      {formatKES(kpis.total_statutory)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Section 2: Compact Employee Register Summary */}
              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">
                  3. Employee Payroll &amp; Bank Disbursement Register ({employees.length} Records)
                </div>
                <table className="w-full text-left border-collapse text-[11px]">
                  <thead>
                    <tr className="border-b border-gray-300 uppercase text-gray-500">
                      <th className="py-1.5 px-2">ID &amp; Employee</th>
                      <th className="py-1.5 px-2">Department</th>
                      <th className="py-1.5 px-2">Bank &amp; Account</th>
                      <th className="py-1.5 px-2 text-right">Oct Gross</th>
                      <th className="py-1.5 px-2 text-right">Statutory Tax</th>
                      <th className="py-1.5 px-2 text-right">Oct Net Pay</th>
                      <th className="py-1.5 px-2 text-right">Audit Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {employees.map((e) => (
                      <tr key={e.employee_id}>
                        <td className="py-1.5 px-2 font-semibold text-[#1D1D1F]">
                          {e.employee_id} • {e.full_name}
                        </td>
                        <td className="py-1.5 px-2 text-gray-600">{e.department}</td>
                        <td className="py-1.5 px-2 font-mono text-gray-600">
                          {e.current_bank_name} ({e.current_bank_account})
                        </td>
                        <td className="py-1.5 px-2 text-right font-mono">
                          {formatKES(e.current_gross_pay)}
                        </td>
                        <td className="py-1.5 px-2 text-right font-mono">
                          -{formatKES(e.draft_total_statutory)}
                        </td>
                        <td className="py-1.5 px-2 text-right font-mono font-bold">
                          {formatKES(e.draft_net_pay)}
                        </td>
                        <td className="py-1.5 px-2 text-right font-semibold">
                          {e.has_exceptions ? 'FLAGGED' : e.approval_status}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-gray-900 font-bold text-xs">
                      <td colSpan={3} className="py-2 px-2">
                        OCTOBER 2026 TOTAL PAYROLL DISBURSEMENT
                      </td>
                      <td className="py-2 px-2 text-right font-mono">
                        {formatKES(kpis.current_total_gross)}
                      </td>
                      <td className="py-2 px-2 text-right font-mono">
                        -{formatKES(kpis.total_statutory)}
                      </td>
                      <td className="py-2 px-2 text-right font-mono text-[#0071E3]">
                        {formatKES(kpis.current_total_net)}
                      </td>
                      <td className="py-2 px-2 text-right">
                        {kpis.approved_count}/{kpis.total_records} Approved
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              {/* Section 3: Executive Sign-Off Blocks */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-6 border-t border-gray-200 text-xs">
                <div className="space-y-4">
                  <div className="font-bold text-[#1D1D1F]">1. Prepared &amp; Reconciled By</div>
                  <div className="border-b border-gray-400 pb-1 font-mono text-gray-800">
                    {user.name}
                  </div>
                  <div className="text-gray-500">Head of Payroll &amp; Statutory Compliance</div>
                </div>
                <div className="space-y-4">
                  <div className="font-bold text-[#1D1D1F]">2. People &amp; HR Master Sign-Off</div>
                  <div className="border-b border-gray-400 pb-1 font-mono text-gray-800">
                    Signed Electronically / Pending CHRO
                  </div>
                  <div className="text-gray-500">Chief Human Resources Officer (CHRO)</div>
                </div>
                <div className="space-y-4">
                  <div className="font-bold text-[#1D1D1F]">
                    3. Treasury &amp; Bank Release Approval
                  </div>
                  <div className="border-b border-gray-400 pb-1 font-mono text-gray-800">
                    Signed Electronically / Pending CFO
                  </div>
                  <div className="text-gray-500">Chief Financial Officer (CFO)</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
