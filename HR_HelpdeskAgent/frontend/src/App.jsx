import React, { useState, useEffect } from 'react';
import {
  MessageCircleQuestion,
  BookOpen,
  Send,
  Calendar,
  HeartPulse,
  Wallet,
  Car,
  Clock,
  Sun,
  CheckCircle2,
  ArrowRight,
  LogOut,
  FileText,
  UserCheck,
  Sparkles,
  PlusCircle,
  Check
} from 'lucide-react';
import SignInPage from './components/SignInPage';

const STORAGE_KEY = 'hr_helpdesk_agent_user_v1';

const CATEGORY_ICONS = {
  annual_maternity_leave: Calendar,
  medical_dental_insurance: HeartPulse,
  payroll_payslip: Wallet,
  transport_expense_claims: Car,
  working_hours_remote: Clock,
  public_holidays_compassionate: Sun,
};

export default function App() {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [activeTab, setActiveTab] = useState('helpdesk'); // 'helpdesk' | 'requests' | 'handbook'
  const [categories, setCategories] = useState([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState('annual_maternity_leave');
  const [questionInput, setQuestionInput] = useState('');
  const [asking, setAsking] = useState(false);
  const [agentAnswer, setAgentAnswer] = useState(null);

  const [requests, setRequests] = useState([]);
  const [summary, setSummary] = useState(null);

  // "Send Request to HR Team" modal / drawer state
  const [showRequestForm, setShowRequestForm] = useState(false);
  const [reqCategory, setReqCategory] = useState('annual_maternity_leave');
  const [reqSubject, setReqSubject] = useState('');
  const [reqDetails, setReqDetails] = useState('');
  const [submittingReq, setSubmittingReq] = useState(false);
  const [requestBanner, setRequestBanner] = useState('');

  // HR Team response input per request
  const [hrReplyText, setHrReplyText] = useState({});

  const loadInitialData = async () => {
    try {
      const [hbRes, reqRes] = await Promise.all([
        fetch('/api/handbook'),
        fetch('/api/helpdesk/requests'),
      ]);
      const hbData = await hbRes.json();
      const reqData = await reqRes.json();

      if (hbData.categories && hbData.categories.length > 0) {
        setCategories(hbData.categories);
        const firstCat = hbData.categories[0];
        setSelectedCategoryId(firstCat.id);
        setAgentAnswer({
          question: firstCat.sample_questions?.[0]?.q || `What is our policy on ${firstCat.title}?`,
          plain_english_answer:
            firstCat.sample_questions?.[0]?.a || firstCat.policy_rule,
          category_id: firstCat.id,
          category_title: firstCat.title,
          handbook_section: firstCat.handbook_section,
          policy_rule: firstCat.policy_rule,
          entitlements_at_a_glance: firstCat.entitlements_at_a_glance,
          steps_to_follow: firstCat.steps_to_follow,
          when_to_contact_hr: firstCat.when_to_contact_hr,
          suggested_request_subject: firstCat.suggested_request_subject,
        });
      }
      if (reqData.requests) {
        setRequests(reqData.requests);
      }
      if (reqData.summary || hbData.summary) {
        setSummary(reqData.summary || hbData.summary);
      }
    } catch (err) {
      console.error('Failed to load HR Helpdesk data:', err);
    }
  };

  useEffect(() => {
    if (user) {
      loadInitialData();
    }
  }, [user]);

  const handleSignIn = (authenticatedUser) => {
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

  if (!user) {
    return <SignInPage onSignIn={handleSignIn} />;
  }

  const handleSelectCategoryCard = (cat) => {
    setSelectedCategoryId(cat.id);
    setRequestBanner('');
    const sampleQ = cat.sample_questions?.[0]?.q || `What are the rules for ${cat.title}?`;
    const sampleA = cat.sample_questions?.[0]?.a || cat.policy_rule;
    setAgentAnswer({
      question: sampleQ,
      plain_english_answer: sampleA,
      category_id: cat.id,
      category_title: cat.title,
      handbook_section: cat.handbook_section,
      policy_rule: cat.policy_rule,
      entitlements_at_a_glance: cat.entitlements_at_a_glance,
      steps_to_follow: cat.steps_to_follow,
      when_to_contact_hr: cat.when_to_contact_hr,
      suggested_request_subject: cat.suggested_request_subject,
    });
  };

  const handleAskQuestion = async (customQuestion, customCategoryId) => {
    const qText = (customQuestion !== undefined ? customQuestion : questionInput).trim();
    if (!qText) return;
    setAsking(true);
    setRequestBanner('');
    try {
      const res = await fetch('/api/helpdesk/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: qText,
          category_id: customCategoryId || null,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setAgentAnswer(data);
        if (data.category_id) {
          setSelectedCategoryId(data.category_id);
        }
        if (customQuestion === undefined) {
          setQuestionInput('');
        }
      }
    } catch (err) {
      console.error('Failed to ask HR Helpdesk Agent:', err);
    } finally {
      setAsking(false);
    }
  };

  const openSendToHrModal = () => {
    const catId = agentAnswer?.category_id || selectedCategoryId || 'annual_maternity_leave';
    setReqCategory(catId);
    setReqSubject(
      agentAnswer?.suggested_request_subject ||
        `Personal HR Assistance: ${agentAnswer?.category_title || 'General HR Inquiry'}`
    );
    setReqDetails(
      agentAnswer?.question
        ? `Following up on my question ("${agentAnswer.question}"): I would appreciate personal help from the HR team with `
        : ''
    );
    setShowRequestForm(true);
  };

  const handleCreateHrRequest = async (e) => {
    e.preventDefault();
    if (!reqSubject.trim() || !reqDetails.trim()) return;
    setSubmittingReq(true);
    try {
      const res = await fetch('/api/helpdesk/requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          employee_name: user.name || 'Alex Mwangi',
          employee_email: user.email || 'alex.mwangi@sybyl.com',
          department: user.department || 'Product & Engineering',
          category_id: reqCategory,
          subject: reqSubject.trim(),
          details: reqDetails.trim(),
        }),
      });
      const data = await res.json();
      if (res.ok && data.request) {
        setRequests((prev) => [data.request, ...prev]);
        if (data.summary) setSummary(data.summary);
        setShowRequestForm(false);
        setRequestBanner(
          `Request ${data.request.request_id} ("${data.request.subject}") has been sent to the HR Team.`
        );
      }
    } catch (err) {
      console.error('Error creating HR request:', err);
    } finally {
      setSubmittingReq(false);
    }
  };

  const handleResolveRequest = async (requestId) => {
    try {
      const customNote = (hrReplyText[requestId] || '').trim();
      const res = await fetch(`/api/helpdesk/requests/${requestId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'Resolved',
          hr_owner: user.name || 'People Services Desk',
          hr_response:
            customNote ||
            `Resolved by ${user.name || 'HR Team'}. Confirmation sent to employee.`,
        }),
      });
      const data = await res.json();
      if (res.ok && data.request) {
        setRequests((prev) =>
          prev.map((item) => (item.request_id === data.request.request_id ? data.request : item))
        );
        if (data.summary) setSummary(data.summary);
      }
    } catch (err) {
      console.error('Failed to resolve HR request:', err);
    }
  };

  const currentCategory =
    categories.find((c) => c.id === selectedCategoryId) || categories[0] || null;

  return (
    <div className="min-h-screen bg-[#F5F5F7] text-[#1D1D1F] flex flex-col">
      {/* Apple-Inspired Sticky Header */}
      <header className="apple-glass sticky top-0 z-20 no-print">
        <div className="max-w-6xl mx-auto px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-2xl bg-[#0071E3] text-white flex items-center justify-center shadow-xs">
              <MessageCircleQuestion className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200/80">
                  Agent #07 • Employee Self-Service
                </span>
                <span className="text-xs text-neutral-500 hidden sm:inline">
                  Official Employee Handbook &amp; HR Support Desk
                </span>
              </div>
              <h1 className="text-base sm:text-lg font-bold tracking-tight text-[#1D1D1F]">
                Employee HR Helpdesk Agent
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <div className="text-xs font-semibold text-[#1D1D1F]">{user.name}</div>
              <div className="text-[11px] text-neutral-500">{user.email}</div>
            </div>
            <button
              onClick={handleSignOut}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-neutral-700 bg-white hover:bg-neutral-100 border border-neutral-200/90 transition cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>

        {/* Clean 3-Tab Navigation Strip */}
        <div className="max-w-6xl mx-auto px-6 flex overflow-x-auto gap-2 border-t border-neutral-200/60 py-2.5">
          {[
            {
              id: 'helpdesk',
              label: 'Ask HR Helpdesk Agent',
              icon: MessageCircleQuestion,
            },
            {
              id: 'requests',
              label: `My HR Team Requests (${requests.length})`,
              icon: UserCheck,
            },
            {
              id: 'handbook',
              label: 'Complete Employee Handbook Reference',
              icon: BookOpen,
            },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition cursor-pointer ${
                  active
                    ? 'bg-[#0071E3] text-white shadow-xs'
                    : 'text-neutral-600 hover:bg-white/80'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Container */}
      <main className="max-w-6xl mx-auto px-6 py-7 w-full flex-1 space-y-6">
        {/* Confirmation Banner when an HR Request is created */}
        {requestBanner && (
          <div className="apple-card rounded-2xl p-4 border-l-4 border-l-emerald-600 bg-emerald-50/70 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 text-xs font-semibold text-emerald-900">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{requestBanner}</span>
            </div>
            <button
              onClick={() => setActiveTab('requests')}
              className="px-3.5 py-1.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold transition cursor-pointer"
            >
              Track Request Status →
            </button>
          </div>
        )}

        {/* TAB 1: Ask HR Helpdesk Agent (Core Focused Experience) */}
        {activeTab === 'helpdesk' && (
          <div className="space-y-6">
            {/* Search / Plain-English Question Bar */}
            <div className="apple-card rounded-3xl p-6 sm:p-7 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#0071E3]">
                    Step 1 • Ask in Plain English or Pick a Topic Below
                  </span>
                  <h2 className="text-xl font-bold text-[#1D1D1F] mt-0.5">
                    How can the Employee HR Helpdesk Agent help you today?
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={openSendToHrModal}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-[#0071E3] bg-blue-50 hover:bg-blue-100/80 border border-blue-200/80 transition cursor-pointer"
                >
                  <PlusCircle className="w-3.5 h-3.5" />
                  <span>Send Request to HR Team</span>
                </button>
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAskQuestion();
                }}
                className="flex flex-col sm:flex-row gap-3"
              >
                <input
                  type="text"
                  value={questionInput}
                  onChange={(e) => setQuestionInput(e.target.value)}
                  placeholder="Ask any HR question (e.g., How many annual leave days do I get? What is my dental limit? When is payday?)..."
                  className="flex-1 px-4 py-3.5 rounded-2xl bg-[#F5F5F7] border border-neutral-300/90 text-sm text-[#1D1D1F] focus:bg-white focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 outline-none transition"
                />
                <button
                  type="submit"
                  disabled={asking}
                  className="px-6 py-3.5 rounded-2xl bg-[#0071E3] hover:bg-[#0077ED] disabled:opacity-60 text-white font-semibold text-sm shadow-xs transition inline-flex items-center justify-center gap-2 cursor-pointer shrink-0"
                >
                  <Send className="w-4 h-4" />
                  <span>{asking ? 'Checking Handbook...' : 'Ask HR Helpdesk Agent'}</span>
                </button>
              </form>

              {/* 6 Simple Category Cards */}
              <div className="pt-2">
                <div className="text-xs font-semibold text-neutral-500 mb-3">
                  Or click a topic from the Official Employee Handbook:
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {categories.map((cat) => {
                    const IconComponent = CATEGORY_ICONS[cat.id] || BookOpen;
                    const isSelected = selectedCategoryId === cat.id;
                    return (
                      <button
                        key={cat.id}
                        type="button"
                        onClick={() => handleSelectCategoryCard(cat)}
                        className={`text-left p-4 rounded-2xl border transition-all cursor-pointer flex items-start gap-3.5 ${
                          isSelected
                            ? 'bg-blue-50/70 border-[#0071E3] shadow-xs'
                            : 'bg-[#F5F5F7]/70 hover:bg-white border-neutral-200/90'
                        }`}
                      >
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                            isSelected
                              ? 'bg-[#0071E3] text-white'
                              : 'bg-white text-[#0071E3] border border-neutral-200/80'
                          }`}
                        >
                          <IconComponent className="w-4 h-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-bold text-[#1D1D1F] leading-snug">
                            {cat.title}
                          </div>
                          <div className="text-[11px] text-neutral-500 mt-1 line-clamp-2 leading-relaxed">
                            {cat.short_description}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Instant Handbook-Backed Answer Card */}
            {agentAnswer && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* Left 8 Columns: Answer, Official Policy Rule & Entitlements at a Glance */}
                <div className="lg:col-span-8 apple-card rounded-3xl p-6 sm:p-7 space-y-6">
                  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-neutral-100 pb-4">
                    <div className="space-y-1">
                      <div className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#0071E3] bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200/70">
                        <BookOpen className="w-3.5 h-3.5" />
                        <span>{agentAnswer.handbook_section}</span>
                      </div>
                      <h3 className="text-lg font-bold text-[#1D1D1F] mt-1">
                        {agentAnswer.question}
                      </h3>
                    </div>
                    <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                      Official Policy Verified
                    </span>
                  </div>

                  {/* Plain-English Answer */}
                  <div className="p-4 sm:p-5 rounded-2xl bg-blue-50/50 border border-blue-200/70 space-y-1.5">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-[#0071E3] flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>HR Helpdesk Agent Answer</span>
                    </div>
                    <p className="text-sm text-[#1D1D1F] leading-relaxed font-medium">
                      {agentAnswer.plain_english_answer.replace(/\*\*/g, '')}
                    </p>
                  </div>

                  {/* Key Entitlement Numbers at a Glance */}
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-3">
                      Key Entitlement Numbers at a Glance ({agentAnswer.category_title})
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {(agentAnswer.entitlements_at_a_glance || []).map((ent, idx) => (
                        <div
                          key={idx}
                          className="p-3.5 rounded-2xl bg-[#F5F5F7] border border-neutral-200/80"
                        >
                          <div className="text-[11px] font-medium text-neutral-500">
                            {ent.label}
                          </div>
                          <div className="text-sm font-bold text-[#1D1D1F] mt-0.5">
                            {ent.value}
                          </div>
                          <div className="text-[11px] text-neutral-600 mt-0.5">
                            {ent.note}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Exact Official Handbook Rule */}
                  <div className="p-4 rounded-2xl bg-[#F5F5F7] border border-neutral-200/80 space-y-1">
                    <div className="text-xs font-bold text-[#1D1D1F]">
                      Exact Employee Handbook Rule
                    </div>
                    <p className="text-xs text-neutral-600 leading-relaxed">
                      {agentAnswer.policy_rule}
                    </p>
                  </div>

                  {/* Steps to Follow */}
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2.5">
                      Simple Steps to Follow
                    </h4>
                    <ol className="space-y-2">
                      {(agentAnswer.steps_to_follow || []).map((stepText, idx) => (
                        <li
                          key={idx}
                          className="flex items-start gap-2.5 text-xs text-neutral-700 leading-relaxed"
                        >
                          <span className="w-5 h-5 rounded-full bg-[#0071E3] text-white text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                            {idx + 1}
                          </span>
                          <span>{stepText}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>

                {/* Right 4 Columns: Common Questions in This Topic + 1-Click Send Request to HR Team */}
                <div className="lg:col-span-4 space-y-5">
                  {/* Common Questions for Selected Category */}
                  {currentCategory && (
                    <div className="apple-card rounded-3xl p-5 space-y-3.5">
                      <div className="text-xs font-bold uppercase tracking-wider text-neutral-500">
                        Common Questions • {currentCategory.title}
                      </div>
                      <div className="space-y-2">
                        {(currentCategory.sample_questions || []).map((sq, i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => handleAskQuestion(sq.q, currentCategory.id)}
                            className="w-full text-left p-3 rounded-2xl bg-[#F5F5F7] hover:bg-blue-50/70 border border-neutral-200/80 hover:border-blue-200 text-xs font-medium text-[#1D1D1F] transition flex items-start justify-between gap-2 cursor-pointer"
                          >
                            <span className="leading-relaxed">{sq.q}</span>
                            <ArrowRight className="w-3.5 h-3.5 text-[#0071E3] shrink-0 mt-0.5" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Need Personal Human Help? Send Request to HR Team */}
                  <div className="apple-card rounded-3xl p-5 space-y-3.5">
                    <div className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#0071E3] bg-blue-50 px-2.5 py-0.5 rounded-full">
                      <UserCheck className="w-3.5 h-3.5" />
                      <span>Need Personal HR Assistance?</span>
                    </div>
                    <h4 className="text-sm font-bold text-[#1D1D1F]">
                      Forward to the HR Team in One Click
                    </h4>
                    <p className="text-xs text-neutral-600 leading-relaxed">
                      {agentAnswer.when_to_contact_hr}
                    </p>
                    <button
                      type="button"
                      onClick={openSendToHrModal}
                      className="w-full py-3 px-4 rounded-2xl bg-[#0071E3] hover:bg-[#0077ED] text-white font-semibold text-xs shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>Send Request to HR Team</span>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: My HR Team Requests (Status Tracker & HR Follow-Up) */}
        {activeTab === 'requests' && (
          <div className="space-y-5">
            <div className="apple-card rounded-3xl p-6 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-[#1D1D1F]">
                  HR Helpdesk Requests &amp; Status Tracker
                </h2>
                <p className="text-xs text-neutral-500 mt-0.5">
                  Personal requests sent to the HR Team with reference numbers, handbook references, and live status updates.
                </p>
              </div>
              <button
                type="button"
                onClick={openSendToHrModal}
                className="px-4 py-2.5 rounded-2xl bg-[#0071E3] hover:bg-[#0077ED] text-white text-xs font-semibold shadow-xs transition inline-flex items-center gap-2 cursor-pointer"
              >
                <PlusCircle className="w-4 h-4" />
                <span>Send Request to HR Team</span>
              </button>
            </div>

            <div className="space-y-4">
              {requests.map((req) => {
                const isResolved = req.status === 'Resolved';
                return (
                  <div
                    key={req.request_id}
                    className="apple-card rounded-3xl p-6 space-y-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-neutral-100 pb-3.5">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xs font-bold px-2.5 py-0.5 rounded-lg bg-blue-50 text-[#0071E3] border border-blue-200/80">
                            {req.request_id}
                          </span>
                          <span className="text-xs font-medium text-neutral-500">
                            {req.category_title}
                          </span>
                          <span className="text-xs text-neutral-400">• {req.created_at}</span>
                        </div>
                        <h3 className="text-base font-bold text-[#1D1D1F] mt-1.5">
                          {req.subject}
                        </h3>
                        <p className="text-xs text-neutral-500 mt-0.5">
                          Employee: <span className="font-semibold text-neutral-700">{req.employee_name}</span> ({req.department}) • {req.handbook_reference}
                        </p>
                      </div>

                      <span
                        className={`px-3 py-1 rounded-full text-xs font-semibold border ${
                          isResolved
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : req.status === 'In Progress'
                            ? 'bg-amber-50 text-amber-800 border-amber-200'
                            : 'bg-blue-50 text-[#0071E3] border-blue-200'
                        }`}
                      >
                        {req.status}
                      </span>
                    </div>

                    <div className="text-xs text-neutral-700 leading-relaxed bg-[#F5F5F7] p-4 rounded-2xl border border-neutral-200/70">
                      <div className="font-semibold text-neutral-900 mb-1">Employee Request Details:</div>
                      {req.details}
                    </div>

                    <div className="p-4 rounded-2xl bg-emerald-50/50 border border-emerald-200/80 text-xs space-y-1">
                      <div className="font-bold text-emerald-900 flex items-center gap-1.5">
                        <UserCheck className="w-3.5 h-3.5 text-emerald-700" />
                        <span>HR Team Update ({req.hr_owner}):</span>
                      </div>
                      <p className="text-emerald-950 leading-relaxed">{req.hr_response}</p>
                    </div>

                    {!isResolved && (
                      <div className="pt-1 flex flex-col sm:flex-row gap-2.5">
                        <input
                          type="text"
                          value={hrReplyText[req.request_id] || ''}
                          onChange={(e) =>
                            setHrReplyText({ ...hrReplyText, [req.request_id]: e.target.value })
                          }
                          placeholder="Add an HR Team response note to resolve this request..."
                          className="flex-1 px-3.5 py-2 rounded-xl bg-[#F5F5F7] border border-neutral-300 text-xs outline-none focus:bg-white focus:border-[#0071E3]"
                        />
                        <button
                          type="button"
                          onClick={() => handleResolveRequest(req.request_id)}
                          className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition inline-flex items-center justify-center gap-1.5 cursor-pointer shrink-0"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Mark Resolved</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* TAB 3: Complete Employee Handbook Reference */}
        {activeTab === 'handbook' && (
          <div className="space-y-5">
            <div className="apple-card rounded-3xl p-6">
              <h2 className="text-lg font-bold text-[#1D1D1F]">
                Official Employee Handbook Knowledge Base
              </h2>
              <p className="text-xs text-neutral-500 mt-0.5">
                All 6 core company HR policies with clear rules, entitlement figures, and steps for employees.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {categories.map((cat) => (
                <div key={cat.id} className="apple-card rounded-3xl p-6 space-y-4">
                  <div>
                    <span className="text-[11px] font-semibold text-[#0071E3] bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200/70">
                      {cat.handbook_section}
                    </span>
                    <h3 className="text-base font-bold text-[#1D1D1F] mt-2">{cat.title}</h3>
                    <p className="text-xs text-neutral-600 mt-1 leading-relaxed">
                      {cat.policy_rule}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {cat.entitlements_at_a_glance.map((e, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl bg-[#F5F5F7] border border-neutral-200/70"
                      >
                        <div className="text-[11px] text-neutral-500">{e.label}</div>
                        <div className="text-xs font-bold text-[#1D1D1F] mt-0.5">{e.value}</div>
                      </div>
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      handleSelectCategoryCard(cat);
                      setActiveTab('helpdesk');
                    }}
                    className="w-full py-2.5 px-4 rounded-xl bg-[#F5F5F7] hover:bg-blue-50 text-xs font-semibold text-[#0071E3] border border-neutral-200/80 transition cursor-pointer"
                  >
                    Ask Questions About {cat.title} →
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Modal: Send Request to HR Team */}
      {showRequestForm && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="apple-card rounded-3xl max-w-lg w-full p-6 sm:p-7 space-y-5 bg-white">
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[#0071E3]">
                  Personal HR Team Assistance
                </span>
                <h3 className="text-lg font-bold text-[#1D1D1F] mt-0.5">
                  Send Request to HR Team
                </h3>
                <p className="text-xs text-neutral-500 mt-0.5">
                  Creates a tracked HR Helpdesk Request for personal follow-up by People Services.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowRequestForm(false)}
                className="text-xs font-semibold text-neutral-400 hover:text-neutral-700 cursor-pointer"
              >
                Close ✕
              </button>
            </div>

            <form onSubmit={handleCreateHrRequest} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-neutral-700 mb-1">
                  HR Topic
                </label>
                <select
                  value={reqCategory}
                  onChange={(e) => setReqCategory(e.target.value)}
                  className="w-full rounded-xl bg-[#F5F5F7] border border-neutral-300 px-3.5 py-2.5 text-xs outline-none focus:bg-white focus:border-[#0071E3]"
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-semibold text-neutral-700 mb-1">
                  Subject
                </label>
                <input
                  type="text"
                  required
                  value={reqSubject}
                  onChange={(e) => setReqSubject(e.target.value)}
                  placeholder="e.g., Add newborn dependent to Medical Insurance cover"
                  className="w-full rounded-xl bg-[#F5F5F7] border border-neutral-300 px-3.5 py-2.5 text-xs outline-none focus:bg-white focus:border-[#0071E3]"
                />
              </div>

              <div>
                <label className="block font-semibold text-neutral-700 mb-1">
                  How can the HR Team help you?
                </label>
                <textarea
                  rows={4}
                  required
                  value={reqDetails}
                  onChange={(e) => setReqDetails(e.target.value)}
                  placeholder="Provide any helpful details (such as dates, dependent name, or payslip month)..."
                  className="w-full rounded-xl bg-[#F5F5F7] border border-neutral-300 px-3.5 py-2.5 text-xs outline-none focus:bg-white focus:border-[#0071E3]"
                />
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRequestForm(false)}
                  className="px-4 py-2.5 rounded-xl bg-neutral-100 hover:bg-neutral-200 text-neutral-700 font-semibold transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReq}
                  className="px-5 py-2.5 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white font-semibold shadow-xs transition inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{submittingReq ? 'Sending...' : 'Send Request to HR Team'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
