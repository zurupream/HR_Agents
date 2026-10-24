import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BellRing,
  CalendarCheck,
  CheckCircle2,
  Clock,
  Edit3,
  FileText,
  LogOut,
  MailCheck,
  MessageSquare,
  Printer,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  UserCheck,
  Users
} from 'lucide-react';
import SignInPage from './components/SignInPage';

const STORAGE_KEY = 'hr_attendance_leave_agent06_user';
const THEME_STORAGE_KEY = 'hr_attendance_leave_theme';

const APPEARANCE_THEMES = [
  { id: 'daylight', label: 'Daylight', title: 'Studio Daylight', swatch: '#F5F5F7' },
  { id: 'sand', label: 'Sand', title: 'Warm Sand (Default)', swatch: '#F7F5F0' },
  { id: 'dusk', label: 'Dusk', title: 'Quiet Dusk', swatch: '#1C1E26' },
  { id: 'midnight', label: 'Midnight', title: 'Midnight OLED', swatch: '#0B0C10' }
];

const LEAVE_OPTIONS = [
  'None',
  'Approved Annual Leave',
  'Approved Sick Leave',
  'Approved Half-Day Leave',
  'Pending'
];

function parseTimeMinutes(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') return null;
  const cleaned = timeStr.trim();
  if (!cleaned || cleaned === '—' || cleaned === '-') return null;
  const parts = cleaned.split(':');
  if (parts.length < 2) return null;
  const h = Number(parts[0]);
  const m = Number(parts[1]);
  if (Number.isNaN(h) || Number.isNaN(m) || h < 0 || h > 23 || m < 0 || m > 59) {
    return null;
  }
  return h * 60 + m;
}

function computeClientPreview(emp, clockIn, clockOut, leaveStatus) {
  const reqHours = Number(emp?.required_hours || 8.0);
  const inMin = parseTimeMinutes(clockIn);
  const outMin = parseTimeMinutes(clockOut);
  const hoursWorked =
    inMin !== null && outMin !== null && outMin > inMin
      ? Math.round(((outMin - inMin) / 60.0) * 100) / 100
      : 0.0;

  let approvedLeaveHours = 0.0;
  if (leaveStatus === 'Approved Annual Leave' || leaveStatus === 'Approved Sick Leave') {
    approvedLeaveHours = reqHours;
  } else if (leaveStatus === 'Approved Half-Day Leave') {
    approvedLeaveHours = Math.round((reqHours / 2.0) * 100) / 100;
  }

  const effectiveRequired = Math.max(0.0, Math.round((reqHours - approvedLeaveHours) * 100) / 100);
  const hoursShortfall = Math.max(0.0, Math.round((effectiveRequired - hoursWorked) * 100) / 100);

  let statusBadge = 'On Time / Full Hours';
  let hrActionRequired = false;

  if (hoursShortfall === 0) {
    statusBadge = approvedLeaveHours > 0 ? 'Approved Leave' : 'On Time / Full Hours';
    hrActionRequired = false;
  } else {
    hrActionRequired = true;
    statusBadge =
      hoursWorked === 0 && approvedLeaveHours === 0
        ? 'Absent — No Leave'
        : 'Missed Hours — No Leave';
  }

  const clockInDisp = clockIn && clockIn.trim() ? clockIn.trim() : 'No Clock-In';
  const clockOutDisp = clockOut && clockOut.trim() ? clockOut.trim() : 'No Clock-Out';

  const subject = hrActionRequired
    ? `HR Attendance Notice: ${emp?.employee_name} (${emp?.department}) — ${statusBadge} (${hoursShortfall.toFixed(2)}h Shortfall on ${emp?.attendance_date})`
    : `Attendance Verified: ${emp?.employee_name} (${emp?.attendance_date}) — ${statusBadge}`;

  const body = hrActionRequired
    ? `To: HR Operations (${emp?.hr_partner_email || 'hr.operations@company.co.ke'}), ${emp?.employee_name} (${emp?.email})\nCc: ${emp?.line_manager || 'Line Manager'}\n\nDaily Attendance & Leave Check Summary (${emp?.attendance_date}):\n• Employee: ${emp?.employee_name} (${emp?.employee_id}) — ${emp?.department}\n• Clock-In / Clock-Out: ${clockInDisp} to ${clockOutDisp}\n• Hours Worked vs. Required: ${hoursWorked.toFixed(2)} hrs worked of ${reqHours.toFixed(1)} hrs required\n• Leave Application Status: ${leaveStatus}\n• Unexplained Hours Shortfall: ${hoursShortfall.toFixed(2)} hrs (${statusBadge})\n\nRequired Action:\nPlease submit an approved leave application or confirm attendance regularization with HR Operations and your line manager before payroll cut-off.`
    : `${emp?.employee_name} has no attendance shortfall on ${emp?.attendance_date} (${hoursWorked.toFixed(2)} hrs worked, Leave Status: ${leaveStatus}). No HR notification required.`;

  return {
    hoursWorked,
    reqHours,
    approvedLeaveHours,
    effectiveRequired,
    hoursShortfall,
    statusBadge,
    hrActionRequired,
    subject,
    body
  };
}

function StatusBadgePill({ status }) {
  if (status === 'On Time / Full Hours') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
        On Time / Full Hours
      </span>
    );
  }
  if (status === 'Approved Leave') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-[#0071E3] border border-blue-200">
        <CalendarCheck className="w-3.5 h-3.5 text-[#0071E3]" />
        Approved Leave
      </span>
    );
  }
  if (status === 'Missed Hours — No Leave') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
        <Clock className="w-3.5 h-3.5 text-amber-600" />
        Missed Hours — No Leave
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
      <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
      Absent — No Leave
    </span>
  );
}

function LeaveStatusPill({ leaveStatus }) {
  if (leaveStatus.startsWith('Approved')) {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-[#0071E3] border border-blue-200">
        {leaveStatus}
      </span>
    );
  }
  if (leaveStatus === 'Pending') {
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">
        Pending (Unapproved)
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
      None
    </span>
  );
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

  const [activeView, setActiveView] = useState('dashboard'); // 'dashboard' | 'ask' | 'report'
  const [employees, setEmployees] = useState([]);
  const [summary, setSummary] = useState(null);
  const [notificationsLog, setNotificationsLog] = useState([]);
  const [selectedId, setSelectedId] = useState('EMP-1001');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [bannerMessage, setBannerMessage] = useState('');

  // Editable fields for the selected employee
  const [editClockIn, setEditClockIn] = useState('');
  const [editClockOut, setEditClockOut] = useState('');
  const [editLeaveStatus, setEditLeaveStatus] = useState('None');

  // Ask Attendance Agent state
  const [question, setQuestion] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [askingAgent, setAskingAgent] = useState(false);

  const selectedEmployee = useMemo(
    () => employees.find((e) => e.employee_id === selectedId) || employees[0] || null,
    [employees, selectedId]
  );

  const fetchAttendanceData = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/attendance');
      const data = await res.json();
      setEmployees(data.employees || []);
      setSummary(data.summary || null);
      setNotificationsLog(data.notifications_log || []);
    } catch (err) {
      console.error('Failed to load attendance data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchAttendanceData();
    }
  }, [user]);

  useEffect(() => {
    if (selectedEmployee) {
      setEditClockIn(selectedEmployee.clock_in || '');
      setEditClockOut(selectedEmployee.clock_out || '');
      setEditLeaveStatus(selectedEmployee.leave_status || 'None');
    }
  }, [selectedEmployee?.employee_id, selectedEmployee?.clock_in, selectedEmployee?.clock_out, selectedEmployee?.leave_status]);

  const livePreview = useMemo(() => {
    if (!selectedEmployee) return null;
    return computeClientPreview(
      selectedEmployee,
      editClockIn,
      editClockOut,
      editLeaveStatus
    );
  }, [selectedEmployee, editClockIn, editClockOut, editLeaveStatus]);

  const filteredEmployees = useMemo(() => {
    return employees.filter((emp) => {
      if (statusFilter === 'FLAGGED' && !emp.hr_action_required) return false;
      if (statusFilter === 'MISSED' && emp.status_badge !== 'Missed Hours — No Leave') return false;
      if (statusFilter === 'ABSENT' && emp.status_badge !== 'Absent — No Leave') return false;
      if (statusFilter === 'LEAVE' && emp.status_badge !== 'Approved Leave') return false;
      if (statusFilter === 'FULL' && emp.status_badge !== 'On Time / Full Hours') return false;

      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const matchName = emp.employee_name.toLowerCase().includes(q);
        const matchDept = emp.department.toLowerCase().includes(q);
        const matchId = emp.employee_id.toLowerCase().includes(q);
        if (!matchName && !matchDept && !matchId) return false;
      }
      return true;
    });
  }, [employees, statusFilter, searchQuery]);

  const handleSignInSuccess = (authenticatedUser) => {
    setUser(authenticatedUser);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(authenticatedUser));
    } catch {
      // ignore storage error
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

  const handleUpdateEmployee = async (e) => {
    if (e) e.preventDefault();
    if (!selectedEmployee) return;
    setLoading(true);
    setBannerMessage('');
    try {
      const res = await fetch(`/api/attendance/${selectedEmployee.employee_id}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clock_in: editClockIn,
          clock_out: editClockOut,
          leave_status: editLeaveStatus,
          required_hours: selectedEmployee.required_hours
        })
      });
      const data = await res.json();
      if (res.ok) {
        setEmployees((prev) =>
          prev.map((item) =>
            item.employee_id === data.employee.employee_id ? data.employee : item
          )
        );
        setSummary(data.summary);
        setBannerMessage(data.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleQuickPreset = async (clockInVal, clockOutVal, leaveVal) => {
    setEditClockIn(clockInVal);
    setEditClockOut(clockOutVal);
    setEditLeaveStatus(leaveVal);
    if (!selectedEmployee) return;
    setLoading(true);
    setBannerMessage('');
    try {
      const res = await fetch(`/api/attendance/${selectedEmployee.employee_id}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clock_in: clockInVal,
          clock_out: clockOutVal,
          leave_status: leaveVal,
          required_hours: selectedEmployee.required_hours
        })
      });
      const data = await res.json();
      if (res.ok) {
        setEmployees((prev) =>
          prev.map((item) =>
            item.employee_id === data.employee.employee_id ? data.employee : item
          )
        );
        setSummary(data.summary);
        setBannerMessage(data.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleNotifySingleEmployee = async (employeeId) => {
    setLoading(true);
    setBannerMessage('');
    try {
      const res = await fetch(`/api/attendance/${employeeId}/notify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sent_by: `${user?.name || 'Sarah Wambui'} (${user?.role || 'HR Operations Manager'})`
        })
      });
      const data = await res.json();
      if (res.ok) {
        setEmployees((prev) =>
          prev.map((item) =>
            item.employee_id === data.employee.employee_id ? data.employee : item
          )
        );
        setSummary(data.summary);
        setNotificationsLog(data.notifications_log || []);
        setBannerMessage(data.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleNotifyAllFlagged = async () => {
    setLoading(true);
    setBannerMessage('');
    try {
      const res = await fetch('/api/attendance/notify-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sent_by: `${user?.name || 'Sarah Wambui'} (${user?.role || 'HR Operations Manager'})`
        })
      });
      const data = await res.json();
      if (res.ok) {
        setEmployees(data.employees || []);
        setSummary(data.summary);
        setNotificationsLog(data.notifications_log || []);
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
      const res = await fetch('/api/attendance/reset', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setEmployees(data.employees || []);
        setSummary(data.summary || null);
        setNotificationsLog(data.notifications_log || []);
        setBannerMessage(data.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAskAttendanceAgent = async (customPrompt) => {
    const q = (customPrompt ?? question).trim();
    if (!q) return;
    setAskingAgent(true);
    setQuestion('');
    setChatHistory((prev) => [
      ...prev,
      {
        role: 'user',
        text: q,
        employee_name: selectedEmployee?.employee_name
      }
    ]);
    try {
      const res = await fetch('/api/agent/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          employee_id: selectedEmployee?.employee_id
        })
      });
      const data = await res.json();
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: data.answer || 'No response received from Attendance & Leave Agent.',
          model: data.model || 'Enterprise People & Analytics Engine'
        }
      ]);
    } catch (err) {
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Unable to reach Attendance & Leave Agent: ${err.message}`,
          model: 'error'
        }
      ]);
    } finally {
      setAskingAgent(false);
    }
  };

  if (!user) {
    return <SignInPage onSuccess={handleSignInSuccess} theme={theme} onThemeChange={setTheme} />;
  }

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)] flex flex-col">
      {/* Frosted-Glass Top Navigation Bar */}
      <header className="no-print apple-glass sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#0071E3] flex items-center justify-center text-white shadow-sm">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200">
                  Agent #06 • Attendance &amp; Leave Agent
                </span>
                <span className="text-xs text-gray-500 hidden md:inline">
                  Daily Shift Check (8.0h) &amp; HR Notification Workflow
                </span>
              </div>
              <h1 className="text-base sm:text-lg font-bold text-gray-900 tracking-tight">
                Attendance Clock-In/Out &amp; Leave Notification Agent
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
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

            <button
              onClick={handleResetDemo}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-xs font-medium text-gray-700 cursor-pointer"
              title="Reset demo data to initial state"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Reset Demo</span>
            </button>

            <div className="text-right hidden sm:block pl-1">
              <div className="text-xs font-semibold text-gray-900">{user.name}</div>
              <div className="text-[11px] text-gray-500">{user.role || 'HR Operations Manager'}</div>
            </div>

            <button
              onClick={handleSignOut}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-xs font-medium text-gray-700 cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>

        {/* Clean View Switcher */}
        <div className="max-w-7xl mx-auto px-6 flex items-center gap-2 overflow-x-auto pb-2.5">
          {[
            {
              id: 'dashboard',
              label: 'Daily Clock-In/Out & Leave Check',
              icon: Users
            },
            {
              id: 'ask',
              label: 'Ask Attendance Agent',
              icon: MessageSquare
            },
            {
              id: 'report',
              label: '1-Page Daily Attendance & Missed-Hours HR Report',
              icon: FileText
            }
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeView === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveView(tab.id)}
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

      {/* Main Content */}
      <main className="max-w-7xl mx-auto w-full px-6 py-6 flex-1 space-y-6">
        {/* Top 5 Summary Cards (Hidden when printing 1-Page Report) */}
        {summary && (
          <section className="no-print grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {/* 1. Total Employees Checked */}
            <div className="apple-card rounded-2xl p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Total Employees Checked
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-1">
                {summary.total_employees_checked}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Date: {summary.attendance_date} • 8.0h Shift
              </div>
            </div>

            {/* 2. Full Hours Completed */}
            <div className="apple-card rounded-2xl p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Full Hours Completed
              </div>
              <div className="text-2xl font-bold text-emerald-700 mt-1">
                {summary.full_hours_completed}
              </div>
              <div className="text-xs text-emerald-700 font-medium mt-1">
                Worked 8.0+ hours on schedule
              </div>
            </div>

            {/* 3. Covered by Approved Leave */}
            <div className="apple-card rounded-2xl p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Covered by Approved Leave
              </div>
              <div className="text-2xl font-bold text-[#0071E3] mt-1">
                {summary.covered_by_approved_leave}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Annual, Sick &amp; Half-Day Leave
              </div>
            </div>

            {/* 4. Missed Hours / Absent with No Leave (HR Action Required) */}
            <div className="rounded-2xl p-4 bg-rose-50/70 border border-rose-200 shadow-xs">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-rose-700">
                Missed Hours / Absent — No Leave
              </div>
              <div className="text-2xl font-bold text-rose-700 mt-1">
                {summary.flagged_for_hr_action} Employees
              </div>
              <div className="text-xs text-rose-800 font-medium mt-1">
                HR Action Required • {summary.total_shortfall_hours.toFixed(1)}h total shortfall
              </div>
            </div>

            {/* 5. HR Notifications Sent */}
            <div className="apple-card rounded-2xl p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                HR Notifications Sent
              </div>
              <div className="text-2xl font-bold text-gray-900 mt-1">
                {summary.hr_notifications_sent}
              </div>
              <div className="text-xs text-amber-700 font-medium mt-1">
                {summary.pending_hr_notifications > 0
                  ? `${summary.pending_hr_notifications} flagged employee(s) awaiting notice`
                  : 'All flagged employees notified'}
              </div>
            </div>
          </section>
        )}

        {/* Confirmation Banner */}
        {bannerMessage && (
          <div className="no-print rounded-2xl bg-emerald-50 border border-emerald-200 px-4 py-3 flex items-center justify-between text-xs text-emerald-900 font-medium">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{bannerMessage}</span>
            </div>
            <button
              onClick={() => setBannerMessage('')}
              className="text-emerald-700 hover:underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* VIEW 1: Daily Clock-In/Out & Leave Check (Table + Live Editor & Notification Preview) */}
        {activeView === 'dashboard' && (
          <div className="space-y-6">
            {/* Employee Attendance & Leave Table Card */}
            <div className="apple-card rounded-3xl p-6 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-base font-bold text-gray-900">
                    Daily Employee Clock-In/Out &amp; Leave Application Check
                  </h2>
                  <p className="text-xs text-gray-500">
                    Reviews clock-in and clock-out times against required daily hours (8.0h) and approved leave applications. Click any employee to edit/test hours or send a 1-click HR notification.
                  </p>
                </div>

                {/* Bulk Notify HR Button + Printable Report Shortcut */}
                <div className="flex flex-wrap items-center gap-2.5">
                  <button
                    onClick={() => setActiveView('report')}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-gray-300 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-700 cursor-pointer"
                  >
                    <Printer className="w-3.5 h-3.5" />
                    <span>Printable 1-Page HR Report</span>
                  </button>

                  <button
                    onClick={handleNotifyAllFlagged}
                    disabled={loading}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] disabled:opacity-50 text-white text-xs font-semibold shadow-sm transition cursor-pointer"
                  >
                    <BellRing className="w-3.5 h-3.5" />
                    <span>Notify HR for All Flagged Employees</span>
                  </button>
                </div>
              </div>

              {/* Filter Pills & Search Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  {[
                    { id: 'ALL', label: `All Employees (${employees.length})` },
                    {
                      id: 'FLAGGED',
                      label: `HR Action Required (${employees.filter((e) => e.hr_action_required).length})`
                    },
                    {
                      id: 'MISSED',
                      label: `Missed Hours — No Leave (${employees.filter((e) => e.status_badge === 'Missed Hours — No Leave').length})`
                    },
                    {
                      id: 'ABSENT',
                      label: `Absent — No Leave (${employees.filter((e) => e.status_badge === 'Absent — No Leave').length})`
                    },
                    {
                      id: 'LEAVE',
                      label: `Approved Leave (${employees.filter((e) => e.status_badge === 'Approved Leave').length})`
                    },
                    {
                      id: 'FULL',
                      label: `On Time / Full Hours (${employees.filter((e) => e.status_badge === 'On Time / Full Hours').length})`
                    }
                  ].map((pill) => (
                    <button
                      key={pill.id}
                      onClick={() => setStatusFilter(pill.id)}
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold transition cursor-pointer ${
                        statusFilter === pill.id
                          ? 'bg-gray-900 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {pill.label}
                    </button>
                  ))}
                </div>

                <div className="relative w-full sm:w-64">
                  <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filter by employee or department..."
                    className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl border border-gray-200 bg-[#F5F5F7] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0071E3]"
                  />
                </div>
              </div>

              {/* Clean Filterable Employee Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-gray-200 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                      <th className="py-3 px-3">Employee Name &amp; Department</th>
                      <th className="py-3 px-3">Date</th>
                      <th className="py-3 px-3">Clock-In Time</th>
                      <th className="py-3 px-3">Clock-Out Time</th>
                      <th className="py-3 px-3">Hours Worked vs. Required (8h)</th>
                      <th className="py-3 px-3">Leave Application Status</th>
                      <th className="py-3 px-3">Hours Shortfall</th>
                      <th className="py-3 px-3">Status Badge</th>
                      <th className="py-3 px-3 text-right">HR Notification Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-xs">
                    {filteredEmployees.map((emp) => {
                      const isSelected = emp.employee_id === selectedEmployee?.employee_id;
                      return (
                        <tr
                          key={emp.employee_id}
                          onClick={() => setSelectedId(emp.employee_id)}
                          className={`transition cursor-pointer ${
                            isSelected ? 'bg-blue-50/60' : 'hover:bg-gray-50/80'
                          }`}
                        >
                          <td className="py-3.5 px-3">
                            <div className="font-semibold text-gray-900">
                              {emp.employee_name}
                            </div>
                            <div className="text-[11px] text-gray-500">
                              {emp.department} • {emp.employee_id}
                            </div>
                          </td>

                          <td className="py-3.5 px-3 text-gray-700 font-medium whitespace-nowrap">
                            {emp.attendance_date}
                          </td>

                          <td className="py-3.5 px-3 font-mono font-medium">
                            {emp.clock_in ? (
                              <span className="text-gray-900">{emp.clock_in}</span>
                            ) : (
                              <span className="text-rose-600 font-sans text-[11px] font-semibold">
                                No Clock-In
                              </span>
                            )}
                          </td>

                          <td className="py-3.5 px-3 font-mono font-medium">
                            {emp.clock_out ? (
                              <span className="text-gray-900">{emp.clock_out}</span>
                            ) : (
                              <span className="text-rose-600 font-sans text-[11px] font-semibold">
                                No Clock-Out
                              </span>
                            )}
                          </td>

                          <td className="py-3.5 px-3">
                            <div className="font-semibold text-gray-900">
                              {emp.hours_worked.toFixed(2)}h{' '}
                              <span className="text-gray-400 font-normal">
                                / {emp.required_hours.toFixed(1)}h
                              </span>
                            </div>
                            <div className="w-24 h-1.5 bg-gray-200 rounded-full overflow-hidden mt-1">
                              <div
                                className={`h-full rounded-full ${
                                  emp.hr_action_required
                                    ? 'bg-rose-500'
                                    : emp.status_badge === 'Approved Leave'
                                      ? 'bg-[#0071E3]'
                                      : 'bg-emerald-500'
                                }`}
                                style={{
                                  width: `${Math.min(
                                    100,
                                    Math.round(
                                      ((emp.hours_worked + emp.approved_leave_hours) /
                                        emp.required_hours) *
                                        100
                                    )
                                  )}%`
                                }}
                              />
                            </div>
                          </td>

                          <td className="py-3.5 px-3">
                            <LeaveStatusPill leaveStatus={emp.leave_status} />
                          </td>

                          <td className="py-3.5 px-3">
                            {emp.hours_shortfall > 0 ? (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
                                −{emp.hours_shortfall.toFixed(2)} hrs
                              </span>
                            ) : (
                              <span className="text-emerald-700 font-semibold">0.00 hrs</span>
                            )}
                          </td>

                          <td className="py-3.5 px-3 whitespace-nowrap">
                            <StatusBadgePill status={emp.status_badge} />
                          </td>

                          <td className="py-3.5 px-3 text-right whitespace-nowrap">
                            {emp.hr_action_required ? (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedId(emp.employee_id);
                                  handleNotifySingleEmployee(emp.employee_id);
                                }}
                                disabled={loading}
                                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                                  emp.notification_sent
                                    ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100'
                                    : 'bg-[#0071E3] text-white hover:bg-[#0077ED] shadow-xs'
                                }`}
                              >
                                {emp.notification_sent ? (
                                  <>
                                    <MailCheck className="w-3.5 h-3.5 text-emerald-600" />
                                    <span>Notified ({emp.notification_ref}) • Resend</span>
                                  </>
                                ) : (
                                  <>
                                    <Send className="w-3.5 h-3.5" />
                                    <span>Notify HR &amp; Employee</span>
                                  </>
                                )}
                              </button>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedId(emp.employee_id);
                                }}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl text-[11px] font-medium text-gray-500 hover:bg-gray-100 cursor-pointer"
                              >
                                <Edit3 className="w-3 h-3" />
                                <span>Edit / Test Hours</span>
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Bottom 2-Column Split: Edit/Test Clock-In, Clock-Out & Leave Status + Live HR Notification Preview */}
            {selectedEmployee && livePreview && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left 6/12: Interactive Clock-In, Clock-Out & Leave Status Tester */}
                <div className="lg:col-span-6 apple-card rounded-3xl p-6 space-y-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-[#0071E3]">
                        Interactive Attendance &amp; Leave Tester
                      </span>
                      <h3 className="text-base font-bold text-gray-900 mt-0.5">
                        Edit / Test Clock-In, Clock-Out or Leave Status — {selectedEmployee.employee_name}
                      </h3>
                      <p className="text-xs text-gray-500">
                        Change clock-in time, clock-out time, or leave application status below to immediately see the hours shortfall calculation and notification preview.
                      </p>
                    </div>
                  </div>

                  {/* Quick Test Presets */}
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-semibold text-gray-500">
                      Quick Test Scenarios for {selectedEmployee.employee_name}:
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleQuickPreset('09:45', '15:15', 'None')}
                        className="px-2.5 py-1 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-xs font-medium cursor-pointer"
                      >
                        Missed 2.5h — No Leave (09:45–15:15)
                      </button>
                      <button
                        type="button"
                        onClick={() => handleQuickPreset('', '', 'None')}
                        className="px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-medium cursor-pointer"
                      >
                        Absent — No Leave (0.0h)
                      </button>
                      <button
                        type="button"
                        onClick={() => handleQuickPreset('', '', 'Approved Annual Leave')}
                        className="px-2.5 py-1 rounded-lg bg-blue-50 hover:bg-blue-100 text-[#0071E3] border border-blue-200 text-xs font-medium cursor-pointer"
                      >
                        Approved Annual Leave
                      </button>
                      <button
                        type="button"
                        onClick={() => handleQuickPreset('08:30', '16:30', 'None')}
                        className="px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-medium cursor-pointer"
                      >
                        Full 8.0h Completed (08:30–16:30)
                      </button>
                    </div>
                  </div>

                  <form onSubmit={handleUpdateEmployee} className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                          Clock-In Time (HH:MM)
                        </label>
                        <input
                          type="text"
                          value={editClockIn}
                          onChange={(e) => setEditClockIn(e.target.value)}
                          placeholder="e.g. 08:30 or leave blank"
                          className="w-full px-3 py-2 rounded-xl border border-gray-300 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-[#0071E3]"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                          Clock-Out Time (HH:MM)
                        </label>
                        <input
                          type="text"
                          value={editClockOut}
                          onChange={(e) => setEditClockOut(e.target.value)}
                          placeholder="e.g. 16:30 or leave blank"
                          className="w-full px-3 py-2 rounded-xl border border-gray-300 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-[#0071E3]"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-gray-700 mb-1">
                          Leave Application Status
                        </label>
                        <select
                          value={editLeaveStatus}
                          onChange={(e) => setEditLeaveStatus(e.target.value)}
                          className="w-full px-3 py-2 rounded-xl border border-gray-300 text-xs bg-white focus:outline-none focus:ring-2 focus:ring-[#0071E3]"
                        >
                          {LEAVE_OPTIONS.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Deterministic Calculation Breakdown Box */}
                    <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/80 space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Required Daily Shift Hours:</span>
                        <span className="font-semibold text-gray-900">
                          {livePreview.reqHours.toFixed(2)} hrs
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Approved Leave Hours Covered:</span>
                        <span className="font-semibold text-[#0071E3]">
                          −{livePreview.approvedLeaveHours.toFixed(2)} hrs ({editLeaveStatus})
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">Clock-In to Clock-Out Hours Worked:</span>
                        <span className="font-semibold text-gray-900">
                          −{livePreview.hoursWorked.toFixed(2)} hrs
                        </span>
                      </div>
                      <div className="pt-2 border-t border-gray-200 flex items-center justify-between">
                        <span className="font-bold text-gray-900">
                          Calculated Hours Shortfall:
                        </span>
                        <span
                          className={`font-bold text-sm ${
                            livePreview.hoursShortfall > 0 ? 'text-rose-600' : 'text-emerald-700'
                          }`}
                        >
                          {livePreview.hoursShortfall.toFixed(2)} hrs
                        </span>
                      </div>
                      <div className="pt-1 flex items-center justify-between">
                        <span className="font-semibold text-gray-700">Resulting Status:</span>
                        <StatusBadgePill status={livePreview.statusBadge} />
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full py-2.5 px-4 rounded-xl bg-gray-900 hover:bg-gray-800 text-white text-xs font-semibold shadow-xs transition cursor-pointer"
                    >
                      Save &amp; Update Employee Attendance Check
                    </button>
                  </form>
                </div>

                {/* Right 6/12: Live HR & Employee Notification Preview */}
                <div className="lg:col-span-6 apple-card rounded-3xl p-6 flex flex-col justify-between space-y-4">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-[#0071E3]">
                          Step 3 • Automated HR &amp; Employee Notice Preview
                        </span>
                        <h3 className="text-base font-bold text-gray-900 mt-0.5">
                          HR Notification Preview — {selectedEmployee.employee_name}
                        </h3>
                      </div>
                      <StatusBadgePill status={livePreview.statusBadge} />
                    </div>

                    <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/90 space-y-2.5 text-xs">
                      <div>
                        <span className="font-semibold text-gray-500">Subject: </span>
                        <span className="font-semibold text-gray-900">{livePreview.subject}</span>
                      </div>
                      <pre className="whitespace-pre-wrap font-sans text-xs text-gray-700 leading-relaxed bg-white p-3.5 rounded-xl border border-gray-200/80">
                        {livePreview.body}
                      </pre>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                    <div className="text-xs text-gray-500">
                      {selectedEmployee.notification_sent ? (
                        <span className="text-emerald-700 font-semibold">
                          ✓ Sent ({selectedEmployee.notification_ref}) at {selectedEmployee.notification_sent_at}
                        </span>
                      ) : livePreview.hrActionRequired ? (
                        <span className="text-rose-700 font-medium">
                          Ready to notify HR Operations &amp; {selectedEmployee.employee_name}
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-medium">
                          No shortfall — no HR notification needed
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      disabled={loading || !selectedEmployee.hr_action_required}
                      onClick={() => handleNotifySingleEmployee(selectedEmployee.employee_id)}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] disabled:opacity-40 text-white text-xs font-semibold shadow-sm transition cursor-pointer"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>
                        {selectedEmployee.notification_sent
                          ? 'Resend Notification to HR & Employee'
                          : 'Notify HR & Employee'}
                      </span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Sent HR Notifications Log */}
            {notificationsLog.length > 0 && (
              <div className="apple-card rounded-3xl p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-gray-900">
                      Sent HR &amp; Employee Attendance Notifications Log
                    </h3>
                    <p className="text-xs text-gray-500">
                      Record of notifications dispatched to HR Operations, employees, and line managers for missed hours or absences without approved leave.
                    </p>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-semibold">
                    {notificationsLog.length} Sent
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-gray-200 text-[11px] uppercase text-gray-400">
                        <th className="py-2.5 px-3">Notice Ref</th>
                        <th className="py-2.5 px-3">Employee &amp; Department</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3">Shortfall</th>
                        <th className="py-2.5 px-3">Recipients</th>
                        <th className="py-2.5 px-3">Sent At</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {notificationsLog.map((item, idx) => (
                        <tr key={`${item.notification_ref}-${idx}`}>
                          <td className="py-2.5 px-3 font-mono font-semibold text-[#0071E3]">
                            {item.notification_ref}
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-gray-900">
                            {item.employee_name}{' '}
                            <span className="text-gray-500 font-normal">({item.department})</span>
                          </td>
                          <td className="py-2.5 px-3">
                            <StatusBadgePill status={item.status_badge} />
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-rose-700">
                            −{Number(item.hours_shortfall).toFixed(2)} hrs
                          </td>
                          <td className="py-2.5 px-3 text-gray-600">{item.recipients}</td>
                          <td className="py-2.5 px-3 text-gray-500">{item.sent_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* VIEW 2: Ask Attendance Agent */}
        {activeView === 'ask' && (
          <div className="apple-card rounded-3xl p-6 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#0071E3]">
                  <Sparkles className="w-3.5 h-3.5" />
                  Interactive HR Assistant
                </div>
                <h2 className="text-base font-bold text-gray-900 mt-0.5">
                  Ask Attendance Agent
                </h2>
                <p className="text-xs text-gray-500">
                  Ask plain-English questions about today&apos;s clock-in/clock-out logs, approved leave cross-checks, or employees who missed hours without leave.
                </p>
              </div>
            </div>

            {/* Preset Questions */}
            <div className="flex flex-wrap gap-2">
              {[
                'Which employees missed hours or were absent today with no approved leave?',
                'Why was Brian Mutua flagged when he submitted a leave request?',
                'Which employees are covered by approved annual, sick, or half-day leave today?',
                'Draft a summary of today’s missed-hours exceptions for the HR Operations Manager.'
              ].map((preset) => (
                <button
                  key={preset}
                  onClick={() => handleAskAttendanceAgent(preset)}
                  disabled={askingAgent}
                  className="px-3 py-1.5 rounded-xl bg-[#F5F5F7] hover:bg-blue-50 hover:text-[#0071E3] border border-gray-200 text-xs font-medium text-gray-700 transition cursor-pointer"
                >
                  {preset}
                </button>
              ))}
            </div>

            {/* Chat Conversation Area */}
            <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/80 min-h-[260px] max-h-[420px] overflow-y-auto space-y-3">
              {chatHistory.length === 0 ? (
                <div className="text-center py-12 text-xs text-gray-500 space-y-1">
                  <p className="font-semibold text-gray-700">
                    Ask Attendance Agent anything about today&apos;s attendance &amp; leave records
                  </p>
                  <p>
                    Click one of the suggested HR questions above or type your own question below.
                  </p>
                </div>
              ) : (
                chatHistory.map((msg, i) => (
                  <div
                    key={i}
                    className={`p-4 rounded-2xl text-xs leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-[#0071E3] text-white ml-auto max-w-xl font-medium'
                        : 'bg-white border border-gray-200/90 text-gray-800 max-w-3xl whitespace-pre-wrap'
                    }`}
                  >
                    {msg.text}
                  </div>
                ))
              )}
            </div>

            {/* Question Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAskAttendanceAgent();
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask Attendance Agent a question in plain English..."
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-300 text-xs focus:outline-none focus:ring-2 focus:ring-[#0071E3]"
              />
              <button
                type="submit"
                disabled={askingAgent || !question.trim()}
                className="px-5 py-2.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] disabled:opacity-50 text-white text-xs font-semibold cursor-pointer"
              >
                {askingAgent ? 'Checking...' : 'Ask Attendance Agent'}
              </button>
            </form>
          </div>
        )}

        {/* VIEW 3: Printable 1-Page Daily Attendance & Missed-Hours HR Report */}
        {activeView === 'report' && summary && (
          <div className="space-y-4">
            <div className="no-print flex items-center justify-between bg-white rounded-2xl p-4 border border-gray-200">
              <div>
                <h2 className="text-sm font-bold text-gray-900">
                  Printable 1-Page Daily Attendance &amp; Missed-Hours HR Report
                </h2>
                <p className="text-xs text-gray-500">
                  Formatted for one-page printing or saving as PDF for daily HR Operations review.
                </p>
              </div>
              <button
                onClick={() => window.print()}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-xs font-semibold shadow-sm cursor-pointer"
              >
                <Printer className="w-4 h-4" />
                <span>Print / Save 1-Page HR Report</span>
              </button>
            </div>

            {/* Printable Sheet */}
            <div className="bg-white rounded-3xl p-8 border border-gray-200 shadow-xs space-y-6">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-gray-200 pb-4">
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider text-[#0071E3]">
                    Enterprise HR &amp; People Operations • Agent #06
                  </div>
                  <h2 className="text-xl font-bold text-gray-900 mt-0.5">
                    Daily Attendance &amp; Missed-Hours HR Report
                  </h2>
                  <p className="text-xs text-gray-500">
                    Daily Clock-In/Out vs. Required Shift Hours (8.0h) &amp; Approved Leave Cross-Check
                  </p>
                </div>
                <div className="text-right text-xs text-gray-600 space-y-0.5">
                  <div>
                    <strong>Attendance Date:</strong> {summary.attendance_date}
                  </div>
                  <div>
                    <strong>Prepared By:</strong> {user.name} ({user.role || 'HR Operations Manager'})
                  </div>
                  <div>
                    <strong>Standard Shift Requirement:</strong> 8.0 Hours / Day
                  </div>
                </div>
              </div>

              {/* Summary Strip inside Printable Report */}
              <div className="grid grid-cols-5 gap-3 text-center">
                <div className="p-3 rounded-xl bg-[#F5F5F7] border border-gray-200">
                  <div className="text-[10px] uppercase font-semibold text-gray-500">
                    Employees Checked
                  </div>
                  <div className="text-lg font-bold text-gray-900">
                    {summary.total_employees_checked}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200">
                  <div className="text-[10px] uppercase font-semibold text-emerald-700">
                    Full Hours (8h+)
                  </div>
                  <div className="text-lg font-bold text-emerald-800">
                    {summary.full_hours_completed}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-blue-50 border border-blue-200">
                  <div className="text-[10px] uppercase font-semibold text-[#0071E3]">
                    Approved Leave
                  </div>
                  <div className="text-lg font-bold text-[#0071E3]">
                    {summary.covered_by_approved_leave}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200">
                  <div className="text-[10px] uppercase font-semibold text-rose-700">
                    Missed / Absent (No Leave)
                  </div>
                  <div className="text-lg font-bold text-rose-700">
                    {summary.flagged_for_hr_action} ({summary.total_shortfall_hours.toFixed(1)}h)
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-[#F5F5F7] border border-gray-200">
                  <div className="text-[10px] uppercase font-semibold text-gray-500">
                    HR Notices Sent
                  </div>
                  <div className="text-lg font-bold text-gray-900">
                    {summary.hr_notifications_sent}
                  </div>
                </div>
              </div>

              {/* Section 1: Flagged Employees (Missed Hours or Absent with No Approved Leave) */}
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-rose-700">
                  1. Employees with Missed Hours or Unapproved Absence (HR Action Required)
                </h3>
                <table className="w-full text-left border-collapse text-xs border border-gray-200">
                  <thead>
                    <tr className="bg-gray-100 border-b border-gray-200 text-[11px] font-semibold text-gray-700">
                      <th className="py-2 px-2.5">Employee</th>
                      <th className="py-2 px-2.5">Department</th>
                      <th className="py-2 px-2.5">Clock-In / Out</th>
                      <th className="py-2 px-2.5">Worked / Req</th>
                      <th className="py-2 px-2.5">Leave Status</th>
                      <th className="py-2 px-2.5">Shortfall</th>
                      <th className="py-2 px-2.5">Status Badge</th>
                      <th className="py-2 px-2.5">HR Notice Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {employees
                      .filter((e) => e.hr_action_required)
                      .map((emp) => (
                        <tr key={emp.employee_id}>
                          <td className="py-2 px-2.5 font-semibold text-gray-900">
                            {emp.employee_name} ({emp.employee_id})
                          </td>
                          <td className="py-2 px-2.5 text-gray-700">{emp.department}</td>
                          <td className="py-2 px-2.5 font-mono">
                            {emp.clock_in || '—'} – {emp.clock_out || '—'}
                          </td>
                          <td className="py-2 px-2.5">
                            {emp.hours_worked.toFixed(2)}h / {emp.required_hours.toFixed(1)}h
                          </td>
                          <td className="py-2 px-2.5">{emp.leave_status}</td>
                          <td className="py-2 px-2.5 font-bold text-rose-700">
                            −{emp.hours_shortfall.toFixed(2)}h
                          </td>
                          <td className="py-2 px-2.5 font-semibold text-rose-700">
                            {emp.status_badge}
                          </td>
                          <td className="py-2 px-2.5">
                            {emp.notification_sent
                              ? `Sent (${emp.notification_ref})`
                              : 'Pending HR Notice'}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              {/* Section 2: Compliant Employees (Full Hours Completed or Covered by Approved Leave) */}
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-700">
                  2. Employees with Full Hours Completed or Covered by Approved Leave
                </h3>
                <table className="w-full text-left border-collapse text-xs border border-gray-200">
                  <thead>
                    <tr className="bg-gray-100 border-b border-gray-200 text-[11px] font-semibold text-gray-700">
                      <th className="py-2 px-2.5">Employee</th>
                      <th className="py-2 px-2.5">Department</th>
                      <th className="py-2 px-2.5">Clock-In / Out</th>
                      <th className="py-2 px-2.5">Worked / Req</th>
                      <th className="py-2 px-2.5">Leave Status</th>
                      <th className="py-2 px-2.5">Shortfall</th>
                      <th className="py-2 px-2.5">Status Badge</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {employees
                      .filter((e) => !e.hr_action_required)
                      .map((emp) => (
                        <tr key={emp.employee_id}>
                          <td className="py-2 px-2.5 font-semibold text-gray-900">
                            {emp.employee_name} ({emp.employee_id})
                          </td>
                          <td className="py-2 px-2.5 text-gray-700">{emp.department}</td>
                          <td className="py-2 px-2.5 font-mono">
                            {emp.clock_in || '—'} – {emp.clock_out || '—'}
                          </td>
                          <td className="py-2 px-2.5">
                            {emp.hours_worked.toFixed(2)}h / {emp.required_hours.toFixed(1)}h
                          </td>
                          <td className="py-2 px-2.5">{emp.leave_status}</td>
                          <td className="py-2 px-2.5 text-emerald-700 font-semibold">0.00h</td>
                          <td className="py-2 px-2.5 font-semibold text-emerald-700">
                            {emp.status_badge}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              {/* Sign-Off Footer */}
              <div className="pt-4 border-t border-gray-200 flex items-center justify-between text-xs text-gray-600">
                <div>
                  <strong>Reviewed By (HR Operations):</strong> {user.name} ({user.email})
                </div>
                <div>
                  <strong>Verification Status:</strong> Human-in-the-Loop Attendance &amp; Leave Check Complete
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
