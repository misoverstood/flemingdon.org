// ============================================================
// footer.js — shared site footer, same across all my sites
// ============================================================

const SITES = [
  { host: 'thatstheworst.com', url: 'https://thatstheworst.com' },
  { host: 'flemingdon.org',    url: 'https://flemingdon.org'    },
  { host: 'muhummud.org',      url: 'https://muhummud.org'      },
  { host: 'naseema.net',       url: 'https://naseema.net'       },
  { host: 'iseentit.com',      url: 'https://iseentit.com'      },
];

const CURRENT = 'iseentit.com';

export function siteFooter() {
  return `
    <div class="site-footer">
      ${SITES.map(s => s.host === CURRENT
        ? `<span class="site-footer-current">${s.host}</span>`
        : `<a href="${s.url}">${s.host}</a>`
      ).join('<span class="site-footer-sep">·</span>')}
    </div>
  `;
}
