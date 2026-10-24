import React, { useState, useEffect } from 'react';
import {
  Users,
  TrendingDown,
  UserMinus,
  Clock,
  DollarSign,
  Sliders,
  MessageSquareText,
  Printer,
  RotateCcw,
  LogOut,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Send,
  Building2,
  Briefcase,
  ArrowUpRight,
  ArrowDownRight,
  FileText,
  ShieldAlert,
} from 'lucide-react';
import SignInPage, { AppleAppearanceSwitcher, APPLE_READING_THEMES } from './components/SignInPage';

function formatCurrency(amount) {
  const num = Number(amount || 0);
  const abs = Math.abs(num);
  const sign = num < 0 ? '-' : '';
  return `${sign}$${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function formatSignedCurrency(amount) {
  const num = Number(amount || 0);
  if (num === 0) return '$0';
  const sign = num > 0 ? '+' : '-';
  return `${sign}$${Math.abs(num).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

export default function App() {
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('apple_reading_theme');
      const valid = APPLE_READING_THEMES.map((t) => t.id);
      return valid.includes(saved) ? saved : 'sand';
    } catch {
      return 'sand';
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('apple_reading_theme', theme);
    } catch {
      // ignore storage errors
    }
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
    if (theme === 'dusk' || theme === 'midnight') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  const [user, setUser] = useState(() => {
    try {
      const saved = sessionStorage.getItem('hr_workforce_agent_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [overview, setOverview] = useState(null);
  const [simulation, setSimulation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [simLoading, setSimLoading] = useState(false);

  // What-If Simulator Sliders
  const [salaryIncrementPct, setSalaryIncrementPct] = useState(5.0);
  const [projectedTurnoverPct, setProjectedTurnoverPct] = useState(13.8);
  const [plannedNewHires, setPlannedNewHires] = useState(25);

  // Department Filter & Selection
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedDept, setSelectedDept] = useState(null);

  // Ask Workforce Agent Q&A State
  const [questionInput, setQuestionInput] = useState('');
  const [agentResponse, setAgentResponse] = useState(null);
  const [askingAgent, setAskingAgent] = useState(false);

  const handleSignInSuccess = (authenticatedUser) => {
    setUser(authenticatedUser);
    try {
      sessionStorage.setItem('hr_workforce_agent_user', JSON.stringify(authenticatedUser));
    } catch {
      // ignore storage errors
    }
  };

  const handleSignOut = () => {
    setUser(null);
    try {
      sessionStorage.removeItem('hr_workforce_agent_user');
    } catch {
      // ignore
    }
  };

  const fetchOverview = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/workforce/overview');
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
        setSimulation(data.default_simulation);
        if (data.departments?.length && !selectedDept) {
          setSelectedDept(data.departments[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load workforce overview:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchOverview();
      handleAskQuestion(
        'Which departments have the highest turnover and regrettable departures right now?',
        5.0,
        13.8,
        25
      );
    }
  }, [user]);

  const runSimulation = async (nextSalaryPct, nextTurnoverPct, nextNewHires) => {
    setSimLoading(true);
    try {
      const res = await fetch('/api/workforce/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          annual_salary_increment_pct: Number(nextSalaryPct),
          projected_turnover_pct: Number(nextTurnoverPct),
          planned_new_hires: Number(nextNewHires),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSimulation(data);
      }
    } catch (err) {
      console.error('Failed to run workforce simulation:', err);
    } finally {
      setSimLoading(false);
    }
  };

  const handleSliderChange = (type, value) => {
    let nextSalary = salaryIncrementPct;
    let nextTurnover = projectedTurnoverPct;
    let nextHires = plannedNewHires;

    if (type === 'salary') {
      nextSalary = Number(value);
      setSalaryIncrementPct(nextSalary);
    } else if (type === 'turnover') {
      nextTurnover = Number(value);
      setProjectedTurnoverPct(nextTurnover);
    } else if (type === 'hires') {
      nextHires = Number(value);
      setPlannedNewHires(nextHires);
    }

    runSimulation(nextSalary, nextTurnover, nextHires);
  };

  const applyPresetScenario = (presetSalary, presetTurnover, presetHires) => {
    setSalaryIncrementPct(presetSalary);
    setProjectedTurnoverPct(presetTurnover);
    setPlannedNewHires(presetHires);
    runSimulation(presetSalary, presetTurnover, presetHires);
  };

  const handleAskQuestion = async (
    customQuestion,
    sal = salaryIncrementPct,
    turn = projectedTurnoverPct,
    hires = plannedNewHires
  ) => {
    const q = (customQuestion ?? questionInput).trim();
    if (!q) return;
    setAskingAgent(true);
    try {
      const res = await fetch('/api/agent/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          annual_salary_increment_pct: Number(sal),
          projected_turnover_pct: Number(turn),
          planned_new_hires: Number(hires),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAgentResponse({ question: q, ...data });
      }
    } catch (err) {
      console.error('Error asking Workforce Analytics Agent:', err);
    } finally {
      setAskingAgent(false);
    }
  };

  const handleResetDemo = async () => {
    setSalaryIncrementPct(5.0);
    setProjectedTurnoverPct(13.8);
    setPlannedNewHires(25);
    setStatusFilter('ALL');
    try {
      const res = await fetch('/api/workforce/reset', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setOverview(data.overview);
        setSimulation(data.overview.default_simulation);
      }
    } catch {
      fetchOverview();
    }
  };

  if (!user) {
    return <SignInPage onSuccess={handleSignInSuccess} theme={theme} onSelectTheme={setTheme} />;
  }

  const kpis = overview?.executive_kpis || {
    total_active_headcount: 480,
    total_open_roles: 34,
    total_annual_departures: 66,
    annual_attrition_rate_pct: 13.8,
    regrettable_departures: 24,
    regrettable_share_pct: 36.4,
    avg_time_to_hire_days: 32,
    avg_tenure_years: 2.8,
    monthly_payroll_cost: 3040000,
    annual_payroll_cost: 36480000,
    avg_monthly_cost_per_employee: 6333.33,
  };

  const departments = overview?.departments || [];
  const filteredDepartments =
    statusFilter === 'ALL'
      ? departments
      : departments.filter((d) => d.retention_status === statusFilter);

  const simProjected = simulation?.projected || {
    headcount: 505,
    monthly_payroll_cost: 3358000,
    annual_payroll_cost: 40299000,
    annual_turnover_pct: 13.8,
    annual_departures: 66,
    annual_salary_increment_cost: 1824000,
    monthly_salary_increment_cost: 152000,
    new_hires_annual_payroll_cost: 1995000,
    new_hires_recruitment_cost: 285000,
    annual_replacement_cost: 1254000,
    replacement_cost_variance: 0,
    total_recruitment_and_replacement_cost: 1539000,
    net_annual_budget_impact: 4104000,
    total_projected_people_budget: 41838000,
  };

  const getStatusBadgeStyle = (status) => {
    if (status === 'Action Needed') {
      return 'bg-red-50 text-red-700 border-red-200';
    }
    if (status === 'Watch Closely') {
      return 'bg-amber-50 text-amber-800 border-amber-200';
    }
    return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  };

  return (
    <div className="min-h-screen bg-[#F5F5F7] text-[#1D1D1F] pb-16">
      {/* Frosted-Glass Apple Header */}
      <header className="apple-glass sticky top-0 z-30 no-print">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#0071E3] flex items-center justify-center text-white shadow-xs">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight text-[#1D1D1F]">
                  Workforce Analytics Agent
                </h1>
                <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200">
                  Agent #09 • Executive Boardroom View
                </span>
              </div>
              <p className="text-xs text-gray-500">
                {overview?.company_profile?.name || 'Apex Global Enterprises'} •{' '}
                {overview?.company_profile?.reporting_period || 'Q4 2026 Executive Board Cycle'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <AppleAppearanceSwitcher theme={theme} onSelectTheme={setTheme} />

            <button
              type="button"
              onClick={() => window.print()}
              className="px-3.5 py-2 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-xs font-semibold shadow-xs transition flex items-center gap-1.5 cursor-pointer"
            >
              <Printer className="w-3.5 h-3.5" />
              Print 1-Page Board Summary
            </button>

            <button
              type="button"
              onClick={handleResetDemo}
              className="px-3 py-2 rounded-xl bg-white hover:bg-gray-50 text-gray-700 border border-gray-200 text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer"
              title="Reset sliders and workforce state"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </button>

            <div className="hidden sm:flex items-center gap-2 pl-2 border-l border-gray-200">
              <div className="text-right">
                <div className="text-xs font-semibold text-[#1D1D1F]">{user.name}</div>
                <div className="text-[10px] text-gray-500">{user.role || 'CHRO / Executive View'}</div>
              </div>
              <button
                type="button"
                onClick={handleSignOut}
                className="p-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-600 transition cursor-pointer"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 pt-6 space-y-8">
        {/* =====================================================================
            SECTION 1: 5 EXECUTIVE KPI CARDS (Plain Business Language)
        ===================================================================== */}
        <section aria-label="Executive Workforce KPIs">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div>
              <h2 className="text-lg font-bold tracking-tight text-[#1D1D1F]">
                1. Live Workforce &amp; Turnover Overview
              </h2>
              <p className="text-xs text-gray-500">
                Real-time people, attrition, hiring speed, and monthly payroll figures across all 5 company departments
              </p>
            </div>
            <span className="text-xs font-medium text-gray-500">
              Average Employee Tenure: <strong className="text-[#1D1D1F]">{kpis.avg_tenure_years} Years</strong>
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {/* Card 1: Total Active Headcount */}
            <div className="apple-card rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-gray-500">Total Active Headcount</span>
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-[#0071E3] flex items-center justify-center">
                  <Users className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-[#1D1D1F]">
                {kpis.total_active_headcount}
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded-md">
                  +{kpis.total_open_roles} Open Roles
                </span>
                <span className="text-gray-500">5 Departments</span>
              </div>
            </div>

            {/* Card 2: Annual Attrition Rate % */}
            <div className="apple-card rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-gray-500">Annual Attrition Rate %</span>
                <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                  <TrendingDown className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-[#1D1D1F]">
                {kpis.annual_attrition_rate_pct}%
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-amber-800 font-semibold bg-amber-50 px-2 py-0.5 rounded-md">
                  {kpis.total_annual_departures} Departures / Yr
                </span>
                <span className="text-gray-500">Target: 11.0%</span>
              </div>
            </div>

            {/* Card 3: Regrettable Departures */}
            <div className="apple-card rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-gray-500">Regrettable Departures</span>
                <div className="w-8 h-8 rounded-xl bg-red-50 text-red-600 flex items-center justify-center">
                  <UserMinus className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-[#1D1D1F]">
                {kpis.regrettable_departures}
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-red-700 font-semibold bg-red-50 px-2 py-0.5 rounded-md">
                  {kpis.regrettable_share_pct}% of All Exits
                </span>
                <span className="text-gray-500">High Performers</span>
              </div>
            </div>

            {/* Card 4: Average Time to Hire (Days) */}
            <div className="apple-card rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-gray-500">Average Time to Hire (Days)</span>
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <Clock className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-[#1D1D1F]">
                {kpis.avg_time_to_hire_days} Days
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded-md">
                  -3 Days vs Q1
                </span>
                <span className="text-gray-500">Eng: 42 Days</span>
              </div>
            </div>

            {/* Card 5: Monthly Payroll Cost */}
            <div className="apple-card rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-gray-500">Monthly Payroll Cost</span>
                <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <DollarSign className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-extrabold text-[#1D1D1F]">
                {formatCurrency(kpis.monthly_payroll_cost)}
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                <span className="text-gray-700 font-semibold bg-gray-100 px-2 py-0.5 rounded-md">
                  {formatCurrency(kpis.annual_payroll_cost)} / Yr
                </span>
                <span className="text-gray-500">${Math.round(kpis.avg_monthly_cost_per_employee).toLocaleString()}/emp</span>
              </div>
            </div>
          </div>
        </section>

        {/* =====================================================================
            SECTION 2: DEPARTMENT BREAKDOWN TABLE
        ===================================================================== */}
        <section aria-label="Department Breakdown Table" className="apple-card rounded-3xl p-6">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-5">
            <div>
              <h2 className="text-lg font-bold text-[#1D1D1F]">
                Department Breakdown Table
              </h2>
              <p className="text-xs text-gray-500">
                Headcount, Open Roles, Turnover %, Retention Status, and Monthly Cost across all 5 departments
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2 no-print">
              {['ALL', 'Action Needed', 'Watch Closely', 'Healthy'].map((status) => (
                <button
                  key={status}
                  type="button"
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                    statusFilter === status
                      ? 'bg-[#0071E3] text-white shadow-2xs'
                      : 'bg-[#F5F5F7] text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {status === 'ALL' ? 'All Departments (5)' : status}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-gray-200 text-[11px] font-bold uppercase tracking-wider text-gray-400">
                  <th className="py-3 pr-4">Department</th>
                  <th className="py-3 px-4 text-right">Headcount</th>
                  <th className="py-3 px-4 text-right">Open Roles</th>
                  <th className="py-3 px-4 text-right">Turnover %</th>
                  <th className="py-3 px-4 text-right">Regrettable Exits</th>
                  <th className="py-3 px-4 text-right">Time to Hire</th>
                  <th className="py-3 px-4">Retention Status</th>
                  <th className="py-3 pl-4 text-right">Monthly Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-sm">
                {filteredDepartments.map((dept) => {
                  const isSelected = selectedDept?.id === dept.id;
                  return (
                    <tr
                      key={dept.id}
                      onClick={() => setSelectedDept(dept)}
                      className={`transition cursor-pointer ${
                        isSelected ? 'bg-blue-50/50' : 'hover:bg-gray-50/80'
                      }`}
                    >
                      <td className="py-4 pr-4">
                        <div className="font-bold text-[#1D1D1F]">{dept.name}</div>
                        <div className="text-xs text-gray-500">{dept.head_of_department}</div>
                      </td>
                      <td className="py-4 px-4 text-right font-semibold text-[#1D1D1F]">
                        {dept.headcount}
                      </td>
                      <td className="py-4 px-4 text-right">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-[#0071E3]">
                          {dept.open_roles} open
                        </span>
                      </td>
                      <td className="py-4 px-4 text-right">
                        <div className="font-bold text-[#1D1D1F]">{dept.turnover_pct}%</div>
                        <div className="text-[11px] text-gray-500">{dept.annual_departures} exits/yr</div>
                      </td>
                      <td className="py-4 px-4 text-right">
                        <span className="font-semibold text-gray-800">{dept.regrettable_departures}</span>
                      </td>
                      <td className="py-4 px-4 text-right text-gray-700 font-medium">
                        {dept.avg_time_to_hire_days} days
                      </td>
                      <td className="py-4 px-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ${getStatusBadgeStyle(
                            dept.retention_status
                          )}`}
                        >
                          {dept.retention_status}
                        </span>
                      </td>
                      <td className="py-4 pl-4 text-right font-bold text-[#1D1D1F]">
                        {formatCurrency(dept.monthly_cost)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-gray-200 bg-[#F5F5F7]/70 font-bold text-sm">
                  <td className="py-3.5 pr-4 pl-2 text-[#1D1D1F]">Company Total / Average</td>
                  <td className="py-3.5 px-4 text-right text-[#1D1D1F]">{kpis.total_active_headcount}</td>
                  <td className="py-3.5 px-4 text-right text-[#0071E3]">{kpis.total_open_roles} open</td>
                  <td className="py-3.5 px-4 text-right text-[#1D1D1F]">{kpis.annual_attrition_rate_pct}%</td>
                  <td className="py-3.5 px-4 text-right text-[#1D1D1F]">{kpis.regrettable_departures}</td>
                  <td className="py-3.5 px-4 text-right text-[#1D1D1F]">{kpis.avg_time_to_hire_days} days</td>
                  <td className="py-3.5 px-4 text-xs text-gray-600">5 Active Departments</td>
                  <td className="py-3.5 pl-4 pr-2 text-right text-[#1D1D1F]">
                    {formatCurrency(kpis.monthly_payroll_cost)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Selected Department Plain-English Action Box */}
          {selectedDept && (
            <div className="mt-5 p-4 rounded-2xl bg-[#F5F5F7] border border-gray-200/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#0071E3]">
                    Department Focus: {selectedDept.name}
                  </span>
                  <span className="text-xs text-gray-400">•</span>
                  <span className="text-xs text-gray-600">
                    Avg Tenure: <strong>{selectedDept.avg_tenure_years} yrs</strong> | Replacement Cost per Exit:{' '}
                    <strong>{formatCurrency(selectedDept.replacement_cost_per_exit)}</strong>
                  </span>
                </div>
                <p className="text-xs text-gray-700">
                  <strong>Why People Leave:</strong> {selectedDept.primary_turnover_driver}
                </p>
                <p className="text-xs text-[#1D1D1F]">
                  <strong>Recommended CHRO Action:</strong> {selectedDept.recommended_action}
                </p>
              </div>
              <div className="shrink-0 flex items-center gap-3">
                <div className="bg-white px-3.5 py-2 rounded-xl border border-gray-200 text-right">
                  <div className="text-[11px] text-gray-500">Annualized Dept Payroll</div>
                  <div className="text-sm font-bold text-[#1D1D1F]">
                    {formatCurrency(selectedDept.monthly_cost * 12)}
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* =====================================================================
            SECTION 3: INTERACTIVE BUDGET & ATTRITION WHAT-IF SIMULATOR
        ===================================================================== */}
        <section
          aria-label="Interactive Budget and Attrition What-If Simulator"
          className="apple-card rounded-3xl p-6"
        >
          <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-blue-50 text-[#0071E3] flex items-center justify-center">
                <Sliders className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-[#1D1D1F]">
                  2. Interactive Budget &amp; Attrition What-If Simulator
                </h2>
                <p className="text-xs text-gray-500">
                  Adjust Annual Salary Increment %, Projected Turnover %, and Planned New Hires to see exact annual payroll and replacement-cost impact
                </p>
              </div>
            </div>

            {/* Quick Executive Scenario Presets */}
            <div className="flex flex-wrap items-center gap-2 no-print">
              <button
                type="button"
                onClick={() => applyPresetScenario(5.0, 13.8, 25)}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#F5F5F7] hover:bg-gray-200 text-[#1D1D1F] transition cursor-pointer"
              >
                Current Baseline (5% / 13.8% / 25)
              </button>
              <button
                type="button"
                onClick={() => applyPresetScenario(6.0, 10.0, 20)}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 transition cursor-pointer"
              >
                Retention Push (6% / 10% / 20)
              </button>
              <button
                type="button"
                onClick={() => applyPresetScenario(5.0, 20.0, 35)}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 transition cursor-pointer"
              >
                High Attrition Stress-Test (5% / 20% / 35)
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* LEFT 5/12: 3 Simple Business Sliders */}
            <div className="lg:col-span-5 bg-[#F5F5F7] rounded-2xl p-5 space-y-6 border border-gray-200/70">
              {/* Slider 1: Annual Salary Increment % */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="slider-salary-increment"
                    className="text-xs font-bold text-[#1D1D1F]"
                  >
                    Annual Salary Increment %
                  </label>
                  <span className="text-sm font-extrabold text-[#0071E3] bg-white px-2.5 py-0.5 rounded-lg border border-blue-200">
                    {salaryIncrementPct.toFixed(1)}%
                  </span>
                </div>
                <input
                  id="slider-salary-increment"
                  type="range"
                  min="0"
                  max="20"
                  step="0.5"
                  value={salaryIncrementPct}
                  onChange={(e) => handleSliderChange('salary', e.target.value)}
                  className="w-full cursor-pointer"
                />
                <div className="flex justify-between text-[11px] text-gray-500">
                  <span>0% (Pay Freeze)</span>
                  <span>5% (Standard Review)</span>
                  <span>20% (Max Cap)</span>
                </div>
              </div>

              {/* Slider 2: Projected Turnover % */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="slider-projected-turnover"
                    className="text-xs font-bold text-[#1D1D1F]"
                  >
                    Projected Turnover %
                  </label>
                  <span className="text-sm font-extrabold text-amber-700 bg-white px-2.5 py-0.5 rounded-lg border border-amber-200">
                    {projectedTurnoverPct.toFixed(1)}% ({simProjected.annual_departures} exits)
                  </span>
                </div>
                <input
                  id="slider-projected-turnover"
                  type="range"
                  min="4"
                  max="30"
                  step="0.2"
                  value={projectedTurnoverPct}
                  onChange={(e) => handleSliderChange('turnover', e.target.value)}
                  className="w-full cursor-pointer"
                />
                <div className="flex justify-between text-[11px] text-gray-500">
                  <span>4% (High Retention)</span>
                  <span>13.8% (Current Rate)</span>
                  <span>30% (Severe Attrition)</span>
                </div>
              </div>

              {/* Slider 3: Planned New Hires */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="slider-planned-hires"
                    className="text-xs font-bold text-[#1D1D1F]"
                  >
                    Planned New Hires (Net Headcount Expansion)
                  </label>
                  <span className="text-sm font-extrabold text-emerald-700 bg-white px-2.5 py-0.5 rounded-lg border border-emerald-200">
                    +{plannedNewHires} Hires
                  </span>
                </div>
                <input
                  id="slider-planned-hires"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={plannedNewHires}
                  onChange={(e) => handleSliderChange('hires', e.target.value)}
                  className="w-full cursor-pointer"
                />
                <div className="flex justify-between text-[11px] text-gray-500">
                  <span>0 Hires (Replacement Only)</span>
                  <span>25 Hires (Current Plan)</span>
                  <span>100 Hires</span>
                </div>
              </div>

              <div className="pt-3 border-t border-gray-200 text-[11px] text-gray-600 space-y-1">
                <div>
                  • <strong>Replacement Cost per Departure:</strong> $19,000 (25% of avg annual salary for sourcing, onboarding &amp; ramp-up)
                </div>
                <div>
                  • <strong>Recruitment Fee per Planned Hire:</strong> $11,400 (15% of avg annual salary)
                </div>
              </div>
            </div>

            {/* RIGHT 7/12: Deterministic Financial Impact Summary */}
            <div className="lg:col-span-7 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Impact Card 1: Projected Annual Payroll */}
                <div className="p-4 rounded-2xl bg-[#F5F5F7] border border-gray-200/80">
                  <div className="text-xs font-semibold text-gray-500 mb-1">
                    Projected Annual Payroll Cost
                  </div>
                  <div className="text-2xl font-extrabold text-[#1D1D1F]">
                    {formatCurrency(simProjected.annual_payroll_cost)}
                  </div>
                  <div className="mt-1.5 text-xs text-gray-600 flex items-center justify-between">
                    <span>Baseline: {formatCurrency(kpis.annual_payroll_cost)}</span>
                    <span className="font-bold text-[#0071E3]">
                      {formatCurrency(simProjected.monthly_payroll_cost)} / mo
                    </span>
                  </div>
                </div>

                {/* Impact Card 2: Salary Increment Cost */}
                <div className="p-4 rounded-2xl bg-[#F5F5F7] border border-gray-200/80">
                  <div className="text-xs font-semibold text-gray-500 mb-1">
                    Annual Salary Review Cost ({salaryIncrementPct.toFixed(1)}%)
                  </div>
                  <div className="text-2xl font-extrabold text-[#0071E3]">
                    {formatSignedCurrency(simProjected.annual_salary_increment_cost)}
                  </div>
                  <div className="mt-1.5 text-xs text-gray-600 flex items-center justify-between">
                    <span>Across {kpis.total_active_headcount} active staff</span>
                    <span className="font-semibold">
                      {formatSignedCurrency(simProjected.monthly_salary_increment_cost)} / mo
                    </span>
                  </div>
                </div>

                {/* Impact Card 3: Turnover Replacement Hiring Cost */}
                <div className="p-4 rounded-2xl bg-[#F5F5F7] border border-gray-200/80">
                  <div className="text-xs font-semibold text-gray-500 mb-1">
                    Annual Turnover Replacement Cost ({simProjected.annual_departures} Exits)
                  </div>
                  <div className="text-2xl font-extrabold text-amber-700">
                    {formatCurrency(simProjected.annual_replacement_cost)}
                  </div>
                  <div className="mt-1.5 text-xs flex items-center justify-between">
                    <span className="text-gray-600">Baseline (66 exits): $1,254,000</span>
                    <span
                      className={`font-bold ${
                        simProjected.replacement_cost_variance <= 0
                          ? 'text-emerald-700'
                          : 'text-red-600'
                      }`}
                    >
                      {simProjected.replacement_cost_variance <= 0
                        ? `Saves ${formatCurrency(Math.abs(simProjected.replacement_cost_variance))}`
                        : `${formatSignedCurrency(simProjected.replacement_cost_variance)} vs Base`}
                    </span>
                  </div>
                </div>

                {/* Impact Card 4: Planned New Hires Cost */}
                <div className="p-4 rounded-2xl bg-[#F5F5F7] border border-gray-200/80">
                  <div className="text-xs font-semibold text-gray-500 mb-1">
                    Planned New Hires Cost ({plannedNewHires} Roles)
                  </div>
                  <div className="text-2xl font-extrabold text-emerald-700">
                    {formatSignedCurrency(
                      simProjected.new_hires_annual_payroll_cost +
                        simProjected.new_hires_recruitment_cost
                    )}
                  </div>
                  <div className="mt-1.5 text-xs text-gray-600 flex items-center justify-between">
                    <span>Payroll: {formatCurrency(simProjected.new_hires_annual_payroll_cost)}</span>
                    <span>Hiring Fees: {formatCurrency(simProjected.new_hires_recruitment_cost)}</span>
                  </div>
                </div>
              </div>

              {/* Net Budget Impact Banner */}
              <div className="p-5 rounded-2xl bg-gradient-to-r from-[#0071E3] to-blue-700 text-white shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-wider text-blue-100">
                      Total Simulated People Budget (Payroll + Recruitment &amp; Backfill)
                    </div>
                    <div className="text-2xl sm:text-3xl font-extrabold mt-0.5">
                      {formatCurrency(simProjected.total_projected_people_budget)} / Year
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-blue-100">Net Annual Budget Change vs Baseline</div>
                    <div className="text-xl font-extrabold">
                      {formatSignedCurrency(simProjected.net_annual_budget_impact)}
                    </div>
                    <div className="text-[11px] text-blue-100">
                      Year-End Headcount: <strong>{simProjected.headcount} Employees</strong>
                    </div>
                  </div>
                </div>
                <p className="mt-3 pt-3 border-t border-white/20 text-xs text-blue-50 leading-relaxed">
                  <strong>Executive Guidance ({simulation?.risk_status || 'Balanced Plan'}):</strong>{' '}
                  {simulation?.board_guidance}
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* =====================================================================
            SECTION 4: ASK WORKFORCE AGENT (Plain-English Q&A)
        ===================================================================== */}
        <section
          aria-label="Ask Workforce Agent and CHRO Boardroom Summary"
          className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start"
        >
          {/* Left 7/12: Ask Workforce Agent Interactive Q&A */}
          <div className="lg:col-span-7 apple-card rounded-3xl p-6 space-y-5 no-print">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <MessageSquareText className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-[#1D1D1F]">
                    3. Ask Workforce Agent
                  </h2>
                  <p className="text-xs text-gray-500">
                    Ask plain-English questions about turnover, hiring speed, or salary review scenarios
                  </p>
                </div>
              </div>
              <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700">
                Plain-English People Q&amp;A
              </span>
            </div>

            {/* Sample 1-Click Executive Prompts */}
            <div className="space-y-1.5">
              <div className="text-xs font-semibold text-gray-500">
                Quick Executive Questions:
              </div>
              <div className="flex flex-wrap gap-2">
                {(overview?.sample_questions || [
                  'Which departments have the highest turnover and regrettable departures right now?',
                  'What is the total budget impact of a 6% salary review and 20 new hires if we cut turnover to 10%?',
                  'Why is Engineering taking 42 days to hire and how do we speed up recruitment?',
                  'Give me a 1-page CHRO & CEO summary of our workforce health and Q1 priorities.',
                ]).map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => {
                      setQuestionInput(q);
                      handleAskQuestion(q);
                    }}
                    className="text-left text-xs px-3 py-1.5 rounded-xl bg-[#F5F5F7] hover:bg-blue-50 hover:text-[#0071E3] text-gray-700 font-medium transition cursor-pointer border border-gray-200/70"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {/* Question Input Form */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAskQuestion(questionInput);
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={questionInput}
                onChange={(e) => setQuestionInput(e.target.value)}
                placeholder="Ask Workforce Agent a question (e.g., How much do we save if Sales turnover drops to 12%?)..."
                className="flex-1 px-4 py-2.5 text-sm rounded-xl border border-gray-300 focus:border-[#0071E3] focus:ring-2 focus:ring-blue-100 outline-none"
              />
              <button
                type="submit"
                disabled={askingAgent}
                className="px-4 py-2.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] disabled:opacity-60 text-white font-semibold text-sm transition flex items-center gap-1.5 cursor-pointer shrink-0"
              >
                <Send className="w-4 h-4" />
                {askingAgent ? 'Analyzing...' : 'Ask Workforce Agent'}
              </button>
            </form>

            {/* Agent Response Card */}
            {agentResponse && (
              <div className="p-5 rounded-2xl bg-[#F5F5F7] border border-gray-200/90 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200">
                    {agentResponse.agent_badge || 'Workforce Analytics Agent'}
                  </span>
                  <span className="text-[11px] text-gray-500">{agentResponse.engine}</span>
                </div>

                <h3 className="text-base font-bold text-[#1D1D1F]">
                  {agentResponse.headline}
                </h3>

                <p className="text-xs text-gray-700 leading-relaxed">
                  {agentResponse.executive_summary}
                </p>

                {agentResponse.ai_live_summary && (
                  <div className="p-3 rounded-xl bg-white border border-blue-100 text-xs text-gray-800">
                    <strong className="text-[#0071E3]">Live Executive Synthesis: </strong>
                    {agentResponse.ai_live_summary}
                  </div>
                )}

                <ul className="space-y-2 pt-1">
                  {(agentResponse.key_points || []).map((pt, index) => (
                    <li key={index} className="flex items-start gap-2 text-xs text-gray-800">
                      <CheckCircle2 className="w-4 h-4 text-[#0071E3] shrink-0 mt-0.5" />
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>

                {agentResponse.recommended_action && (
                  <div className="pt-3 border-t border-gray-200 text-xs text-[#1D1D1F]">
                    <strong className="text-emerald-700">Recommended Executive Action: </strong>
                    {agentResponse.recommended_action}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right 5/12: Printable 1-Page CHRO Boardroom Summary */}
          <div className="lg:col-span-5 apple-card rounded-3xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-4">
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#0071E3]">
                  Boardroom Memorandum
                </span>
                <h2 className="text-lg font-bold text-[#1D1D1F]">
                  1-Page CHRO Boardroom Summary
                </h2>
                <p className="text-xs text-gray-500">
                  Prepared for CEO, CFO &amp; Compensation Committee
                </p>
              </div>
              <button
                type="button"
                onClick={() => window.print()}
                className="no-print px-3 py-1.5 rounded-xl bg-[#F5F5F7] hover:bg-gray-200 text-xs font-semibold text-[#1D1D1F] flex items-center gap-1.5 cursor-pointer"
              >
                <Printer className="w-3.5 h-3.5" />
                Print
              </button>
            </div>

            {/* Key Priorities for the Board */}
            <div className="space-y-3">
              {(overview?.board_highlights || []).map((item, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-2xl bg-[#F5F5F7] border border-gray-200/70 space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-[#0071E3] uppercase">
                      {item.category}
                    </span>
                    <span className="text-[11px] font-semibold text-gray-600">{item.impact}</span>
                  </div>
                  <div className="text-xs font-bold text-[#1D1D1F]">{item.title}</div>
                  <p className="text-xs text-gray-600 leading-relaxed">{item.summary}</p>
                </div>
              ))}
            </div>

            {/* Active Scenario Snapshot for Board Sign-Off */}
            <div className="p-4 rounded-2xl bg-blue-50/60 border border-blue-200/80 space-y-2">
              <div className="text-xs font-bold text-[#1D1D1F]">
                Simulated Budget Scenario Attached to Summary
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-white p-2 rounded-xl border border-gray-200">
                  <div className="text-[10px] text-gray-500">Salary Review</div>
                  <div className="text-xs font-bold text-[#0071E3]">{salaryIncrementPct.toFixed(1)}%</div>
                </div>
                <div className="bg-white p-2 rounded-xl border border-gray-200">
                  <div className="text-[10px] text-gray-500">Turnover Target</div>
                  <div className="text-xs font-bold text-amber-700">{projectedTurnoverPct.toFixed(1)}%</div>
                </div>
                <div className="bg-white p-2 rounded-xl border border-gray-200">
                  <div className="text-[10px] text-gray-500">Planned Hires</div>
                  <div className="text-xs font-bold text-emerald-700">+{plannedNewHires}</div>
                </div>
              </div>
              <div className="flex justify-between text-xs pt-1">
                <span className="text-gray-600">Projected Annual Payroll:</span>
                <strong className="text-[#1D1D1F]">{formatCurrency(simProjected.annual_payroll_cost)}</strong>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-600">Recruitment &amp; Backfill Budget:</span>
                <strong className="text-[#1D1D1F]">
                  {formatCurrency(simProjected.total_recruitment_and_replacement_cost)}
                </strong>
              </div>
            </div>

            {/* Executive Sign-Off Block */}
            <div className="pt-3 border-t border-gray-200 grid grid-cols-3 gap-3 text-[11px] text-gray-600">
              <div>
                <div className="font-bold text-[#1D1D1F]">Grace Njeri</div>
                <div>CHRO Sponsor</div>
              </div>
              <div>
                <div className="font-bold text-[#1D1D1F]">David Kimani</div>
                <div>CFO Budget Review</div>
              </div>
              <div>
                <div className="font-bold text-[#1D1D1F]">Jonathan Sterling</div>
                <div>CEO Approval</div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="max-w-7xl mx-auto px-6 pt-8 pb-4 text-xs text-gray-500 flex flex-wrap items-center justify-between gap-3 no-print">
        <span>Enterprise HR AI Agent Portfolio • Agent #09: Workforce Analytics Agent</span>
        <AppleAppearanceSwitcher theme={theme} onSelectTheme={setTheme} />
      </footer>
    </div>
  );
}
