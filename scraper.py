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
    """
    curama.jp の口コミURLから口コミ内容を取得する。

    Returns:
        dict with keys:
            - success (bool)
            - url (str)
            - review_text (str)
            - reviewer_name (str)
            - rating (str)
            - service_type (str)
            - posted_date (str)
            - error (str, only when success=False)
    """
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

    review_text = _extract_review_text(soup)
    reviewer_name = _extract_reviewer_name(soup)
    rating = _extract_rating(soup)
    service_type = _extract_service_type(soup)
    posted_date = _extract_posted_date(soup)

    if not review_text:
        return {
            "success": False,
            "url": url,
            "error": (
                "口コミ本文を取得できませんでした。"
                "ページが動的に生成されている可能性があります。"
                "URLが正しいか確認してください。"
            ),
        }

    return {
        "success": True,
        "url": url,
        "review_text": review_text,
        "reviewer_name": reviewer_name or "不明",
        "rating": rating or "不明",
        "service_type": service_type or "不明",
        "posted_date": posted_date or "不明",
    }


def _extract_review_text(soup: BeautifulSoup) -> str:
    selectors = [
        {"data-testid": "review-comment"},
        {"class": re.compile(r"review.*comment|comment.*review", re.I)},
        {"class": re.compile(r"ReviewComment|reviewComment", re.I)},
        {"itemprop": "reviewBody"},
    ]
    for attrs in selectors:
        el = soup.find(attrs=attrs)
        if el:
            return el.get_text(strip=True)

    for tag in ["p", "div", "span"]:
        for el in soup.find_all(tag):
            cls = " ".join(el.get("class", []))
            if re.search(r"review|comment|口コミ|感想", cls, re.I):
                text = el.get_text(strip=True)
                if len(text) > 10:
                    return text

    meta = soup.find("meta", {"name": "description"})
    if meta and meta.get("content"):
        content = meta["content"]
        if len(content) > 20:
            return content

    return ""


def _extract_reviewer_name(soup: BeautifulSoup) -> str:
    selectors = [
        {"itemprop": "author"},
        {"data-testid": "reviewer-name"},
        {"class": re.compile(r"reviewer.*name|user.*name", re.I)},
    ]
    for attrs in selectors:
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
