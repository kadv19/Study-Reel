try{ if(!localStorage.getItem('sr_session_token')) location.href='/auth'; }catch(e){}
const BACKEND = window.STUDYREEL_BACKEND || '';
const TOKEN = localStorage.getItem('sr_session_token') || '';
const REAL_ID = localStorage.getItem('sr_user_real_id') || null;
let USER_ID = REAL_ID || localStorage.getItem('sr_user_id') || 'anon';
if(REAL_ID) USER_ID = REAL_ID;

const state = {
  level: 1,
  books: [],
  shelves: [],
  trayCounts: { review: {}, catalog: {}, mastered: {} },
  activeBook: null,
  activeShelf: null,
  deck: null,
  deckRequest: 0,
  modalCard: null,
  modalFlipped: false
};

const STATUS_LABEL = { review: 'Review', catalog: 'Catalog', mastered: 'Mastered', unfiled: 'New' };
const TINTS = ['#38bdf8', '#818cf8', '#34d399', '#fbbf24', '#fb7185', '#22d3ee'];

const bookGrid = document.getElementById('bookGrid');
const bookEmpty = document.getElementById('bookEmpty');
const bookCount = document.getElementById('bookCount');
const shelfList = document.getElementById('shelfList');
const shelfEmpty = document.getElementById('shelfEmpty');
const shelfCount = document.getElementById('shelfCount');
const shelfHead = document.getElementById('shelfHead');
const cardGrid = document.getElementById('cardGrid');
const cardEmpty = document.getElementById('cardEmpty');
const cardCount = document.getElementById('cardCount');
const cardHead = document.getElementById('cardHead');
const subnav = document.getElementById('subnav');
const crumbKicker = document.getElementById('crumbKicker');
const crumbTitle = document.getElementById('crumbTitle');
const cardModal = document.getElementById('cardModal');
const modalFlip = document.getElementById('modalFlip');
const modalFront = document.getElementById('modalFront');
const modalBack = document.getElementById('modalBack');

function headers(){
  const h = { 'X-User-Id': REAL_ID || USER_ID };
  if(TOKEN) h['Authorization'] = 'Bearer ' + TOKEN;
  return h;
}

function esc(value){
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function clampPct(value){
  return Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
}

async function getJSON(path){
  try{
    const res = await fetch(`${BACKEND}${path}`, { headers: headers() });
    if(res.status === 401){ location.href = '/auth'; return null; }
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  }catch(err){
    console.error('cabinet fetch', path, err);
    return null;
  }
}

function loadingHtml(label){
  return `<div class="loading"><span class="spinner"></span>${esc(label)}</div>`;
}

function findBook(bookId){
  return state.books.find((b) =>
    String(b.book_id) === String(bookId) || String(b.syllabus_id) === String(bookId)
  ) || null;
}

function bookShelves(book){
  if(!book) return [];
  const embedded = Array.isArray(book.shelves) ? book.shelves : [];
  const matching = state.shelves.filter((s) =>
    String(s.syllabus_id) === String(book.syllabus_id) ||
    String(s.syllabus_id) === String(book.book_id)
  );
  const byId = new Map();
  [...embedded, ...matching].forEach((s) => {
    if(s && s.shelf_id != null) byId.set(String(s.shelf_id), s);
  });
  return [...byId.values()];
}

function findShelf(shelfId){
  const pools = [
    ...(state.activeBook ? bookShelves(state.activeBook) : []),
    ...state.shelves,
    ...state.books.flatMap((b) => Array.isArray(b.shelves) ? b.shelves : [])
  ];
  return pools.find((s) => String(s.shelf_id) === String(shelfId)) || null;
}

function deriveBooksFromShelves(){
  const byId = {};
  state.shelves.forEach((s) => {
    const id = s.syllabus_id ?? s.book_label ?? 'book';
    if(!byId[id]){
      byId[id] = {
        book_id: String(id),
        syllabus_id: s.syllabus_id,
        label: s.book_label || s.file_name || 'Book',
        file_name: s.file_name || '',
        total_slides: 0,
        mastered_count: 0,
        shelf_count: 0,
        fill_pct: 0,
        is_seed: !!s.is_seed,
        shelves: []
      };
    }
    const book = byId[id];
    book.total_slides += Number(s.total_slides) || 0;
    book.mastered_count += Number(s.mastered_count) || 0;
    book.shelf_count += 1;
    book.shelves.push(s);
  });
  state.books = Object.values(byId).map((b) => ({
    ...b,
    fill_pct: b.total_slides ? b.mastered_count / b.total_slides : 0
  }));
}

function buildTrayCounts(payloads){
  const counts = { review: {}, catalog: {}, mastered: {} };
  ['review', 'catalog', 'mastered'].forEach((tray) => {
    const cards = payloads[tray] && Array.isArray(payloads[tray].cards) ? payloads[tray].cards : [];
    cards.forEach((card) => {
      const key = String(card.post_id);
      counts[tray][key] = (counts[tray][key] || 0) + 1;
    });
  });
  state.trayCounts = counts;
}

function updateChrome(){
  subnav.classList.toggle('show', state.level > 1);
  if(state.level === 2 && state.activeBook){
    crumbKicker.textContent = 'Book';
    crumbTitle.textContent = state.activeBook.label || 'Book';
  }else if(state.level === 3 && state.activeShelf){
    crumbKicker.textContent = 'Shelf';
    crumbTitle.textContent = state.activeShelf.module_name || state.activeShelf.label || 'Shelf';
  }
}

function setLevel(level, opts = {}){
  state.level = level;
  document.querySelectorAll('.level').forEach((el) => {
    const n = Number(el.dataset.level);
    el.classList.toggle('active', n === level);
    el.classList.toggle('before', n < level);
  });
  updateChrome();
  if(opts.push){
    history.pushState({ srView: 'cabinet', level, ...(opts.state || {}) }, '');
  }else if(opts.replace){
    history.replaceState({ srView: 'cabinet', level, ...(opts.state || {}) }, '');
  }
  if(opts.scroll !== false){
    const active = document.querySelector(`.level[data-level="${level}"]`);
    if(active) active.scrollTop = 0;
  }
}

function renderBooks(){
  bookGrid.innerHTML = '';
  const books = state.books;
  bookCount.textContent = `${books.length} book${books.length === 1 ? '' : 's'}`;
  bookEmpty.style.display = books.length ? 'none' : 'block';
  if(!books.length) return;

  books.forEach((book, index) => {
    const pct = clampPct((book.fill_pct || 0) * 100);
    const total = Number(book.total_slides) || 0;
    const mastered = Number(book.mastered_count) || 0;
    const shelfTotal = Number(book.shelf_count) || bookShelves(book).length;
    const shelfLabel = shelfTotal === 1 ? 'shelf' : 'shelves';
    const sub = book.file_name ? String(book.file_name).replace(/\.pdf$/i, '') : 'Study syllabus';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `book-cover cloth${(index % 4) + 1}${book.is_seed ? ' is-demo' : ''}`;
    btn.setAttribute('aria-label', `Open ${book.label || 'book'}`);
    btn.innerHTML = `
      ${book.is_seed ? '<span class="book-demo">DEMO</span>' : ''}
      <span class="book-kicker">${esc(shelfTotal)} ${shelfLabel} · ${esc(total)} cards</span>
      <h2 class="book-title">${esc(book.label || 'Untitled book')}</h2>
      <p class="book-sub">${esc(sub)}</p>
      <div class="book-bottom">
        <div class="book-frac"><b>${mastered}/${total}</b>mastered</div>
        <div class="ring" style="--pct:${pct}"><span>${pct}%</span></div>
      </div>
    `;
    btn.addEventListener('click', () => openBook(book.book_id || book.syllabus_id));
    bookGrid.appendChild(btn);
  });
}

function renderShelves(book){
  state.activeBook = book;
  const scoped = bookShelves(book);
  shelfList.innerHTML = '';
  shelfHead.textContent = 'Shelves';
  shelfCount.textContent = `${scoped.length} shelf${scoped.length === 1 ? '' : 's'}`;
  shelfEmpty.style.display = scoped.length ? 'none' : 'block';
  if(!scoped.length) return;

  scoped.forEach((shelf, index) => {
    const key = String(shelf.carousel_id ?? shelf.shelf_id);
    const total = Number(shelf.total_slides) || 0;
    const mastered = state.trayCounts.mastered[key] || Number(shelf.mastered_count) || 0;
    const review = state.trayCounts.review[key] || 0;
    const catalog = state.trayCounts.catalog[key] || 0;
    const pct = clampPct((shelf.fill_pct || 0) * 100);
    const tint = TINTS[index % TINTS.length];
    let chips = '';
    if(review) chips += `<span class="chip review">${review} Review</span>`;
    if(mastered) chips += `<span class="chip mastered">${mastered} Mastered</span>`;
    if(!review && !mastered && catalog) chips += `<span class="chip cards">${catalog} Saved</span>`;
    if(!chips) chips = `<span class="chip cards">${total} Cards</span>`;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'shelf-card';
    btn.style.setProperty('--tint', tint);
    btn.setAttribute('aria-label', `Open ${shelf.module_name || shelf.label || 'shelf'}`);
    btn.innerHTML = `
      <div class="shelf-main">
        <div class="shelf-kicker">${shelf.is_seed ? 'Demo shelf' : `Module ${String(index + 1).padStart(2, '0')}`}</div>
        <div class="shelf-title">${esc(shelf.module_name || shelf.label || 'Untitled shelf')}</div>
        <div class="shelf-meta">${total} cards · ${pct}% mastered</div>
      </div>
      <div class="shelf-side">${chips}</div>
      <span class="shelf-go">›</span>
    `;
    btn.addEventListener('click', () => openShelf(shelf.shelf_id));
    shelfList.appendChild(btn);
  });
}

function slideImageUrl(shelf, card){
  if(!shelf || shelf.is_seed || String(shelf.shelf_id || '').startsWith('seed_')) return '';
  const cid = card.post_id ?? shelf.carousel_id;
  if(cid == null || !Number.isFinite(Number(cid))) return '';
  return `${BACKEND}/api/v1/carousels/${encodeURIComponent(cid)}/slides/${Number(card.slide_index) || 0}.png`;
}

function renderCardsLoading(shelf){
  cardHead.textContent = 'Cards';
  cardCount.textContent = '—';
  cardEmpty.style.display = 'none';
  cardGrid.innerHTML = loadingHtml('Opening shelf…');
  crumbKicker.textContent = 'Shelf';
  crumbTitle.textContent = shelf.module_name || shelf.label || 'Shelf';
}

function renderCards(data, shelf){
  const cards = data && Array.isArray(data.cards) ? data.cards : [];
  cardGrid.innerHTML = '';
  cardHead.textContent = 'Cards';
  cardCount.textContent = `${cards.length} card${cards.length === 1 ? '' : 's'}`;
  cardEmpty.style.display = cards.length ? 'none' : 'block';
  crumbKicker.textContent = 'Shelf';
  crumbTitle.textContent = shelf.module_name || shelf.label || 'Shelf';
  if(!cards.length) return;

  cards.forEach((card) => {
    const front = card.front || {};
    const image = slideImageUrl(shelf, card);
    const status = STATUS_LABEL[card.status] ? card.status : 'unfiled';
    const statusLabel = STATUS_LABEL[status];
    const slideNumber = String((Number(card.slide_index) || 0) + 1).padStart(2, '0');
    const body = front.body && String(front.body).trim().toLowerCase() !== 'see diagram'
      ? `<p>${esc(front.body)}</p>`
      : (front.diagram ? '<p>Diagram preview</p>' : '');
    const code = front.code ? `<div class="pf-code">${esc(front.code)}</div>` : '';
    const fallback = `
      <div class="preview-fallback">
        <div class="pf-kicker">${esc(front.slide_number || slideNumber)}/${esc(front.total_slides || cards.length)} · ${esc(card.tag || 'Card')}</div>
        <h4>${esc(front.header || 'Untitled card')}</h4>
        ${body}
        ${code}
      </div>
    `;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'preview-card';
    btn.setAttribute('aria-label', `Open card ${front.header || slideNumber}`);
    btn.innerHTML = `
      <div class="preview-media${image ? ' has-img' : ''}">
        ${image ? `<img src="${esc(image)}" alt="" loading="lazy" decoding="async" onerror="this.parentElement.classList.remove('has-img');this.remove()">` : ''}
        ${fallback}
        <span class="preview-num">${slideNumber}</span>
        <span class="preview-status ${status}"><span class="dot"></span>${statusLabel}</span>
      </div>
      <div class="preview-label">${esc(front.header || `Card ${slideNumber}`)}</div>
    `;
    btn.addEventListener('click', () => openCardModal(card));
    cardGrid.appendChild(btn);
  });
}

async function loadDeck(shelf){
  const request = ++state.deckRequest;
  const data = await getJSON(`/api/v1/deck?shelf=${encodeURIComponent(shelf.shelf_id)}&replay=1`);
  if(request !== state.deckRequest) return;
  if(!data){
    cardGrid.innerHTML = '';
    cardCount.textContent = '—';
    cardEmpty.style.display = 'block';
    cardEmpty.querySelector('b').textContent = 'Could not load this shelf';
    cardEmpty.querySelector('p').textContent = 'Check your connection and try again.';
    return;
  }
  state.deck = data;
  renderCards(data, shelf);
}

function openBook(bookId){
  const book = findBook(bookId);
  if(!book) return;
  state.activeBook = book;
  state.activeShelf = null;
  renderShelves(book);
  setLevel(2, {
    push: true,
    state: { bookId: book.book_id || book.syllabus_id }
  });
}

function openShelf(shelfId){
  const shelf = findShelf(shelfId);
  if(!shelf) return;
  state.activeShelf = shelf;
  renderCardsLoading(shelf);
  setLevel(3, {
    push: true,
    state: {
      bookId: state.activeBook ? (state.activeBook.book_id || state.activeBook.syllabus_id) : null,
      shelfId: shelf.shelf_id
    }
  });
  loadDeck(shelf);
}

function applyHistoryState(st){
  if(!st || st.srView !== 'cabinet'){
    state.activeBook = null;
    state.activeShelf = null;
    setLevel(1, { replace: false });
    return;
  }
  if(st.level === 1){
    state.activeBook = null;
    state.activeShelf = null;
    setLevel(1, { replace: false });
    return;
  }
  if(st.level === 2){
    const book = findBook(st.bookId);
    if(!book){
      setLevel(1, { replace: false });
      return;
    }
    state.activeShelf = null;
    renderShelves(book);
    setLevel(2, { replace: false });
    return;
  }
  const book = findBook(st.bookId);
  const shelf = findShelf(st.shelfId);
  if(!shelf){
    if(book){
      renderShelves(book);
      setLevel(2, { replace: false });
    }else{
      setLevel(1, { replace: false });
    }
    return;
  }
  if(book){
    state.activeBook = book;
    renderShelves(book);
  }
  state.activeShelf = shelf;
  renderCardsLoading(shelf);
  setLevel(3, { replace: false });
  loadDeck(shelf);
}

function cabinetBack(){
  if(cardModal.classList.contains('open')){
    closeCardModal();
    return;
  }
  if(state.level > 1){
    if(history.state && history.state.srView === 'cabinet' && history.state.level === state.level){
      history.back();
    }else{
      applyHistoryState({
        srView: 'cabinet',
        level: state.level - 1,
        bookId: state.activeBook ? (state.activeBook.book_id || state.activeBook.syllabus_id) : null,
        shelfId: state.activeShelf ? state.activeShelf.shelf_id : null
      });
    }
    return;
  }
  if(history.length > 1) history.back();
  else location.replace('/deck');
}

function diagramHtml(diagram){
  if(!diagram || !Array.isArray(diagram.nodes) || !diagram.nodes.length) return '';
  return `<div class="diagram">${diagram.nodes.map((node, index) => {
    const arrow = index < diagram.nodes.length - 1 ? '<div class="diagram-arrow">↓</div>' : '';
    return `<div class="diagram-node">${esc(node)}</div>${arrow}`;
  }).join('')}</div>`;
}

function weightDots(weight){
  const n = { low: 1, medium: 2, high: 3 }[weight] || 2;
  return [1, 2, 3].map((i) => `<span class="dot ${i <= n ? 'on' : ''}"></span>`).join('');
}

function openCardModal(card){
  const front = card.front || {};
  const back = card.back || {};
  const status = STATUS_LABEL[card.status] ? card.status : 'unfiled';
  const bodyIsSeeDiagram = front.body && String(front.body).trim().toLowerCase() === 'see diagram';
  const body = bodyIsSeeDiagram ? '' : (front.body ? `<p>${esc(front.body)}</p>` : '');
  const frontCode = front.code ? `<div class="code mono">${esc(front.code)}</div>` : '';
  const backCode = front.code ? `<div class="code mono">${back.exam_weight ? 'Weight: ' + esc(back.exam_weight) : ''}</div>` : '';
  const postLabel = String(card.post_id || '').slice(0, 4);

  state.modalCard = card;
  state.modalFlipped = false;
  modalFlip.classList.remove('flipped');

  modalFront.innerHTML = `
    <div class="punch"></div>
    <div class="ribbon"></div>
    <div class="cardhead">
      <span class="tab mono">${esc(postLabel)} · ${esc(front.slide_number || 1)}/${esc(front.total_slides || 1)}</span>
      <span class="tab">${STATUS_LABEL[status]}</span>
    </div>
    <div class="cardbody">
      <h2>${esc(front.header || 'Untitled card')}</h2>
      ${diagramHtml(front.diagram)}
      ${body}
      ${frontCode}
    </div>
    <div class="cardfoot">
      <span class="weight">exam weight ${weightDots(card.exam_weight || back.exam_weight)}</span>
      <button class="flipbtn" onclick="flipCard(event)">flip ↻</button>
    </div>
  `;

  modalBack.innerHTML = `
    <div class="punch"></div>
    <div class="cardhead"><span class="tab mono">${esc(back.back_header || 'WHY IT MATTERS')}</span></div>
    <div class="cardbody">
      <h2>${esc(back.back_header || 'Why it matters')}</h2>
      <p>${esc(back.back_body || 'Recall this for VTU.')}</p>
      ${backCode}
    </div>
    <div class="cardfoot">
      <span class="weight">exam weight ${weightDots(back.exam_weight)}</span>
      <button class="flipbtn" onclick="flipCard(event)">flip ↻</button>
    </div>
  `;

  cardModal.classList.add('open');
}

function closeCardModal(){
  cardModal.classList.remove('open');
  state.modalCard = null;
}

function flipCard(event){
  if(event) event.stopPropagation();
  state.modalFlipped = !state.modalFlipped;
  modalFlip.classList.toggle('flipped', state.modalFlipped);
}

function toggleTheme(){
  const body = document.body;
  const isDark = body.getAttribute('data-theme') === 'dark';
  body.setAttribute('data-theme', isDark ? 'light' : 'dark');
  const btn = document.getElementById('themeBtn');
  if(btn) btn.textContent = isDark ? '☀️' : '🌙';
}

function cabinetLogout(){
  localStorage.removeItem('sr_session_token');
  localStorage.removeItem('sr_user_real_id');
  location.href = '/auth';
}

async function loadCabinet(){
  bookGrid.innerHTML = loadingHtml('Loading your cabinet…');
  const [library, shelves, review, catalog, mastered] = await Promise.all([
    getJSON('/api/v1/library'),
    getJSON('/api/v1/shelves'),
    getJSON('/api/v1/cabinet?tray=review'),
    getJSON('/api/v1/cabinet?tray=catalog'),
    getJSON('/api/v1/cabinet?tray=mastered')
  ]);

  state.books = Array.isArray(library) ? library : [];
  state.shelves = Array.isArray(shelves) ? shelves : [];
  buildTrayCounts({ review, catalog, mastered });
  if(!state.books.length && state.shelves.length) deriveBooksFromShelves();
  renderBooks();
}

window.StudyReelBack = function(canGoBack){
  if(cardModal.classList.contains('open')){
    closeCardModal();
    return true;
  }
  if(state.level > 1){
    cabinetBack();
    return true;
  }
  if(canGoBack && history.length > 1) history.back();
  else location.replace('/deck');
  return true;
};

window.addEventListener('popstate', (event) => {
  if(event.state && event.state.srView === 'cabinet'){
    applyHistoryState(event.state);
  }else if(state.level > 1){
    applyHistoryState({ srView: 'cabinet', level: 1 });
  }
});

window.addEventListener('keydown', (event) => {
  if(event.key === 'Escape' && cardModal.classList.contains('open')) closeCardModal();
});

window.toggleTheme = toggleTheme;
window.cabinetBack = cabinetBack;
window.cabinetLogout = cabinetLogout;
window.openCardModal = openCardModal;
window.closeCardModal = closeCardModal;
window.flipCard = flipCard;

if(!history.state || history.state.srView !== 'cabinet'){
  history.replaceState({ srView: 'cabinet', level: 1 }, '');
}
setLevel(1, { scroll: false });
loadCabinet();
