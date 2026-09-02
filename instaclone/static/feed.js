// StudyReel InstaClone Feed Controller
const postStates = {}; // { [postId]: { currentSlide: number, liked: boolean, viewed: boolean } }

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

function renderPost(post) {
  const pid = post.post_id || post.media_id;
  const slides = post.slides || [];
  const coverSlide = (post.cover_slide && post.cover_slide <= slides.length) ? post.cover_slide - 1 : 0;
  
  if (!postStates[pid]) {
    postStates[pid] = { currentSlide: coverSlide, liked: false, viewed: false };
  }
  const curSlide = postStates[pid].currentSlide;
  const isLiked = postStates[pid].liked;

  const slidesHtml = slides.map(s => `
    <div class="carousel-slide">
      <img src="${resolveMediaUrl(s.image_path)}" alt="${s.header || 'Slide'}" loading="lazy" />
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
    return `<a href="#" class="hashtag">${cleanTag}</a>`;
  }).join(' ');

  return `
    <article class="post-card" id="post-${pid}" data-post-id="${pid}">
      <header class="post-header">
        <div class="user-info">
          <div class="avatar-ring"><div class="avatar-inner">SR</div></div>
          <div>
            <div class="author-name">studyreel.ai <span style="color:#38bdf8;font-size:0.8rem;">&#10004;</span></div>
            <div class="post-time">${timeAgo(post.created_at)}</div>
          </div>
        </div>
      </header>

      <div class="carousel-container" ondblclick="handleInteract('${pid}', 'like', document.getElementById('like-btn-${pid}'), document.getElementById('like-count-${pid}'))">
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
          <strong>studyreel.ai</strong>${post.caption || ''}
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
        handleInteract(pid, 'view', null, null);
      }
    }
  });
}, { threshold: 0.5 });

async function loadFeed() {
  try {
    const res = await fetch('/api/feed');
    if (!res.ok) return;
    const posts = await res.json();
    const container = document.getElementById('feed-container');
    if (!container) return;

    if (!posts || posts.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">&#128247;</div>
          <h3>No Posts Yet</h3>
          <p style="color:var(--text-muted); margin-top:8px;">Rendered carousels published via POST /api/posts will appear here live.</p>
        </div>`;
      return;
    }

    container.innerHTML = posts.map(renderPost).join('');
    document.querySelectorAll('.post-card').forEach(card => observer.observe(card));
  } catch (err) { console.error('Error loading feed:', err); }
}

document.addEventListener('DOMContentLoaded', () => {
  loadFeed();
  setInterval(loadFeed, 10000); // 10s auto-refresh
});
