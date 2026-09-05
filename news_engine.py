import re
import xml.etree.ElementTree as ET
import httpx

http = httpx.Client(timeout=12.0, follow_redirects=True)

NEWS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]

def latest_news(limit=40):
    items=[]
    for url in NEWS_FEEDS:
        try:
            r=http.get(url)
            if r.status_code!=200:
                continue
            root=ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title=(item.findtext("title") or "").strip()
                link=(item.findtext("link") or "").strip()
                pub=(item.findtext("pubDate") or "").strip()
                if title:
                    items.append({"title":title,"url":link,"published":pub})
        except Exception:
            continue
    seen=set()
    unique=[]
    for x in items:
        key=x["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(x)
    return unique[:limit]

def for_base(base, news):
    pat=re.compile(rf"\b{re.escape(base.upper())}\b",re.I)
    return [n for n in news if pat.search(n["title"])]
