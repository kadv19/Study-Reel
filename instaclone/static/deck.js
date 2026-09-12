// Deck: shelves, stack, flip, drag-to-file (mastered display=Got it) + pseudo account onboarding 3-dismiss + college dropdown
const BACKEND = localStorage.getItem('backend_url') || 'http://127.0.0.1:8000';
let USER_ID = localStorage.getItem('sr_user_id') || (()=>{const id='anon-'+Math.random().toString(36).slice(2,8); localStorage.setItem('sr_user_id', id); return id;})();
let REAL_ID = localStorage.getItem('sr_user_real_id') || null;
let shelves = [];
let activeShelf = null;
let deck = null;
let deckIndex = 0;
let flipped = false;
const DISPLAY = {review:'Review', catalog:'Catalog', mastered:'Got it'};

const shelfRow = document.getElementById('shelfrow');
const shelfNameEl = document.getElementById('shelfName');
const topCard = document.getElementById('topCard');
const flipInner = document.getElementById('flipInner');
const faceFront = document.getElementById('faceFront');
const faceBack = document.getElementById('faceBack');
const zones = { review: document.getElementById('zoneReview'), catalog: document.getElementById('zoneCatalog'), mastered: document.getElementById('zoneMastered') };
const trays = { review: document.getElementById('trayReview'), catalog: document.getElementById('trayCatalog'), mastered: document.getElementById('trayMastered') };
const back2 = document.getElementById('back2');
const back3 = document.getElementById('back3');
const emptyMsg = document.getElementById('emptyMsg');
const accountNameEl = document.getElementById('accountName');
const onboardingSheet = document.getElementById('onboardingSheet');
const onErrorEl = document.getElementById('onError');

function uidHeaders(){ const id = REAL_ID || USER_ID; return {'X-User-Id': id}; }
function currentUserId(){ return REAL_ID || USER_ID; }
function updateBadge(){
  if(REAL_ID){
    const name = localStorage.getItem('sr_user_name') || REAL_ID.slice(0,6);
    if(accountNameEl) accountNameEl.textContent = name;
  } else {
    if(accountNameEl) accountNameEl.textContent = USER_ID;
  }
}
updateBadge();

function spineColor(idx){
  const pals = ["#5a4a3a,#3a2f26","#4a3a4a,#2f2636","#3a4a3f,#26362c","#4a3f2f,#362c1f","#2f3f4a,#1f2c36","#4a3a3a,#362626"];
  return pals[idx % pals.length];
}

async function loadShelves(){
  try{
    const res = await fetch(`${BACKEND}/api/v1/shelves`, {headers: uidHeaders()});
    if(!res.ok) throw new Error(res.status);
    shelves = await res.json();
    if(!shelves.length){
      shelfRow.innerHTML = '<span style="font-size:11px;color:var(--muted)">No shelves — upload syllabus</span>';
      shelfNameEl.textContent = 'No shelves yet';
      maybeShowOnboarding();
      return;
    }
    shelfRow.innerHTML = '';
    shelves.forEach((s, i)=>{
      const el = document.createElement('div');
      el.className = 'spine' + (i===0 ? ' active' : '');
      const h = 56 + Math.round(s.fill_pct*26) + (i%3)*4;
      el.style.height = h+'px';
      el.style.background = `linear-gradient(180deg,${spineColor(i)})`;
      el.dataset.shelf = s.shelf_id;
      el.innerHTML = `<div class="fillcap" style="height:${Math.round(s.fill_pct*100)}%; background:linear-gradient(180deg,#38bdf8,#818cf8);"></div><span class="vlabel">${s.label}</span>`;
      el.onclick = ()=> selectShelf(s.shelf_id);
      shelfRow.appendChild(el);
    });
    selectShelf(shelves[0].shelf_id);
    maybeShowOnboarding();
  }catch(e){
    console.error('shelves', e);
    shelfNameEl.textContent = 'Failed to load shelves';
  }
}

async function selectShelf(shelfId){
  document.querySelectorAll('.spine').forEach(el=>el.classList.toggle('active', el.dataset.shelf===shelfId));
  activeShelf = shelves.find(s=>s.shelf_id===shelfId);
  shelfNameEl.textContent = activeShelf ? `${activeShelf.label} — ${activeShelf.module_name || 'Module'}` : shelfId;
  deckIndex = 0;
  flipped = false;
  flipInner.classList.remove('flipped');
  await loadDeck(shelfId);
}

async function loadDeck(shelfId){
  try{
    const res = await fetch(`${BACKEND}/api/v1/deck?shelf=${encodeURIComponent(shelfId)}`, {headers: uidHeaders()});
    if(!res.ok) throw new Error(await res.text());
    deck = await res.json();
    if(!deck.cards || deck.cards.length===0){
      emptyMsg.style.display='block';
      topCard.style.display='none';
      back2.style.display='none';
      back3.style.display='none';
      return;
    }
    emptyMsg.style.display='none';
    topCard.style.display='';
    back2.style.display='';
    back3.style.display='';
    deckIndex = 0;
    renderStack();
  }catch(e){
    console.error('deck', e);
    emptyMsg.textContent = 'Deck load failed: '+e.message;
    emptyMsg.style.display='block';
  }
}

function currentCard(){
  if(!deck || !deck.cards || deckIndex>=deck.cards.length) return null;
  return deck.cards[deckIndex];
}

function renderStack(){
  const card = currentCard();
  if(!card){
    emptyMsg.textContent = 'Shelf cleared — check My Cabinet or switch shelf.';
    emptyMsg.style.display='block';
    topCard.style.display='none';
    back2.style.display='none';
    back3.style.display='none';
    return;
  }
  const next1 = deck.cards[deckIndex+1];
  const next2 = deck.cards[deckIndex+2];
  back2.style.background = next1 ? 'var(--card)' : 'transparent';
  back3.style.background = next2 ? 'var(--card)' : 'transparent';
  const ft = card.front, bk = card.back;
  const weightDots = (w)=>{
    const map={low:1, medium:2, high:3};
    const n=map[w]||2;
    return `<span class="dot ${n>=1?'on':''}"></span><span class="dot ${n>=2?'on':''}"></span><span class="dot ${n>=3?'on':''}"></span>`;
  };
  faceFront.innerHTML = `
    <div class="punch"></div><div class="ribbon"></div>
    <div class="cardhead"><span class="tab mono">${card.post_id.slice(0,4)} · ${ft.slide_number}/${ft.total_slides}</span><span class="tab">${Math.round(30 + Math.random()*10)}s read</span></div>
    <div class="cardbody"><h2>${ft.header}</h2><p>${ft.body}</p>${ft.code?`<div class="code mono">${ft.code.replace(/</g,'&lt;')}</div>`:''}</div>
    <div class="cardfoot"><span class="weight">exam weight ${weightDots(card.exam_weight||bk.exam_weight)}</span><button class="flipbtn" onclick="flipCard(event)">flip ↻</button></div>
  `;
  faceBack.innerHTML = `
    <div class="punch"></div>
    <div class="cardhead"><span class="tab mono">${bk.back_header||'WHY IT MATTERS'}</span></div>
    <div class="cardbody"><h2>${bk.back_header||'Why it matters'}</h2><p>${bk.back_body||'Recall this for VTU.'}</p>${ft.code?`<div class="code mono">${bk.exam_weight? 'Weight: '+bk.exam_weight : ''}</div>`:''}</div>
    <div class="cardfoot"><span class="weight">exam weight ${weightDots(bk.exam_weight)}</span><button class="flipbtn" onclick="flipCard(event)">flip ↻</button></div>
  `;
  topCard.style.transition='none';
  topCard.style.transform='';
  topCard.style.opacity='1';
  flipped=false;
  flipInner.classList.remove('flipped');
  void topCard.offsetWidth;
  topCard.style.transition='';
}

function flipCard(e){
  if(e) e.stopPropagation();
  flipped=!flipped;
  flipInner.classList.toggle('flipped', flipped);
}

// drag with dead-zone, tuned thresholds, velocity flick, clamp, haptic
let dragging=false, startX=0, startY=0, dx=0, dy=0, startT=0, vx=0, lockedAxis=null;
topCard.addEventListener('pointerdown', (e)=>{
  if(e.target.closest('.flipbtn')) return;
  dragging=true;
  topCard.classList.add('dragging');
  startX=e.clientX; startY=e.clientY; startT=performance.now(); dx=0; dy=0; vx=0; lockedAxis=null;
  try{ topCard.setPointerCapture(e.pointerId);}catch{}
});
topCard.addEventListener('pointermove', (e)=>{
  if(!dragging) return;
  const ndx=e.clientX-startX, ndy=e.clientY-startY;
  if(!lockedAxis && Math.hypot(ndx,ndy) > 8){
    lockedAxis = Math.abs(ndx) > Math.abs(ndy) ? 'x' : 'y';
  }
  if(lockedAxis==='x') dy=0; else if(lockedAxis==='y') dx=0;
  else { dx=ndx; dy=ndy; }
  if(lockedAxis==='x') dx=ndx;
  if(lockedAxis==='y') dy=ndy;
  if(!lockedAxis){ dx=ndx; dy=ndy; }
  const dt = Math.max(1, performance.now()-startT);
  vx = dx/dt;
  // dead-zone 8
  if(Math.hypot(dx,dy) < 8) return;
  const rot = Math.max(-12, Math.min(12, dx*0.07));
  const clx = Math.max(-160, Math.min(160, dx));
  const cly = Math.max(-60, Math.min(160, dy));
  topCard.style.transform=`translate(${clx}px, ${cly}px) rotate(${rot}deg)`;
  Object.values(zones).forEach(z=>z.classList.remove('on'));
  Object.values(trays).forEach(t=>t.className='tray');
  const hoverX=32, hoverY=32;
  if(lockedAxis==='x' || (!lockedAxis && Math.abs(dx) > Math.abs(dy))){
    if(dx < -hoverX){ zones.review.classList.add('on'); trays.review.className='tray hover-review'; if(dx>-36 && navigator.vibrate) navigator.vibrate(10); }
    else if(dx > hoverX){ zones.mastered.classList.add('on'); trays.mastered.className='tray hover-mastered'; if(dx<36 && navigator.vibrate) navigator.vibrate(10); }
  } else if(lockedAxis==='y' || dy > hoverY){
    if(dy > hoverY && Math.abs(dy) > Math.abs(dx)){ zones.catalog.classList.add('on'); trays.catalog.className='tray hover-catalog'; }
  }
});
topCard.addEventListener('pointerup', (e)=>{
  if(!dragging) return;
  dragging=false;
  topCard.classList.remove('dragging');
  Object.values(zones).forEach(z=>z.classList.remove('on'));
  Object.values(trays).forEach(t=>t.className='tray');
  const relX=84, relY=96;
  const flick = Math.abs(vx) > 0.6;
  let filed=null;
  if((Math.abs(dx) > Math.abs(dy) && dx < -relX) || (flick && dx < -40 && lockedAxis==='x')) filed='review';
  else if((Math.abs(dx) > Math.abs(dy) && dx > relX) || (flick && dx > 40 && lockedAxis==='x')) filed='mastered';
  else if(dy > relY && Math.abs(dy) > Math.abs(dx)) filed='catalog';
  if(filed) file(filed);
  else topCard.style.transform='';
  dx=0; dy=0; lockedAxis=null;
});
topCard.addEventListener('pointercancel', ()=>{
  dragging=false; topCard.classList.remove('dragging'); topCard.style.transform=''; dx=0; dy=0; lockedAxis=null;
  Object.values(zones).forEach(z=>z.classList.remove('on'));
  Object.values(trays).forEach(t=>t.className='tray');
});

async function file(kind){
  const card=currentCard();
  if(!card) return;
  const moves={ review:'translateX(-160%) rotate(-16deg)', mastered:'translateX(160%) rotate(16deg)', catalog:'translateY(160%) scale(.85)' };
  const pulse={ review:'pulse-review', catalog:'pulse-catalog', mastered:'pulse-mastered' };
  topCard.style.transition='transform .38s cubic-bezier(.2,0,0,1), opacity .32s';
  topCard.style.transform=moves[kind];
  topCard.style.opacity='0';
  trays[kind].classList.add(pulse[kind]);
  setTimeout(()=>{ trays[kind].className='tray'; }, 500);
  try{
    await fetch(`${BACKEND}/api/v1/file`, {method:'POST', headers:{'Content-Type':'application/json', ...uidHeaders()}, body: JSON.stringify({post_id: card.post_id, slide_index: card.slide_index, status: kind})});
  }catch(e){ console.error('file', e); }
  try{
    const shelvesRes = await fetch(`${BACKEND}/api/v1/shelves`, {headers: uidHeaders()});
    const ss = await shelvesRes.json();
    const updated = ss.find(s=>s.shelf_id===activeShelf.shelf_id);
    if(updated){
      activeShelf.fill_pct = updated.fill_pct;
      const spine = document.querySelector(`.spine[data-shelf="${activeShelf.shelf_id}"] .fillcap`);
      if(spine) spine.style.height = Math.round(updated.fill_pct*100)+'%';
    }
  }catch{}
  setTimeout(()=>{
    topCard.style.transition='none';
    topCard.style.transform='';
    topCard.style.opacity='1';
    flipped=false;
    flipInner.classList.remove('flipped');
    void topCard.offsetWidth;
    topCard.style.transition='';
    deckIndex++;
    renderStack();
  }, 380);
}

// onboarding: pseudo account with name/college/mail, dropdown clean, 3-dismiss
function maybeShowOnboarding(){
  if(REAL_ID) return; // already has account
  const dismiss = parseInt(localStorage.getItem('sr_nudge_dismissed')||'0',10);
  if(dismiss >= 3) return;
  if(!shelves || shelves.length===0) return;
  // show after short delay to not block first paint
  setTimeout(()=>{ if(!REAL_ID && onboardingSheet) onboardingSheet.style.display='flex'; }, 800);
}
function showOnboarding(force){
  if(force) onboardingSheet.style.display='flex';
  else maybeShowOnboarding();
}
function dismissOnboarding(){
  const c = parseInt(localStorage.getItem('sr_nudge_dismissed')||'0',10);
  localStorage.setItem('sr_nudge_dismissed', String(c+1));
  if(onboardingSheet) onboardingSheet.style.display='none';
}
async function submitOnboarding(){
  const name = document.getElementById('onName').value.trim();
  const college = document.getElementById('onCollege').value.trim().toLowerCase();
  const email = document.getElementById('onEmail').value.trim().toLowerCase();
  if(!name || name.length<1){ onErrorEl.textContent='Enter your name'; onErrorEl.style.display='block'; return; }
  if(!college){ onErrorEl.textContent='Select your college'; onErrorEl.style.display='block'; return; }
  if(!email || !email.includes('@')){ onErrorEl.textContent='Enter valid mail id'; onErrorEl.style.display='block'; return; }
  onErrorEl.style.display='none';
  try{
    const res = await fetch(`${BACKEND}/api/v1/users`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name, email, college})});
    if(!res.ok){ const t=await res.text(); throw new Error(t); }
    const user = await res.json();
    const oldAnon = USER_ID;
    USER_ID = user.id;
    REAL_ID = user.id;
    localStorage.setItem('sr_user_id', user.id);
    localStorage.setItem('sr_user_real_id', user.id);
    localStorage.setItem('sr_user_name', user.name);
    // migrate anon cards
    try{
      await fetch(`${BACKEND}/api/v1/users/migrate`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({from_id: oldAnon, to_id: user.id})});
    }catch(e){ console.warn('migrate', e); }
    localStorage.setItem('sr_nudge_dismissed','0');
    onboardingSheet.style.display='none';
    updateBadge();
    // reload shelves with new id
    await loadShelves();
    alert('Saved! Your shelf is now linked to '+user.name);
  }catch(e){
    onErrorEl.textContent='Failed: '+e.message;
    onErrorEl.style.display='block';
  }
}

function toggleTheme(){
  const b=document.body;
  const isDark=b.getAttribute('data-theme')==='dark';
  b.setAttribute('data-theme', isDark?'light':'dark');
  document.getElementById('themeBtn').textContent=isDark?'☀️':'🌙';
}

// expose for HTML onclick
window.showOnboarding=showOnboarding;
window.dismissOnboarding=dismissOnboarding;
window.submitOnboarding=submitOnboarding;
window.flipCard=flipCard;
window.file=file;

loadShelves();
