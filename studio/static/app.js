/* ===== Thumbnail Studio — frontend logic ===== */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = (p, opts) => fetch(p, opts).then(async r => {
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
});
const fileUrl = p => `/api/file?path=${encodeURIComponent(p)}`;

const state = {
  view: 'studio',
  slug: null,
  concepts: [],      // current project concepts
  selected: new Set(),
  brief: {},
  feedback: {},      // { <image rel path>: {verdict:'like'|'dislike', note} }
  inspoImages: [],   // [{name, media_type, data(base64), dataUrl}]
  intakeMode: 'scratch',  // 'scratch' | 'inspiration'
};

/* ---------- Toasts ---------- */
function toast(msg, kind = '') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  const ic = kind === 'err' ? '⚠' : kind === 'ok' ? '✓' : '✳';
  el.innerHTML = `<span class="t-ic">${ic}</span><span>${msg}</span>`;
  $('#toasts').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = '.3s'; setTimeout(() => el.remove(), 300); }, kind === 'err' ? 5200 : 3000);
}

/* ---------- Views ---------- */
function showView(v) {
  state.view = v;
  $$('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  $$('.view').forEach(s => s.classList.toggle('active', s.id === `view-${v}`));
  if (v === 'memory') loadMemory();
  if (v === 'settings') loadSettings();
}
$$('.nav-item').forEach(b => b.onclick = () => showView(b.dataset.view));

/* ---------- Steps ---------- */
function setStep(n) {
  $$('.step').forEach(s => {
    const sn = +s.dataset.step;
    s.classList.toggle('on', sn === n);
    s.classList.toggle('done', sn < n);
  });
  $('#stage-intake').classList.toggle('hidden', n !== 1);
  $('#stage-concepts').classList.toggle('hidden', n !== 2);
  $('#stage-thumbs').classList.toggle('hidden', n !== 3);
}

/* ---------- Status / keys ---------- */
async function loadStatus() {
  try {
    const s = await api('/api/status');
    $('#keyStatus').innerHTML = `
      <div class="key-row"><span class="dot ${s.anthropic_key ? 'ok' : ''}"></span>Concepts (Claude)</div>
      <div class="key-row"><span class="dot ${s.fal_key ? 'ok' : ''}"></span>Images (fal)</div>`;
    if (!s.anthropic_key || !s.fal_key) {
      $('#keyStatus').innerHTML += `<div class="key-row" style="color:var(--orange);cursor:pointer" onclick="document.querySelector('[data-view=settings]').click()">→ Add keys in Settings</div>`;
    }
  } catch (e) { /* ignore */ }
}

/* ---------- Projects ---------- */
async function loadProjects() {
  const { projects } = await api('/api/projects');
  const list = $('#projectList');
  list.innerHTML = projects.length ? '' : '<div class="mem-empty" style="padding:8px 4px;font-size:12px">No videos yet</div>';
  projects.forEach(p => {
    const b = document.createElement('button');
    b.className = 'proj' + (p.slug === state.slug ? ' active' : '');
    b.innerHTML = `<b>${esc(p.title)}</b><small>${p.n_concepts} concepts · ${p.n_images} images</small>`;
    b.onclick = () => openProject(p.slug);
    list.appendChild(b);
  });
}

async function openProject(slug) {
  const p = await api(`/api/project/${slug}`);
  state.slug = slug;
  state.brief = p.brief || {};
  state.concepts = p.concepts || [];
  state.feedback = p.feedback || {};
  state.selected.clear();
  showView('studio');
  $('#studioTitle').textContent = state.brief.title || 'Untitled video';
  $('#studioSub').textContent = `${state.concepts.length} concepts · review, generate, iterate.`;
  $('#inTitle').value = state.brief.title || '';
  $('#inContext').value = state.brief.context || '';
  setMode(state.brief.mode || 'scratch');
  renderConcepts();
  loadProjects();
  if (state.concepts.some(c => (c.images || []).length)) { renderThumbs(); setStep(3); }
  else if (state.concepts.length) setStep(2);
  else setStep(1);
}

function newProject() {
  state.slug = null; state.brief = {}; state.concepts = []; state.selected.clear();
  state.inspoImages = []; renderInspoStrip(); setMode('scratch');
  $('#inTitle').value = ''; $('#inTranscript').value = ''; $('#inContext').value = ''; $('#inInspo').value = '';
  $('#studioTitle').textContent = 'New thumbnail';
  $('#studioSub').textContent = 'Paste a transcript, get concepts in your style, turn them into thumbnails.';
  showView('studio'); setStep(1);
  loadProjects();
}
$('#newProjectBtn').onclick = newProject;
$('#backToIntake').onclick = () => setStep(1);
$('#backToConcepts').onclick = () => setStep(2);

/* ---------- Inspiration images (paste / drop / browse) ---------- */
const inspoDrop = $('#inspoDrop');
const inspoFile = $('#inspoFile');

function addInspoFiles(files) {
  [...files].filter(f => f.type.startsWith('image/')).forEach(f => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      const comma = dataUrl.indexOf(',');
      state.inspoImages.push({
        name: f.name || 'pasted-image',
        media_type: f.type || 'image/png',
        data: dataUrl.slice(comma + 1),
        dataUrl,
      });
      renderInspoStrip();
    };
    reader.readAsDataURL(f);
  });
}
function renderInspoStrip() {
  const strip = $('#inspoStrip');
  strip.innerHTML = '';
  $('#inspoEmpty').style.display = state.inspoImages.length ? 'none' : 'flex';
  state.inspoImages.forEach((img, i) => {
    const d = document.createElement('div');
    d.className = 'inspo-thumb';
    d.innerHTML = `<img src="${img.dataUrl}" /><button type="button" class="ix" title="Remove">✕</button>`;
    d.querySelector('.ix').onclick = () => { state.inspoImages.splice(i, 1); renderInspoStrip(); };
    strip.appendChild(d);
  });
}
$('#inspoPick').onclick = () => inspoFile.click();
inspoDrop.onclick = e => { if (e.target === inspoDrop || e.target.id === 'inspoEmpty' || e.target.closest('#inspoEmpty')) { if (e.target.tagName !== 'BUTTON') inspoFile.click(); } };
inspoFile.onchange = () => { addInspoFiles(inspoFile.files); inspoFile.value = ''; };
['dragenter', 'dragover'].forEach(ev => inspoDrop.addEventListener(ev, e => { e.preventDefault(); inspoDrop.classList.add('dragover'); }));
['dragleave', 'drop'].forEach(ev => inspoDrop.addEventListener(ev, e => { e.preventDefault(); if (ev === 'dragleave' && inspoDrop.contains(e.relatedTarget)) return; inspoDrop.classList.remove('dragover'); }));
inspoDrop.addEventListener('drop', e => { if (e.dataTransfer?.files?.length) addInspoFiles(e.dataTransfer.files); });
// paste anywhere on the intake stage drops images into inspiration
document.addEventListener('paste', e => {
  if (state.view !== 'studio' || $('#stage-intake').classList.contains('hidden')) return;
  const imgs = [...(e.clipboardData?.items || [])].filter(i => i.type.startsWith('image/'));
  if (!imgs.length) return;
  e.preventDefault();
  addInspoFiles(imgs.map(i => i.getAsFile()).filter(Boolean));
  toast(`Added ${imgs.length} inspiration image${imgs.length > 1 ? 's' : ''}.`, 'ok');
});

/* ---------- Intake mode (scratch vs inspiration) ---------- */
function setMode(mode) {
  state.intakeMode = mode;
  $$('.mode-card').forEach(c => c.classList.toggle('active', c.dataset.mode === mode));
  $('#stage-intake').classList.toggle('from-inspiration', mode === 'inspiration');
  if (mode === 'inspiration') {
    $('#inspoLabel').innerHTML = 'Reference to base concepts on <span class="opt">(required — paste or drop the thumbnail)</span>';
    $('#inInspo').placeholder = 'Optional: what to keep, what to change vs the reference…';
    $('#genConceptsBtn').querySelector('.btn-label').textContent = 'Generate from inspiration';
  } else {
    $('#inspoLabel').innerHTML = 'Inspiration for this video <span class="opt">(optional — paste or drop images)</span>';
    $('#inInspo').placeholder = 'Notes, creators or styles to borrow from…';
    $('#genConceptsBtn').querySelector('.btn-label').textContent = 'Generate concepts';
  }
}
$$('.mode-card').forEach(c => c.onclick = () => setMode(c.dataset.mode));

/* ---------- Intake → concepts ---------- */
$('#inCount').oninput = e => $('#inCountOut').textContent = e.target.value;

const LAB_PHASES = [
  'Reading your style profile…',
  'Studying your likes & dislikes…',
  'Soaking up your inspiration…',
  'Finding distinct angles…',
  'Writing punchy hooks…',
  'Composing the shots…',
  'Polishing the concepts…',
];
let labTimer = null;
function startConceptLab(n, append) {
  const grid = $('#conceptGrid');
  $('#conceptStatus').classList.remove('hidden');
  if (append) renderConcepts(); else grid.innerHTML = '';
  for (let i = 0; i < n; i++) {
    const s = document.createElement('div');
    s.className = 'skel';
    s.style.animationDelay = (i * 0.06) + 's';
    s.innerHTML = `<div class="sk-prev"></div><div class="sk-body">
      <div class="sk-line w40"></div><div class="sk-line w90"></div>
      <div class="sk-line w70"></div><div class="sk-line"></div></div>`;
    grid.appendChild(s);
  }
  let i = 0;
  const phase = $('#labPhase');
  phase.textContent = LAB_PHASES[0];
  labTimer = setInterval(() => {
    i = (i + 1) % LAB_PHASES.length;
    phase.style.opacity = '0';
    setTimeout(() => { phase.textContent = LAB_PHASES[i]; phase.style.opacity = '1'; }, 200);
  }, 1700);
}
function stopConceptLab() {
  clearInterval(labTimer); labTimer = null;
  $('#conceptStatus').classList.add('hidden');
  $$('#conceptGrid .skel').forEach(s => s.remove());
}

async function generateConcepts(append = false) {
  const transcript = $('#inTranscript').value.trim();
  const context = $('#inContext').value.trim();
  const mode = state.intakeMode;
  if (mode === 'inspiration' && !state.inspoImages.length) {
    toast('Add the reference image you want to base concepts on.', 'err');
    return;
  }
  if (!transcript && !context && mode !== 'inspiration') { toast('Paste a transcript or some context first.', 'err'); return; }
  const n = +$('#inCount').value;
  const btn = append ? $('#moreConceptsBtn') : $('#genConceptsBtn');
  const prev = btn.innerHTML; btn.disabled = true;
  btn.innerHTML = append ? 'Thinking…' : '<span class="btn-label">Writing concepts…</span>';
  setStep(2);
  startConceptLab(append ? n : n, append);
  try {
    const body = {
      title: $('#inTitle').value.trim(),
      transcript, context, mode,
      inspiration: $('#inInspo').value.trim(),
      inspiration_images: state.inspoImages.map(({ name, media_type, data }) => ({ name, media_type, data })),
      n,
      slug: state.slug || undefined,
      append,
    };
    if (append) {
      body.start_index = state.concepts.length + 1;
      body.avoid = state.concepts.map(c => c.name);
    }
    const res = await api('/api/concepts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    state.slug = res.slug;
    state.concepts = res.all;
    state.brief.title = body.title;
    $('#studioTitle').textContent = body.title || 'Untitled video';
    stopConceptLab();
    renderConcepts(true);
    loadProjects();
    if (res.warning) toast(res.warning, 'err');
    toast(append ? 'Added more concepts.' : `${res.concepts.length} concepts ready.`, 'ok');
  } catch (e) {
    stopConceptLab();
    toast(e.message, 'err');
    if (!append && !state.concepts.length) setStep(1);
    else renderConcepts();
  } finally {
    btn.disabled = false; btn.innerHTML = prev;
  }
}
$('#genConceptsBtn').onclick = () => generateConcepts(false);
$('#moreConceptsBtn').onclick = () => generateConcepts(true);

/* ---------- Render concepts ---------- */
function renderConcepts(stagger = false) {
  const grid = $('#conceptGrid');
  grid.innerHTML = '';
  $('#conceptCount').textContent = state.concepts.length;
  state.concepts.forEach((c, i) => {
    const card = conceptCard(c);
    card.style.animationDelay = stagger ? (i * 0.07) + 's' : '0s';
    grid.appendChild(card);
  });
  updateSelectbar();
}

const STYLE_META = {
  'cinematic-dark': { label: 'Cinematic', light: false },
  'income-proof': { label: 'Income proof', light: true },
  'storyboard': { label: 'Storyboard', light: true },
  'shocked-laptop': { label: 'Shocked', light: false },
  'graphic-dark': { label: 'Graphic', light: false },
  'graphic-light': { label: 'Graphic', light: true },
};
function conceptStyle(c) { return c.style || (c.mode === 'A' ? 'graphic-light' : c.mode === 'B' ? 'graphic-dark' : 'cinematic-dark'); }

function conceptCard(c) {
  const el = document.createElement('div');
  el.className = 'concept-card';
  if (state.selected.has(c.id)) el.classList.add('selected');
  if (c.status === 'declined') el.classList.add('declined');
  const style = conceptStyle(c);
  const meta = STYLE_META[style] || { label: style, light: false };
  const modeClass = meta.light ? 'modeA' : 'modeB';
  el.innerHTML = `
    <div class="cc-preview ${modeClass}">
      <span class="cc-modebadge">${esc(meta.label.toUpperCase())}</span>
      <span class="cc-check">✓</span>
      <span class="cc-bigtext">${esc(c.big_text || c.name)}</span>
    </div>
    <div class="cc-body">
      <div class="cc-name">${esc(c.name)}</div>
      <div class="cc-meta"><b>Emotion:</b> ${esc(c.emotion || '')}</div>
      <div class="cc-meta"><b>Scene:</b> ${esc(trim(c.scene, 120))}</div>
      ${c.style_ref ? `<div class="cc-meta"><b>Copies:</b> ${esc(c.style_ref)}</div>` : ''}
      <div class="cc-why">${esc(trim(c.why, 130))}</div>
      <div class="cc-actions">
        <button class="cc-btn edit">✎ Edit</button>
        <button class="cc-btn danger decline">${c.status === 'declined' ? '↺ Restore' : '✕ Decline'}</button>
      </div>
    </div>`;
  // select toggle (click on preview)
  el.querySelector('.cc-preview').onclick = () => {
    if (c.status === 'declined') return;
    if (state.selected.has(c.id)) state.selected.delete(c.id); else state.selected.add(c.id);
    el.classList.toggle('selected');
    updateSelectbar();
  };
  el.querySelector('.edit').onclick = () => openConceptModal(c);
  el.querySelector('.decline').onclick = async () => {
    const ns = c.status === 'declined' ? 'pending' : 'declined';
    c.status = ns;
    if (ns === 'declined') state.selected.delete(c.id);
    await api('/api/concept/update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slug: state.slug, id: c.id, status: ns }) });
    renderConcepts();
  };
  return el;
}

function updateSelectbar() {
  const n = state.selected.size;
  const imgs = n * 3;
  $('#selSummary').innerHTML = n
    ? `<b>${n}</b> concept${n > 1 ? 's' : ''} selected · <b>${imgs}</b> images (3 variations each)`
    : 'Select concepts to generate';
  $('#generateBtn').disabled = n === 0;
  $('#generateBtn').textContent = n ? `Generate ${imgs} thumbnails` : 'Generate thumbnails';
}

/* ---------- Edit concept modal ---------- */
let editingConcept = null;
function openConceptModal(c) {
  editingConcept = c;
  $('#ecName').value = c.name || '';
  $('#ecStyle').value = conceptStyle(c);
  $('#ecStyleRef').value = c.style_ref || '';
  $('#ecBig').value = c.big_text || '';
  $('#ecEmotion').value = c.emotion || '';
  $('#ecScene').value = c.scene || '';
  $('#ecPrompt').value = c.image_prompt || '';
  $('#conceptModal').classList.remove('hidden');
}
$('#ecCancel').onclick = () => $('#conceptModal').classList.add('hidden');
$('#ecSave').onclick = async () => {
  const c = editingConcept;
  Object.assign(c, {
    name: $('#ecName').value, style: $('#ecStyle').value, style_ref: $('#ecStyleRef').value.trim(),
    big_text: $('#ecBig').value, emotion: $('#ecEmotion').value, scene: $('#ecScene').value,
    image_prompt: $('#ecPrompt').value,
  });
  await api('/api/concept/update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ slug: state.slug, ...c }) });
  $('#conceptModal').classList.add('hidden');
  renderConcepts();
  toast('Concept updated.', 'ok');
};

/* ---------- Generate thumbnails ---------- */
$('#generateBtn').onclick = async () => {
  const ids = [...state.selected];
  if (!ids.length) return;
  try {
    const { job_id } = await api('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: state.slug, concept_ids: ids, num: 3 }),
    });
    setStep(3);
    await pollJob(job_id, 'Generating thumbnails');
    await refreshProject();
    renderThumbs();
    loadProjects();
    toast('Thumbnails ready.', 'ok');
  } catch (e) { toast(e.message, 'err'); }
};

async function refreshProject() {
  const p = await api(`/api/project/${state.slug}`);
  state.concepts = p.concepts || [];
  state.feedback = p.feedback || {};
}

function renderThumbs() {
  const wrap = $('#thumbGroups');
  wrap.innerHTML = '';
  const withImgs = state.concepts.filter(c => (c.images || []).length);
  if (!withImgs.length) {
    wrap.innerHTML = '<div class="empty-hint">No thumbnails yet. Go back, select concepts, and generate.</div>';
    return;
  }
  withImgs.forEach(c => {
    const g = document.createElement('div');
    g.className = 'thumb-group';
    g.innerHTML = `<div class="tg-head"><h3>${esc(c.name)}</h3><span class="pill">${c.images.length} variations</span>
      <button class="ghost-btn small-more" style="margin-left:auto;padding:6px 12px;font-size:12px">+ More like this</button></div>
      <div class="tg-grid"></div>`;
    const grid = g.querySelector('.tg-grid');
    c.images.forEach(img => grid.appendChild(thumbEl(img, c)));
    g.querySelector('.small-more').onclick = () => moreLikeConcept(c);
    wrap.appendChild(g);
  });
}

function thumbEl(img, concept) {
  const el = document.createElement('div');
  el.className = 'thumb';
  const fb = state.feedback[img.path] || {};
  if (fb.verdict) el.classList.add('fb-' + fb.verdict);
  el.innerHTML = `<img src="${fileUrl(img.path)}" loading="lazy" />
    <span class="fb-badge" title="${esc(fb.note || '')}">${fb.verdict === 'like' ? '♥ Liked' : fb.verdict === 'dislike' ? '✕ Disliked' : ''}</span>
    <div class="thumb-overlay">
      <div class="thumb-verdict">
        <button class="vbtn like ${fb.verdict === 'like' ? 'on' : ''}" title="Like — save to memory">👍</button>
        <button class="vbtn dislike ${fb.verdict === 'dislike' ? 'on' : ''}" title="Dislike — save to memory">👎</button>
        <button class="vbtn comment" title="Suggest an edit to this thumbnail">✎</button>
      </div>
      <div class="thumb-acts">
        <button class="tact view">⤢ View</button>
        <button class="tact up">▲ Upscale</button>
        <button class="tact more">✦ More like</button>
        <a class="tact" href="${fileUrl(img.path)}&download=1" download>↓ Save</a>
      </div>
    </div>`;
  el.querySelector('.view').onclick = () => openLightbox(img, concept);
  el.querySelector('.up').onclick = () => upscale(img.path);
  el.querySelector('.more').onclick = () => moreLikeImage(concept, img.path);
  el.querySelector('.like').onclick = () => sendFeedback(img.path, 'like');
  el.querySelector('.dislike').onclick = () => sendFeedback(img.path, 'dislike');
  el.querySelector('.comment').onclick = () => openEditModal(concept, img.path);
  return el;
}

/* ---------- Like / dislike a final thumbnail (→ memory) ---------- */
async function sendFeedback(path, verdict) {
  const cur = state.feedback[path] || {};
  const isToggle = cur.verdict === verdict;
  let note = '';
  if (!isToggle) {
    const q = verdict === 'like'
      ? 'Why does this one work? (optional — the reason teaches the studio)'
      : 'Why does this one miss? (optional — the reason teaches the studio)';
    note = prompt(q) || '';
  }
  try {
    const res = await api('/api/feedback', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: state.slug, path, verdict, note }),
    });
    if (res.verdict) state.feedback[path] = { verdict: res.verdict, note: res.note };
    else delete state.feedback[path];
    renderThumbs();
    toast(res.verdict === 'like' ? 'Saved to your Likes.'
      : res.verdict === 'dislike' ? 'Saved to your Dislikes.'
      : 'Feedback cleared.', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}

/* ---------- Suggest an edit to one thumbnail ---------- */
let editingThumb = null;
function openEditModal(concept, path) {
  editingThumb = { concept, path };
  $('#etPreview').src = fileUrl(path);
  $('#etInstruction').value = '';
  $('#etCount').value = 2;
  $('#etCountOut').textContent = '2';
  $('#editModal').classList.remove('hidden');
  setTimeout(() => $('#etInstruction').focus(), 50);
}
$('#etCancel').onclick = () => $('#editModal').classList.add('hidden');
$('#etCount').oninput = e => $('#etCountOut').textContent = e.target.value;
$('#etApply').onclick = async () => {
  const instruction = $('#etInstruction').value.trim();
  if (!instruction) { toast('Describe the edit you want.', 'err'); return; }
  const { concept, path } = editingThumb;
  const num = +$('#etCount').value;
  $('#editModal').classList.add('hidden');
  try {
    const { job_id } = await api('/api/edit', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: state.slug, concept_id: concept.id, path, instruction, num }),
    });
    await pollJob(job_id, 'Applying your edit');
    await refreshProject(); renderThumbs();
    toast('Edited versions added.', 'ok');
  } catch (e) { toast(e.message, 'err'); }
};

async function moreLikeConcept(c) {
  try {
    const { job_id } = await api('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: state.slug, concept_ids: [c.id], num: 3 }),
    });
    await pollJob(job_id, 'More variations');
    await refreshProject(); renderThumbs();
    toast('Added more variations.', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}

async function moreLikeImage(c, refPath) {
  try {
    const { job_id } = await api('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: state.slug, concept_ids: [c.id], num: 3, extra_ref: refPath }),
    });
    await pollJob(job_id, 'More like this one');
    await refreshProject(); renderThumbs();
    toast('Generated more like that.', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}

async function upscale(path) {
  try {
    const { job_id } = await api('/api/upscale', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, factor: 2 }),
    });
    const job = await pollJob(job_id, 'Upscaling 2×');
    const r = job.results[0];
    if (r) { toast(`Upscaled to ${r.width || ''}×${r.height || ''}. Saved to final/.`, 'ok'); openLightbox({ path: r.path }); }
  } catch (e) { toast(e.message, 'err'); }
}

/* ---------- Lightbox ---------- */
function openLightbox(img, concept) {
  $('#lbImg').src = fileUrl(img.path);
  const acts = $('#lbActions');
  acts.innerHTML = `<a class="primary-btn small" href="${fileUrl(img.path)}&download=1" download>↓ Download</a>`;
  if (concept) {
    const up = document.createElement('button'); up.className = 'ghost-btn'; up.textContent = '▲ Upscale 2×';
    up.onclick = () => { closeLightbox(); upscale(img.path); }; acts.appendChild(up);
  }
  $('#lightbox').classList.remove('hidden');
}
function closeLightbox() { $('#lightbox').classList.add('hidden'); }
$('.lb-close').onclick = closeLightbox;
$('#lightbox').onclick = e => { if (e.target.id === 'lightbox') closeLightbox(); };
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeLightbox(); $('#conceptModal').classList.add('hidden'); } });

/* ---------- Job polling ---------- */
function pollJob(jid, title) {
  const dock = $('#jobDock');
  dock.classList.remove('hidden');
  $('#jobTitle').textContent = title;
  $('#jobLog').innerHTML = '';
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const j = await api(`/api/job/${jid}`);
        $('#jobPct').textContent = (j.pct || 0) + '%';
        $('#jobFill').style.width = (j.pct || 0) + '%';
        $('#jobLog').innerHTML = j.progress.map(p => `<div>${esc(p)}</div>`).join('');
        $('#jobLog').scrollTop = 1e6;
        if (j.status === 'done') { setTimeout(() => dock.classList.add('hidden'), 900); resolve(j); }
        else if (j.status === 'error') { dock.classList.add('hidden'); reject(new Error(j.error || 'Job failed')); }
        else setTimeout(tick, 1300);
      } catch (e) { dock.classList.add('hidden'); reject(e); }
    };
    tick();
  });
}

/* ---------- Memory ---------- */
async function loadMemory() {
  const m = await api('/api/memory');
  $('#styleProfile').value = m.style_profile || '';
  renderGallery('#memFaces', m.faces.items, 'faces');
  renderGallery('#memLikes', m.likes.items, 'likes');
  renderGallery('#memDislikes', m.dislikes.items, 'dislikes');
  renderGallery('#memInspo', m.inspiration.items, 'inspiration');
}
function renderGallery(sel, items, kind) {
  const el = $(sel);
  if (!items.length) { el.innerHTML = `<div class="mem-empty">Nothing yet — add some.</div>`; return; }
  el.innerHTML = '';
  items.forEach(it => {
    const d = document.createElement('div');
    d.className = 'mem-item';
    const note = (it.meta || []).filter(Boolean).join(' · ');
    d.innerHTML = `<img src="${fileUrl(it.path)}" loading="lazy" />
      ${note ? `<div class="mi-note">${esc(note)}</div>` : ''}
      <button class="mi-del">✕</button>`;
    d.querySelector('img').onclick = () => openLightbox(it);
    d.querySelector('.mi-del').onclick = async () => {
      if (!confirm('Remove this from memory?')) return;
      await api('/api/memory/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: it.path }) });
      loadMemory(); loadStatus();
    };
    el.appendChild(d);
  });
}
$('#saveStyleBtn').onclick = async () => {
  await api('/api/memory/style', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: $('#styleProfile').value }) });
  toast('Style profile saved.', 'ok');
};
$$('input[type=file][data-kind]').forEach(inp => {
  inp.onchange = async () => {
    const file = inp.files[0]; if (!file) return;
    const kind = inp.dataset.kind;
    let note = '', source = '';
    if (kind !== 'faces') {
      note = prompt(kind === 'inspiration' ? 'Technique to borrow (what to reuse)?' : kind === 'likes' ? 'Why does it work?' : 'Why avoid it?') || '';
      source = kind === 'inspiration' ? (prompt('Creator / source? (optional)') || '') : '';
    } else {
      note = prompt('Note (angle / expression)? optional') || '';
    }
    const fd = new FormData();
    fd.append('file', file); fd.append('kind', kind); fd.append('note', note); fd.append('source', source);
    try {
      await fetch('/api/memory/upload', { method: 'POST', body: fd }).then(r => { if (!r.ok) throw new Error('upload failed'); });
      toast('Added to memory.', 'ok'); loadMemory(); loadStatus();
    } catch (e) { toast(e.message, 'err'); }
    inp.value = '';
  };
});

/* ---------- Settings ---------- */
async function loadSettings() {
  const s = await api('/api/status');
  $('#setModel').value = s.model || 'claude-sonnet-4-6';
  $('#setAnthropic').placeholder = s.anthropic_key ? '•••••••• (saved)' : 'sk-ant-…';
  $('#setFal').placeholder = s.fal_key ? '•••••••• (saved)' : '••••••••';
}
$('#saveSettingsBtn').onclick = async () => {
  const body = { model: $('#setModel').value };
  if ($('#setAnthropic').value.trim()) body.ANTHROPIC_API_KEY = $('#setAnthropic').value.trim();
  if ($('#setFal').value.trim()) body.FAL_KEY = $('#setFal').value.trim();
  await api('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  $('#setAnthropic').value = ''; $('#setFal').value = '';
  toast('Settings saved.', 'ok'); loadStatus(); loadSettings();
};

/* ---------- utils ---------- */
function esc(s) { return (s ?? '').toString().replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
function trim(s, n) { s = s || ''; return s.length > n ? s.slice(0, n).trimEnd() + '…' : s; }

/* ---------- boot ---------- */
loadStatus();
loadProjects();
setStep(1);

/* ===== Onboarding ===== */
function _initOnboarding() {
  const onbFaces = [];
  let step = 1;
  const overlay = document.getElementById('onboarding');
  if (!overlay) return;
  const stepEls = [...overlay.querySelectorAll('.onb-step')];
  const dots = [...overlay.querySelectorAll('.onb-steps i')];
  const back = document.getElementById('onbBack');
  const next = document.getElementById('onbNext');

  function render() {
    stepEls.forEach(e => e.classList.toggle('hidden', +e.dataset.onb !== step));
    dots.forEach((d, i) => d.classList.toggle('on', i < step));
    back.classList.toggle('hidden', step === 1);
    next.textContent = step === 3 ? 'Finish & enter studio' : 'Continue';
  }
  function show() { overlay.classList.remove('hidden'); step = 1; render(); }
  function hide() { overlay.classList.add('hidden'); }

  // face upload preview
  const faceFile = document.getElementById('onbFaceFile');
  document.getElementById('onbFaceDrop').onclick = () => faceFile.click();
  faceFile.onchange = () => {
    [...faceFile.files].filter(f => f.type.startsWith('image/')).forEach(f => onbFaces.push(f));
    faceFile.value = '';
    const strip = document.getElementById('onbFaceStrip');
    strip.innerHTML = '';
    onbFaces.forEach((f, i) => {
      const d = document.createElement('div');
      d.className = 'inspo-thumb';
      d.innerHTML = `<img src="${URL.createObjectURL(f)}" /><button type="button" class="ix">✕</button>`;
      d.querySelector('.ix').onclick = () => { onbFaces.splice(i, 1); faceFile.onchange(); };
      strip.appendChild(d);
    });
  };

  document.getElementById('onbSkip').onclick = hide;
  back.onclick = () => { if (step > 1) { step--; render(); } };

  next.onclick = async () => {
    if (step < 3) { step++; render(); return; }
    // Finish — save everything
    next.disabled = true; next.textContent = 'Setting up…';
    try {
      const fal = document.getElementById('onbFal').value.trim();
      const ant = document.getElementById('onbAnt').value.trim();
      if (fal || ant) {
        const body = {};
        if (fal) body.FAL_KEY = fal;
        if (ant) body.ANTHROPIC_API_KEY = ant;
        await api('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      }
      const name = document.getElementById('onbName').value.trim();
      const niche = document.getElementById('onbNiche').value.trim();
      const persona = document.getElementById('onbPersona').value.trim();
      const color = document.getElementById('onbColor').value.trim() || '#FF7300';
      if (niche || persona || name) {
        const text = `# Style profile\n\n## Channel / niche\n${name ? name + ' — ' : ''}${niche}\n\n## Persona on camera\n${persona}\n\n## Visual signature\n- Colors: ${color} (brand)\n- Fonts / text style: bold condensed sans, <=4 words\n- Composition habits: face on one third, hook text on another\n- Background style: clean designed background, cinematic premium\n\n## Do's\n- Strong, real facial expression with eye contact\n- One concrete number or curiosity gap\n\n## Don'ts\n- No clutter or more than ~4 words of text\n- No weak / neutral expression\n`;
        await api('/api/memory/style', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
      }
      for (const f of onbFaces) {
        const fd = new FormData();
        fd.append('file', f); fd.append('kind', 'faces'); fd.append('note', 'onboarding');
        await fetch('/api/memory/upload', { method: 'POST', body: fd });
      }
      toast('You\'re all set! 🧡', 'ok');
      setTimeout(() => location.reload(), 700);
    } catch (e) {
      toast(e.message || 'Setup failed', 'err');
      next.disabled = false; next.textContent = 'Finish & enter studio';
    }
  };

  // show onboarding on a fresh / blank workspace
  api('/api/status').then(s => { if (s.needs_onboarding) show(); }).catch(() => {});
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _initOnboarding); else _initOnboarding();
