/* ===== Supabase auth (multi-user). Loads BEFORE app.js. ===== */
(function () {
  const LS = 'ts_session';
  let session = null;
  try { session = JSON.parse(localStorage.getItem(LS) || 'null'); } catch (e) {}
  let cfg = null;

  window.__AUTH = { get token() { return session && session.access_token; }, logout };

  // Inject the token into every /api/ request + auto-refresh once on 401.
  const of = window.fetch.bind(window);
  let refreshing = null;
  window.fetch = async (url, opts = {}) => {
    const isApi = typeof url === 'string' && url.startsWith('/api/');
    if (isApi && session && session.access_token) {
      opts.headers = Object.assign({}, opts.headers || {}, { Authorization: 'Bearer ' + session.access_token });
    }
    let r = await of(url, opts);
    if (r.status === 401 && isApi && session && session.refresh_token && cfg && cfg.multiuser) {
      const ok = await doRefresh();
      if (ok) {
        opts.headers = Object.assign({}, opts.headers || {}, { Authorization: 'Bearer ' + session.access_token });
        r = await of(url, opts);
      } else { showAuth(); }
    }
    return r;
  };

  async function doRefresh() {
    if (refreshing) return refreshing;
    refreshing = (async () => {
      try {
        const res = await of(cfg.supabase_url + '/auth/v1/token?grant_type=refresh_token', {
          method: 'POST', headers: { apikey: cfg.anon_key, 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: session.refresh_token }),
        });
        if (!res.ok) return false;
        const d = await res.json();
        if (!d.access_token) return false;
        session = { access_token: d.access_token, refresh_token: d.refresh_token };
        localStorage.setItem(LS, JSON.stringify(session));
        return true;
      } catch (e) { return false; } finally { refreshing = null; }
    })();
    return refreshing;
  }

  function logout() { session = null; localStorage.removeItem(LS); location.reload(); }
  function showAuth() { const e = document.getElementById('authScreen'); if (e) e.classList.remove('hidden'); }
  function hideAuth() { const e = document.getElementById('authScreen'); if (e) e.classList.add('hidden'); }

  let mode = 'login';
  function renderMode() {
    const t = document.getElementById('authTitle'), s = document.getElementById('authSubmit');
    const tt = document.getElementById('authToggleText'), tg = document.getElementById('authToggle');
    if (t) t.textContent = mode === 'signup' ? 'Create your account' : 'Welcome back';
    if (s) s.textContent = mode === 'signup' ? 'Sign up' : 'Log in';
    if (tt) tt.textContent = mode === 'signup' ? 'Already have an account?' : "New here?";
    if (tg) tg.textContent = mode === 'signup' ? 'Log in' : 'Create one';
    const e = document.getElementById('authErr'); if (e) e.textContent = '';
  }

  function wireForm() {
    const form = document.getElementById('authForm');
    if (!form) return;
    renderMode();
    const _tg = document.getElementById('authToggle'); if (_tg) _tg.onclick = (e) => { e.preventDefault(); mode = mode === 'login' ? 'signup' : 'login'; renderMode(); };
    form.onsubmit = async (e) => {
      e.preventDefault();
      const email = document.getElementById('authEmail').value.trim();
      const pw = document.getElementById('authPass').value;
      const btn = document.getElementById('authSubmit'); const label = btn.textContent;
      btn.disabled = true; btn.textContent = '…';
      const ep = mode === 'signup' ? '/auth/v1/signup' : '/auth/v1/token?grant_type=password';
      try {
        const res = await of(cfg.supabase_url + ep, {
          method: 'POST', headers: { apikey: cfg.anon_key, 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password: pw }),
        });
        const d = await res.json();
        const at = d.access_token || (d.session && d.session.access_token);
        if (!at) throw new Error(d.error_description || d.msg || d.error || 'Check your email & password and try again.');
        const rt = d.refresh_token || (d.session && d.session.refresh_token);
        session = { access_token: at, refresh_token: rt };
        localStorage.setItem(LS, JSON.stringify(session));
        location.reload();
      } catch (err) {
        document.getElementById('authErr').textContent = err.message;
        btn.disabled = false; btn.textContent = label;
      }
    };
  }

  async function init() {
    try { cfg = await (await of('/api/auth-config')).json(); } catch (e) { cfg = { multiuser: false }; }
    window.__AUTH.cfg = cfg;
    if (!cfg.multiuser) { hideAuth(); return; }      // single-tenant: no auth screen
    if (session && session.access_token) { hideAuth(); const lo = document.getElementById('logoutBtn'); if (lo) lo.classList.remove('hidden'); return; }
    wireForm();
    showAuth();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
