import React, { useState, useEffect, useRef } from 'react';
import {
  BookOpen,
  MessageCircleQuestion,
  CheckCircle2,
  Mail,
  KeyRound,
  ArrowRight,
  AlertCircle,
  Lock,
  Sparkles,
  UserCheck
} from 'lucide-react';

const GOOGLE_CLIENT_ID = '259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com';

export default function SignInPage({ onSignIn }) {
  const [email, setEmail] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [step, setStep] = useState('request'); // 'request' | 'verify'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  const googleBtnRef = useRef(null);

  useEffect(() => {
    const initGoogle = () => {
      if (window.google && window.google.accounts && googleBtnRef.current) {
        try {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: handleGoogleResponse,
          });
          window.google.accounts.id.renderButton(googleBtnRef.current, {
            theme: 'outline',
            size: 'large',
            width: 340,
            text: 'signin_with',
            shape: 'pill',
          });
        } catch (err) {
          console.error('Google Sign-In initialization error:', err);
        }
      }
    };

    const timer = setInterval(() => {
      if (window.google && window.google.accounts) {
        initGoogle();
        clearInterval(timer);
      }
    }, 300);

    return () => clearInterval(timer);
  }, []);

  const handleGoogleResponse = async (response) => {
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
        throw new Error(data.detail || 'Google Single Sign-On failed.');
      }
      onSignIn(data.user);
    } catch (err) {
      setError(err.message || 'Unable to sign in with Google.');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    setError('');
    setInfoMessage('');
    if (!email.trim()) {
      setError('Please enter your work email address.');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/auth/otp/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to send verification code.');
      }
      setInfoMessage(data.message || `6-digit code sent to ${email}`);
      if (data.demo_otp_hint) {
        setOtpCode(data.demo_otp_hint);
      }
      setStep('verify');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setError('');
    if (!otpCode.trim()) {
      setError('Please enter the 6-digit verification code.');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch('/api/auth/otp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), code: otpCode.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Invalid or expired verification code.');
      }
      onSignIn(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleInstantDemoSignIn = async (viewMode = 'employee') => {
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ view_mode: viewMode }),
      });
      const data = await res.json();
      if (res.ok && data.user) {
        onSignIn(data.user);
      } else {
        onSignIn({
          name: 'Alex Mwangi',
          email: 'alex.mwangi@sybyl.com',
          department: 'Product & Engineering',
          role: 'Employee & HR View',
          auth_method: 'instant_demo',
        });
      }
    } catch {
      onSignIn({
        name: 'Alex Mwangi',
        email: 'alex.mwangi@sybyl.com',
        department: 'Product & Engineering',
        role: 'Employee & HR View',
        auth_method: 'instant_demo',
      });
    } finally {
      setLoading(false);
    }
  };

  const workflowSteps = [
    {
      num: 'Step 1',
      title: 'Step 1: Employee Asks a Question',
      desc: 'Select a common HR topic (Annual & Maternity/Paternity Leave, Medical Cover, Payroll Dates, Expense Claims, Working Hours, or Public Holidays) or ask in everyday language.',
      badge: 'Plain Everyday English',
      icon: MessageCircleQuestion,
      highlights: ['6 Quick HR Topic Cards', 'Ask Any Everyday HR Question'],
    },
    {
      num: 'Step 2',
      title: 'Step 2: HR Helpdesk Agent Checks Official Handbook',
      desc: 'Provides an instant, accurate answer backed by the Official Employee Handbook with key entitlement numbers at a glance and simple next steps.',
      badge: 'Official Employee Handbook',
      icon: BookOpen,
      highlights: ['Exact Handbook Policy Rule', 'Entitlement Numbers at a Glance'],
    },
    {
      num: 'Step 3',
      title: 'Step 3: Instant Resolution or HR Team Follow-Up',
      desc: 'Your question is answered immediately, or forwarded to the HR team in one click ("Send Request to HR Team") if personal human action is required.',
      badge: '1-Click HR Support Tracker',
      icon: UserCheck,
      highlights: ['Resolves 70%+ Questions Instantly', 'Tracked Reference Number & Status'],
    },
  ];

  return (
    <div className="min-h-screen bg-[#F5F5F7] text-[#1D1D1F] flex flex-col justify-between">
      {/* Top Apple-Style Header */}
      <header className="apple-glass sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-2xl bg-[#0071E3] flex items-center justify-center text-white shadow-sm">
              <MessageCircleQuestion className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200/80">
                  HR Agent #07 • Employee Self-Service
                </span>
                <span className="text-xs text-neutral-500 font-medium hidden sm:inline">
                  Official Employee Handbook &amp; Support Desk
                </span>
              </div>
              <h1 className="text-lg font-semibold tracking-tight text-[#1D1D1F]">
                Employee HR Helpdesk Agent
              </h1>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 text-xs font-medium text-neutral-600 bg-white px-3.5 py-1.5 rounded-full border border-neutral-200/80 shadow-2xs">
            <Sparkles className="w-3.5 h-3.5 text-[#0071E3]" />
            <span>Simple, Focused Employee HR Assistance</span>
          </div>
        </div>
      </header>

      {/* Main Split Content */}
      <main className="max-w-7xl mx-auto px-6 py-10 w-full flex-1 flex items-center">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 w-full items-center">
          {/* Left Panel: 3-Step Visual Workflow Diagram */}
          <div className="lg:col-span-7 space-y-6">
            <div className="space-y-2.5">
              <div className="inline-flex items-center gap-2 text-xs font-semibold text-[#0071E3] bg-blue-50 border border-blue-200/70 px-3 py-1 rounded-full">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>How the Employee HR Helpdesk Agent Works</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1D1D1F] leading-tight">
                Instant, Handbook-Backed Answers for Every Employee Question
              </h2>
              <p className="text-sm text-neutral-600 leading-relaxed">
                Designed around one focused mission: helping employees get clear answers on leave days, medical cover, payroll dates, expense claims, and working hours—and connecting with the HR team whenever personal help is needed.
              </p>
            </div>

            {/* 3-Step Visual Workflow Cards */}
            <div className="space-y-4">
              {workflowSteps.map((item, idx) => {
                const IconComponent = item.icon;
                return (
                  <div
                    key={item.num}
                    className="apple-card rounded-2xl p-5 transition-all hover:shadow-md"
                  >
                    <div className="flex items-start gap-4">
                      <div className="w-11 h-11 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-[#0071E3] shrink-0">
                        <IconComponent className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <h3 className="text-sm font-semibold text-[#1D1D1F]">{item.title}</h3>
                          <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-[#F5F5F7] text-neutral-700 border border-neutral-200/80">
                            {item.badge}
                          </span>
                        </div>
                        <p className="text-xs text-neutral-600 mt-1.5 leading-relaxed">{item.desc}</p>
                        <div className="flex flex-wrap gap-2 mt-3">
                          {item.highlights.map((h) => (
                            <span
                              key={h}
                              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-[#1D1D1F] bg-[#F5F5F7] px-2.5 py-1 rounded-lg border border-neutral-200/70"
                            >
                              <CheckCircle2 className="w-3 h-3 text-[#0071E3]" />
                              {h}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                    {idx < workflowSteps.length - 1 && (
                      <div className="hidden sm:flex justify-center -mb-6 mt-1 text-neutral-300">
                        <ArrowRight className="w-4 h-4 rotate-90" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Panel: Single Sign-On (SSO) Card */}
          <div className="lg:col-span-5">
            <div className="apple-card rounded-3xl p-7 sm:p-8 space-y-6">
              <div className="space-y-1.5">
                <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
                  <Lock className="w-3 h-3" />
                  <span>Single Sign-On (SSO)</span>
                </div>
                <h3 className="text-xl font-bold text-[#1D1D1F]">
                  Sign in to Employee HR Helpdesk Agent
                </h3>
                <p className="text-xs text-neutral-500 leading-relaxed">
                  Use Google Single Sign-On, your company email verification code, or open the instant demo below.
                </p>
              </div>

              {/* 1-Click Instant Demo Sign-In Button */}
              <div className="p-3.5 rounded-2xl bg-[#F5F5F7] border border-neutral-200/80 space-y-2">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
                  Quick Preview
                </div>
                <button
                  type="button"
                  onClick={() => handleInstantDemoSignIn('employee')}
                  disabled={loading}
                  className="w-full py-2.5 px-4 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white font-semibold text-xs shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Instant Demo Sign-In (Employee / HR View)</span>
                </button>
              </div>

              {error && (
                <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
                  <span>{error}</span>
                </div>
              )}

              {infoMessage && (
                <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2.5">
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-600" />
                  <span>{infoMessage}</span>
                </div>
              )}

              {/* Google SSO Button */}
              <div className="space-y-2">
                <div className="flex flex-col items-center justify-center">
                  <div ref={googleBtnRef} className="min-h-[42px] flex items-center justify-center" />
                </div>
              </div>

              <div className="relative flex py-1 items-center">
                <div className="flex-grow border-t border-neutral-200"></div>
                <span className="flex-shrink mx-3 text-[11px] uppercase tracking-wider text-neutral-400 font-semibold">
                  Or Sign In With Work Email
                </span>
                <div className="flex-grow border-t border-neutral-200"></div>
              </div>

              {/* Work Email 6-Digit OTP Form */}
              {step === 'request' ? (
                <form onSubmit={handleRequestOtp} className="space-y-3.5">
                  <div>
                    <label className="block text-xs font-semibold text-neutral-700 mb-1.5">
                      Company Work Email
                    </label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-neutral-400 absolute left-3.5 top-3" />
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="name@company.com"
                        className="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl bg-white border border-neutral-300 focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 outline-none transition"
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-xl bg-neutral-900 hover:bg-neutral-800 disabled:opacity-60 text-white font-semibold text-xs shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <span>{loading ? 'Sending Verification Code...' : 'Send 6-Digit Verification Code'}</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyOtp} className="space-y-3.5">
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="block text-xs font-semibold text-neutral-700">
                        6-Digit Verification Code
                      </label>
                      <button
                        type="button"
                        onClick={() => {
                          setStep('request');
                          setOtpCode('');
                          setError('');
                        }}
                        className="text-xs font-medium text-[#0071E3] hover:underline cursor-pointer"
                      >
                        Change email
                      </button>
                    </div>
                    <div className="relative">
                      <KeyRound className="w-4 h-4 text-neutral-400 absolute left-3.5 top-3" />
                      <input
                        type="text"
                        required
                        maxLength={6}
                        value={otpCode}
                        onChange={(e) => setOtpCode(e.target.value)}
                        placeholder="Enter 6-digit code"
                        className="w-full pl-10 pr-4 py-2.5 text-sm tracking-widest font-mono rounded-xl bg-white border border-neutral-300 focus:border-[#0071E3] focus:ring-2 focus:ring-[#0071E3]/20 outline-none transition"
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 px-4 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] disabled:opacity-60 text-white font-semibold text-xs shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <span>{loading ? 'Verifying Code...' : 'Verify & Open HR Helpdesk Agent'}</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-neutral-200/80 bg-white/70 py-3.5 px-6 text-center text-xs text-neutral-500">
        Employee HR Helpdesk Agent • Official Employee Handbook Self-Service &amp; HR Support Tracker
      </footer>
    </div>
  );
}
