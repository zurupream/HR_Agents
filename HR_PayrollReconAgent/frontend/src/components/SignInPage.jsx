import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowRight,
  Calculator,
  CheckCircle2,
  FileCheck2,
  KeyRound,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Users
} from 'lucide-react';

const GOOGLE_CLIENT_ID =
  '259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com';

export default function SignInPage({ onSuccess }) {
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
      if (data.preview_code) {
        setOtpCode(data.preview_code);
      }
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
      const data = await res.json();
      if (res.ok && data.user) {
        onSuccess(data.user);
        return;
      }
    } catch {
      // Fallback if offline
    } finally {
      setLoading(false);
    }
    onSuccess({
      email: 'head.payroll@sybyl.com',
      name: 'Margaret Ndungu (Head of Payroll)',
      role: 'Head of Payroll & Statutory Compliance',
      auth_method: 'demo'
    });
  };

  return (
    <div className="min-h-screen bg-[#F5F5F7] text-[#1D1D1F] flex flex-col justify-between">
      {/* Frosted-Glass Apple Header */}
      <header className="apple-glass sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#0071E3] flex items-center justify-center text-white shadow-sm">
              <Calculator className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-blue-50 text-[#0071E3] border border-blue-200">
                  HR Agent #05 • People &amp; Payroll Operations
                </span>
                <span className="text-xs text-gray-500 hidden sm:inline">
                  Pre-Disbursement Payroll &amp; Statutory Control
                </span>
              </div>
              <h1 className="text-lg font-bold text-[#1D1D1F] tracking-tight">
                Payroll Variance, Statutory Compliance &amp; Payslip Recon Agent
              </h1>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-2 text-xs text-gray-600 bg-white px-3.5 py-1.5 rounded-full border border-gray-200">
            <ShieldCheck className="w-4 h-4 text-[#34C759]" />
            <span>PAYE • NSSF • SHIF • Housing Levy • Bank Audit</span>
          </div>
        </div>
      </header>

      {/* Main Split Content */}
      <main className="max-w-7xl mx-auto w-full px-6 py-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Left Panel (7/12): 3-Step Visual Workflow Diagram */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-white rounded-3xl p-8 border border-gray-200/90 shadow-xs space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 text-[#1D1D1F] text-xs font-semibold border border-[#34C759]/40">
              <Sparkles className="w-3.5 h-3.5 text-[#34C759]" />
              Catches Payroll Errors, Ghost Workers &amp; Bank Changes Before Salaries Are Paid
            </div>

            <div className="space-y-2">
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1D1D1F]">
                Reconcile Monthly Payroll &amp; Statutory Taxes With Complete Confidence
              </h2>
              <p className="text-sm text-gray-600 leading-relaxed">
                Before releasing monthly salaries to the bank, the{' '}
                <span className="font-semibold text-[#1D1D1F]">Payroll Reconciliation Agent</span>{' '}
                compares every employee’s draft payslip against last month’s payroll and official HR
                records—catching unexplained pay jumps, unverified bank account changes, exited
                employees still on payroll, and statutory deduction discrepancies.
              </p>
            </div>

            {/* High-Level 3-Step Visual Workflow Diagram */}
            <div className="pt-2">
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
                3-Step Monthly Payroll Reconciliation Workflow
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                {/* Step 1 */}
                <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/80 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#0071E3] bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200">
                        STEP 1
                      </span>
                      <Users className="w-4 h-4 text-[#0071E3]" />
                    </div>
                    <h3 className="text-sm font-semibold text-[#1D1D1F]">
                      Step 1: Compare Prior vs. Current Payroll &amp; HR Master
                    </h3>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      Cross-checks current-month draft salaries against last month’s payroll, new
                      hires from Agent #03, and employee exits from Agent #04.
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-gray-200/70 text-[11px] font-medium text-gray-500">
                    Headcount &amp; Basic Pay Bridge
                  </div>
                </div>

                {/* Step 2 */}
                <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-blue-200 bg-gradient-to-b from-blue-50/50 to-[#F5F5F7] flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#0071E3] bg-white px-2.5 py-0.5 rounded-full border border-blue-200">
                        STEP 2
                      </span>
                      <Calculator className="w-4 h-4 text-[#0071E3]" />
                    </div>
                    <h3 className="text-sm font-semibold text-[#1D1D1F]">
                      Step 2: Deterministic Statutory Tax &amp; Bank-Swap Audit
                    </h3>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      Recalculates exact PAYE, NSSF, SHIF (2.75%), and Housing Levy (1.5%), and
                      flags unauthorized bank account changes or exited staff still on payroll.
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-blue-200/60 text-[11px] font-semibold text-[#0071E3]">
                    100% Exact Statutory Math
                  </div>
                </div>

                {/* Step 3 */}
                <div className="rounded-2xl bg-[#F5F5F7] p-4 border border-gray-200/80 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#1D1D1F] bg-emerald-50 px-2.5 py-0.5 rounded-full border border-[#34C759]/50">
                        STEP 3
                      </span>
                      <FileCheck2 className="w-4 h-4 text-[#34C759]" />
                    </div>
                    <h3 className="text-sm font-semibold text-[#1D1D1F]">
                      Step 3: Approve Payroll &amp; Print CFO/CHRO Sign-Off Sheet
                    </h3>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      Resolve flagged exceptions in one click, approve verified payslips, and print
                      the 1-Page CFO &amp; CHRO Payroll Reconciliation Sign-Off Certificate.
                    </p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-gray-200/70 text-[11px] font-semibold text-[#34C759]">
                    Ready for Bank Disbursement
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Summary Strip */}
            <div className="rounded-2xl bg-[#1D1D1F] text-white p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-0.5">
                <div className="text-[11px] uppercase tracking-wider text-blue-300 font-semibold">
                  Built-In Payroll Protection Controls
                </div>
                <div className="text-xs text-gray-200">
                  Gross Pay − (PAYE + NSSF + SHIF 2.75% + Housing Levy 1.5%) = Net Take-Home Pay
                </div>
              </div>
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#34C759] shrink-0">
                <CheckCircle2 className="w-4 h-4" />
                Zero Ghost Workers or Unauthorized Bank Swaps
              </span>
            </div>
          </div>
        </div>

        {/* Right Panel (5/12): Single Sign-On & Instant Demo Sign-In */}
        <div className="lg:col-span-5">
          <div className="bg-white rounded-3xl p-8 border border-gray-200/90 shadow-xs space-y-5">
            <div className="space-y-1.5">
              <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#0071E3]">
                <Lock className="w-3.5 h-3.5" />
                Enterprise Single Sign-On (SSO)
              </div>
              <h3 className="text-xl font-bold text-[#1D1D1F]">
                Sign in to Payroll Reconciliation Agent
              </h3>
              <p className="text-xs text-gray-500">
                Sign in with Google SSO, your work email 6-digit verification code, or use Instant
                Demo Sign-In below.
              </p>
            </div>

            {/* 1-Click Instant Demo Sign-In (Head of Payroll) */}
            <div className="p-3.5 rounded-2xl bg-blue-50/70 border border-blue-200/80 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[#0071E3]">
                  Executive Review Mode
                </span>
                <span className="text-[11px] text-gray-500">October 2026 Payroll Run</span>
              </div>
              <button
                type="button"
                onClick={handleInstantDemoSignIn}
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-xl bg-[#0071E3] hover:bg-[#0077ED] text-white font-semibold text-sm shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
              >
                <UserCheck className="w-4 h-4" />
                <span>Instant Demo Sign-In (Head of Payroll)</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>

            {error && (
              <div className="p-3.5 rounded-2xl bg-red-50 border border-red-200 text-xs text-[#FF3B30] font-medium">
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
                      placeholder="payroll.lead@company.co.ke"
                      className="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-[#0071E3] focus:border-transparent"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 px-4 rounded-xl bg-[#1D1D1F] hover:bg-gray-800 text-white font-semibold text-sm transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
                >
                  <span>
                    {loading ? 'Sending Verification Code...' : 'Send 6-Digit Verification Code'}
                  </span>
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
                      Change work email
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
                  className="w-full py-2.5 px-4 rounded-xl bg-[#34C759] hover:bg-emerald-600 text-white font-semibold text-sm transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
                >
                  <span>{loading ? 'Verifying...' : 'Verify & Open Payroll Agent'}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </form>
            )}

            <div className="relative flex py-1 items-center">
              <div className="flex-grow border-t border-gray-200"></div>
              <span className="flex-shrink mx-3 text-[11px] uppercase tracking-wider text-gray-400 font-semibold">
                Or sign in with Google SSO
              </span>
              <div className="flex-grow border-t border-gray-200"></div>
            </div>

            <div className="flex justify-center">
              <div ref={googleBtnRef} />
            </div>

            <div className="pt-2 border-t border-gray-100 flex items-center justify-between text-[11px] text-gray-400">
              <span>Role: Head of Payroll &amp; HR Operations</span>
              <span>100% Human-in-the-Loop Control</span>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-gray-200/70 bg-white/60 py-3 px-6 text-center text-xs text-gray-500">
        HR Agent #05 • Payroll Variance, Statutory Compliance &amp; Payslip Recon Agent • Connected
        to HR Onboarding Pro Agent (#03) &amp; HR Offboarding Pro Agent (#04)
      </footer>
    </div>
  );
}
