// ============================================================
// dashboard.js — Dashboard screen
// ============================================================

import { getTitles, getWatchStats, getEpisodeProgress } from '../supabase.js';
import { getTVShow, img } from '../tmdb.js';
import { navigate } from '../utils/router.js';
import { statusLabel } from '../utils/status.js';

export async function renderDashboard() {
  const app = document.getElementById('app');

  const [titles, stats] = await Promise.all([
    getTitles(),
    getWatchStats(),
  ]);

  const watching   = titles.filter(t => t.status === 'watching');
  const completed  = titles.filter(t => t.status === 'completed');
  const movies     = titles.filter(t => t.media_type === 'movie');
  const totalHrs   = Math.round(stats.totalMinutes / 60 * 10) / 10;
  const movieHrs   = Math.round(stats.movieMinutes / 60 * 10) / 10;
  const tvHrs      = Math.round(stats.tvMinutes / 60 * 10) / 10;

  // Real progress for each show currently being watched
  const progress = {};
  await Promise.all(watching.filter(t => t.media_type === 'tv').map(async t => {
    try {
      const [show, eps] = await Promise.all([getTVShow(t.tmdb_id), getEpisodeProgress(t.id)]);
      const total   = show.number_of_episodes || 0;
      const watched = eps.filter(e => e.watched).length;
      progress[t.id] = { watched, total, pct: total ? Math.min(100, Math.round(watched / total * 100)) : 0 };
    } catch (err) {
      console.error('progress:', t.title, err);
    }
  }));

  // Build weekly bar chart data
  const days = Object.entries(stats.byDay);
  const weekMins = days.reduce((s, [, m]) => s + m, 0);
  const maxMins = Math.max(...days.map(([, m]) => m), 1);

  app.innerHTML = `
    <div class="screen-header">
      <span class="screen-title" style="display:flex;align-items:center;gap:10px;">
        <img src="icons/android-chrome-192x192.png" alt="" style="width:38px;height:38px;" />
        iseentit
      </span>
    </div>

    <!-- Stat row -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-value">${totalHrs}</div>
        <div class="stat-label">HRS WATCHED</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${movies.length}</div>
        <div class="stat-label">MOVIES</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${completed.filter(t => t.media_type === 'tv').length}</div>
        <div class="stat-label">SHOWS DONE</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${titles.length}</div>
        <div class="stat-label">TOTAL</div>
      </div>
    </div>

    <!-- Watch time split -->
    <div class="section-label">WATCH TIME</div>
    <div class="card" style="margin: 0 16px 10px;">
      <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
        <span style="font-size:12px; color:var(--muted);">🎬 Movies <strong style="color:var(--text)">${movieHrs}h</strong></span>
        <span style="font-size:12px; color:var(--muted);">📺 TV <strong style="color:var(--text)">${tvHrs}h</strong></span>
      </div>
      <!-- Weekly bar chart -->
      <div style="display:flex; align-items:flex-end; gap:4px; height:60px;">
        ${days.map(([date, mins]) => `
          <div style="flex:1; display:flex; flex-direction:column; align-items:center; gap:3px;">
            <div style="width:100%; background:var(--accent); border-radius:3px 3px 0 0; opacity:${mins > 0 ? 0.85 : 0.15};
                 height:${Math.max(Math.round((mins / maxMins) * 52), mins > 0 ? 4 : 2)}px;"></div>
            <span style="font-size:9px; color:var(--muted);">${new Date(date + 'T12:00:00').toLocaleDateString('en',{weekday:'narrow'})}</span>
          </div>
        `).join('')}
      </div>
      <div style="font-size:10px; color:var(--muted); text-align:center; margin-top:8px;">
        ${weekMins > 0 ? `${Math.round(weekMins / 60 * 10) / 10}h this week` : 'Nothing logged this week'}
      </div>
    </div>

    <!-- Currently watching -->
    ${watching.length ? `
      <div class="section-label">CURRENTLY WATCHING</div>
      <div style="display:flex; gap:10px; padding:0 16px 16px; overflow-x:auto; scrollbar-width:none;">
        ${watching.map(t => {
          const p = progress[t.id];
          return `
          <div class="poster-card" style="min-width:100px; max-width:100px;" data-id="${t.tmdb_id}" data-type="${t.media_type}">
            <img src="${img.poster(t.poster_path)}" alt="${t.title}" loading="lazy" />
            <div class="poster-info">
              <div class="poster-title">${t.title}</div>
              ${p ? `
                <div class="progress-bar"><div class="progress-bar-fill" style="width:${p.pct}%"></div></div>
                <div class="poster-year" style="margin-top:3px;">${p.watched} / ${p.total} eps · ${p.pct}%</div>
              ` : `<div class="poster-year">${t.year ?? ''}</div>`}
            </div>
          </div>`;
        }).join('')}
      </div>
    ` : ''}

    <!-- Recent additions -->
    <div class="section-label">RECENTLY ADDED</div>
    <div class="poster-grid">
      ${titles.slice(0, 8).map(t => `
        <div class="poster-card" data-id="${t.tmdb_id}" data-type="${t.media_type}">
          <img src="${img.poster(t.poster_path)}" alt="${t.title}" loading="lazy" />
          <div class="poster-info">
            <div class="poster-title">${t.title}</div>
            <div class="poster-year"><span class="badge badge-${t.status}">${statusLabel(t.status)}</span></div>
          </div>
        </div>
      `).join('')}
    </div>

    ${titles.length === 0 ? `
      <div class="error-state">
        <p style="font-size:32px; margin-bottom:12px;">🎬</p>
        <p style="font-weight:700; margin-bottom:6px;">Nothing here yet</p>
        <p style="color:var(--muted); font-size:13px;">Search for a movie or show to get started</p>
        <button class="btn btn-primary" style="margin-top:16px;" id="go-search">Search now</button>
      </div>
    ` : ''}
  `;

  // Wire up click handlers
  app.querySelectorAll('.poster-card[data-id]').forEach(card => {
    card.addEventListener('click', () =>
      navigate(`/title/${card.dataset.type}/${card.dataset.id}`)
    );
  });

  document.getElementById('go-search')?.addEventListener('click', () => navigate('/search'));
}
