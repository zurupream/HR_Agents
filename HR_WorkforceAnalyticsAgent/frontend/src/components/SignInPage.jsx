import React, { useState, useEffect, useRef } from 'react';
import {
  Users,
  Sliders,
  MessageSquareText,
  ShieldCheck,
  Lock,
  Mail,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Building2,
  Play,
} from 'lucide-react';

const GOOGLE_CLIENT_ID = '259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com';

export const APPLE_READING_THEMES = [
  { id: 'daylight', label: 'Daylight', swatch: '#F5F5F7', border: '#D2D2D7' },
  { id: 'sand', label: 'Sand', swatch: '#F7F5F0', border: '#D4CFC3' },
  { id: 'dusk', label: 'Dusk', swatch: '#1C1E26', border: '#3E4251' },
  { id: 'midnight', label: 'Midnight', swatch: '#0B0C10', border: '#2D3142' },
];

export function AppleAppearanceSwitcher({ theme, onSelectTheme }) {
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-card)] shadow-2xs"
      role="radiogroup"
      aria-label="Appearance Theme"
    >
      <span className="text-[10px] font-semibold tracking-tight text-[var(--text-muted)] pr-0.5 hidden sm:inline">
        Theme
      </span>
      {APPLE_READING_THEMES.map((item) => {
        const active = theme === item.id;
        return (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={`${item.label} theme`}
            title={item.label}
            onClick={() => onSelectTheme(item.id)}
            className={`w-4 h-4 rounded-full transition-all cursor-pointer flex items-center justify-center ${
              active
                ? 'ring-2 ring-[#0071E3] ring-offset-1 ring-offset-[var(--bg-card)] scale-110'
                : 'opacity-80 hover:opacity-100 hover:scale-105'
            }`}
            style={{
              backgroundColor: item.swatch,
              border: `1px solid ${item.border}`,
            }}
          />
        );
      })}
    </div>
  );
}

export default function SignInPage({ onSuccess, theme = 'sand', onSelectTheme = () => {} }) {
  const [email, setEmail] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const googleBtnRef = useRef(null);

  useEffect(() => {
    const scriptId = 'google-identity-services';
    const initializeGoogle = () => {
      if (window.google?.accounts?.id && googleBtnRef.current) {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleGoogleCredentialResponse,
        });
        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: 'outline',
          size: 'large',
          width: 340,
          text: 'continue_with',
          shape: 'pill',
        });
      }
    };

    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = initializeGoogle;
      document.body.appendChild(script);
    } else {
      initializeGoogle();
    }
  }, []);

  const handleGoogleCredentialResponse = async (response) => {
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: response.credential }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Google Single Sign-On failed');
      }
      onSuccess(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInstantDemoSignIn = async () => {
    setError('');
    setDemoLoading(true);
    try {
      const res = await fetch('/api/auth/demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: 'CHRO / Executive View' }),
      });
      if (res.ok) {
        const data = await res.json();
        onSuccess(data.user);
        return;
      }
    } catch {
      // Fallback if network request fails
    } finally {
      setDemoLoading(false);
    }
    onSuccess({
      email: 'grace.njeri@sybyl.com',
      name: 'Grace Njeri (CHRO)',
      role: 'CHRO / Executive View',
      auth_method: 'instant_demo_sso',
    });
  };

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    setError('');
    setStatusMessage('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/otp/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Could not send verification code.');
      }
      setOtpSent(true);
      setStatusMessage(data.message || `6-digit verification code sent to ${email}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/otp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code: otpCode }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Invalid or expired verification code.');
      }
      onSuccess(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const workflowSteps = [
    {
      step: '01',
      badge: 'Step 1 • Live People Metrics',
      title: 'Step 1: Live Workforce & Turnover Overview',
      desc: 'Consolidates headcount, department attrition, hiring speed, and monthly payroll cost in plain business English across Engineering, Sales & Commercial, Customer Operations, Finance & Admin, and People & Culture.',
      metrics: ['480 Active Headcount', '13.8% Annual Attrition Rate', '$3.04M Monthly Payroll Cost'],
      icon: Users,
      accent: 'from-[#0071E3] to-blue-700',
      pillBg: 'bg-blue-50 text-[#0071E3] border-blue-200',
    },
    {
      step: '02',
      badge: 'Step 2 • What-If Scenario Planning',
      title: 'Step 2: Interactive Salary & Attrition Stress-Test',
      desc: 'Adjust salary review %, projected turnover %, and planned new hires sliders to see immediate annual payroll impact and replacement-cost savings calculated deterministically.',
      metrics: ['Annual Salary Increment % Slider', 'Projected Turnover % Slider', 'Exact Replacement Cost Impact'],
      icon: Sliders,
      accent: 'from-emerald-600 to-teal-600',
      pillBg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    },
    {
      step: '03',
      badge: 'Step 3 • Executive People Q&A',
      title: 'Step 3: Ask the Workforce Agent & Board Summary',
      desc: 'Ask plain-English questions about workforce trends, retention priorities, or hiring speed, and print a clean 1-Page Executive People Summary for the CEO, CHRO, and CFO.',
      metrics: ['Ask Workforce Agent in Plain English', '1-Page CHRO Boardroom Summary', 'Zero Technical Jargon'],
      icon: MessageSquareText,
      accent: 'from-indigo-600 to-purple-600',
      pillBg: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    },
  ];

  return (
    <div className="min-h-screen bg-[#F5F5F7] text-[#1D1D1F] flex flex-col justify-between">
      {/* Frosted-Glass Apple Header */}
      <header className="apple-glass sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#0071E3] flex items-center justify-center text-white shadow-xs">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-tight text-[#1D1D1F]">
                  Workforce Analytics Agent
                </span>
                <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200">
                  HR Agent #09 • CHRO &amp; CEO Suite
                </span>
              </div>
              <p className="text-xs text-gray-500">
                Executive &ldquo;Talk-to-Your-Workforce&rdquo; &amp; Attrition Stress-Test Agent
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-600">
            <span className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 font-medium border border-emerald-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Live Workforce &amp; Payroll Feed
            </span>
            <span className="hidden md:inline text-gray-300">|</span>
            <span className="hidden md:inline font-medium text-gray-700">CHRO • CEO • CFO Boardroom View</span>
            <AppleAppearanceSwitcher theme={theme} onSelectTheme={onSelectTheme} />
          </div>
        </div>
      </header>

      {/* Main Split Container */}
      <main className="max-w-7xl mx-auto px-6 py-8 lg:py-10 flex-1 flex items-center">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center w-full">
          {/* LEFT PANEL (7/12): High-Level 3-Step Visual Workflow Diagram */}
          <div className="lg:col-span-7 space-y-5">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white border border-gray-200 shadow-2xs text-xs font-semibold text-gray-700">
                <Sparkles className="w-3.5 h-3.5 text-[#0071E3]" />
                3-Step Executive People Analytics Workflow
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#1D1D1F] leading-tight">
                Talk to Your Workforce &amp; Stress-Test Your People Budget in Plain English
              </h1>
              <p className="text-sm text-gray-600 leading-relaxed">
                Built for the Chief Human Resources Officer, Chief Executive Officer, and Chief Financial Officer to inspect live headcount, department attrition, and salary review scenarios in seconds.
              </p>
            </div>

            {/* 3-Step Visual Workflow Cards */}
            <div className="space-y-3.5">
              {workflowSteps.map((item) => {
                const IconComponent = item.icon;
                return (
                  <div
                    key={item.step}
                    className="apple-card rounded-2xl p-4 sm:p-5 hover:shadow-md transition-all relative overflow-hidden"
                  >
                    <div className="flex items-start gap-4">
                      <div
                        className={`w-11 h-11 rounded-xl bg-gradient-to-br ${item.accent} text-white flex items-center justify-center shrink-0 shadow-xs`}
                      >
                        <IconComponent className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                          <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${item.pillBg}`}>
                            {item.badge}
                          </span>
                          <span className="text-xs font-bold text-gray-400">STEP {item.step} OF 03</span>
                        </div>
                        <h3 className="text-sm sm:text-base font-bold text-[#1D1D1F] mb-1">
                          {item.title}
                        </h3>
                        <p className="text-xs text-gray-600 leading-relaxed mb-3">
                          {item.desc}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {item.metrics.map((m) => (
                            <span
                              key={m}
                              className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-1 rounded-lg bg-[#F5F5F7] text-[#1D1D1F]"
                            >
                              <CheckCircle2 className="w-3 h-3 text-[#0071E3]" />
                              {m}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* RIGHT PANEL (5/12): Single Sign-On (SSO) Card */}
          <div className="lg:col-span-5">
            <div className="apple-card rounded-3xl p-6 sm:p-8 shadow-xl">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-[#0071E3]">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-[#1D1D1F]">Executive Sign-In</h2>
                    <p className="text-xs text-gray-500">Google Workspace SSO or Work Email Code</p>
                  </div>
                </div>
                <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-[#F5F5F7] text-gray-700">
                  Single Sign-On
                </span>
              </div>

              {error && (
                <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {statusMessage && (
                <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>{statusMessage}</span>
                </div>
              )}

              {/* 1-Click Instant Demo Sign-In (CHRO / Executive View) */}
              <div className="mb-5">
                <button
                  type="button"
                  onClick={handleInstantDemoSignIn}
                  disabled={demoLoading}
                  className="w-full py-3 px-4 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white font-semibold text-sm shadow-sm transition flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Play className="w-4 h-4 fill-current" />
                  {demoLoading
                    ? 'Opening CHRO Executive View...'
                    : 'Instant Demo Sign-In (CHRO / Executive View)'}
                </button>
                <p className="text-[11px] text-center text-gray-500 mt-1.5">
                  One-click boardroom preview with live 480-employee dataset
                </p>
              </div>

              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-white px-3 text-gray-400 font-medium">
                    OR GOOGLE WORKSPACE SSO
                  </span>
                </div>
              </div>

              {/* Google Single Sign-On Button */}
              <div className="mb-4">
                <div className="flex justify-center" ref={googleBtnRef} />
              </div>

              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-white px-3 text-gray-400 font-medium">
                    OR WORK EMAIL 6-DIGIT CODE
                  </span>
                </div>
              </div>

              {!otpSent ? (
                <form onSubmit={handleRequestOtp} className="space-y-3.5">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                      Work Email Address
                    </label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" />
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="chro@company.com"
                        className="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl border border-gray-300 focus:border-[#0071E3] focus:ring-2 focus:ring-blue-100 outline-none transition"
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-xl bg-[#1D1D1F] hover:bg-gray-800 disabled:opacity-60 text-white font-semibold text-sm shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
                  >
                    {loading ? 'Sending Verification Code...' : 'Send 6-Digit Verification Code'}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyOtp} className="space-y-3.5">
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-semibold text-gray-700">
                        Enter 6-Digit Code Sent to {email}
                      </label>
                      <button
                        type="button"
                        onClick={() => {
                          setOtpSent(false);
                          setOtpCode('');
                          setStatusMessage('');
                        }}
                        className="text-xs text-[#0071E3] hover:underline font-medium"
                      >
                        Change email
                      </button>
                    </div>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" />
                      <input
                        type="text"
                        required
                        maxLength={6}
                        value={otpCode}
                        onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                        placeholder="123456"
                        className="w-full pl-10 pr-4 py-2.5 text-sm tracking-widest font-mono rounded-xl border border-gray-300 focus:border-[#0071E3] focus:ring-2 focus:ring-blue-100 outline-none transition"
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={loading || otpCode.length < 6}
                    className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold text-sm shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
                  >
                    {loading ? 'Verifying Code...' : 'Verify & Open Workforce Agent'}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </form>
              )}

              <div className="mt-6 pt-4 border-t border-gray-100 flex items-center justify-between text-[11px] text-gray-500">
                <span className="inline-flex items-center gap-1">
                  <Building2 className="w-3.5 h-3.5 text-gray-400" />
                  Enterprise People &amp; Payroll Privacy
                </span>
                <span>For CEO • CHRO • CFO</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-gray-200/70 bg-white py-3 px-6 text-xs text-gray-500">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
          <span>Enterprise HR AI Agent Portfolio • Agent #09: Workforce Analytics Agent</span>
          <AppleAppearanceSwitcher theme={theme} onSelectTheme={onSelectTheme} />
        </div>
      </footer>
    </div>
  );
}
