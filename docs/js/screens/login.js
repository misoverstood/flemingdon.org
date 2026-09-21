// ============================================================
// login.js — OTP code login screen
// ============================================================

import { sendOTP, verifyOTP } from '../supabase.js';
import { siteFooter } from '../components/footer.js';

export async function renderLogin(message = '') {
  const app = document.getElementById('app');

  app.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;">
      <div style="width:100%;max-width:360px;">

        <div style="text-align:center;margin-bottom:40px;">
          <img src="icons/android-chrome-192x192.png" alt=""
               style="width:80px;height:80px;margin-bottom:8px;" />
          <div style="font-size:28px;font-weight:900;letter-spacing:-1px;">iseentit</div>
          <div style="font-size:13px;color:var(--muted);margin-top:4px;">Your personal TV &amp; movie tracker</div>
        </div>

        <div id="step-email">
          ${message ? `<div style="color:#e05;font-size:13px;margin-bottom:12px;text-align:center;">${message}</div>` : ''}
          <div style="font-size:13px;color:var(--muted);margin-bottom:12px;text-align:center;">
            Enter your email to receive a sign-in code
          </div>
          <input id="email-input" type="email" placeholder="your@email.com"
            style="width:100%;padding:14px 16px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-family:inherit;font-size:15px;outline:none;margin-bottom:12px;" />
          <button id="btn-send-otp" class="btn btn-primary" style="width:100%;justify-content:center;padding:14px;">
            Send code
          </button>
          <div id="email-error" style="color:#e05;font-size:12px;margin-top:8px;text-align:center;"></div>
        </div>

        <div id="step-otp" style="display:none;">
          <div style="font-size:13px;color:var(--muted);margin-bottom:12px;text-align:center;">
            Enter the 6-digit code sent to<br /><strong id="sent-email" style="color:var(--text);"></strong>
          </div>
          <input id="otp-input" type="text" inputmode="numeric" placeholder="000000" maxlength="6"
            style="width:100%;padding:14px 16px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-family:monospace;font-size:28px;outline:none;margin-bottom:12px;text-align:center;letter-spacing:10px;" />
          <button id="btn-verify-otp" class="btn btn-primary" style="width:100%;justify-content:center;padding:14px;">
            Sign in
          </button>
          <button id="btn-back" class="btn btn-secondary" style="width:100%;justify-content:center;padding:12px;margin-top:8px;">
            Back
          </button>
          <div id="otp-error" style="color:#e05;font-size:12px;margin-top:8px;text-align:center;"></div>
        </div>

        ${siteFooter()}

      </div>
    </div>
  `;

  const emailInput = document.getElementById('email-input');
  const otpInput   = document.getElementById('otp-input');
  const stepEmail  = document.getElementById('step-email');
  const stepOtp    = document.getElementById('step-otp');
  const emailError = document.getElementById('email-error');
  const otpError   = document.getElementById('otp-error');

  let currentEmail = '';

  document.getElementById('btn-send-otp').addEventListener('click', async () => {
    const btn = document.getElementById('btn-send-otp');
    emailError.textContent = '';
    const email = emailInput.value.trim();
    if (!email) { emailError.textContent = 'Enter your email.'; return; }
    btn.textContent = 'Sending...';
    btn.disabled = true;
    try {
      await sendOTP(email);
      currentEmail = email;
      document.getElementById('sent-email').textContent = email;
      stepEmail.style.display = 'none';
      stepOtp.style.display = 'block';
      otpInput.focus();
    } catch (e) {
      emailError.textContent = e.message || 'Failed to send code.';
      btn.textContent = 'Send code';
      btn.disabled = false;
    }
  });

  document.getElementById('btn-verify-otp').addEventListener('click', async () => {
    const btn = document.getElementById('btn-verify-otp');
    otpError.textContent = '';
    const token = otpInput.value.trim();
    if (token.length !== 6) { otpError.textContent = 'Enter the 6-digit code.'; return; }
    btn.textContent = 'Verifying...';
    btn.disabled = true;
    try {
      await verifyOTP(currentEmail, token);
      window.location.hash = '/';
      window.location.reload();
    } catch (e) {
      otpError.textContent = 'Invalid or expired code. Try again.';
      btn.textContent = 'Sign in';
      btn.disabled = false;
    }
  });

  document.getElementById('btn-back').addEventListener('click', () => {
    stepOtp.style.display = 'none';
    stepEmail.style.display = 'block';
    otpInput.value = '';
    otpError.textContent = '';
  });

  emailInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('btn-send-otp').click();
  });

  otpInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('btn-verify-otp').click();
  });

  emailInput.focus();
}