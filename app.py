"""Free positive-news carousel workflow. No LLM, no fabricated news.
Run: python app.py discover | render | publish
"""
import hashlib
import html
import json
import os
import re
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import feedparser
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
DATA = ROOT / 'data'
DOCS = ROOT / 'docs'
CFG = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
TIMEOUT = 25


def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', s or ''))).strip()


def canonical(url):
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith('utm_')]
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), '', urlencode(q), ''))


def discover():
    existing = {s['id']: s for s in load(DATA / 'candidates.json', [])}
    cutoff = datetime.now(timezone.utc) - timedelta(days=CFG['max_age_days'])
    for source in CFG['feeds']:
        try:
            response = requests.get(source['url'], timeout=TIMEOUT, headers={'User-Agent': 'PositiveNewsEditorialBot/1.0'})
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:CFG['max_candidates']]:
                title = clean(entry.get('title', ''))
                url = canonical(entry.get('link', ''))
                dt = entry.get('published_parsed') or entry.get('updated_parsed')
                if not dt or not title or not url.startswith('https://'):
                    continue
                published = datetime(*dt[:6], tzinfo=timezone.utc)
                if published < cutoff or published > datetime.now(timezone.utc) + timedelta(days=1):
                    continue
                sid = hashlib.sha256(url.encode()).hexdigest()[:16]
                if sid not in existing:
                    existing[sid] = {'id': sid, 'title': title, 'url': url, 'source': source['name'],
                                     'published_at': published.isoformat(), 'summary': clean(entry.get('summary', ''))[:700],
                                     'status': 'NEEDS_REVIEW'}
        except Exception as exc:
            print(f'Feed failed: {source["name"]}: {exc}', file=sys.stderr)
    save(DATA / 'candidates.json', list(existing.values())[-300:])
    print(f'{len(existing)} candidate stories saved. REVIEW required; RSS is not independent verification.')


def font(size, bold=False):
    candidates = ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                  '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf']
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def lines(draw, text, f, max_width):
    words = text.split()
    result, current = [], ''
    for word in words:
        trial = (current + ' ' + word).strip()
        if draw.textbbox((0, 0), trial, font=f)[2] > max_width and current:
            result.append(current)
            current = word
        else:
            current = trial
    if current:
        result.append(current)
    return result


def slide(path, headline, subtext, index, total):
    im = Image.new('RGB', (1080, 1350), '#173E35')
    d = ImageDraw.Draw(im)
    cream, pale = '#F5E9D5', '#C4E7B5'
    d.text((86, 92), CFG['brand'], font=font(35, True), fill=pale)
    d.line((86, 160, 994, 160), fill='#78988C', width=3)
    size = 68
    while size >= 35:
        f = font(size, True)
        wrapped = lines(d, headline, f, 890)
        if len(wrapped) * (size + 20) <= 640:
            break
        size -= 3
    y = max(320, 680 - len(wrapped) * (size + 20) // 2)
    for ln in wrapped:
        d.text((86, y), ln, font=f, fill=cream)
        y += size + 20
    small = font(30)
    for ln in lines(d, subtext, small, 890)[:4]:
        d.text((86, y + 35), ln, font=small, fill=pale)
        y += 44
    d.line((86, 1210, 994, 1210), fill='#78988C', width=2)
    d.text((86, 1245), CFG['tagline'], font=font(24, True), fill=pale)
    d.text((910, 1245), f'{index}/{total}', font=font(24), fill=pale)
    im.save(path, 'JPEG', quality=92, optimize=True)


def render():
    approved = load(DATA / 'approved.json', [])
    published = set(load(DATA / 'published.json', []))
    candidates = {x['id']: x for x in load(DATA / 'candidates.json', [])}
    usable = []
    for x in approved:
        if x.get('id') in published or x.get('id') not in candidates:
            continue
        c = candidates[x['id']]
        if x.get('verified') is not True or x.get('rights_checked') is not True:
            continue
        if not x.get('evidence_url', '').startswith('https://'):
            continue
        headline = clean(x.get('approved_headline', ''))
        body = clean(x.get('approved_summary', ''))
        if not headline or not body or len(headline) > 140 or len(body) > 230:
            continue
        usable.append((c, x, headline, body))
    usable = usable[:CFG['stories_per_post']]
    if len(usable) < CFG['stories_per_post']:
        print('Not enough approved, verified, rights-checked stories; skip rendering.')
        return
    ids = [x[0]['id'] for x in usable]
    post_id = hashlib.sha256('|'.join(ids).encode()).hexdigest()[:12]
    folder = DOCS / 'posts' / post_id
    folder.mkdir(parents=True, exist_ok=True)
    total = len(usable) + 2
    slide(folder / '01.jpg', 'GOOD NEWS IS STILL HAPPENING.', 'Three real stories worth sharing today.', 1, total)
    for i, (candidate, approved_item, headline, body) in enumerate(usable, start=2):
        attribution = f'{candidate["source"]} · {candidate["published_at"][:10]}'
        slide(folder / f'{i:02d}.jpg', headline, body + '\n' + attribution, i, total)
    slide(folder / f'{total:02d}.jpg', 'GOOD STILL EXISTS.', 'Share this with someone who needs a little hope.', total, total)
    caption = 'Three verified stories that remind us good things are happening.\n\n'
    for i, (candidate, _, headline, _) in enumerate(usable, 1):
        caption += f'{i}. {headline}\nSource: {candidate["source"]} ({candidate["published_at"][:10]})\n{candidate["url"]}\n\n'
    caption += 'Follow for real stories of kindness and progress. #PositiveNews #GoodNews #Kindness'
    if len(caption) > 2200:
        raise ValueError('Caption exceeds Instagram limit; shorten before publishing')
    save(DATA / 'ready.json', {'post_id': post_id, 'ids': ids, 'caption': caption,
                               'files': [f'posts/{post_id}/{i:02d}.jpg' for i in range(1, total + 1)]})
    print(f'Rendered {total} slides in {folder}')


def api(method, endpoint, token, data=None):
    base = f'https://graph.facebook.com/{os.environ.get("META_API_VERSION", "v25.0")}/'
    url = base + endpoint.lstrip('/')
    for attempt in range(3):
        try:
            r = requests.request(method, url, data={**(data or {}), 'access_token': token} if method == 'POST' else None,
                                 params={'access_token': token, **(data or {})} if method == 'GET' else None, timeout=45)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def wait_ready(container, token):
    for _ in range(12):
        result = api('GET', container, token, {'fields': 'status_code'})
        status = result.get('status_code')
        if status == 'FINISHED':
            return
        if status in ('ERROR', 'EXPIRED'):
            raise RuntimeError(f'Container {container}: {status}')
        time.sleep(10)
    raise TimeoutError(f'Container {container} not ready')


def publish():
    ready = load(DATA / 'ready.json', {})
    if not ready:
        print('Nothing ready to publish')
        return
    if ready['post_id'] in load(DATA / 'published_posts.json', []):
        print('Post already published; skipping')
        return
    if CFG['require_manual_approval'] and ready['post_id'] not in load(DATA / 'approved_posts.json', []):
        print(f'Post {ready["post_id"]} requires approval in data/approved_posts.json')
        return
    token = os.environ['META_ACCESS_TOKEN']
    ig = os.environ['IG_USER_ID']
    base = os.environ['PAGES_BASE_URL'].rstrip('/')
    # Publishing only after GitHub Pages deployment and public URL checks.
    urls = [base + '/' + f for f in ready['files']]
    for url in urls:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        if 'image/' not in resp.headers.get('Content-Type', ''):
            raise ValueError(f'Not an image: {url}')
    children = []
    for url in urls:
        item = api('POST', f'{ig}/media', token, {'image_url': url, 'is_carousel_item': 'true'})
        children.append(item['id'])
    parent = api('POST', f'{ig}/media', token, {'media_type': 'CAROUSEL',
                    'children': ','.join(children), 'caption': ready['caption']})['id']
    wait_ready(parent, token)
    # No retry on media_publish: ambiguous network failure may mean it was published.
    url = f'https://graph.facebook.com/{os.environ.get("META_API_VERSION", "v25.0")}/{ig}/media_publish'
    response = requests.post(url, data={'creation_id': parent, 'access_token': token}, timeout=45)
    response.raise_for_status()
    media_id = response.json()['id']
    save(DATA / 'published_posts.json', load(DATA / 'published_posts.json', []) + [ready['post_id']])
    save(DATA / 'published.json', list(set(load(DATA / 'published.json', []) + ready['ids'])))
    save(DATA / 'last_result.json', {'post_id': ready['post_id'], 'media_id': media_id})
    print(f'Published media {media_id}')


if __name__ == '__main__':
    commands = {'discover': discover, 'render': render, 'publish': publish}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit('Usage: python app.py discover|render|publish')
    commands[sys.argv[1]]()
