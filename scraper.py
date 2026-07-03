import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CURAMA_REVIEW_PATTERN = re.compile(
    r"https?://curama\.jp/.+/review/[0-9a-f-]+", re.IGNORECASE
)


def is_valid_curama_review_url(url: str) -> bool:
    return bool(CURAMA_REVIEW_PATTERN.match(url.strip()))


def scrape_review(url: str) -> dict:
    url = url.strip()

    if not is_valid_curama_review_url(url):
        return {
            "success": False,
            "url": url,
            "error": "くらしのマーケットの口コミURLの形式ではありません。\n"
                     "正しい形式: https://curama.jp/[カテゴリ]/[タイプ]/[サービスID]/review/[口コミID]",
        }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return {"success": False, "url": url, "error": "タイムアウト: ページの読み込みに時間がかかりすぎました。"}
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "不明"
        return {"success": False, "url": url, "error": f"HTTPエラー {status}: ページを取得できませんでした。"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "url": url, "error": f"通信エラー: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1. Next.js の __NEXT_DATA__ から取得（最も確実）
    next_data = _extract_from_next_data(soup)
    if next_data and next_data.get("review_text"):
        return {**next_data, "success": True, "url": url}

    # 2. JSON-LD から取得
    jsonld_data = _extract_from_jsonld(soup)
    if jsonld_data and jsonld_data.get("review_text"):
        return {**jsonld_data, "success": True, "url": url}

    # 3. HTML セレクタで取得
    review_text = _extract_review_text(soup)
    if review_text:
        return {
            "success": True,
            "url": url,
            "review_text": review_text,
            "reviewer_name": _extract_reviewer_name(soup) or "不明",
            "rating": _extract_rating(soup) or "不明",
            "service_type": _extract_service_type(soup) or "不明",
            "posted_date": _extract_posted_date(soup) or "不明",
        }

    return {
        "success": False,
        "url": url,
        "error": (
            "口コミ本文を取得できませんでした。"
            "ページが動的に生成されているため取得できない可能性があります。"
            "URLが正しいか確認してください。"
        ),
    }


def _extract_from_next_data(soup: BeautifulSoup) -> dict:
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script or not script.string:
        return {}
    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return {}

    def search(obj, depth=0):
        if depth > 15:
            return None
        if isinstance(obj, dict):
            for key in ("comment", "reviewComment", "body", "text", "content", "message", "review"):
                val = obj.get(key)
                if isinstance(val, str) and len(val) > 10:
                    return {
                        "review_text": val,
                        "reviewer_name": str(obj.get("userName") or obj.get("name") or obj.get("nickname") or "不明"),
                        "rating": str(obj.get("rating") or obj.get("score") or obj.get("star") or "不明"),
                        "service_type": "不明",
                        "posted_date": str(obj.get("createdAt") or obj.get("date") or obj.get("publishedAt") or "不明"),
                    }
            for v in obj.values():
                result = search(v, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = search(item, depth + 1)
                if result:
                    return result
        return None

    return search(data) or {}


def _extract_from_jsonld(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") in ("Review", "UserReview"):
                text = item.get("reviewBody", "")
                if not text:
                    continue
                author = item.get("author", {})
                name = author.get("name", "不明") if isinstance(author, dict) else str(author)
                rating_obj = item.get("reviewRating", {})
                rating = rating_obj.get("ratingValue", "不明") if isinstance(rating_obj, dict) else "不明"
                return {
                    "review_text": text,
                    "reviewer_name": name,
                    "rating": str(rating),
                    "service_type": (item.get("itemReviewed") or {}).get("name", "不明"),
                    "posted_date": item.get("datePublished", "不明"),
                }
    return {}


def _extract_review_text(soup: BeautifulSoup) -> str:
    # 1. 属性セレクタで探す
    selectors = [
        {"data-testid": "review-comment"},
        {"itemprop": "reviewBody"},
        {"class": re.compile(r"review.*comment|comment.*review|ReviewComment|reviewComment", re.I)},
    ]
    for attrs in selectors:
        el = soup.find(attrs=attrs)
        if el:
            text = el.get_text(strip=True)
            if len(text) > 10:
                return text

    # 2. クラス名にreview・comment・口コミを含む要素
    for tag in ["p", "div", "span"]:
        for el in soup.find_all(tag):
            cls = " ".join(el.get("class", []))
            if re.search(r"review|comment|口コミ|感想", cls, re.I):
                text = el.get_text(strip=True)
                if len(text) > 30:
                    return text

    # 3. ページ内のテキストブロックを「口コミらしさ」でスコアリングして抽出
    # 地名リスト・エリア説明など非口コミテキストを除外するためスコア方式を採用
    import re as _re

    GEO_SUFFIXES = _re.compile(r'[都道府県市区町村郡]')
    SENTENCE_ENDS = _re.compile(r'[。！？!?]')

    def _review_score(text: str) -> float:
        if len(text) == 0:
            return -1
        geo_density = len(GEO_SUFFIXES.findall(text)) / len(text)
        # 地名密度が高い（エリアリスト）はスコアを大幅に下げる
        if geo_density > 0.05:
            return -1
        sentence_density = len(SENTENCE_ENDS.findall(text)) / len(text)
        # 長さボーナス（上限500文字で飽和）
        length_bonus = min(len(text), 500) / 500
        return sentence_density * 10 + length_bonus

    candidates = []
    for tag in ["p", "div", "section", "article"]:
        for el in soup.find_all(tag):
            if len(el.find_all(recursive=False)) > 5:
                continue
            text = el.get_text(strip=True)
            if 50 < len(text) < 3000:
                candidates.append(text)

    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    if unique:
        best = max(unique, key=_review_score)
        if _review_score(best) > 0:
            return best

    # 4. metaタグから取得
    for attr in [{"property": "og:description"}, {"name": "description"}]:
        meta = soup.find("meta", attr)
        if meta and meta.get("content") and len(meta["content"]) > 20:
            return meta["content"]

    return ""


def _extract_reviewer_name(soup: BeautifulSoup) -> str:
    for attrs in [{"itemprop": "author"}, {"data-testid": "reviewer-name"}]:
        el = soup.find(attrs=attrs)
        if el:
            return el.get_text(strip=True)
    return ""


def _extract_rating(soup: BeautifulSoup) -> str:
    el = soup.find(attrs={"itemprop": "ratingValue"})
    if el:
        return el.get("content") or el.get_text(strip=True)
    el = soup.find(attrs={"data-testid": "rating"})
    if el:
        return el.get_text(strip=True)
    return ""


def _extract_service_type(soup: BeautifulSoup) -> str:
    breadcrumbs = soup.find_all(attrs={"itemprop": "name"})
    if breadcrumbs:
        names = [b.get_text(strip=True) for b in breadcrumbs if b.get_text(strip=True)]
        if names:
            return " > ".join(names[:3])
    title_el = soup.find("title")
    if title_el:
        return title_el.get_text(strip=True)
    return ""


def _extract_posted_date(soup: BeautifulSoup) -> str:
    el = soup.find(attrs={"itemprop": "datePublished"})
    if el:
        return el.get("content") or el.get_text(strip=True)
    el = soup.find("time")
    if el:
        return el.get("datetime") or el.get_text(strip=True)
    return ""
