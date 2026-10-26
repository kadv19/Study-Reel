const BACKEND = window.STUDYREEL_BACKEND || '';
const NIE_ONLY_DETAIL = 'Only NIE student emails (@nie.ac.in) are allowed.';
const NIE_EMAIL_RE = /^[^\s@]+@nie\.ac\.in$/i;

let pendingVerifyEmail = '';
let resendTimer = null;

function getChosenCollege(){
  const el = document.querySelector('#collegeStamps .stamp.chosen');
  return el ? el.dataset.college : null;
}

function isNieEmail(email){
  return NIE_EMAIL_RE.test((email || '').trim());
}

function flagCollegeError(){
  const row = document.getElementById('collegeStamps');
  const err = document.getElementById('collegeError');
  if(row){
    row.classList.remove('error');
    void row.offsetWidth;
    row.classList.add('error');
    setTimeout(()=> row.classList.remove('error'), 700);
  }
  if(err){
    err.textContent = 'Please select your college';
    err.classList.add('show');
    setTimeout(()=> err.classList.remove('show'), 2500);
  }
  showFailInk('front');
}

function showSuccessInk(side){
  const id = side === 'front' ? 'inkFront' : 'inkBack';
  const el = document.getElementById(id);
  if(!el) return;
  const span = el.querySelector('span');
  if(span){
    span.textContent = side === 'front' ? 'ISSUED' : 'WELCOME';
    el.classList.remove('muted');
  }
  el.classList.add('show');
  setTimeout(()=> el.classList.remove('show'), 1100);
}

function showFailInk(side){
  const id = side === 'front' ? 'inkFront' : 'inkBack';
  const el = document.getElementById(id);
  if(!el) return;
  const span = el.querySelector('span');
  if(span) span.textContent = 'TRY AGAIN';
  el.classList.add('muted');
  el.classList.add('show');
  setTimeout(()=>{
    el.classList.remove('show');
    setTimeout(()=>{
      el.classList.remove('muted');
      if(span) span.textContent = side === 'front' ? 'ISSUED' : 'WELCOME';
    }, 200);
  }, 1400);
}

function showVerifyInk(){
  const el = document.getElementById('inkVerify');
  if(!el) return;
  el.classList.add('show');
  setTimeout(()=> el.classList.remove('show'), 1200);
}

function setBtnLoading(btn, loading, text){
  if(!btn) return;
  if(loading){
    if(!btn.dataset.origText) btn.dataset.origText = btn.textContent;
    btn.disabled = true;
    btn.classList.add('loading');
    if(text) btn.textContent = text;
  } else {
    btn.disabled = false;
    btn.classList.remove('loading');
    if(btn.dataset.origText){
      btn.textContent = btn.dataset.origText;
      delete btn.dataset.origText;
    }
  }
}

function showFormError(id, msg){
  const el = document.getElementById(id);
  if(!el) return;
  el.textContent = msg;
  el.classList.add('show');
  el.style.display = 'block';
}

function clearFormError(id){
  const el = document.getElementById(id);
  if(!el) return;
  el.classList.remove('show');
  el.style.display = '';
  el.textContent = '';
}

function showVerifyMessage(msg, isError){
  const err = document.getElementById('verifyError');
  const notice = document.getElementById('verifyNotice');
  if(isError){
    if(err){ err.textContent = msg; err.classList.add('show'); }
    if(notice) notice.classList.remove('show');
  } else {
    if(notice){ notice.textContent = msg; notice.classList.add('show'); }
    if(err) err.classList.remove('show');
  }
}

function clearVerifyMessages(){
  const err = document.getElementById('verifyError');
  const notice = document.getElementById('verifyNotice');
  if(err){ err.textContent = ''; err.classList.remove('show'); }
  if(notice){ notice.textContent = ''; notice.classList.remove('show'); }
}

async function readError(res){
  const text = await res.text();
  let detail = text;
  try{
    const data = JSON.parse(text);
    detail = data.detail || data.message || data;
  }catch{}
  if(Array.isArray(detail)){
    detail = detail.map(item => item && item.msg ? item.msg : JSON.stringify(item)).join('; ');
  } else if(detail && typeof detail === 'object'){
    detail = JSON.stringify(detail);
  }
  return {status: res.status, detail: String(detail || 'Request failed')};
}

function persistSession(data){
  if(!data || !data.token || !data.user) return false;
  const uid = data.user_id || data.user.id;
  localStorage.setItem('sr_session_token', data.token);
  localStorage.setItem('sr_user_real_id', uid);
  localStorage.setItem('sr_user_name', data.user.name);
  localStorage.setItem('sr_user_email', data.user.email);
  localStorage.setItem('sr_user_college', data.user.college);
  localStorage.setItem('sr_user_id', uid);
  return true;
}

function startResendCountdown(seconds){
  const btn = document.getElementById('resendBtn');
  if(!btn) return;
  if(resendTimer){
    clearInterval(resendTimer);
    resendTimer = null;
  }
  let remaining = Math.max(0, Number(seconds) || 0);
  if(remaining <= 0){
    btn.disabled = false;
    btn.textContent = 'Resend code';
    return;
  }
  btn.disabled = true;
  const tick = ()=>{
    if(remaining <= 0){
      clearInterval(resendTimer);
      resendTimer = null;
      btn.disabled = false;
      btn.textContent = 'Resend code';
      return;
    }
    btn.textContent = `Resend in ${remaining}s`;
    remaining -= 1;
  };
  tick();
  resendTimer = setInterval(tick, 1000);
}

function showVerifyView(email, options){
  const opts = options || {};
  pendingVerifyEmail = email;
  const stageEl = document.getElementById('stage');
  if(stageEl) stageEl.classList.add('pulled', 'verify');

  const emailEl = document.getElementById('verifyEmail');
  if(emailEl) emailEl.textContent = email;

  const codeEl = document.getElementById('verifyCode');
  if(codeEl) codeEl.value = '';
  clearVerifyMessages();
  const ink = document.getElementById('inkVerify');
  if(ink) ink.classList.remove('show');
  startResendCountdown(opts.sent ? 60 : 0);
  setTimeout(()=>{ if(codeEl) codeEl.focus(); }, 450);
}

function hideVerifyView(showLogin){
  const email = pendingVerifyEmail;
  pendingVerifyEmail = '';
  if(resendTimer){
    clearInterval(resendTimer);
    resendTimer = null;
  }
  const stageEl = document.getElementById('stage');
  if(stageEl) stageEl.classList.remove('verify');
  clearVerifyMessages();

  if(showLogin === false) return email;

  const card = document.getElementById('card3d');
  if(card && !card.classList.contains('flipped')){
    if(typeof flipCard === 'function') flipCard();
    else card.classList.add('flipped');
  }
  const loginEmail = document.getElementById('liEmail');
  if(loginEmail && email) loginEmail.value = email;
  const loginPassword = document.getElementById('liPassword');
  if(loginPassword){
    loginPassword.value = '';
    setTimeout(()=> loginPassword.focus(), 450);
  }
  return email;
}

function switchTab(which){}
function clearMessages(){}

async function handleSignup(e){
  if(e && e.preventDefault) e.preventDefault();
  clearFormError('suError');
  clearFormError('collegeError');
  const row = document.getElementById('collegeStamps');
  if(row) row.classList.remove('error');

  const nameEl = document.getElementById('suName');
  const emailEl = document.getElementById('suEmail');
  const pwEl = document.getElementById('suPassword');
  const name = nameEl ? nameEl.value.trim() : '';
  const email = emailEl ? emailEl.value.trim().toLowerCase() : '';
  const password = pwEl ? pwEl.value : '';

  if(!name){
    showFailInk('front');
    if(nameEl) nameEl.focus();
    return;
  }
  if(!isNieEmail(email)){
    showFormError('suError', NIE_ONLY_DETAIL);
    showFailInk('front');
    if(emailEl) emailEl.focus();
    return;
  }
  if(!password || password.length < 6){
    showFormError('suError', 'Password must be at least 6 characters.');
    showFailInk('front');
    if(pwEl) pwEl.focus();
    return;
  }

  const btn = document.getElementById('suBtn');
  setBtnLoading(btn, true, 'Stamping…');
  try{
    const res = await fetch(`${BACKEND}/api/v1/auth/signup`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name, email, password})
    });
    if(!res.ok){
      const {status, detail} = await readError(res);
      if(status === 403 && detail === 'EMAIL_UNVERIFIED'){
        setBtnLoading(btn, false);
        showVerifyView(email, {sent:true});
        return;
      }
      throw new Error(detail);
    }
    const data = await res.json();
    persistSession(data);
    showSuccessInk('front');
    setTimeout(()=>{
      const uid = data.user_id || (data.user && data.user.id);
      const perUserKey = `sr_onboarding_seen_${uid}`;
      if(!localStorage.getItem(perUserKey)) location.href='/onboarding';
      else location.href='/deck';
    }, 900);
  }catch(err){
    const msg = err && err.message ? err.message : 'Signup failed – try again';
    showFormError('suError', msg);
    showFailInk('front');
    setBtnLoading(btn, false);
  }
}

async function handleLogin(e){
  if(e && e.preventDefault) e.preventDefault();
  clearFormError('liError');
  const emailEl = document.getElementById('liEmail');
  const pwEl = document.getElementById('liPassword');
  const email = emailEl ? emailEl.value.trim().toLowerCase() : '';
  const password = pwEl ? pwEl.value : '';

  if(!isNieEmail(email)){
    showFormError('liError', NIE_ONLY_DETAIL);
    showFailInk('back');
    if(emailEl) emailEl.focus();
    return;
  }
  if(!password){
    showFormError('liError', 'Enter your password.');
    showFailInk('back');
    if(pwEl) pwEl.focus();
    return;
  }

  const btn = document.getElementById('liBtn');
  setBtnLoading(btn, true, 'Checking…');
  try{
    const res = await fetch(`${BACKEND}/api/v1/auth/login`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, password})
    });
    if(!res.ok){
      const {status, detail} = await readError(res);
      if(status === 403 && detail === 'EMAIL_UNVERIFIED'){
        setBtnLoading(btn, false);
        showVerifyView(email, {sent:false});
        return;
      }
      throw new Error(detail);
    }
    const data = await res.json();
    persistSession(data);
    showSuccessInk('back');
    setTimeout(()=>{ location.href='/deck'; }, 900);
  }catch(err){
    const msg = err && err.message ? err.message : 'Login failed – try again';
    showFormError('liError', msg);
    showFailInk('back');
    setBtnLoading(btn, false);
  }
}

async function handleVerify(e){
  if(e && e.preventDefault) e.preventDefault();
  clearVerifyMessages();
  const email = pendingVerifyEmail || (document.getElementById('liEmail') || {}).value || '';
  const codeEl = document.getElementById('verifyCode');
  const code = codeEl ? codeEl.value.trim() : '';

  if(!/^\d{6}$/.test(code)){
    showVerifyMessage('Enter the 6-digit code from your email.', true);
    if(codeEl) codeEl.focus();
    return;
  }

  const btn = document.getElementById('verifyBtn');
  setBtnLoading(btn, true, 'Verifying…');
  try{
    const res = await fetch(`${BACKEND}/api/v1/auth/verify`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, code})
    });
    if(!res.ok){
      const {detail} = await readError(res);
      showVerifyMessage(detail, true);
      setBtnLoading(btn, false);
      return;
    }
    await res.json();
    showVerifyMessage('Email verified. You can sign in now.', false);
    showVerifyInk();
    setTimeout(()=>{
      setBtnLoading(btn, false);
      hideVerifyView(true);
    }, 1100);
  }catch(err){
    showVerifyMessage('Verification failed. Try again.', true);
    setBtnLoading(btn, false);
  }
}

async function handleResend(e){
  if(e && e.preventDefault) e.preventDefault();
  clearVerifyMessages();
  const email = pendingVerifyEmail || (document.getElementById('liEmail') || {}).value || '';
  if(!email){
    showVerifyMessage('Enter your email to resend the code.', true);
    return;
  }
  const btn = document.getElementById('resendBtn');
  if(btn && btn.disabled) return;
  if(btn){
    btn.disabled = true;
    btn.textContent = 'Sending…';
  }
  try{
    const res = await fetch(`${BACKEND}/api/v1/auth/resend`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email})
    });
    if(!res.ok){
      const {detail} = await readError(res);
      showVerifyMessage(detail, true);
      const retryAfter = Number(res.headers.get('Retry-After'));
      startResendCountdown(Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : 0);
      return;
    }
    const data = await res.json();
    showVerifyMessage('A new code is on its way.', false);
    startResendCountdown(data.retry_after || 60);
    const codeEl = document.getElementById('verifyCode');
    if(codeEl){
      codeEl.value = '';
      codeEl.focus();
    }
  }catch(err){
    showVerifyMessage('Could not resend the code. Try again.', true);
    startResendCountdown(0);
  }
}

async function stampIt(side){
  if(side === 'front') await handleSignup();
  else await handleLogin();
}

function bindVerifyControls(){
  const verifyBtn = document.getElementById('verifyBtn');
  if(verifyBtn) verifyBtn.addEventListener('click', handleVerify);
  const resendBtn = document.getElementById('resendBtn');
  if(resendBtn) resendBtn.addEventListener('click', handleResend);
  const back = document.getElementById('verifyBack');
  if(back){
    back.addEventListener('click', (e)=>{
      if(e && e.preventDefault) e.preventDefault();
      hideVerifyView(true);
    });
  }
}

window.switchTab = switchTab;
window.handleSignup = handleSignup;
window.handleLogin = handleLogin;
window.handleVerify = handleVerify;
window.handleResend = handleResend;
window.stampIt = stampIt;
window.getChosenCollege = getChosenCollege;
window.flagCollegeError = flagCollegeError;
window.showSuccessInk = showSuccessInk;
window.showFailInk = showFailInk;
window.showVerifyView = showVerifyView;
window.hideVerifyView = hideVerifyView;

function bindEnterToStamp(){
  const suIds = ['suName','suEmail','suPassword'];
  const liIds = ['liEmail','liPassword'];
  suIds.forEach(id=>{
    const el = document.getElementById(id);
    if(el){
      el.addEventListener('keydown', (e)=>{
        if(e.key === 'Enter' || e.keyCode === 13){
          e.preventDefault();
          stampIt('front');
        }
      });
    }
  });
  liIds.forEach(id=>{
    const el = document.getElementById(id);
    if(el){
      el.addEventListener('keydown', (e)=>{
        if(e.key === 'Enter' || e.keyCode === 13){
          e.preventDefault();
          stampIt('back');
        }
      });
    }
  });
  const codeEl = document.getElementById('verifyCode');
  if(codeEl){
    codeEl.addEventListener('keydown', (e)=>{
      if(e.key === 'Enter' || e.keyCode === 13){
        e.preventDefault();
        handleVerify();
      }
    });
  }
}

function initAuthUi(){
  bindEnterToStamp();
  bindVerifyControls();
}

if(document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', initAuthUi);
} else {
  initAuthUi();
}
