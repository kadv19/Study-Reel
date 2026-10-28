// Deck: library (books → shelves), stack, flip, drag-to-file + replayMode
const BACKEND = window.STUDYREEL_BACKEND || '';
try{ if(!localStorage.getItem('sr_session_token')) location.href='/auth'; }catch(e){}
let USER_ID = localStorage.getItem('sr_user_real_id') || localStorage.getItem('sr_user_id') || 'anon';
let REAL_ID = localStorage.getItem('sr_user_real_id') || null;
let TOKEN = localStorage.getItem('sr_session_token') || '';
let books = [];
let shelves = [];
let activeBook = null;
let activeShelf = null;
let activeModuleNo = 1;
let deck = null;
let deckIndex = 0;
let flipped = false;
let replayMode = false;
let deepLinkHandled = false;
let historyDeckRestored = false;
const rewindHistory = [];
let busy = false;

const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

const libraryView = document.getElementById('libraryView');
const bookView = document.getElementById('bookView');
const bookRow = document.getElementById('bookRow');
const libraryEmpty = document.getElementById('libraryEmpty');
const libraryCount = document.getElementById('libraryCount');
const bookTitleEl = document.getElementById('bookTitle');
const shelfNameEl = document.getElementById('shelfName');
const moduleNumEl = document.getElementById('moduleNum');
const kickerEl = document.getElementById('kicker');
const segsEl = document.getElementById('segs');
const topCard = document.getElementById('topCard');
const flipInner = document.getElementById('flipInner');
const faceFront = document.getElementById('faceFront');
const faceBack = document.getElementById('faceBack');
const zones = { review: document.getElementById('zoneReview'), mastered: document.getElementById('zoneMastered'), replay: document.getElementById('zoneReplay') };
const actionButtons = { review: document.getElementById('btnReview'), mastered: document.getElementById('btnGot') };
const rewindBtn = document.getElementById('btnRewind');
const actionsRow = document.getElementById('actionsRow');
const deckHint = document.getElementById('deckHint');
const back2 = document.getElementById('back2');
const back3 = document.getElementById('back3');
const emptyMsg = document.getElementById('emptyMsg');
const emptyTextEl = emptyMsg ? emptyMsg.querySelector('.empty-text') : null;
const replayBtn = document.getElementById('replayBtn');
const uploadLink = document.getElementById('uploadLink');
const accountNameEl = document.getElementById('accountName');
const accountCollegeEl = document.getElementById('accountCollege');

function uidHeaders(){
  return TOKEN ? {'Authorization':'Bearer '+TOKEN} : {};
}

function handleUnauthorized(){
  try{ localStorage.clear(); }catch(e){}
  location.href='/auth';
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
    fetch(`${window.STUDYREEL_BACKEND}/api/v1/auth/me`, {headers: uidHeaders()}).then(r=>{ if(r.status===401){ handleUnauthorized(); return null; } return r.ok?r.text().then(t=>JSON.parse(t)):null; }).then(u=>{
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
    if(tok) fetch(`${window.STUDYREEL_BACKEND}/api/v1/auth/logout`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({token: tok})}).catch(()=>{});
  }catch{}
  localStorage.removeItem('sr_session_token');
  localStorage.removeItem('sr_user_real_id');
  location.href='/auth';
}
window.handleLogout = handleLogout;

function showLibrary(opts){
  opts = opts || {};
  // Hardware/browser back from the card deck: pop the deck history entry first.
  if(!opts.fromPop && history.state && history.state.srView==='deck'){
    history.back();
    return;
  }
  if(!opts.fromPop && (!history.state || history.state.srView!=='library')){
    history.replaceState({srView:'library'}, '');
  }
  replayMode = false;
  rewindHistory.length = 0;
  busy = false;
  document.body.classList.remove('deck-open');
  if(libraryView) libraryView.style.display='block';
  if(bookView) bookView.style.display='none';
  if(replayBtn) replayBtn.classList.remove('show');
  loadLibrary();
}
window.showLibrary = showLibrary;

function openBook(bookId, opts){
  opts = opts || {};
  const b = books.find(x=> String(x.book_id)===String(bookId) || String(x.syllabus_id)===String(bookId));
  if(!b){
    if(opts.fromPop) showLibrary({fromPop:true});
    return;
  }
  const resolvedBookId = b.book_id || b.syllabus_id;
  if(!opts.fromPop){
    history.pushState({srView:'deck', bookId: resolvedBookId, shelfId: opts.shelfId || null}, '');
  } else if(history.state && history.state.srView==='deck'){
    history.replaceState({...history.state, bookId: resolvedBookId}, '');
  }
  activeBook = b;
  replayMode = false;
  rewindHistory.length = 0;
  busy = false;
  document.body.classList.add('deck-open');
  if(bookTitleEl) bookTitleEl.textContent = b.label;
  if(libraryView) libraryView.style.display='none';
  if(bookView) bookView.style.display='flex';
  // filter shelves for this book
  const scoped = shelves.filter(s=> String(s.syllabus_id)===String(b.syllabus_id) || String(s.syllabus_id)===String(b.book_id));
  if(scoped.length){
    const preferred = opts.shelfId && scoped.find(s=> String(s.shelf_id)===String(opts.shelfId));
    selectShelf(preferred ? preferred.shelf_id : scoped[0].shelf_id, {fromPop: opts.fromPop});
  } else {
    if(shelfNameEl) shelfNameEl.textContent = b.label + ' — no shelves';
    if(moduleNumEl) moduleNumEl.textContent = '1';
    if(kickerEl) kickerEl.textContent = 'MODULE 1 · CARD 0 OF 0';
    renderSegs();
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
    const res = await fetch(`${window.STUDYREEL_BACKEND}/api/v1/library/${encodeURIComponent(bookId)}`, {method:'DELETE', headers: uidHeaders()});
    if(res.status===401){ handleUnauthorized(); return; }
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

function moduleNumberFor(shelf){
  if(!shelf) return 1;
  const raw = `${shelf.module_name || ''} ${shelf.label || ''}`;
  const m = raw.match(/module\s*(\d+)/i);
  if(m) return parseInt(m[1], 10);
  if(activeBook){
    const scoped = shelves.filter(s=> String(s.syllabus_id)===String(activeBook.syllabus_id) || String(s.syllabus_id)===String(activeBook.book_id));
    const idx = scoped.findIndex(s=> String(s.shelf_id)===String(shelf.shelf_id));
    if(idx >= 0) return idx + 1;
  }
  return 1;
}

function setEmptyState(show, message, showReplay){
  if(!emptyMsg) return;
  if(show){
    if(message && emptyTextEl) emptyTextEl.textContent = message;
    emptyMsg.style.display='flex';
    topCard.style.display='none';
    back2.style.display='none';
    back3.style.display='none';
    if(actionsRow) actionsRow.style.display='none';
    if(deckHint) deckHint.style.display='none';
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
    if(actionsRow) actionsRow.style.display='flex';
    if(deckHint){
      deckHint.style.display='block';
      deckHint.textContent = replayMode ? 'replay — swipe up to continue ↺' : "swipe left to review again · swipe right when you've got it";
    }
    if(replayBtn) replayBtn.classList.remove('show');
  }
  updateActionState();
}

async function loadLibrary(){
  try{
    const [bRes, sRes] = await Promise.all([
      fetch(`${window.STUDYREEL_BACKEND}/api/v1/library`, {headers: uidHeaders()}),
      fetch(`${window.STUDYREEL_BACKEND}/api/v1/shelves`, {headers: uidHeaders()})
    ]);
    if(bRes.status===401 || sRes.status===401){ handleUnauthorized(); return; }
    const bText = bRes.ok ? await bRes.text() : null;
    books = bRes.ok ? JSON.parse(bText) : [];
    const sText = sRes.ok ? await sRes.text() : null;
    shelves = sRes.ok ? JSON.parse(sText) : [];
    // if library endpoint fails, fallback derive books from shelves
    renderLibrary();
    // Restore the deck view when returning from an external page (same history entry).
    if(!historyDeckRestored && history.state && history.state.srView==='deck'){
      historyDeckRestored = true;
      openBook(history.state.bookId, {fromPop:true, shelfId:history.state.shelfId});
      return;
    }
    // if there's a book param, auto-open once (do not reopen after returning to library)
    const params = new URLSearchParams(location.search);
    const wantBook = params.get('book') || params.get('syllabus') || params.get('shelf');
    if(wantBook && !deepLinkHandled){
      deepLinkHandled = true;
      // try to find matching book or shelf
      const mBook = books.find(b=> String(b.book_id)===wantBook || String(b.syllabus_id)===wantBook);
      if(mBook){ openBook(mBook.book_id); return; }
      const mShelf = shelves.find(s=> String(s.shelf_id)===wantBook);
      if(mShelf){ openBook(mShelf.syllabus_id, {shelfId:mShelf.shelf_id}); return; }
    }
  }catch(e){
    console.error('loadLibrary', e);
    if(bookRow) bookRow.innerHTML='<span style="font-size:11px;color:var(--muted)">Failed to load library</span>';
  }
}

async function selectShelf(shelfId, opts){
  opts = opts || {};
  replayMode = false;
  rewindHistory.length = 0;
  busy = false;
  activeShelf = shelves.find(s=>s.shelf_id===shelfId);
  if(!activeShelf) activeShelf = shelves.find(s=> String(s.shelf_id)===String(shelfId));
  if(!opts.fromPop && history.state && history.state.srView==='deck'){
    history.replaceState({...history.state, shelfId: shelfId}, '');
  }
  activeModuleNo = moduleNumberFor(activeShelf);
  if(moduleNumEl) moduleNumEl.textContent = String(activeModuleNo);
  if(shelfNameEl) shelfNameEl.textContent = activeShelf ? (activeShelf.module_name || activeShelf.label) : shelfId;
  if(kickerEl) kickerEl.textContent = `MODULE ${activeModuleNo} · CARD 1 OF 1`;
  deckIndex = 0;
  flipped = false;
  if(flipInner) flipInner.classList.remove('flipped');
  if(replayBtn) replayBtn.classList.remove('show');
  await loadDeck(shelfId, false);
}

async function loadDeck(shelfId, isReplay){
  try{
    const url = `${window.STUDYREEL_BACKEND}/api/v1/deck?shelf=${encodeURIComponent(shelfId)}` + (isReplay ? '&replay=1' : '');
    const res = await fetch(url, {headers: uidHeaders()});
    if(res.status===401){ handleUnauthorized(); return; }
    if(!res.ok) throw new Error(await res.text());
    const deckText = await res.text();
    deck = JSON.parse(deckText);
    if(!deck.cards || deck.cards.length===0){
      renderSegs();
      if(kickerEl) kickerEl.textContent = `MODULE ${activeModuleNo} · CARD 0 OF 0`;
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

function renderStack(resetCard=true){
  const card = currentCard();
  if(!card){
    renderSegs();
    updateKicker();
    if(replayMode){
      setEmptyState(true, 'End of replay — all cards seen again.', true);
      if(emptyTextEl) emptyTextEl.textContent='End of replay — all cards seen again.';
      if(replayBtn){ replayBtn.textContent='Replay again ↻'; replayBtn.classList.add('show'); }
      return;
    }
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
  if(faceFront) faceFront.innerHTML = faceHTML(card, false);
  if(faceBack) faceBack.innerHTML = faceHTML(card, true);
  if(topCard && resetCard){
    topCard.classList.add('no-anim');
    topCard.style.transform='';
    topCard.style.opacity='1';
    flipped=false;
    if(flipInner) flipInner.classList.remove('flipped');
    void topCard.offsetWidth;
    topCard.style.transition='';
    topCard.classList.remove('no-anim');
  }
  renderSegs();
  updateKicker();
  updateActionState();
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(()=>{
    fitFace(faceFront);
    fitFace(faceBack);
  });
}

const weightNum = w => ({low:1, medium:2, high:3})[w] || 2;
const dots = w => [1,2,3].map(n=>`<span class="dot ${n<=w?'on':''}"></span>`).join('');

function readTime(card){
  const ft = card.front || {}, bk = card.back || {};
  const words = [ft.header, ft.body, ft.code, ft.example, bk.back_header, bk.back_body]
    .filter(Boolean).join(' ').trim().split(/\s+/).filter(Boolean).length;
  return Math.max(10, Math.round(words / 200 * 60));
}

function faceHTML(card, back){
  const ft = card.front || {};
  const bk = card.back || {};
  if(back){
    const header = bk.back_header || 'Why it matters';
    const body = bk.back_body || 'Recall this for VTU.';
    return `<div class="punch"></div>
      <div class="cardhead"><span class="tab mono">${esc(String(header).toUpperCase())}</span></div>
      <div class="cardbody"><div class="cardfit"><h2>${esc(header)}</h2><p>${esc(body)}</p></div></div>
      <div class="cardfoot"><span class="weight">exam weight ${dots(weightNum(bk.exam_weight))}</span><div class="cardactions"><button class="reportbtn" type="button" data-card-id="${esc(card.card_key)}" aria-label="Report wrong card" onpointerdown="event.stopPropagation()" onpointerup="event.stopPropagation()" ontouchstart="event.stopPropagation()" ontouchend="event.stopPropagation()" onclick="reportWrongCard(event, this)">Report wrong card</button><button class="flipbtn" type="button" onclick="flipCard(event)">flip ↻</button></div></div>`;
  }
  let diagramHtml = '';
  if(ft.diagram && ft.diagram.nodes && ft.diagram.nodes.length){
    const nodes = ft.diagram.nodes;
    const edges = ft.diagram.edges || [];
    diagramHtml = '<div class="diagram">' +
      nodes.map((n,i)=>`<div class="node">${esc(n)}</div>${i < nodes.length - 1 ? '<div class="arrow">↓</div>' : ''}`).join('') +
      (edges.length ? `<div class="edges">${edges.map(e=> `${esc(e[0])} → ${esc(e[1])}`).join(' · ')}</div>` : '') +
      '</div>';
  }
  let bodyHtml = '';
  const bodyIsSeeDiagram = ft.body && String(ft.body).trim().toLowerCase() === 'see diagram';
  if(ft.diagram && bodyIsSeeDiagram){ bodyHtml = ''; }
  else if(ft.body){ bodyHtml = `<p>${esc(ft.body)}</p>`; }
  const codeHtml = ft.code ? `<pre class="code mono">${esc(ft.code)}</pre>` : '';
  const exampleHtml = ft.example ? `<div class="spot"><b>Spot it:</b> ${esc(ft.example)}</div>` : '';
  const w = weightNum(card.exam_weight || bk.exam_weight);
  return `<div class="punch"></div><div class="ribbon"></div>
    <div class="cardhead"><span class="tab mono">${esc(String(card.post_id || '').slice(0,4))} · ${esc(ft.slide_number)}/${esc(ft.total_slides)}</span><span class="tab">${readTime(card)}s read</span></div>
    <div class="cardbody"><div class="cardfit">
      <h2>${esc(ft.header || 'Untitled')}</h2>${bodyHtml}${diagramHtml}${codeHtml}${exampleHtml}
    </div></div>
    <div class="cardfoot"><span class="weight">exam weight ${dots(w)}${w===3?'<span class="hy">high-yield</span>':''}</span><button class="flipbtn" type="button" onclick="flipCard(event)">flip ↻</button></div>`;
}

function fitFace(face){
  if(!face) return;
  const body = face.querySelector('.cardbody'), fit = face.querySelector('.cardfit');
  if (!body || !fit) return;
  const dense = !!fit.querySelector('.code, .diagram');
  const MAX = dense ? {h:32,p:21,s:17,c:15} : {h:46,p:31,s:22,c:14};
  const MIN = {h:21,p:15,s:13,c:12};
  const cs = getComputedStyle(body);
  const avail = body.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
  const set = s => {
    fit.querySelectorAll('h2').forEach(e => e.style.fontSize = (MIN.h + (MAX.h-MIN.h)*s) + 'px');
    fit.querySelectorAll('p').forEach(e => e.style.fontSize = (MIN.p + (MAX.p-MIN.p)*s) + 'px');
    fit.querySelectorAll('.spot,.diagram').forEach(e => e.style.fontSize = (MIN.s + (MAX.s-MIN.s)*s) + 'px');
    fit.querySelectorAll('.code').forEach(e => e.style.fontSize = (MIN.c + (MAX.c-MIN.c)*s) + 'px');
  };
  let lo = 0, hi = 1, best = 0;
  for (let k = 0; k < 9; k++){ const mid = (lo+hi)/2; set(mid); if (fit.offsetHeight <= avail) { best = mid; lo = mid; } else hi = mid; }
  set(best);
}

function renderSegs(){
  if(!segsEl) return;
  const prog = (deck && deck.progress) || [];
  const cur = currentCard() ? currentCard().slide_index : -1;
  segsEl.innerHTML = prog.map((s,k)=>`<i class="${s==='mastered'?'got':s==='review'?'review':''} ${k===cur?'cur':''}"></i>`).join('');
}

function updateKicker(){
  if(!kickerEl) return;
  const total = deck && deck.cards ? deck.cards.length : 0;
  const n = total ? Math.min(deckIndex+1, total) : 0;
  kickerEl.textContent = `MODULE ${activeModuleNo} · CARD ${n} OF ${total}`;
}

function updateRewind(){
  if(!rewindBtn) return;
  const disabled = !rewindHistory.length || replayMode || isSeedShelf();
  rewindBtn.setAttribute('aria-disabled', disabled ? 'true' : 'false');
}

function updateActionState(){
  const canAct = !replayMode && !isSeedShelf();
  if(actionButtons.review) actionButtons.review.setAttribute('aria-disabled', canAct ? 'false' : 'true');
  if(actionButtons.mastered) actionButtons.mastered.setAttribute('aria-disabled', canAct ? 'false' : 'true');
  updateRewind();
}

let resizeTimer;
addEventListener('resize', ()=>{
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(()=>{ fitFace(faceFront); fitFace(faceBack); }, 80);
});

function flipCard(e){
  if(e) e.stopPropagation();
  flipped=!flipped;
  if(flipInner) flipInner.classList.toggle('flipped', flipped);
}

async function reportWrongCard(event, btn){
  if(event){
    event.preventDefault();
    event.stopPropagation();
  }
  if(!btn || btn.disabled) return;
  const cardId = btn.dataset.cardId;
  if(!cardId) return;
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Reporting…';
  try{
    const res = await fetch(`${window.STUDYREEL_BACKEND}/api/v1/report`, {
      method:'POST',
      headers:{'Content-Type':'application/json', ...uidHeaders()},
      body: JSON.stringify({card_id: cardId, user_id: REAL_ID || '', reason: 'Reported wrong card'})
    });
    if(res.status===401){ handleUnauthorized(); return; }
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    btn.textContent = 'Reported ✓';
    setTimeout(()=>{ btn.textContent = original; btn.disabled = false; }, 1600);
  }catch(err){
    console.error('report', err);
    btn.textContent = 'Try again';
    setTimeout(()=>{ btn.textContent = original; btn.disabled = false; }, 1600);
  }
}

async function enterReplay(){
  if(!activeShelf) return;
  replayMode = true;
  rewindHistory.length = 0;
  busy = false;
  if(replayBtn) replayBtn.classList.remove('show');
  if(deckHint) deckHint.textContent = 'replay — swipe up to continue ↺';
  if(actionsRow) actionsRow.style.display='flex';
  updateActionState();
  await loadDeck(activeShelf.shelf_id, true);
}
window.enterReplay = enterReplay;

// drag handling — extends to support upward swipe for replay + scrollable cardbody coexistence
let dragging=false, startX=0, startY=0, dx=0, dy=0, startT=0, vx=0, lockedAxis=null;
let scrollableEl=null, startScrollTop=0;
if(topCard){
topCard.addEventListener('pointerdown', (e)=>{
  if(e.target.closest('.flipbtn') || e.target.closest('.reportbtn')) return;
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
  Object.values(actionButtons).forEach(b=> b && b.classList.remove('hover-review','hover-mastered'));
  const hoverX=32, hoverY=32;
  if(replayMode){
    // replay: only upward swipe matters, show replay hint when dragging up
    if(lockedAxis==='y' && dy < -hoverY && Math.abs(dy) > Math.abs(dx)){
      if(zones.replay) zones.replay.classList.add('on');
    }
    return;
  }
  if(isSeedShelf()) return;
  if(lockedAxis==='x' || (!lockedAxis && Math.abs(dx) > Math.abs(dy))){
    if(dx < -hoverX){ if(zones.review) zones.review.classList.add('on'); if(actionButtons.review) actionButtons.review.classList.add('hover-review'); if(dx>-36 && navigator.vibrate) navigator.vibrate(10); }
    else if(dx > hoverX){ if(zones.mastered) zones.mastered.classList.add('on'); if(actionButtons.mastered) actionButtons.mastered.classList.add('hover-mastered'); if(dx<36 && navigator.vibrate) navigator.vibrate(10); }
  }
}, {passive:false});
topCard.addEventListener('pointerup', (e)=>{
  if(!dragging) return;
  dragging=false;
  topCard.classList.remove('dragging');
  Object.values(zones).forEach(z=> z && z.classList.remove('on'));
  Object.values(actionButtons).forEach(b=> b && b.classList.remove('hover-review','hover-mastered'));
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
  const relX=84;
  const flick = Math.abs(vx) > 0.6;
  let filed=null;
  if((Math.abs(dx) > Math.abs(dy) && dx < -relX) || (flick && dx < -40 && lockedAxis==='x')) filed='review';
  else if((Math.abs(dx) > Math.abs(dy) && dx > relX) || (flick && dx > 40 && lockedAxis==='x')) filed='mastered';
  if(filed) file(filed);
  else topCard.style.transform='';
  dx=0; dy=0; lockedAxis=null; scrollableEl=null;
});
topCard.addEventListener('pointercancel', ()=>{
  dragging=false; topCard.classList.remove('dragging'); topCard.style.transform=''; dx=0; dy=0; lockedAxis=null; scrollableEl=null;
  Object.values(zones).forEach(z=> z && z.classList.remove('on'));
  Object.values(actionButtons).forEach(b=> b && b.classList.remove('hover-review','hover-mastered'));
});
}

function isSeedShelf(){ return activeShelf && (activeShelf.is_seed || String(activeShelf.shelf_id).startsWith('seed_')); }

async function file(kind){
  if(busy || replayMode || isSeedShelf()) return;
  const card=currentCard();
  if(!card) return;
  const moves={ review:'translateX(-160%) rotate(-16deg)', mastered:'translateX(160%) rotate(16deg)' };
  if(!moves[kind]) return;
  const i = deckIndex;
  const prev = card.status || 'unfiled';
  busy = true;
  topCard.classList.remove('no-anim');
  topCard.style.transition='transform .38s cubic-bezier(.2,0,0,1), opacity .32s';
  topCard.style.transform=moves[kind];
  topCard.style.opacity='0';
  try{
    const res = await fetch(`${window.STUDYREEL_BACKEND}/api/v1/file`, {method:'POST', headers:{'Content-Type':'application/json', ...uidHeaders()}, body: JSON.stringify({post_id: card.post_id, slide_index: card.slide_index, status: kind})});
    if(res.status===401){ handleUnauthorized(); busy=false; return; }
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    card.status = kind;
    if(deck.progress) deck.progress[card.slide_index] = kind;
    rewindHistory.push({cardKey: card.card_key, deckIndex: i, prevStatus: prev, kind});
    if(rewindHistory.length > 50) rewindHistory.shift();
    updateRewind();
    renderSegs();
  }catch(e){
    console.error('file', e);
    topCard.classList.add('no-anim');
    topCard.style.transform='';
    topCard.style.opacity='1';
    void topCard.offsetWidth;
    topCard.style.transition='';
    topCard.classList.remove('no-anim');
    busy=false;
    return;
  }
  setTimeout(()=>{
    if(!topCard){ busy=false; return; }
    deckIndex = Math.min(i+1, deck.cards.length-1);
    renderStack();
    if(i === deck.cards.length-1 && deckHint) deckHint.textContent = 'Module cleared. Rewind to look again.';
    busy=false;
    updateActionState();
  }, 380);
}

async function rewindCard(){
  if(busy || replayMode || isSeedShelf() || !rewindHistory.length) return;
  const h = rewindHistory[rewindHistory.length-1];
  const card = deck && deck.cards ? deck.cards.find(c=> String(c.card_key)===String(h.cardKey)) : null;
  if(!card){ rewindHistory.pop(); updateRewind(); return; }
  busy = true;
  try{
    const res = await fetch(`${window.STUDYREEL_BACKEND}/api/v1/file`, {method:'POST', headers:{'Content-Type':'application/json', ...uidHeaders()}, body: JSON.stringify({post_id: card.post_id, slide_index: card.slide_index, status: h.prevStatus})});
    if(res.status===401){ handleUnauthorized(); busy=false; return; }
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    rewindHistory.pop();
    card.status = h.prevStatus;
    if(deck.progress) deck.progress[card.slide_index] = h.prevStatus;
    deckIndex = h.deckIndex;
    flipped = false;
    if(flipInner) flipInner.classList.remove('flipped');
    topCard.classList.add('no-anim');
    topCard.style.transition='none';
    topCard.style.transform = h.kind === 'mastered' ? 'translateX(160%) rotate(16deg)' : 'translateX(-160%) rotate(-16deg)';
    topCard.style.opacity='0';
    renderStack(false);
    void topCard.offsetWidth;
    topCard.classList.remove('no-anim');
    topCard.style.transition='';
    topCard.style.transform='';
    topCard.style.opacity='1';
    if(deckHint) deckHint.textContent = "swipe left to review again · swipe right when you've got it";
  }catch(e){
    console.error('rewind', e);
  }
  busy = false;
  updateActionState();
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
window.rewindCard=rewindCard;
window.reportWrongCard=reportWrongCard;

function isDeckOpen(){
  return !!(bookView && bookView.style.display!=='none');
}

// Android hardware back (via Capacitor App plugin) and browser back.
window.StudyReelBack = function(canGoBack){
  if(isDeckOpen()){
    if(canGoBack && history.state && history.state.srView==='deck'){
      history.back();
    } else {
      if(history.state && history.state.srView==='deck'){
        history.replaceState({srView:'library'}, '');
      }
      showLibrary({fromPop:true});
    }
    return true;
  }
  // Root library view: leave the app rather than walking back into auth/onboarding.
  if(window.StudyReelExit && window.StudyReelExit()) return true;
  if(canGoBack) history.back();
  return true;
};

window.addEventListener('popstate', (e)=>{
  const st = e.state;
  if(st && st.srView==='deck'){
    openBook(st.bookId, {fromPop:true, shelfId:st.shelfId});
  } else {
    showLibrary({fromPop:true});
  }
});

if(!history.state || !history.state.srView){
  history.replaceState({srView:'library'}, '');
}
loadLibrary();
