import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowRight,
  BellRing,
  CalendarCheck,
  CheckCircle2,
  Clock,
  KeyRound,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  UserCheck
} from 'lucide-react';

const GOOGLE_CLIENT_ID =
  '259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com';

const APPEARANCE_THEMES = [
  { id: 'daylight', label: 'Daylight', title: 'Studio Daylight', swatch: '#F5F5F7' },
  { id: 'sand', label: 'Sand', title: 'Warm Sand (Default)', swatch: '#F7F5F0' },
  { id: 'dusk', label: 'Dusk', title: 'Quiet Dusk', swatch: '#1C1E26' },
  { id: 'midnight', label: 'Midnight', title: 'Midnight OLED', swatch: '#0B0C10' }
];

export default function SignInPage({ onSuccess, theme = 'sand', onThemeChange }) {
  const [email, setEmail] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [step, setStep] = useState('email'); // 'email' | 'otp'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  const googleBtnRef = useRef(null);

  useEffect(() => {
    let intervalId = null;

    const initGoogle = () => {
      if (window.google?.accounts?.id && googleBtnRef.current) {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: async (response) => {
            if (!response?.credential) return;
            setError('');
            setLoading(true);
            try {
              const res = await fetch('/api/auth/google', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential: response.credential })
              });
              const data = await res.json();
              if (!res.ok) {
                throw new Error(data.detail || 'Google authentication failed');
              }
              onSuccess(data.user);
            } catch (err) {
              setError(err.message || 'Unable to verify Google identity.');
            } finally {
              setLoading(false);
            }
          }
        });

        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: 'outline',
          size: 'large',
          width: 340,
          text: 'signin_with',
          shape: 'pill'
        });
        return true;
      }
      return false;
    };

    if (!initGoogle()) {
      intervalId = setInterval(() => {
        if (initGoogle()) {
          clearInterval(intervalId);
        }
      }, 300);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [onSuccess]);

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    setError('');
    setInfoMessage('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/otp/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to send verification code.');
      }
      setInfoMessage(data.message || `6-digit code sent to ${email}`);
      setStep('otp');
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
        body: JSON.stringify({ email, code: otpCode })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Invalid verification code.');
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
    setLoading(true);
    try {
      const res = await fetch('/api/auth/demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        onSuccess(data.user);
        return;
      }
    } catch {
      // Fallback to local demo user if offline
    } finally {
      setLoading(false);
    }
    onSuccess({
      email: 'sarah.wambui@company.co.ke',
      name: 'Sarah Wambui',
      role: 'HR Operations Manager',
      auth_method: 'demo'
    });
  };

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)] flex flex-col justify-between">
      {/* Frosted-Glass Top Bar */}
      <header className="apple-glass sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#0071E3] flex items-center justify-center text-white shadow-sm">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200">
                  Agent #06 • Enterprise HR &amp; People Operations
                </span>
                <span className="text-xs text-gray-500 hidden sm:inline">
                  Attendance &amp; Leave Agent
                </span>
              </div>
              <h1 className="text-lg font-semibold text-gray-900 tracking-tight">
                Attendance Clock-In/Out &amp; Leave Notification Agent
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {onThemeChange && (
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
                      onClick={() => onThemeChange(t.id)}
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
            )}
            <div className="hidden sm:flex items-center gap-2 text-xs text-gray-600 bg-gray-100 px-3.5 py-1.5 rounded-full border border-gray-200/80">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Daily Shift Hours + Leave Cross-Check</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Split Content */}
      <main className="max-w-7xl mx-auto w-full px-6 py-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Left Panel (7/12): High-Level 3-Step Visual Workflow Diagram */}
        <div className="lg:col-span-7 space-y-6">
          <div className="apple-card rounded-3xl p-8 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-[#0071E3] text-xs font-semibold border border-blue-200">
              <Sparkles className="w-3.5 h-3.5" />
              Instant Daily Missed-Hours &amp; Unapproved Absence Detection
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
                Daily Clock-In/Out Check &amp; Approved Leave Verification
              </h2>
              <p className="text-sm text-gray-600 leading-relaxed">
                Automatically checks each employee&apos;s daily{' '}
                <span className="font-semibold text-gray-900">Clock-In and Clock-Out times</span>{' '}
                against the required daily shift hours (<span className="font-semibold text-gray-900">8.0 hours</span>),
                cross-checks approved leave applications, and notifies HR for every employee who
                missed hours or was absent with no approved leave.
              </p>
            </div>

            {/* High-Level 3-Step Visual Workflow Diagram */}
            <div className="pt-2">
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                How the Attendance &amp; Leave Agent Works (3-Step Workflow)
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Step 1 */}
                <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/90 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#0071E3] bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200">
                        STEP 1
                      </span>
                      <Clock className="w-4 h-4 text-[#0071E3]" />
                    </div>
                    <h3 className="text-sm font-semibold text-gray-900">
                      Daily Clock-In &amp; Clock-Out Log
                    </h3>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      Reads employee clock-in and clock-out times against required daily shift hours (e.g., 8.0 hours).
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-gray-200/80 text-[11px] font-medium text-gray-600">
                    Clock-Out − Clock-In vs. 8.0h Shift
                  </div>
                </div>

                {/* Step 2 */}
                <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-blue-200 bg-gradient-to-b from-blue-50/40 to-[#F5F5F7] flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#0071E3] bg-white px-2.5 py-0.5 rounded-full border border-blue-200">
                        STEP 2
                      </span>
                      <CalendarCheck className="w-4 h-4 text-[#0071E3]" />
                    </div>
                    <h3 className="text-sm font-semibold text-gray-900">
                      Cross-Check Approved Leave Applications
                    </h3>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      Matches missing hours or absences against approved annual, sick, or half-day leave records.
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-blue-200/60 text-[11px] font-medium text-[#0071E3]">
                    Annual • Sick • Half-Day Leave Check
                  </div>
                </div>

                {/* Step 3 */}
                <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/90 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                        STEP 3
                      </span>
                      <BellRing className="w-4 h-4 text-emerald-600" />
                    </div>
                    <h3 className="text-sm font-semibold text-gray-900">
                      Notify HR for Missed Hours with No Leave
                    </h3>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      Flags each employee who missed hours or was absent without approved leave and sends one-click notifications to HR and the employee.
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-gray-200/80 text-[11px] font-medium text-emerald-700">
                    1-Click HR &amp; Employee Notice
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Summary Banner */}
            <div className="rounded-2xl bg-gray-900 text-white p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-0.5">
                <div className="text-[11px] uppercase tracking-wider text-blue-300 font-semibold">
                  Clear Attendance Calculation Rule
                </div>
                <div className="text-xs text-gray-200">
                  Required Shift (8.0h) − Approved Leave Hours − Hours Worked = Unexplained Hours Shortfall
                </div>
              </div>
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-300 shrink-0">
                <CheckCircle2 className="w-4 h-4" />
                100% Transparent HR Review
              </span>
            </div>
          </div>
        </div>

        {/* Right Panel (5/12): Google SSO, Email OTP & 1-Click Instant Demo Sign-In */}
        <div className="lg:col-span-5">
          <div className="apple-card rounded-3xl p-8 space-y-5">
            <div className="space-y-1.5">
              <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#0071E3]">
                <Lock className="w-3.5 h-3.5" />
                HR Single Sign-On (SSO)
              </div>
              <h3 className="text-xl font-bold text-gray-900">
                Sign in to Attendance &amp; Leave Agent
              </h3>
              <p className="text-xs text-gray-500">
                Use Google Single Sign-On, your work email 6-digit verification code, or launch the instant HR demo below.
              </p>
            </div>

            {/* 1-Click Instant Demo Sign-In Button */}
            <div className="p-3.5 rounded-2xl bg-blue-50/70 border border-blue-200/80 space-y-2">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[#0071E3]">
                Quick Executive Preview
              </div>
              <button
                type="button"
                onClick={handleInstantDemoSignIn}
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white font-semibold text-xs sm:text-sm shadow-sm transition flex items-center justify-center gap-2 cursor-pointer"
              >
                <UserCheck className="w-4 h-4" />
                <span>Instant Demo Sign-In (HR Operations Manager)</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>

            <div className="relative flex py-0.5 items-center">
              <div className="flex-grow border-t border-gray-200"></div>
              <span className="flex-shrink mx-3 text-[11px] uppercase tracking-wider text-gray-400 font-semibold">
                Or Sign In with Google SSO
              </span>
              <div className="flex-grow border-t border-gray-200"></div>
            </div>

            <div className="flex justify-center">
              <div ref={googleBtnRef} />
            </div>

            <div className="relative flex py-0.5 items-center">
              <div className="flex-grow border-t border-gray-200"></div>
              <span className="flex-shrink mx-3 text-[11px] uppercase tracking-wider text-gray-400 font-semibold">
                Or Work Email Verification Code
              </span>
              <div className="flex-grow border-t border-gray-200"></div>
            </div>

            {error && (
              <div className="p-3.5 rounded-2xl bg-red-50 border border-red-200 text-xs text-red-700 font-medium">
                {error}
              </div>
            )}

            {infoMessage && (
              <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 font-medium">
                {infoMessage}
              </div>
            )}

            {step === 'email' ? (
              <form onSubmit={handleRequestOtp} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                    Work Email Address
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="sarah.wambui@company.co.ke"
                      className="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[#0071E3] focus:border-transparent"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 px-4 rounded-xl bg-gray-900 hover:bg-gray-800 text-white font-semibold text-xs sm:text-sm shadow-sm transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
                >
                  <span>{loading ? 'Sending Verification Code...' : 'Send 6-Digit Verification Code'}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </form>
            ) : (
              <form onSubmit={handleVerifyOtp} className="space-y-3.5">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-gray-700">
                      Enter 6-Digit Verification Code
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        setStep('email');
                        setOtpCode('');
                        setError('');
                      }}
                      className="text-xs text-[#0071E3] hover:underline cursor-pointer"
                    >
                      Change email
                    </button>
                  </div>
                  <div className="relative">
                    <KeyRound className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      required
                      maxLength={6}
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                      placeholder="123456"
                      className="w-full pl-10 pr-4 py-2.5 text-sm tracking-widest font-mono rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[#0071E3]"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading || otpCode.length < 6}
                  className="w-full py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm shadow-sm transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
                >
                  <span>{loading ? 'Verifying Code...' : 'Verify & Open Attendance Agent'}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </form>
            )}

            <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-[11px] text-gray-400">
              <span>Role: HR Operations Manager</span>
              <span>Human-in-the-Loop Verified</span>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-gray-200/70 bg-white/60 py-3 px-6 text-center text-xs text-gray-500">
        Agent #06 • Attendance Clock-In/Out &amp; Leave Notification Agent • Enterprise HR &amp; People Operations Portfolio
      </footer>
    </div>
  );
}
