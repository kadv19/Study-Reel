// Cabinet: fetch drawers from GET /api/v1/cabinet?tray=... (Got it display, mastered enum)
try{ if(!localStorage.getItem('sr_session_token')) location.href='/auth'; }catch(e){}
const BACKEND = '';
let USER_ID = localStorage.getItem('sr_user_real_id') || localStorage.getItem('sr_user_id') || 'anon';
const REAL_ID = localStorage.getItem('sr_user_real_id') || null;
const TOKEN = localStorage.getItem('sr_session_token') || '';
if(REAL_ID) USER_ID = REAL_ID;
function headers(){ const id = REAL_ID || USER_ID; const h={'X-User-Id': id}; if(TOKEN) h['Authorization']='Bearer '+TOKEN; return h; }

async function loadDrawer(tray){
  const id = `list-${tray}`;
  const el = document.getElementById(id);
  if(!el) return;
  try{
    const res = await fetch(`${BACKEND}/api/v1/cabinet?tray=${tray}`, {headers: headers()});
    if(!res.ok) throw new Error(res.status);
    const text = await res.text();
    const data = JSON.parse(text);
    const cards = data.cards || [];
    if(cards.length===0){
      el.innerHTML = '<div class="empty-note">No cards yet</div>';
      return;
    }
    el.innerHTML = cards.map(c=>`
      <div class="idxcard tone-${tray}" onclick="openCard('${c.post_id}', ${c.slide_index})">
        <span class="punchmini"></span>
        <span class="tab mono">${c.tag}</span>
        <span class="title">${c.title}</span>
        <span class="arrow">›</span>
      </div>
    `).join('');
  }catch(e){
    el.innerHTML = `<div class="empty-note">Failed: ${e.message}</div>`;
  }
}

function openCard(postId, slideIdx){
  // open deck at that shelf? For now alert and navigate to deck with query
  // Find shelf that contains this post
  window.location.href = `/deck?shelf=${encodeURIComponent(postId)}#${slideIdx}`;
}

function toggleDrawer(id){
  const el=document.getElementById(id);
  const wasOpen=el.classList.contains('open');
  document.querySelectorAll('.drawer-unit').forEach(d=>d.classList.remove('open'));
  if(!wasOpen) el.classList.add('open');
  // lazy load already done
}

function toggleTheme(){
  const b=document.body;
  const isDark=b.getAttribute('data-theme')==='dark';
  b.setAttribute('data-theme', isDark?'light':'dark');
  document.getElementById('themeBtn').textContent=isDark?'☀️':'🌙';
}

// initial load all three
loadDrawer('review');
loadDrawer('catalog');
loadDrawer('mastered');
