// Upload page — dropdown-driven auto-publish (no checklist)
try{ if(!localStorage.getItem('sr_session_token')) location.href='/auth'; }catch(e){}
const BACKEND = '';
function uidHeaders(){
  const id = localStorage.getItem('sr_user_real_id') || localStorage.getItem('sr_user_id') || 'anon';
  const tok = localStorage.getItem('sr_session_token') || '';
  const h={'X-User-Id': id};
  if(tok) h['Authorization']='Bearer '+tok;
  return h;
}
function jsonHeaders(){ return {...uidHeaders(), 'Content-Type':'application/json'}; }

let slideCount = 10;
const syllabusFile = document.getElementById('syllabusFile');
const resourceFile = document.getElementById('resourceFile');
const syllabusLabel = document.getElementById('syllabusLabel');
const syllabusName = document.getElementById('syllabusName');
const resourceLabel = document.getElementById('resourceLabel');
const resourceName = document.getElementById('resourceName');
const depthSelect = document.getElementById('depthSelect');
const toneSelect = document.getElementById('toneSelect');
const slideCountVal = document.getElementById('slideCountVal');
const generateBtn = document.getElementById('generateBtn');
const formStatus = document.getElementById('formStatus');
const formCard = document.getElementById('formCard');
const progressCard = document.getElementById('progressCard');
const overallBar = document.getElementById('overallBar');
const overallText = document.getElementById('overallText');
const logBox = document.getElementById('logBox');
const doneCard = document.getElementById('doneCard');
const doneMsg = document.getElementById('doneMsg');

function stepSlide(d){
  slideCount = Math.max(5, Math.min(20, slideCount + d));
  if(slideCountVal) slideCountVal.textContent = String(slideCount);
  validate();
}
window.stepSlide = stepSlide;

function validate(){
  const hasSyllabus = syllabusFile && syllabusFile.files && syllabusFile.files[0];
  if(generateBtn) generateBtn.disabled = !hasSyllabus;
}
syllabusFile.addEventListener('change', ()=>{
  const f = syllabusFile.files[0];
  if(!f){ syllabusName.textContent='Tap to choose syllabus PDF *'; syllabusLabel.classList.remove('has-file'); validate(); return; }
  if(!f.name.toLowerCase().endsWith('.pdf')){ syllabusName.textContent='❌ Only PDF allowed'; syllabusLabel.classList.remove('has-file'); generateBtn.disabled=true; return; }
  syllabusName.textContent = `📄 ${f.name} (${(f.size/1024).toFixed(0)} KB)`;
  syllabusLabel.classList.add('has-file');
  validate();
});
resourceFile.addEventListener('change', ()=>{
  const f = resourceFile.files[0];
  if(!f){ resourceName.textContent='Module notes / resources (optional)'; resourceLabel.classList.remove('has-file'); return; }
  if(!f.name.toLowerCase().endsWith('.pdf')){ resourceName.textContent='❌ Only PDF allowed'; resourceLabel.classList.remove('has-file'); return; }
  resourceName.textContent = `📎 ${f.name} (${(f.size/1024).toFixed(0)} KB)`;
  resourceLabel.classList.add('has-file');
});

function log(msg){
  if(!logBox) return;
  logBox.style.display='block';
  const line=document.createElement('div');
  line.textContent=`[${new Date().toLocaleTimeString()}] ${msg}`;
  logBox.appendChild(line);
  logBox.scrollTop = logBox.scrollHeight;
}
function setProgress(pct, text){
  if(overallBar) overallBar.style.width = pct+'%';
  if(overallText) overallText.textContent = text;
}

generateBtn.addEventListener('click', async ()=>{
  const sFile = syllabusFile.files[0];
  if(!sFile){ alert('Choose syllabus PDF'); return; }
  const rFile = resourceFile.files[0] || null;
  const depth = depthSelect.value;
  const tone = toneSelect.value;
  // disable
  generateBtn.disabled=true;
  formStatus.textContent='';
  if(formCard) formCard.style.opacity='0.6';
  if(progressCard) progressCard.style.display='block';
  if(doneCard) doneCard.style.display='none';
  if(logBox){ logBox.innerHTML=''; logBox.style.display='none'; }
  setProgress(5, 'Uploading syllabus…');

  let uploaded = null;
  try{
    const form = new FormData();
    form.append('file', sFile);
    if(rFile) form.append('resource_file', rFile);
    log(`Uploading ${sFile.name} ${rFile ? '+ '+rFile.name : ''} as ${depth}/${tone} ×${slideCount}`);
    const res = await fetch(`${BACKEND}/api/v1/syllabus/upload`, {method:'POST', body: form, headers: uidHeaders()});
    if(!res.ok){ const t=await res.text(); throw new Error(t); }
    const upText = await res.text();
    uploaded = JSON.parse(upText);
    log(`Extracted ${uploaded.modules.length} modules from ${uploaded.file_name}`);
    setProgress(15, `Extracted ${uploaded.modules.length} modules — generating tailored topics…`);
  }catch(e){
    setProgress(0, 'Upload failed');
    log('❌ Upload failed: '+e.message);
    formStatus.textContent='❌ '+e.message;
    generateBtn.disabled=false;
    if(formCard) formCard.style.opacity='1';
    return;
  }

  const modules = uploaded.modules || [];
  if(!modules.length){
    log('No modules found');
    setProgress(0, 'No modules');
    generateBtn.disabled=false;
    return;
  }

  // automatic-all: iterate each module
  const totalSteps = modules.length * 3 + 1; // topics, render, publish per module + upload done
  let step = 1;
  const results = [];
  for(let idx=0; idx<modules.length; idx++){
    const mod = modules[idx];
    const modLabel = mod.module_title || `Module ${mod.module_number}`;
    try{
      // 1) topics
      setProgress(Math.round((step/totalSteps)*100), `Generating topics for ${modLabel} (${idx+1}/${modules.length})…`);
      log(`Generating topics for ${modLabel} — ${depth}/${tone} ×${slideCount}`);
      const tRes = await fetch(`${BACKEND}/api/v1/modules/${mod.module_number}/topics`, {
        method:'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({depth_format: depth, tone: tone, slide_count: slideCount})
      });
      if(!tRes.ok){ const t=await tRes.text(); throw new Error(t); }
      const tText = await tRes.text();
      const topics = JSON.parse(tText);
      log(`→ ${topics.length} topics for ${modLabel}: ${topics.map(t=>t.header).join(' | ').slice(0,120)}`);
      step++; setProgress(Math.round((step/totalSteps)*100), `Rendering carousel for ${modLabel}…`);

      // 2) render
      const rRes = await fetch(`${BACKEND}/api/v1/carousels/render`, {
        method:'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({module_name: modLabel.slice(0,60), topics: topics})
      });
      if(!rRes.ok){ const t=await rRes.text(); throw new Error(t); }
      const rText = await rRes.text();
      const rendered = JSON.parse(rText);
      log(`→ Rendered ${rendered.slide_count} slides (id ${rendered.id}, ${rendered.carousel_id})`);
      step++; setProgress(Math.round((step/totalSteps)*100), `Publishing ${modLabel}…`);

      // 3) auto caption via preview (don't show edit)
      let meta = null;
      try{
        const mRes = await fetch(`${BACKEND}/api/v2/metadata/preview`, {
          method:'POST',
          headers: jsonHeaders(),
          body: JSON.stringify({module_name: modLabel, topics: topics})
        });
        if(mRes.ok) { const mText = await mRes.text(); meta = JSON.parse(mText); }
      }catch{}
      if(!meta) meta = {caption: `${modLabel} — key concepts!`, hashtags: ["studyreel","exam","learn"], cover_slide: 0};
      // ensure hashtags at least 3
      if(!meta.hashtags || meta.hashtags.length<3) meta.hashtags = ["studyreel","exam","learn"];
      const pRes = await fetch(`${BACKEND}/api/v2/publish`, {
        method:'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({carousel_id: rendered.id, caption: meta.caption, hashtags: meta.hashtags, cover_slide: Math.min(meta.cover_slide||0, topics.length-1)})
      });
      if(!pRes.ok){ const t=await pRes.text(); throw new Error(t); }
      const pText = await pRes.text();
      const pub = JSON.parse(pText);
      log(`→ Published ${modLabel} → ${pub.media_id} (${pub.provider||'instaclone'})`);
      results.push({module: modLabel, rendered, pub, topics});
      step++; setProgress(Math.round((step/totalSteps)*100), `${modLabel} done (${idx+1}/${modules.length})`);

    } catch(e){
      log(`❌ Failed ${modLabel}: ${e.message}`);
      // continue to next module
      step+=3; // skip remaining steps for this module
    }
  }

  setProgress(100, `Done — ${results.length}/${modules.length} modules published`);
  log(`✅ All done — ${results.length} carousels published`);
  if(doneCard){
    doneCard.style.display='block';
    if(doneMsg) doneMsg.textContent = `Published ${results.length} of ${modules.length} modules. Your new Book appears in My Library.`;
  }
  // refetch shelves on next library load is automatic; redirect after short delay
  setTimeout(()=>{
    location.href='/deck';
  }, 1800);
});
