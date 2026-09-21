// ============================================================
// settings.js — Settings screen
// ============================================================

import { db, getSetting, signOut } from '../supabase.js';
import { siteFooter } from '../components/footer.js';

export async function renderSettings() {
  const app = document.getElementById('app');

  app.innerHTML = `
    <div class="screen-header">
      <span class="screen-title">Settings</span>
    </div>

    <!-- Account -->
    <div class="section-label">ACCOUNT</div>
    <div class="card" style="margin:0 16px 10px;">
      <div style="font-size:12px;color:var(--muted);margin-bottom:4px;">Signed in as</div>
      <div id="user-email" style="font-weight:700;font-size:14px;margin-bottom:12px;">Loading...</div>
      <button class="btn btn-secondary" id="btn-signout">Sign out</button>
    </div>

    <!-- Data -->
    <div class="section-label">DATA</div>
    <div class="card" style="margin:0 16px 10px;">
      <div style="font-weight:700;font-size:13px;margin-bottom:4px;">Export library</div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:12px;">Download a full JSON backup of your library, episode progress, and watch sessions.</div>
      <button class="btn btn-secondary" id="btn-export">Export JSON</button>
    </div>

    <div class="card" style="margin:0 16px 10px;">
      <div style="font-weight:700;font-size:13px;margin-bottom:4px;">Import library</div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:12px;">Restore from a previously exported JSON file.</div>
      <input type="file" id="import-file" accept=".json" style="display:none;" />
      <button class="btn btn-secondary" id="btn-import">Import JSON</button>
    </div>

    <!-- API -->
    <div class="section-label">API</div>
    <div class="card" style="margin:0 16px 10px;">
      <div style="font-weight:700;font-size:13px;margin-bottom:8px;">TMDB Read Access Token</div>
      <div id="tmdb-display" style="font-size:11px;color:var(--muted);font-family:monospace;word-break:break-all;">Loading...</div>
    </div>

    <!-- About -->
    <div class="section-label">ABOUT</div>
    <div class="card" style="margin:0 16px 10px;">
      <div style="font-size:13px;line-height:1.8;color:var(--muted);">
        <div><strong style="color:var(--text);">iseentit</strong></div>
        <div>Personal TV &amp; movie tracker</div>
        <div>Data from TMDB · Hosted on GitHub Pages</div>
        <div style="margin-top:8px;"><a href="https://github.com/misoverstood/iseentit" target="_blank" style="color:var(--accent);">github.com/misoverstood/iseentit</a></div>
      </div>
    </div>

    <!-- Danger zone -->
    <div class="section-label">DANGER ZONE</div>
    <div class="card" style="margin:0 16px 24px;border-color:#e0555540;">
      <div style="font-weight:700;font-size:13px;margin-bottom:4px;color:#e05;">Clear all data</div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:12px;">Permanently deletes your entire library. Cannot be undone.</div>
      <button class="btn" id="btn-clear" style="background:#e0555520;color:#e05;border:1px solid #e0555540;">Clear everything</button>
    </div>

    ${siteFooter()}
  `;

  // Load user email
  const { data: userData } = await db.auth.getUser();
  document.getElementById('user-email').textContent = userData?.user?.email ?? 'Unknown';

  // Load TMDB token (masked)
  const token = await getSetting('tmdb_token');
  document.getElementById('tmdb-display').textContent = token
    ? token.slice(0, 24) + '…' + token.slice(-8)
    : 'Not set';

  // Sign out
  document.getElementById('btn-signout').addEventListener('click', async () => {
    await signOut();
    window.location.hash = '';
    window.location.reload();
  });

  // Export
  document.getElementById('btn-export').addEventListener('click', async () => {
    const btn = document.getElementById('btn-export');
    btn.textContent = 'Exporting…';
    try {
      const [titles, episodes, sessions] = await Promise.all([
        db.from('titles').select('*'),
        db.from('episode_progress').select('*'),
        db.from('watch_sessions').select('*'),
      ]);
      const payload = {
        exported_at: new Date().toISOString(),
        version: 1,
        titles: titles.data ?? [],
        episode_progress: episodes.data ?? [],
        watch_sessions: sessions.data ?? [],
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `iseentit_backup_${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      btn.textContent = 'Export JSON';
    } catch (e) {
      btn.textContent = 'Export failed';
      console.error(e);
    }
  });

  // Import
  document.getElementById('btn-import').addEventListener('click', () => {
    document.getElementById('import-file').click();
  });

  document.getElementById('import-file').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const btn = document.getElementById('btn-import');
    btn.textContent = 'Importing…';
    try {
      const payload = JSON.parse(await file.text());
      if (payload.titles?.length) {
        await db.from('titles').upsert(payload.titles, { onConflict: 'tmdb_id,media_type' });
      }
      if (payload.episode_progress?.length) {
        await db.from('episode_progress').upsert(payload.episode_progress, { onConflict: 'title_id,season_number,episode_number' });
      }
      if (payload.watch_sessions?.length) {
        await db.from('watch_sessions').insert(payload.watch_sessions);
      }
      btn.textContent = `Imported ${payload.titles?.length ?? 0} titles`;
    } catch (err) {
      btn.textContent = 'Import failed';
      console.error(err);
    }
  });

  // Clear all
  document.getElementById('btn-clear').addEventListener('click', async () => {
    if (!confirm('Delete your entire library? This cannot be undone.')) return;
    if (!confirm('Are you sure? All titles, episodes, and watch history will be gone.')) return;
    const btn = document.getElementById('btn-clear');
    btn.textContent = 'Clearing…';
    const NIL = '00000000-0000-0000-0000-000000000000';
    await db.from('watch_sessions').delete().neq('id', NIL);
    await db.from('episode_progress').delete().neq('id', NIL);
    await db.from('titles').delete().neq('id', NIL);
    btn.textContent = 'Cleared';
  });
}