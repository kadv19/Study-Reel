// StudyReel Auth — Borrower's Pocket (book-cover + pull-out card)
// Maps to SignupRequest/LoginRequest shape exactly — no backend changes
const BACKEND = '';

function getChosenCollege(){
  const el = document.querySelector('#collegeStamps .stamp.chosen');
  return el ? el.dataset.college : null;
}

function flagCollegeError(){
  const row = document.getElementById('collegeStamps');
  const err = document.getElementById('collegeError');
  if(row){
    row.classList.remove('error');
    // trigger reflow to restart animation
    void row.offsetWidth;
    row.classList.add('error');
    setTimeout(()=> row.classList.remove('error'), 700);
  }
  if(err){
    err.classList.add('show');
    setTimeout(()=> err.classList.remove('show'), 2500);
  }
  // also muted stamp to make it obvious
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
  // keep visible long enough to read before redirect; caller will redirect after ~900ms
  setTimeout(()=> el.classList.remove('show'), 1100);
}

function showFailInk(side){
  const id = side === 'front' ? 'inkFront' : 'inkBack';
  const el = document.getElementById(id);
  if(!el) return;
  const span = el.querySelector('span');
  const prev = span ? span.textContent : '';
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

// Keep old tab helper harmless (no tabs in pocket design, but keep for compat)
function switchTab(which){ /* no-op: pocket uses flipCard() */ }
function clearMessages(){ /* pocket uses ink stamps, not .error divs */ }

async function handleSignup(e){
  if(e && e.preventDefault) e.preventDefault();
  // clear college error visuals
  const row = document.getElementById('collegeStamps');
  if(row) row.classList.remove('error');
  const err = document.getElementById('collegeError');
  if(err) err.classList.remove('show');
  const suErr = document.getElementById('suError');
  if(suErr) suErr.classList.remove('show');

  const nameEl = document.getElementById('suName');
  const emailEl = document.getElementById('suEmail');
  const pwEl = document.getElementById('suPassword');
  const name = nameEl ? nameEl.value.trim() : '';
  const collegeRaw = getChosenCollege();
  const college = collegeRaw ? collegeRaw.trim().toUpperCase() : '';
  const email = emailEl ? emailEl.value.trim().toLowerCase() : '';
  const password = pwEl ? pwEl.value : '';

  // client-side validation — mirror backend SignupRequest
  if(!name){
    showFailInk('front');
    if(nameEl) nameEl.focus();
    return;
  }
  if(!college || !['NIE','VVCE','SJCE'].includes(college)){
    flagCollegeError();
    return;
  }
  if(!email || !email.includes('@') || !email.split('@')[1].includes('.')){
    showFailInk('front');
    if(emailEl) emailEl.focus();
    return;
  }
  if(!password || password.length < 6){
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
      body: JSON.stringify({name, college, email, password})
    });
    if(!res.ok){
      let msg = await res.text();
      console.log(`[auth] signup failed: status=${res.status} body=${msg}`);
      try{ const j=JSON.parse(msg); msg = j.detail || j.message || JSON.stringify(j); }catch{}
      throw new Error(msg);
    }
    const data = await res.json();
    localStorage.setItem('sr_session_token', data.token);
    localStorage.setItem('sr_user_real_id', data.user_id || data.user.id);
    localStorage.setItem('sr_user_name', data.user.name);
    localStorage.setItem('sr_user_email', data.user.email);
    localStorage.setItem('sr_user_college', data.user.college);
    localStorage.setItem('sr_user_id', data.user_id || data.user.id);
    showSuccessInk('front');
    setTimeout(()=>{
      const uid = data.user_id || data.user.id;
      const perUserKey = `sr_onboarding_seen_${uid}`;
      if(!localStorage.getItem(perUserKey)){
        location.href='/onboarding';
      } else {
        location.href='/deck';
      }
    }, 900);
    // keep button disabled while ink shows and redirect pending
  }catch(err){
    console.log(`[auth] signup failed:`, err, err.message);
    // Show real backend error instead of generic "try again"
    let msg = err && err.message ? err.message : 'Signup failed – try again';
    // Use existing collegeError as generic error display, or create suError under password field
    let errorEl = document.getElementById('suError');
    if(!errorEl){
      const pwField = document.getElementById('suPassword');
      const container = pwField ? pwField.parentElement : null;
      if(container){
        errorEl = document.createElement('div');
        errorEl.id = 'suError';
        errorEl.className = 'field-error show';
        errorEl.style.display = 'block';
        container.appendChild(errorEl);
      } else {
        errorEl = document.getElementById('collegeError');
      }
    }
    if(errorEl){
      errorEl.textContent = msg;
      errorEl.classList.add('show');
      errorEl.style.display = 'block';
    }
    showFailInk('front');
    // If message is short, also show it in the ink stamp for immediate visibility
    try{
      const ink = document.getElementById('inkFront');
      if(ink && msg && msg.length < 40){
        const span = ink.querySelector('span');
        if(span) span.textContent = msg.toUpperCase().slice(0, 32);
      }
    }catch{}
    setBtnLoading(btn, false);
  }
}

async function handleLogin(e){
  if(e && e.preventDefault) e.preventDefault();
  const emailEl = document.getElementById('liEmail');
  const pwEl = document.getElementById('liPassword');
  const email = emailEl ? emailEl.value.trim().toLowerCase() : '';
  const password = pwEl ? pwEl.value : '';
  if(!email || !email.includes('@') || !email.split('@')[1].includes('.')){
    showFailInk('back');
    if(emailEl) emailEl.focus();
    return;
  }
  if(!password){
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
      let msg = await res.text();
      try{ const j=JSON.parse(msg); msg = j.detail || JSON.stringify(j); }catch{}
      throw new Error(msg);
    }
    const data = await res.json();
    localStorage.setItem('sr_session_token', data.token);
    localStorage.setItem('sr_user_real_id', data.user_id || data.user.id);
    localStorage.setItem('sr_user_name', data.user.name);
    localStorage.setItem('sr_user_email', data.user.email);
    localStorage.setItem('sr_user_college', data.user.college);
    localStorage.setItem('sr_user_id', data.user_id || data.user.id);
    showSuccessInk('back');
    setTimeout(()=>{ location.href='/deck'; }, 900);
  }catch(err){
    showFailInk('back');
    setBtnLoading(btn, false);
  }
}

// Wire the mockup's stampIt placeholder to real flows
async function stampIt(side){
  if(side === 'front'){
    await handleSignup();
  } else {
    await handleLogin();
  }
}

window.switchTab = switchTab;
window.handleSignup = handleSignup;
window.handleLogin = handleLogin;
window.stampIt = stampIt;
window.getChosenCollege = getChosenCollege;
window.flagCollegeError = flagCollegeError;
window.showSuccessInk = showSuccessInk;
window.showFailInk = showFailInk;

// --- Phone keyboard: Enter / Go / Done should submit ---
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
}
if(document.readyState === 'loading'){
  document.addEventListener('DOMContentLoaded', bindEnterToStamp);
} else {
  bindEnterToStamp();
}
