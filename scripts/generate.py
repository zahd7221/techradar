import os, json, datetime, urllib.request, urllib.parse, re, pathlib

TOKEN = os.environ["GITHUB_TOKEN"]
OUT = pathlib.Path("src/content/articles")
OUT.mkdir(parents=True, exist_ok=True)
today = datetime.date.today().isoformat()

def gh_search():
    seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    q = f"created:>{seven_days_ago} stars:>5"
    url = "https://api.github.com/search/repositories?q=" + urllib.parse.quote(q) + "&sort=stars&order=desc&per_page=8"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        return [{"name": x["full_name"], "url": x["html_url"], "desc": (x.get("description") or "")[:200], "stars": x["stargazers_count"]} for x in data.get("items", [])]
    except Exception as e:
        return [{"error": str(e)}]

def arxiv_recent():
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=5"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            xml = r.read().decode()
        entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
        out = []
        for e in entries:
            t = re.search(r"<title>(.*?)</title>", e, re.S)
            l = re.search(r"<id>(.*?)</id>", e, re.S)
            if t and l:
                out.append({"title": t.group(1).strip().replace("\n"," "), "url": l.group(1).strip()})
        return out
    except Exception as e:
        return [{"error": str(e)}]

repos = gh_search()
papers = arxiv_recent()

context = "GitHub trending (new repos, high stars):\n" + json.dumps(repos, ensure_ascii=False) + "\n\narXiv recent cs.AI:\n" + json.dumps(papers, ensure_ascii=False)

prompt = f"""You are TechRadar editor. Generate exactly 3 Arabic articles as JSON array.
Each article object: title, slug (ascii-kebab), category (one of: news, oss-tool, tip), summary (1-2 sentences Arabic), tags (array of 2-4), body (markdown Arabic, 150-250 words), sources (array of REAL URLs from the provided context only).

Context:
{context}

Rules:
- Arabic language only for title/summary/body.
- sources must be real URLs from context; never invent.
- If a claim lacks source, mark it "غير مؤكد".
- Output ONLY valid JSON array, no markdown fences.
"""

try:
    req = urllib.request.Request(
        "https://models.github.ai/inference/chat/completions",
        data=json.dumps({"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "temperature": 0.4, "max_tokens": 2000}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode()
    resp = json.loads(raw)
    text = resp["choices"][0]["message"]["content"].strip()
except Exception as e:
    print("LLM failed, fallback:", repr(e))
    text = None

if text:
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        articles = json.loads(text)
    except Exception as e:
        print("JSON parse failed, fallback:", e)
        articles = None
else:
    articles = None

if not articles:
    articles = []
    for x in repos:
        if "error" in x: continue
        desc = (x.get("desc") or "").strip()
        # keep only ASCII descriptions (avoid Chinese/garbage)
        if desc and not all(ord(c) < 128 for c in desc):
            desc = ""
        if not desc:
            desc = "مستودع جديد على GitHub (وصف غير متوفر)."
        slug = x["name"].split("/")[-1].lower()
        slug = re.sub(r"[^a-z0-9-]", "", slug) or "repo"
        articles.append({
            "title": f"أداة OSS: {x['name']}",
            "slug": slug,
            "category": "oss-tool",
            "summary": f"مستودع جديد ({x.get('stars',0)} ⭐). {desc[:80]}",
            "tags": ["OSS", "GitHub"],
            "body": f"## {x['name']}\n\n{x.get('stars',0)} ⭐ على GitHub.\n\n{desc}\n\n**الرابط:** {x['url']}",
            "sources": [x["url"]]
        })
        if len(articles) >= 2: break
    for x in papers:
        if "error" in x: continue
        articles.append({
            "title": f"ورقة بحث: {x['title'][:70]}",
            "slug": "paper-" + str(len(articles)),
            "category": "news",
            "summary": "ورقة بحث حديثة في الذكاء الاصطناعي (arXiv cs.AI).",
            "tags": ["research", "AI"],
            "body": f"## {x['title']}\n\nورقة بحث حديثة من arXiv (cs.AI).\n\n**الرابط:** {x['url']}",
            "sources": [x["url"]]
        })
        if len(articles) >= 3: break
    if not articles:
        articles = [{"title": "TechRadar — لا بيانات", "slug": "empty", "category": "news", "summary": "لا توجد بيانات.", "tags": ["info"], "body": "حاول لاحقاً.", "sources": []}]

for a in articles:
    slug = re.sub(r"[^a-z0-9-]", "", a["slug"].lower()) or "article"
    fname = OUT / f"{today}-{slug}.md"
    if fname.exists():
        i = 1
        while (OUT / f"{today}-{slug}-{i}.md").exists():
            i += 1
        slug = f"{slug}-{i}"
        fname = OUT / f"{today}-{slug}.md"
    a["slug"] = slug
    tags = ", ".join(f'"{t}"' for t in a.get("tags", []))
    sources = "\n".join(f"- {s}" for s in a.get("sources", []))
    content = f"""---
title: "{a['title'].replace(chr(34), "'")}"
date: "{today}"
category: "{a['category']}"
summary: "{a['summary'].replace(chr(34), "'")}"
tags: [{tags}]
---
{a['body']}

## المصادر
{sources}
"""
    fname.write_text(content, encoding="utf-8")
    print("wrote", fname)
print("done", len(articles))
