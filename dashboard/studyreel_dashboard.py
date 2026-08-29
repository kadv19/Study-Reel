"""StudyReel Admin Dashboard — Syllabus Ingestion, Pipeline Monitor, Manual Review & Publish Queue."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone

import streamlit as st

from api_client import (
    check_backend_health,
    connect_oauth,
    export_carousel_zip,
    fetch_module_topics,
    fetch_pipeline_status,
    fetch_published_posts,
    fetch_v2_status,
    publish_carousel,
    render_carousel,
    revoke_oauth,
    upload_syllabus_pdf,
)

st.set_page_config(page_title="StudyReel Admin Dashboard", page_icon="??", layout="wide")
st.markdown(
    """
    <style>
      .stApp{background-color:#0F172A;color:#F8FAFC}
      .slide-card{background:#182234;border:1px solid #3B82F6;border-radius:10px;padding:18px;}
      .chip-published{background:#064E3B;color:#6EE7B7;border-radius:999px;padding:2px 12px;font-size:0.8rem;font-weight:600;display:inline-block;}
      .chip-queued{background:#1E3A5F;color:#93C5FD;border-radius:999px;padding:2px 12px;font-size:0.8rem;font-weight:600;display:inline-block;}
      .chip-connected{background:#064E3B;color:#6EE7B7;border-radius:999px;padding:2px 10px;font-size:0.75rem;font-weight:700;display:inline-block;}
      .chip-disconnected{background:#450A0A;color:#FCA5A5;border-radius:999px;padding:2px 10px;font-size:0.75rem;font-weight:700;display:inline-block;}
    </style>
    """,
    unsafe_allow_html=True,
)

for key, default in {
    "syllabus": None,
    "micro_topics": [],
    "active_module": None,
    "carousel": None,
    "oauth_token": None,
    "publish_result": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.title("?? StudyReel Admin")
    st.caption("Phase 1-4 Pipeline Control Panel")
    api_url = st.text_input("Backend API URL", value="http://127.0.0.1:8000").rstrip("/")
    if check_backend_health(api_url):
        st.success("?? Backend Connected", icon="?")
    else:
        st.error("?? Backend Offline (Start uvicorn)")
    st.divider()
    st.subheader("System Telemetry")
    status_data = fetch_pipeline_status(api_url)
    st.write(f"**State:** `{status_data.get('state', 'UNKNOWN')}`")
    st.write(f"**Stage:** `{status_data.get('stage', 'none')}`")
    st.write(f"**Progress:** `{int(status_data.get('progress', 0.0) * 100)}%`")
    if status_data.get("message"):
        st.caption(status_data.get("message"))
    st.divider()
    st.subheader("?? Connect Account")
    v2_status = fetch_v2_status(api_url)
    is_connected: bool = v2_status.get("oauth_connected", False)
    provider: str = v2_status.get("provider", "instaclone")
    if is_connected:
        st.markdown('<span class="chip-connected">? CONNECTED</span>', unsafe_allow_html=True)
        st.caption(f"Provider: `{provider}` · {v2_status.get('posts_published', 0)} posts published")
        if st.session_state["oauth_token"]:
            tok = st.session_state["oauth_token"]
            try:
                exp = datetime.fromisoformat(tok["expires_at"])
                days_left = max(0, (exp - datetime.now(timezone.utc)).days)
                st.caption(f"?? Token: `{tok['token'][:12]}…` · expires in **{days_left}d**")
            except Exception:
                pass
        if st.button("?? Revoke", key="btn_revoke", use_container_width=True):
            try:
                revoke_oauth(api_url)
                st.session_state["oauth_token"] = None
                st.success("Token revoked.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        st.markdown('<span class="chip-disconnected">? DISCONNECTED</span>', unsafe_allow_html=True)
        st.caption("Connect to unlock the Publish tab.")
        if st.button("? Connect (Simulated)", key="btn_connect", type="primary", use_container_width=True):
            try:
                tok = connect_oauth(api_url)
                st.session_state["oauth_token"] = tok
                st.success("Connected!")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

tabs = st.tabs([
    "?? Ingestion & Pipeline",
    "?? Manual Review (HITL)",
    "??? Carousel Preview & Export",
    "?? Publish",
])

with tabs[0]:
    st.subheader("Syllabus PDF Ingestion")
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader("Select Syllabus PDF", type=["pdf"])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("?? Run Pipeline", type="primary", use_container_width=True, disabled=not uploaded_file)
    if run_btn and uploaded_file:
        progress_bar = st.progress(0.0, text="Uploading syllabus PDF...")
        try:
            st.session_state["syllabus"] = upload_syllabus_pdf(api_url, uploaded_file.name, uploaded_file.getvalue())
            for _ in range(30):
                time.sleep(2)
                st_resp = fetch_pipeline_status(api_url)
                state = st_resp.get("state", "PROCESSING")
                progress_bar.progress(float(st_resp.get("progress", 0.5)), text=f"[{state}] {st_resp.get('message', 'Processing...')}")
                if state in {"DONE", "FAILED", "NEEDS_SUPERVISION"}:
                    break
            if st_resp.get("state") == "FAILED":
                st.error(f"Pipeline Failed: {st_resp.get('message', 'Unknown error')}")
            else:
                st.success("? Ingestion completed successfully!")
        except Exception as exc:
            st.error(f"Error: {exc}")
    if st.session_state["syllabus"]:
        sdata = st.session_state["syllabus"]
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("File Name", sdata.get("file_name", "Unknown"))
        m2.metric("Total Pages", sdata.get("total_pages", 0))
        modules = sdata.get("modules", [])
        m3.metric("Modules Extracted", len(modules))
        st.subheader("Extracted Modules & Topics")
        for mod in modules:
            title = mod.get("module_title") or f"Module {mod.get('module_number')}"
            topics = mod.get("topic_strings", [])
            with st.expander(f"?? {title} ({len(topics)} Topics)", expanded=True):
                for idx, t in enumerate(topics, 1):
                    st.markdown(f"**{idx}.** {t}")
                gen_btn = st.button(f"?? Generate AI Topics for {title}", key=f"gen_{mod.get('module_number')}", type="primary")
                if gen_btn:
                    try:
                        with st.spinner(f"Calling Gemini for {title} (45-90s)..."):
                            generated = fetch_module_topics(api_url, mod.get("module_number"))
                        st.session_state["micro_topics"] = generated
                        st.session_state["active_module"] = title
                        st.success(f"? {len(generated)} micro-topics generated — review them in the Manual Review tab!")
                    except Exception as exc:
                        st.error(f"Generation failed: {exc}")

with tabs[1]:
    st.subheader("Manual Review & Approval (Human-In-The-Loop)")
    topics = st.session_state["micro_topics"]
    if not topics:
        st.info("?? No topics yet — upload a syllabus and click 'Generate AI Topics' on a module in the Ingestion tab.")
    for i, t in enumerate(topics):
        with st.expander(f"Slide {i+1}: {t.get('header', 'Untitled')}", expanded=True):
            col_a, col_b = st.columns([1, 1])
            with col_a:
                new_h = st.text_input("Slide Title (max 30 chars)", value=t["header"], key=f"h_{i}", max_chars=30)
                new_b = st.text_area("Body Text (max 140 chars)", value=t["body"], key=f"b_{i}", max_chars=140)
            with col_b:
                new_c = st.text_area("Code Snippet (optional, max 22 lines)", value=t["code_block"] or "", key=f"c_{i}")
                lang_opts = ["", "python", "java", "cpp", "c", "js", "sql", "kotlin", "go", "bash", "html", "css"]
                new_lang = st.selectbox("Language Tag", options=lang_opts, index=lang_opts.index(t["language_tag"]) if t["language_tag"] else 0, key=f"l_{i}")
            topics[i]["header"], topics[i]["body"] = new_h, new_b
            topics[i]["code_block"] = new_c.strip() if new_c.strip() else None
            topics[i]["language_tag"] = new_lang if new_lang else None
    if topics:
        if st.button("?? Save & Approve Topics", type="primary"):
            st.session_state["micro_topics"] = topics
            st.session_state["carousel"] = None
            st.success(f"? {len(topics)} MicroTopics approved — render them in the Export tab!")

with tabs[2]:
    st.subheader("Carousel Visual Preview & Export")
    preview_topics = st.session_state["micro_topics"]
    if preview_topics:
        slide_idx = st.slider("Select Slide", 1, len(preview_topics), 1) - 1
        active = preview_topics[slide_idx]
        st.markdown(
            f"""
            <div class="slide-card">
                <div style="font-size: 0.85rem; color: #94A3B8; text-transform: uppercase;">StudyReel • Slide {slide_idx+1}/{len(preview_topics)}</div>
                <h2 style="color: #60A5FA; margin-top: 8px;">{active['header']}</h2>
                <p style="font-size: 1.1rem; line-height: 1.6; color: #E2E8F0;">{active['body']}</p>
                {"<div style='background: #020617; border: 1px solid #1E293B; border-radius: 6px; padding: 12px; font-family: monospace; color: #38BDF8;'><pre>" + active['code_block'] + "</pre></div>" if active.get('code_block') else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1])
        with c1:
            module_name = st.session_state.get("active_module") or "Module 1"
            render_topics = preview_topics[:10]
            if len(preview_topics) > 10:
                st.warning(f"?? Instagram allows max 10 slides — rendering first 10 of {len(preview_topics)} topics.")
            if st.button("?? Render Carousel (PNG slides)", type="primary", disabled=not preview_topics):
                try:
                    with st.spinner(f"Rendering {len(render_topics)} slides via Playwright..."):
                        st.session_state["carousel"] = render_carousel(api_url, module_name, render_topics)
                    st.success(f"? Rendered {st.session_state['carousel']['slide_count']} slides (id={st.session_state['carousel']['id']})")
                except Exception as exc:
                    st.error(f"Render failed: {exc}")
            if st.session_state.get("carousel"):
                car = st.session_state["carousel"]
                zip_bytes = export_carousel_zip(api_url, car["id"])
                st.download_button(label=f"?? Download Carousel ZIP ({car['slide_count']} slides)", data=zip_bytes, file_name=f"studyreel_carousel_{car['id']}.zip", mime="application/zip", type="primary")
                st.caption(f"?? Carousel `{car['carousel_id']}` • slides: {', '.join(car['slides'])}")
        with c2:
            st.download_button(label="?? Export Approved Topics (JSON)", data=str(st.session_state["micro_topics"]), file_name="studyreel_approved_topics.json", mime="application/json")
    else:
        st.info("?? Generate topics first — nothing to preview yet.")

with tabs[3]:
    st.subheader("?? Publish to InstaClone Feed")
    car = st.session_state.get("carousel")
    if not car:
        st.info("?? Render a carousel first (Carousel Preview & Export tab) before publishing.")
    else:
        module_name = st.session_state.get("active_module") or "Module 1"
        carousel_id: int = car["id"]
        st.markdown(f"Publishing carousel **`{car['carousel_id']}`** · {car['slide_count']} slides · module: *{module_name}*")
        st.divider()
        col_cap, col_hash = st.columns([3, 2])
        with col_cap:
            caption_default = (
                f"?? {module_name} — key concepts you need to know! ??\n"
                f"Save this carousel for your next study session.\n"
                f"Follow @StudyReel for daily CS content! ??"
            )
            caption = st.text_area("Caption (max 2 200 chars)", value=caption_default, max_chars=2200, height=110, key="pub_caption")
        with col_hash:
            hashtag_str = st.text_input("Hashtags (comma-separated, no #)", value="studyreel, computerscience, coding, learntocode, techstudent", key="pub_hashtags")
            hashtags = [h.strip().lstrip("#") for h in hashtag_str.split(",") if h.strip()]
            st.caption(f"{len(hashtags)} hashtag(s) · 3 minimum required")
        st.divider()
        btn_col, sched_col = st.columns([1, 2])
        with btn_col:
            publish_now = st.button("?? Publish Now", type="primary", use_container_width=True, key="btn_publish_now")
        with sched_col:
            with st.expander("?? Schedule for later"):
                sched_date = st.date_input("Date", value=date.today(), key="sched_date")
                sched_time = st.time_input("Time (local)", key="sched_time")
                schedule_btn = st.button("? Schedule Post", key="btn_schedule", use_container_width=True)
        if publish_now:
            if len(hashtags) < 3:
                st.error("Please enter at least 3 hashtags.")
            else:
                try:
                    with st.spinner("Publishing to InstaClone..."):
                        result = publish_carousel(api_url, carousel_id, caption, hashtags, schedule_at=None)
                    st.session_state["publish_result"] = result
                    st.rerun()
                except Exception as exc:
                    st.error(f"Publish failed: {exc}")
        if schedule_btn:
            if len(hashtags) < 3:
                st.error("Please enter at least 3 hashtags.")
            else:
                try:
                    sched_dt = datetime.combine(sched_date, sched_time).astimezone(timezone.utc).isoformat()
                    with st.spinner("Scheduling post..."):
                        result = publish_carousel(api_url, carousel_id, caption, hashtags, schedule_at=sched_dt)
                    st.session_state["publish_result"] = result
                    st.rerun()
                except Exception as exc:
                    st.error(f"Schedule failed: {exc}")
        if st.session_state.get("publish_result"):
            res = st.session_state["publish_result"]
            status = res.get("status", "unknown")
            chip_cls = "chip-published" if status == "published" else "chip-queued"
            feed_url = res.get("feed_url") or "http://127.0.0.1:8100/feed"
            st.markdown(f'<span class="{chip_cls}">? {status.upper()}</span> &nbsp; media_id: <code>{res.get("media_id") or "queued"}</code>', unsafe_allow_html=True)
            if status == "published":
                st.markdown(f"?? [View on InstaClone feed]({feed_url})")
        st.divider()
        st.subheader("?? Published Posts")
        posts = fetch_published_posts(api_url)
        has_queued = any(p.get("status") == "queued" for p in posts)
        if not posts:
            st.info("No posts yet — publish a carousel above.")
        else:
            rows = []
            for p in posts:
                raw_tags = p.get("hashtags", "[]")
                try:
                    tags = json.loads(raw_tags) if isinstance(raw_tags, str) else raw_tags
                except Exception:
                    tags = []
                cap_preview = (p.get("caption") or "")[:60] + ("…" if len(p.get("caption") or "") > 60 else "")
                rows.append({
                    "#": p.get("id"),
                    "Caption": cap_preview,
                    "Provider": p.get("provider", "instaclone"),
                    "Published At": (p.get("published_at") or "")[:16].replace("T", " "),
                    "Feed Link": p.get("feed_url") or "http://127.0.0.1:8100/feed",
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)
            for p in posts:
                feed = p.get("feed_url") or "http://127.0.0.1:8100/feed"
                st.markdown(f"  · `{p.get('media_id', '—')}` ? [?? Open feed]({feed})")
        if has_queued:
            st.caption("? Posts still queued — auto-refreshing every 5s…")
            time.sleep(5)
            st.rerun()
