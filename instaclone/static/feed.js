// StudyReel Feed Controller — global trending, tag filter, diff, swipe
try{ if(!localStorage.getItem('sr_session_token')) location.href='/auth'; }catch(e){}
const postStates = {}; // { [postId]: { currentSlide: number, liked: boolean, viewed: boolean } }
let currentTag = "all";
let currentSort = "trending";
let lastHash = "";
let touchStartX = 0;

function resolveMediaUrl(path) {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/')) return path;
  return `/api/media?path=${encodeURIComponent(path)}`;
}

function timeAgo(isoString) {
  if (!isoString) return 'Just now';
  const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

async function handleInteract(postId, action, btnEl = null, countEl = null) {
  try {
    const res = await fetch(`/api/posts/${encodeURIComponent(postId)}/interact`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    });
    if (!res.ok) return;
    const data = await res.json();
    if (action === 'like') {
      postStates[postId].liked = true;
      if (btnEl) btnEl.classList.add('liked');
      if (countEl) countEl.textContent = data.likes;
    } else if (action === 'view' && countEl) {
      countEl.textContent = data.views;
    }
  } catch (err) { console.error('Interact failed:', err); }
}

function changeSlide(postId, newIdx, total) {
  if (newIdx < 0 || newIdx >= total) return;
  postStates[postId].currentSlide = newIdx;
  const track = document.getElementById(`track-${postId}`);
  const badge = document.getElementById(`badge-${postId}`);
  const dots = document.querySelectorAll(`.dot-${postId}`);
  if (track) track.style.transform = `translateX(-${newIdx * 100}%)`;
  if (badge) badge.textContent = `${newIdx + 1}/${total}`;
  dots.forEach((dot, idx) => dot.classList.toggle('active', idx === newIdx));
}

function attachSwipe(postId, total) {
  const container = document.getElementById(`carousel-${postId}`);
  if (!container) return;
  container.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; }, {passive:true});
  container.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) < 40) return;
    const cur = postStates[postId].currentSlide;
    if (dx < 0) changeSlide(postId, cur+1, total);
    else changeSlide(postId, cur-1, total);
  }, {passive:true});
}

function setFilter(tag) {
  currentTag = tag;
  document.querySelectorAll('.filter-chip').forEach(c => {
    const t = c.dataset.tag;
    if (["trending","newest"].includes(t)) return;
    c.classList.toggle('active', t===tag);
  });
  // Keep sort chip active separately
  loadFeed(true);
}

function setSort(sort) {
  currentSort = sort;
  document.querySelectorAll('.filter-chip').forEach(c => {
    if (c.dataset.tag==="trending" || c.dataset.tag==="newest") {
      c.classList.toggle('active', c.dataset.tag===sort);
    }
  });
  loadFeed(true);
}

function onHashtagClick(tag, e) {
  e.preventDefault();
  const clean = tag.replace(/^#/,'').toLowerCase();
  // Map hashtag to filter bucket: if tag is ai/rag etc -> ai, ev/bms/battery -> ev, aero/lift -> aero
  const map = {rag:"ai", transformer:"ai", machinelearning:"ai", llm:"ai", ev:"ev", bldc:"ev", battery:"ev", bms:"ev", aerodynamics:"aerodynamics", lift:"aerodynamics", drag:"aerodynamics", aviation:"aerodynamics"};
  const bucket = map[clean] || clean;
  // Try direct tag first
  setFilter(bucket);
}

function renderPost(post) {
  const pid = post.post_id || post.media_id;
  const slides = post.slides || [];
  const coverSlide = (Number.isInteger(post.cover_slide) && post.cover_slide >= 0 && post.cover_slide < slides.length) ? post.cover_slide : 0;
  
  if (!postStates[pid]) {
    postStates[pid] = { currentSlide: coverSlide, liked: false, viewed: false };
  }
  const curSlide = postStates[pid].currentSlide;
  const isLiked = postStates[pid].liked;

  const slidesHtml = slides.map(s => `
    <div class="carousel-slide">
      <img src="${resolveMediaUrl(s.image_path)}" alt="${s.header || 'Slide'}" loading="lazy" onerror="this.style.opacity='0.3'" />
    </div>`).join('');

  const dotsHtml = slides.length > 1 ? `
    <div class="carousel-dots">
      ${slides.map((_, i) => `<div class="dot dot-${pid} ${i === curSlide ? 'active' : ''}" onclick="changeSlide('${pid}', ${i}, ${slides.length})"></div>`).join('')}
    </div>` : '';

  const navButtons = slides.length > 1 ? `
    <button class="nav-btn nav-prev" onclick="changeSlide('${pid}', postStates['${pid}'].currentSlide - 1, ${slides.length})">&#10094;</button>
    <button class="nav-btn nav-next" onclick="changeSlide('${pid}', postStates['${pid}'].currentSlide + 1, ${slides.length})">&#10095;</button>` : '';

  const hashtagsHtml = (post.hashtags || []).map(tag => {
    const cleanTag = tag.startsWith('#') ? tag : `#${tag}`;
    const raw = tag.replace(/^#/,'');
    return `<a href="#" class="hashtag" onclick="onHashtagClick('${raw}', event)">${cleanTag}</a>`;
  }).join(' ');

  return `
    <article class="post-card" id="post-${pid}" data-post-id="${pid}">
      <header class="post-header">
        <div class="user-info">
          <div class="avatar-ring"><div class="avatar-inner">SR</div></div>
          <div>
            <div class="author-name">studyreel.ai <span style="color:#38bdf8;font-size:0.8rem;">&#10004;</span></div>
            <div class="post-time">${timeAgo(post.created_at)} · ${post.likes||0} likes</div>
          </div>
        </div>
      </header>

      <div class="carousel-container" id="carousel-${pid}" ondblclick="handleInteract('${pid}', 'like', document.getElementById('like-btn-${pid}'), document.getElementById('like-count-${pid}'))">
        <div class="carousel-track" id="track-${pid}" style="transform: translateX(-${curSlide * 100}%);">
          ${slidesHtml}
        </div>
        ${slides.length > 1 ? `<div class="slide-badge" id="badge-${pid}">${curSlide + 1}/${slides.length}</div>` : ''}
        ${navButtons}
        ${dotsHtml}
      </div>

      <div class="post-actions">
        <div class="action-group">
          <button class="action-btn ${isLiked ? 'liked' : ''}" id="like-btn-${pid}" onclick="handleInteract('${pid}', 'like', this, document.getElementById('like-count-${pid}'))">
            &hearts; <span class="count-label" id="like-count-${pid}">${post.likes || 0}</span>
          </button>
        </div>
        <div class="views-pill">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          <span id="view-count-${pid}">${post.views || 0}</span> views
        </div>
      </div>

      <div class="post-content">
        <div class="post-caption">
          <strong>studyreel.ai</strong> ${post.caption || ''}
        </div>
        <div class="hashtags-container">${hashtagsHtml}</div>
      </div>
    </article>`;
}

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const pid = entry.target.dataset.postId;
      if (pid && postStates[pid] && !postStates[pid].viewed) {
        postStates[pid].viewed = true;
        const vc = document.getElementById(`view-count-${pid}`);
        handleInteract(pid, 'view', null, vc);
        if (vc) vc.textContent = String((parseInt(vc.textContent)||0)+1);
      }
    }
  });
}, { threshold: 0.5 });

function hashPosts(posts) {
  return posts.map(p => `${p.post_id}:${p.likes}:${p.views}`).join('|');
}

function showSkeleton() {
  const container = document.getElementById('feed-container');
  if (!container) return;
  if (container.dataset.loaded==="true") return;
  container.innerHTML = [1,2].map(()=>`<div class="skeleton-card"><div class="skeleton-line" style="width:40%"></div><div class="skeleton-img"></div><div class="skeleton-line" style="width:80%"></div></div>`).join('');
}

async function loadFeed(force=false) {
  if (!force) showSkeleton();
  try {
    const params = new URLSearchParams({sort: currentSort});
    if (currentTag && currentTag!=="all" && currentTag!=="trending" && currentTag!=="newest") params.set("tag", currentTag);
    const res = await fetch(`/api/feed?${params.toString()}`);
    if (!res.ok) return;
    const data = await res.json();
    const posts = Array.isArray(data) ? data : (data.posts || []);
    const container = document.getElementById('feed-container');
    if (!container) return;

    if (!posts || posts.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">&#128247;</div>
          <h3>No Posts Yet</h3>
          <p style="color:var(--text-muted); margin-top:8px;">Trending AI/EV/Aero carousels will appear here. Upload a syllabus to generate your first post!</p>
        </div>`;
      container.dataset.loaded="true";
      return;
    }

    const h = hashPosts(posts);
    if (!force && h===lastHash && container.dataset.loaded==="true") {
      // still update counts live via DOM without full rebuild? quick patch counts
      posts.forEach(p=>{
        const pid=p.post_id||p.media_id;
        const lc=document.getElementById(`like-count-${pid}`);
        const vc=document.getElementById(`view-count-${pid}`);
        if(lc) lc.textContent=p.likes||0;
        if(vc) vc.textContent=p.views||0;
      });
      return;
    }
    lastHash=h;
    container.dataset.loaded="true";
    container.innerHTML = posts.map(renderPost).join('');
    // attach swipe + observer
    posts.forEach(p=>{
      const pid=p.post_id||p.media_id;
      attachSwipe(pid, (p.slides||[]).length);
    });
    document.querySelectorAll('.post-card').forEach(card => observer.observe(card));
    // keyboard nav for first post
    document.onkeydown = (e)=>{
      const first = posts[0]; if(!first) return;
      const pid=first.post_id||first.media_id;
      const total=(first.slides||[]).length;
      if(e.key==="ArrowRight") changeSlide(pid, postStates[pid].currentSlide+1, total);
      if(e.key==="ArrowLeft") changeSlide(pid, postStates[pid].currentSlide-1, total);
    };
  } catch (err) { console.error('Error loading feed:', err); }
}

document.addEventListener('DOMContentLoaded', () => {
  loadFeed();
  setInterval(loadFeed, 10000);
});
