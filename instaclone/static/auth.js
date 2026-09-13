// StudyReel Auth — signup/login gate, visually strong, StudyReel dark theme
const BACKEND = '';

function switchTab(which){
  const suTab = document.getElementById('tabSignup');
  const liTab = document.getElementById('tabLogin');
  const suForm = document.getElementById('formSignup');
  const liForm = document.getElementById('formLogin');
  if(which === 'signup'){
    suTab.classList.add('active'); suTab.setAttribute('aria-selected','true');
    liTab.classList.remove('active'); liTab.setAttribute('aria-selected','false');
    suForm.classList.remove('hidden'); liForm.classList.add('hidden');
  } else {
    liTab.classList.add('active'); liTab.setAttribute('aria-selected','true');
    suTab.classList.remove('active'); suTab.setAttribute('aria-selected','false');
    liForm.classList.remove('hidden'); suForm.classList.add('hidden');
  }
  clearMessages();
}
function clearMessages(){
  ['suError','suSuccess','liError','liSuccess'].forEach(id=>{
    const el=document.getElementById(id);
    if(el){ el.textContent=''; el.classList.remove('show'); }
  });
}
function showError(id, msg){
  const el=document.getElementById(id);
  if(el){ el.textContent=msg; el.classList.add('show'); }
}
function showSuccess(id, msg){
  const el=document.getElementById(id);
  if(el){ el.textContent=msg; el.classList.add('show'); }
}

async function handleSignup(e){
  e.preventDefault();
  clearMessages();
  const name = document.getElementById('suName').value.trim();
  const college = document.getElementById('suCollege').value.trim().toUpperCase();
  const email = document.getElementById('suEmail').value.trim().toLowerCase();
  const password = document.getElementById('suPassword').value;
  if(!name){ showError('suError','Enter your name'); return; }
  if(!college || !['NIE','VVCE','SJCE'].includes(college)){ showError('suError','Select college: NIE, VVCE or SJCE'); return; }
  if(!email || !email.includes('@')){ showError('suError','Enter a valid email'); return; }
  if(!password || password.length < 6){ showError('suError','Password must be at least 6 characters'); return; }
  const btn=document.getElementById('suBtn');
  btn.disabled=true; btn.textContent='Creating…';
  try{
    const res = await fetch(`${BACKEND}/api/v1/auth/signup`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name, college, email, password})
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
    // keep legacy key for other files
    localStorage.setItem('sr_user_id', data.user_id || data.user.id);
    showSuccess('suSuccess','Account created — taking you to your deck…');
    setTimeout(()=>{ location.href='/deck'; }, 700);
  }catch(err){
    showError('suError', 'Signup failed: ' + (err.message || err));
    btn.disabled=false; btn.textContent='Create account →';
  }
}

async function handleLogin(e){
  e.preventDefault();
  clearMessages();
  const email = document.getElementById('liEmail').value.trim().toLowerCase();
  const password = document.getElementById('liPassword').value;
  if(!email || !email.includes('@')){ showError('liError','Enter a valid email'); return; }
  if(!password){ showError('liError','Enter your password'); return; }
  const btn=document.getElementById('liBtn');
  btn.disabled=true; btn.textContent='Logging in…';
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
    showSuccess('liSuccess','Welcome back — loading your deck…');
    setTimeout(()=>{ location.href='/deck'; }, 600);
  }catch(err){
    showError('liError', 'Login failed: ' + (err.message || err));
    btn.disabled=false; btn.textContent='Log in →';
  }
}

window.switchTab = switchTab;
window.handleSignup = handleSignup;
window.handleLogin = handleLogin;
