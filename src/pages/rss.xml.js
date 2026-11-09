import { getCollection } from 'astro:content';

export async function GET() {
  const modules = import.meta.glob('../content/articles/*.md', { eager: true });
  const posts = Object.entries(modules).map(([path, mod]) => ({
    slug: path.split('/').pop().replace('.md',''),
    ...mod.frontmatter,
  })).sort((a,b) => new Date(b.date) - new Date(a.date));

  const site = 'https://zahd7221.github.io/techradar';
  const items = posts.map((p) => `
    <item>
      <title>${escapeXml(p.title)}</title>
      <link>${site}/articles/${p.slug}/</link>
      <guid>${site}/articles/${p.slug}/</guid>
      <pubDate>${new Date(p.date).toUTCString()}</pubDate>
      <description>${escapeXml(p.summary || '')}</description>
    </item>`).join('');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TechRadar</title>
    <link>${site}</link>
    <description>أخبار AI + أدوات OSS (مجانية)</description>
    <language>ar</language>
    ${items}
  </channel>
</rss>`;
  return new Response(xml, { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } });
}

function escapeXml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
