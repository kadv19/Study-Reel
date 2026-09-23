// Deck: library (books → shelves), stack, flip, drag-to-file + replayMode
const BACKEND = '';
try{ if(!localStorage.getItem('sr_session_token')) location.href='/auth'; }catch(e){}
let USER_ID = localStorage.getItem('sr_user_real_id') || localStorage.getItem('sr_user_id') || 'anon';
let REAL_ID = localStorage.getItem('sr_user_real_id') || null;
let TOKEN = localStorage.getItem('sr_session_token') || '';
let books = [];
let shelves = [];
let activeBook = null;
let activeShelf = null;
let deck = null;
let deckIndex = 0;
let flipped = false;
let replayMode = false;

const libraryView = document.getElementById('libraryView');
const bookView = document.getElementById('bookView');
const bookRow = document.getElementById('bookRow');
const libraryEmpty = document.getElementById('libraryEmpty');
const libraryCount = document.getElementById('libraryCount');
const bookTitleEl = document.getElementById('bookTitle');
const shelfRow = document.getElementById('shelfrow');
const shelfNameEl = document.getElementById('shelfName');
const topCard = document.getElementById('topCard');
const flipInner = document.getElementById('flipInner');
const faceFront = document.getElementById('faceFront');
const faceBack = document.getElementById('faceBack');
const zones = { review: document.getElementById('zoneReview'), catalog: document.getElementById('zoneCatalog'), mastered: document.getElementById('zoneMastered'), replay: document.getElementById('zoneReplay') };
const trays = { review: document.getElementById('trayReview'), catalog: document.getElementById('trayCatalog'), mastered: document.getElementById('trayMastered') };
const back2 = document.getElementById('back2');
const back3 = document.getElementById('back3');
const emptyMsg = document.getElementById('emptyMsg');
const emptyTextEl = emptyMsg ? emptyMsg.querySelector('.empty-text') : null;
const replayBtn = document.getElementById('replayBtn');
const uploadLink = document.getElementById('uploadLink');
const traysRow = document.querySelector('.trays');
const dragTipEl = document.getElementById('dragTip');
const accountNameEl = document.getElementById('accountName');
const accountCollegeEl = document.getElementById('accountCollege');

function uidHeaders(){
  const id = REAL_ID || USER_ID;
  const h={'X-User-Id': id};
  if(TOKEN) h['Authorization']='Bearer '+TOKEN;
  return h;
}
function updateBadge(){
  const rawName = localStorage.getItem('sr_user_name');
  const name = (rawName && rawName.trim()) ? rawName.trim() : (REAL_ID ? REAL_ID.slice(0,6) : USER_ID);
  const college = localStorage.getItem('sr_user_college') || '';
  if(accountNameEl) accountNameEl.textContent = name;
  if(accountCollegeEl) accountCollegeEl.textContent = college ? '· '+college : '';
  const initialEl = document.getElementById('accountInitial');
  if(initialEl) initialEl.textContent = (name.trim()[0] || 'S').toUpperCase();
  const welcomeEl = document.getElementById('welcomeTitle');
  if(welcomeEl){
    const firstName = name.split(' ')[0] || name;
    welcomeEl.textContent = firstName ? `Welcome back, ${firstName}` : 'Welcome back';
  }
  // If name was fallback (no sr_user_name), try to fetch fresh from backend and retry
  if(!rawName || !rawName.trim()){
    fetch(`${BACKEND}/api/v1/auth/me?token=${encodeURIComponent(TOKEN||'')}`, {headers: uidHeaders()}).then(r=>r.ok?r.json():null).then(u=>{
      if(u && u.name && u.name.trim()){
        localStorage.setItem('sr_user_name', u.name);
        if(u.college) localStorage.setItem('sr_user_college', u.college);
        // retry
        const n2 = u.name.trim();
        if(accountNameEl) accountNameEl.textContent = n2;
        if(document.getElementById('accountInitial')) document.getElementById('accountInitial').textContent = n2[0].toUpperCase();
        if(welcomeEl) welcomeEl.textContent = `Welcome back, ${n2.split(' ')[0]}`;
      }
    }).catch(()=>{});
  }
}
updateBadge();
// Re-run after a short delay to catch cases where DOM was not ready at first call (e.g., service worker cached old HTML)
setTimeout(updateBadge, 500);
function handleLogout(){
  try{
    const tok = localStorage.getItem('sr_session_token');
    if(tok) fetch(`${BACKEND}/api/v1/auth/logout`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({token: tok})}).catch(()=>{});
  }catch{}
  localStorage.removeItem('sr_session_token');
  localStorage.removeItem('sr_user_real_id');
  location.href='/auth';
}
window.handleLogout = handleLogout;

function showLibrary(){
  replayMode = false;
  // reset trays/dragTip visibility for next book open (will be shown after shelf select)
  if(libraryView) libraryView.style.display='block';
  if(bookView) bookView.style.display='none';
  if(replayBtn) replayBtn.classList.remove('show');
  // refresh library to update progress
  loadLibrary();
}
window.showLibrary = showLibrary;

function openBook(bookId){
  const b = books.find(x=> String(x.book_id)===String(bookId) || String(x.syllabus_id)===String(bookId));
  if(!b) return;
  activeBook = b;
  replayMode = false;
  if(bookTitleEl) bookTitleEl.textContent = b.label;
  if(libraryView) libraryView.style.display='none';
  if(bookView) bookView.style.display='flex';
  // filter shelves for this book
  const scoped = shelves.filter(s=> String(s.syllabus_id)===String(b.syllabus_id) || String(s.syllabus_id)===String(b.book_id));
  renderShelfRow(scoped);
  if(scoped.length){
    selectShelf(scoped[0].shelf_id);
  } else {
    shelfRow.innerHTML = '<span style="font-size:11px;color:var(--muted)">No shelves in this book — render a module first</span>';
    shelfNameEl.textContent = b.label + ' — no shelves';
    setEmptyState(true, 'No cards in this shelf — upload a syllabus and render.', false);
  }
}
window.openBook = openBook;

async function deleteBook(bookId, event){
  if(event) event.stopPropagation();
  const b = books.find(x=> String(x.book_id)===String(bookId) || String(x.syllabus_id)===String(bookId));
  const label = b ? b.label : bookId;
  if(!confirm(`Delete "${label}"? This will remove all its shelves and cards. This cannot be undone.`)) return;
  try{
    const res = await fetch(`${BACKEND}/api/v1/library/${encodeURIComponent(bookId)}`, {method:'DELETE', headers: uidHeaders()});
    if(!res.ok){
      let msg = await res.text();
      try{ const j=JSON.parse(msg); msg=j.detail||msg; }catch{}
      throw new Error(msg);
    }
    // if deleted book was open, go back to library
    if(activeBook && (String(activeBook.book_id)===String(bookId) || String(activeBook.syllabus_id)===String(bookId))){
      activeBook = null;
      activeShelf = null;
      showLibrary();
    } else {
      await loadLibrary();
    }
  }catch(e){
    alert('Delete failed: ' + (e.message||e));
  }
}
window.deleteBook = deleteBook;

function renderLibrary(){
  const statBooksEl = document.getElementById('statBooks');
  const statShelvesEl = document.getElementById('statShelves');
  const statAvgEl = document.getElementById('statAvg');
  if(!bookRow) return;
  if(!books.length && !shelves.length){
    bookRow.innerHTML='';
    if(libraryEmpty) libraryEmpty.style.display='flex';
    if(libraryCount) libraryCount.textContent = '0 books';
    if(statBooksEl) statBooksEl.textContent = '0';
    if(statShelvesEl) statShelvesEl.textContent = '0';
    if(statAvgEl) statAvgEl.textContent = '0%';
    return;
  }
  if(libraryEmpty) libraryEmpty.style.display='none';
  let displayBooks = books;
  if(!displayBooks.length && shelves.length){
    const byId = {};
    shelves.forEach(s=>{
      const bid = s.syllabus_id || s.book_label || 'book';
      if(!byId[bid]) byId[bid] = {book_id: String(bid), syllabus_id: s.syllabus_id, label: s.book_label || s.file_name || 'Book', total_slides:0, mastered_count:0, shelf_count:0, file_name: s.file_name};
      byId[bid].total_slides += s.total_slides;
      byId[bid].mastered_count += s.mastered_count;
      byId[bid].shelf_count += 1;
    });
    displayBooks = Object.values(byId).map(b=> ({...b, fill_pct: b.total_slides? Math.round(b.mastered_count/b.total_slides*1000)/1000 : 0}));
  }
  // Flag duplicate titles for report — don't silently fix data issue
  const seen = {};
  displayBooks.forEach(b=>{ const k=(b.label||'').trim(); seen[k]=(seen[k]||0)+1; });
  const dups = Object.entries(seen).filter(([k,c])=>c>1 && k);
  if(dups.length && !window._dupWarned){
    console.warn('Duplicate book titles detected (flagging, not fixing):', dups);
    window._dupWarned = true;
  }
  if(libraryCount) libraryCount.textContent = `${displayBooks.length} book${displayBooks.length!==1?'s':''}`;
  const totalShelves = displayBooks.reduce((a,b)=>a+(b.shelf_count||0),0);
  const avgFilled = displayBooks.length ? Math.round(displayBooks.reduce((a,b)=>a+(b.fill_pct||0),0)/displayBooks.length*100) : 0;
  if(statBooksEl) statBooksEl.textContent = String(displayBooks.length);
  if(statShelvesEl) statShelvesEl.textContent = String(totalShelves);
  if(statAvgEl) statAvgEl.textContent = avgFilled + '%';
  bookRow.innerHTML='';
  displayBooks.forEach((b, idx)=>{
    const pct = Math.round((b.fill_pct||0)*100);
    const cloth = `cloth${(idx % 4) + 1}`;
    const el = document.createElement('div');
    el.className=`book ${cloth}`;
    el.dataset.book = b.book_id || b.syllabus_id;
    // calltag: reuse subject label or synthesize
    let calltag = '';
    if(b.file_name){
      const base = b.file_name.replace(/\.pdf$/i,'').replace(/ Syllabus$/i,'');
      const initials = b.label ? b.label.split(' ').map(w=>w[0]).join('').slice(0,3).toUpperCase() : 'BK';
      calltag = `${initials} · ${b.shelf_count||0} SH`;
    } else {
      calltag = `${b.shelf_count||0} SHELVES`;
    }
    // Use label as title, keep full subject for book cover (do not truncate)
    const frac = `${b.mastered_count||0}/${b.total_slides||0}`;
    const isSeed = b.is_seed;
    el.innerHTML = `
      ${isSeed ? `<span style="position:absolute; top:8px; right:8px; font-size:7px; background:rgba(0,0,0,0.25); color:rgba(242,233,211,0.8); padding:2px 5px; border-radius:3px; letter-spacing:0.05em;">DEMO</span>` : `<button class="delete-btn" onclick="deleteBook('${b.book_id || b.syllabus_id}', event)" title="Delete book">×</button>`}
      <div class="ribbonmark" style="height:${pct}%"></div>
      <span class="calltag">${calltag.replace(/</g,'&lt;')}</span>
      <h3>${(b.label||'Untitled').replace(/</g,'&lt;')}</h3>
      <div class="meta">${b.shelf_count||0} shelves · ${b.total_slides||0} cards</div>
      <div class="footrow"><span class="pct">${pct}%</span><span class="frac mono">${frac}</span></div>
      <div class="bar"><span style="width:${pct}%"></span></div>
    `;
    el.title = `${b.label} — ${b.shelf_count||0} shelves · ${b.total_slides||0} cards`;
    el.onclick = ()=> openBook(b.book_id || b.syllabus_id);
    bookRow.appendChild(el);
  });
}

function renderShelfRow(scoped){
  if(!shelfRow) return;
  shelfRow.innerHTML='';
  if(!scoped.length){
    shelfRow.innerHTML = '<span style="font-size:11px;color:var(--muted)">No shelves in this book</span>';
    return;
  }
  scoped.forEach((s,i)=>{
    const el=document.createElement('div');
    el.className='spine'+(i===0?' active':'');
    el.dataset.shelf=s.shelf_id;
    const pillLabel = s.module_name || (s.label.includes(' — ') ? s.label.split(' — ').pop() : s.label);
    el.innerHTML=`<span class="vlabel">${pillLabel.replace(/</g,'&lt;')}</span><div class="fillcap" style="--fill-pct:${Math.round(s.fill_pct*100)}%"></div>`;
    el.title=s.label;
    el.onclick=()=> selectShelf(s.shelf_id);
    shelfRow.appendChild(el);
  });
}

function setEmptyState(show, message, showReplay){
  if(!emptyMsg) return;
  if(show){
    if(message && emptyTextEl) emptyTextEl.textContent = message;
    emptyMsg.style.display='flex';
    topCard.style.display='none';
    back2.style.display='none';
    back3.style.display='none';
    if(!replayMode){
      if(traysRow) traysRow.style.display='none';
      if(dragTipEl) dragTipEl.style.display='none';
    }
    if(replayBtn){
      if(showReplay) replayBtn.classList.add('show');
      else replayBtn.classList.remove('show');
    }
    if(uploadLink){
      if(showReplay) uploadLink.style.display='none';
      else uploadLink.style.display='inline-block';
    }
  } else {
    emptyMsg.style.display='none';
    topCard.style.display='';
    back2.style.display='';
    back3.style.display='';
    // trays visibility depends on replayMode
    if(replayMode){
      if(traysRow) traysRow.style.display='none';
      if(dragTipEl) { dragTipEl.style.display='flex'; dragTipEl.textContent='replay — swipe up to continue ↺'; }
    } else {
      if(traysRow) traysRow.style.display='flex';
      if(dragTipEl) { dragTipEl.style.display='flex'; dragTipEl.textContent='try dragging the card toward a tray'; }
    }
    if(replayBtn) replayBtn.classList.remove('show');
  }
}

async function loadLibrary(){
  try{
    const [bRes, sRes] = await Promise.all([
      fetch(`${BACKEND}/api/v1/library`, {headers: uidHeaders()}),
      fetch(`${BACKEND}/api/v1/shelves`, {headers: uidHeaders()})
    ]);
    if(bRes.status===401 || sRes.status===401){ location.href='/auth'; return; }
    books = bRes.ok ? await bRes.json() : [];
    shelves = sRes.ok ? await sRes.json() : [];
    // if library endpoint fails, fallback derive books from shelves
    renderLibrary();
    // if there's a book param, auto-open
    const params = new URLSearchParams(location.search);
    const wantBook = params.get('book') || params.get('syllabus') || params.get('shelf');
    if(wantBook){
      // try to find matching book or shelf
      const mBook = books.find(b=> String(b.book_id)===wantBook || String(b.syllabus_id)===wantBook);
      if(mBook){ openBook(mBook.book_id); return; }
      const mShelf = shelves.find(s=> String(s.shelf_id)===wantBook);
      if(mShelf){ openBook(mShelf.syllabus_id); setTimeout(()=> selectShelf(mShelf.shelf_id), 200); return; }
    }
  }catch(e){
    console.error('loadLibrary', e);
    if(bookRow) bookRow.innerHTML='<span style="font-size:11px;color:var(--muted)">Failed to load library</span>';
  }
}

async function selectShelf(shelfId){
  // leaving shelf resets replayMode
  replayMode = false;
  document.querySelectorAll('.spine').forEach(el=>el.classList.toggle('active', el.dataset.shelf===shelfId));
  activeShelf = shelves.find(s=>s.shelf_id===shelfId);
  // also check scoped? if not found, search all shelves
  if(!activeShelf) activeShelf = shelves.find(s=> String(s.shelf_id)===String(shelfId));
  if(shelfNameEl) shelfNameEl.textContent = activeShelf ? `${activeShelf.label} — ${activeShelf.module_name || 'Module'}` : shelfId;
  deckIndex = 0;
  flipped = false;
  if(flipInner) flipInner.classList.remove('flipped');
  // ensure trays visible for normal mode
  if(traysRow) traysRow.style.display='flex';
  if(dragTipEl){ dragTipEl.style.display='flex'; dragTipEl.textContent='try dragging the card toward a tray'; }
  if(replayBtn) replayBtn.classList.remove('show');
  await loadDeck(shelfId, false);
}

async function loadDeck(shelfId, isReplay){
  try{
    const url = `${BACKEND}/api/v1/deck?shelf=${encodeURIComponent(shelfId)}` + (isReplay ? '&replay=1' : '');
    const res = await fetch(url, {headers: uidHeaders()});
    if(res.status===401){ location.href='/auth'; return; }
    if(!res.ok) throw new Error(await res.text());
    deck = await res.json();
    if(!deck.cards || deck.cards.length===0){
      // distinguish: if replay requested but still empty => truly no cards
      setEmptyState(true, 'No cards in this shelf — upload a syllabus and render.', false);
      return;
    }
    setEmptyState(false);
    deckIndex = 0;
    renderStack();
  }catch(e){
    console.error('deck', e);
    setEmptyState(true, 'Deck load failed: '+e.message, false);
  }
}

function currentCard(){
  if(!deck || !deck.cards || deckIndex>=deck.cards.length) return null;
  return deck.cards[deckIndex];
}

function renderStack(){
  const card = currentCard();
  if(!card){
    if(replayMode){
      // replay also exhausted — show end of replay with option to go back
      setEmptyState(true, 'End of replay — all cards seen again.', true);
      if(emptyTextEl) emptyTextEl.textContent='End of replay — all cards seen again.';
      if(replayBtn){ replayBtn.textContent='Replay again ↻'; replayBtn.classList.add('show'); }
      return;
    }
    // normal exhaustion — show replay button instead of static empty
    setEmptyState(true, 'Shelf cleared — every card filed. Review your work?', true);
    if(replayBtn){ replayBtn.textContent='See it again ↻'; replayBtn.classList.add('show'); }
    if(uploadLink) uploadLink.style.display='none';
    return;
  }
  setEmptyState(false);
  const next1 = deck.cards[deckIndex+1];
  const next2 = deck.cards[deckIndex+2];
  if(back2) back2.style.background = next1 ? 'var(--card)' : 'transparent';
  if(back3) back3.style.background = next2 ? 'var(--card)' : 'transparent';
  const ft = card.front, bk = card.back;
  const weightDots = (w)=>{
    const map={low:1, medium:2, high:3};
    const n=map[w]||2;
    return `<span class="dot ${n>=1?'on':''}"></span><span class="dot ${n>=2?'on':''}"></span><span class="dot ${n>=3?'on':''}"></span>`;
  };
  // diagram support — compact stacked boxes (denser for phone so trays stay visible)
  let diagramHtml = '';
  if(ft.diagram && ft.diagram.nodes && ft.diagram.nodes.length){
    const nodes = ft.diagram.nodes;
    const edges = ft.diagram.edges || [];
    diagramHtml = '<div class="diagram" style="display:flex;flex-direction:column;gap:4px;margin:6px 0 8px;">' +
      nodes.map((n,i)=>{
        const safe = String(n).replace(/</g,'&lt;');
        const box = `<div style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:6px 8px;border-radius:7px;font-weight:600;font-size:11.5px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.1)">${safe}</div>`;
        const showArrow = i < nodes.length - 1;
        const arrow = showArrow ? '<div style="display:flex;flex-direction:column;align-items:center;gap:1px;margin:1px 0"><div style="width:2px;height:8px;background:var(--cyan);opacity:0.55;border-radius:9999px"></div><div style="color:var(--cyan);font-size:10px;line-height:1">↓</div></div>' : '';
        return box + arrow;
      }).join('') +
      (edges.length ? `<div style="font-size:9.5px;color:var(--muted);text-align:center;margin-top:3px;opacity:0.7;word-break:break-word">${edges.map(e=> `${String(e[0]).replace(/</g,'&lt;')} → ${String(e[1]).replace(/</g,'&lt;')}`).join(' · ')}</div>` : '') +
      '</div>';
  }
  let bodyHtml = '';
  const bodyIsSeeDiagram = ft.body && ft.body.trim().toLowerCase() === 'see diagram';
  if(ft.diagram && bodyIsSeeDiagram){ bodyHtml = ''; }
  else if(ft.body){ bodyHtml = `<p>${ft.body}</p>`; }
  if(faceFront) faceFront.innerHTML = `
    <div class="punch"></div><div class="ribbon"></div>
    <div class="cardhead"><span class="tab mono">${card.post_id.slice(0,4)} · ${ft.slide_number}/${ft.total_slides}</span><span class="tab">${Math.round(30 + Math.random()*10)}s read</span></div>
    <div class="cardbody"><h2>${ft.header}</h2>${diagramHtml}${bodyHtml}${ft.code?`<div class="code mono">${ft.code.replace(/</g,'&lt;')}</div>`:''}</div>
    <div class="cardfoot"><span class="weight">exam weight ${weightDots(card.exam_weight||bk.exam_weight)}</span><button class="flipbtn" onclick="flipCard(event)">flip ↻</button></div>
  `;
  if(faceBack) faceBack.innerHTML = `
    <div class="punch"></div>
    <div class="cardhead"><span class="tab mono">${bk.back_header||'WHY IT MATTERS'}</span></div>
    <div class="cardbody"><h2>${bk.back_header||'Why it matters'}</h2><p>${bk.back_body||'Recall this for VTU.'}</p>${ft.code?`<div class="code mono">${bk.exam_weight? 'Weight: '+bk.exam_weight : ''}</div>`:''}</div>
    <div class="cardfoot"><span class="weight">exam weight ${weightDots(bk.exam_weight)}</span><button class="flipbtn" onclick="flipCard(event)">flip ↻</button></div>
  `;
  if(topCard){
    topCard.style.transition='none';
    topCard.style.transform='';
    topCard.style.opacity='1';
    flipped=false;
    if(flipInner) flipInner.classList.remove('flipped');
    void topCard.offsetWidth;
    topCard.style.transition='';
  }
  // in replay mode, ensure trays stay hidden
  if(replayMode){
    if(traysRow) traysRow.style.display='none';
    if(dragTipEl){ dragTipEl.style.display='flex'; dragTipEl.textContent='replay — swipe up to continue ↺'; }
  }
}

function flipCard(e){
  if(e) e.stopPropagation();
  flipped=!flipped;
  if(flipInner) flipInner.classList.toggle('flipped', flipped);
}

async function enterReplay(){
  if(!activeShelf) return;
  replayMode = true;
  if(replayBtn) replayBtn.classList.remove('show');
  // hide trays immediately
  if(traysRow) traysRow.style.display='none';
  if(dragTipEl){ dragTipEl.style.display='flex'; dragTipEl.textContent='replay — swipe up to continue ↺'; }
  await loadDeck(activeShelf.shelf_id, true);
}
window.enterReplay = enterReplay;

// drag handling — extends to support upward swipe for replay + scrollable cardbody coexistence
let dragging=false, startX=0, startY=0, dx=0, dy=0, startT=0, vx=0, lockedAxis=null;
let scrollableEl=null, startScrollTop=0;
if(topCard){
topCard.addEventListener('pointerdown', (e)=>{
  if(e.target.closest('.flipbtn')) return;
  // Check if touch started inside a scrollable cardbody — preserve native scroll for long text
  const cb = e.target.closest('.cardbody');
  if(cb && cb.scrollHeight > cb.clientHeight + 2){
    scrollableEl = cb;
    startScrollTop = cb.scrollTop;
  } else {
    scrollableEl = null;
    startScrollTop = 0;
  }
  dragging=true;
  topCard.classList.add('dragging');
  startX=e.clientX; startY=e.clientY; startT=performance.now(); dx=0; dy=0; vx=0; lockedAxis=null;
  try{ topCard.setPointerCapture(e.pointerId);}catch{}
});
topCard.addEventListener('pointermove', (e)=>{
  if(!dragging) return;
  const ndx=e.clientX-startX, ndy=e.clientY-startY;
  // If started inside scrollable cardbody and still can scroll in drag direction, let native scroll handle it — don't drag card
  if(scrollableEl){
    const canScrollUp = scrollableEl.scrollTop > 0;
    const canScrollDown = scrollableEl.scrollTop + scrollableEl.clientHeight < scrollableEl.scrollHeight - 1;
    if(Math.abs(ndy) > Math.abs(ndx)){
      if(ndy < 0 && canScrollDown){ return; }
      if(ndy > 0 && canScrollUp){ return; }
      // At edge and dragging beyond — will become card swipe, fall through to card drag
      // For at-top + drag down, or at-bottom + drag up, we want card swipe, so continue
      if((ndy > 0 && !canScrollUp) || (ndy < 0 && !canScrollDown)){
        // allow card drag, prevent native scroll chaining
        if(e.cancelable) e.preventDefault();
      }
    } else {
      // Horizontal drag inside scrollable should still be card swipe — prevent scroll
      if(Math.abs(ndx) > 8 && e.cancelable) e.preventDefault();
    }
  } else {
    // No scrollable element — prevent native page scroll during card drag
    if(Math.abs(ndx) > 4 || Math.abs(ndy) > 4){
      if(e.cancelable) e.preventDefault();
    }
  }
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
  if(Math.hypot(dx,dy) < 8) return;
  const rot = Math.max(-12, Math.min(12, dx*0.07));
  const clx = Math.max(-160, Math.min(160, dx));
  const cly = Math.max(-160, Math.min(160, dy));
  topCard.style.transform=`translate(${clx}px, ${cly}px) rotate(${rot}deg)`;
  Object.values(zones).forEach(z=> z && z.classList.remove('on'));
  Object.values(trays).forEach(t=> t && (t.className='tray'));
  const hoverX=32, hoverY=32;
  if(replayMode){
    // replay: only upward swipe matters, show replay hint when dragging up
    if(lockedAxis==='y' && dy < -hoverY && Math.abs(dy) > Math.abs(dx)){
      if(zones.replay) zones.replay.classList.add('on');
    }
    return;
  }
  if(lockedAxis==='x' || (!lockedAxis && Math.abs(dx) > Math.abs(dy))){
    if(dx < -hoverX){ if(zones.review) zones.review.classList.add('on'); if(trays.review) trays.review.className='tray hover-review'; if(dx>-36 && navigator.vibrate) navigator.vibrate(10); }
    else if(dx > hoverX){ if(zones.mastered) zones.mastered.classList.add('on'); if(trays.mastered) trays.mastered.className='tray hover-mastered'; if(dx<36 && navigator.vibrate) navigator.vibrate(10); }
  } else if(lockedAxis==='y' || dy > hoverY){
    if(dy > hoverY && Math.abs(dy) > Math.abs(dx)){ if(zones.catalog) zones.catalog.classList.add('on'); if(trays.catalog) trays.catalog.className='tray hover-catalog'; }
  }
}, {passive:false});
topCard.addEventListener('pointerup', (e)=>{
  if(!dragging) return;
  dragging=false;
  topCard.classList.remove('dragging');
  Object.values(zones).forEach(z=> z && z.classList.remove('on'));
  Object.values(trays).forEach(t=> t && (t.className='tray'));
  if(isSeedShelf()){
    const upThresh = 84;
    if(dy < -upThresh && Math.abs(dy) > Math.abs(dx)){
      deckIndex++;
      renderStack();
    } else if(Math.abs(dx) > 84 || dy > 84){
      // for demo, any swipe just advances (no filing)
      deckIndex++;
      renderStack();
    } else {
      topCard.style.transform='';
    }
    dx=0; dy=0; lockedAxis=null; scrollableEl=null;
    return;
  }
  if(replayMode){
    const upThresh = 84;
    if(dy < -upThresh && Math.abs(dy) > Math.abs(dx)){
      // advance without filing
      deckIndex++;
      renderStack();
    } else {
      topCard.style.transform='';
    }
    dx=0; dy=0; lockedAxis=null; scrollableEl=null;
    return;
  }
  const relX=84, relY=96;
  const flick = Math.abs(vx) > 0.6;
  let filed=null;
  if((Math.abs(dx) > Math.abs(dy) && dx < -relX) || (flick && dx < -40 && lockedAxis==='x')) filed='review';
  else if((Math.abs(dx) > Math.abs(dy) && dx > relX) || (flick && dx > 40 && lockedAxis==='x')) filed='mastered';
  else if(dy > relY && Math.abs(dy) > Math.abs(dx)) filed='catalog';
  if(filed) file(filed);
  else topCard.style.transform='';
  dx=0; dy=0; lockedAxis=null; scrollableEl=null;
});
topCard.addEventListener('pointercancel', ()=>{
  dragging=false; topCard.classList.remove('dragging'); topCard.style.transform=''; dx=0; dy=0; lockedAxis=null; scrollableEl=null;
  Object.values(zones).forEach(z=> z && z.classList.remove('on'));
  Object.values(trays).forEach(t=> t && (t.className='tray'));
});
}

function isSeedShelf(){ return activeShelf && (activeShelf.is_seed || String(activeShelf.shelf_id).startsWith('seed_')); }
async function file(kind){
  if(replayMode || isSeedShelf()) return; // disabled in replay and for demo seeds
  const card=currentCard();
  if(!card) return;
  const moves={ review:'translateX(-160%) rotate(-16deg)', mastered:'translateX(160%) rotate(16deg)', catalog:'translateY(160%) scale(.85)' };
  const pulse={ review:'pulse-review', catalog:'pulse-catalog', mastered:'pulse-mastered' };
  topCard.style.transition='transform .38s cubic-bezier(.2,0,0,1), opacity .32s';
  topCard.style.transform=moves[kind];
  topCard.style.opacity='0';
  if(trays[kind]) trays[kind].classList.add(pulse[kind]);
  setTimeout(()=>{ if(trays[kind]) trays[kind].className='tray'; }, 500);
  try{
    await fetch(`${BACKEND}/api/v1/file`, {method:'POST', headers:{'Content-Type':'application/json', ...uidHeaders()}, body: JSON.stringify({post_id: card.post_id, slide_index: card.slide_index, status: kind})});
  }catch(e){ console.error('file', e); }
  try{
    const shelvesRes = await fetch(`${BACKEND}/api/v1/shelves`, {headers: uidHeaders()});
    const ss = await shelvesRes.json();
    // update activeShelf fill locally and also update library book progress
    const updated = ss.find(s=>s.shelf_id===activeShelf.shelf_id);
    if(updated){
      activeShelf.fill_pct = updated.fill_pct;
      const cap = document.querySelector(`.spine[data-shelf="${activeShelf.shelf_id}"] .fillcap`);
      if(cap) cap.style.setProperty('--fill-pct', Math.round(updated.fill_pct*100)+'%');
      // also refresh books for library progress (but keep bookView)
      // quick update without full re-render: find book and recompute
      const b = books.find(bk=> String(bk.syllabus_id)===String(activeShelf.syllabus_id));
      if(b){
        // recalc from fresh shelves
        const scoped = ss.filter(s=> String(s.syllabus_id)===String(b.syllabus_id));
        const total = scoped.reduce((a,s)=>a+s.total_slides,0);
        const mastered = scoped.reduce((a,s)=>a+s.mastered_count,0);
        b.total_slides = total; b.mastered_count = mastered; b.fill_pct = total? mastered/total:0;
      }
    }
  }catch{}
  setTimeout(()=>{
    if(!topCard) return;
    topCard.style.transition='none';
    topCard.style.transform='';
    topCard.style.opacity='1';
    flipped=false;
    if(flipInner) flipInner.classList.remove('flipped');
    void topCard.offsetWidth;
    topCard.style.transition='';
    deckIndex++;
    renderStack();
  }, 380);
}

function toggleTheme(){
  const b=document.body;
  const isDark=b.getAttribute('data-theme')==='dark';
  b.setAttribute('data-theme', isDark?'light':'dark');
  const btn=document.getElementById('themeBtn');
  if(btn) btn.textContent=isDark?'☀️':'🌙';
}
window.toggleTheme = toggleTheme;

// expose for HTML onclick
window.flipCard=flipCard;
window.file=file;

loadLibrary();
