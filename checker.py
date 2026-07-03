import json
import os
import anthropic
from dotenv import load_dotenv
from guidelines import GUIDELINES

load_dotenv()

_client = None


def _get_api_key() -> str:
    # Streamlit Cloud のシークレット管理から取得を試みる
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    # ローカル環境では .env から取得
    return os.getenv("ANTHROPIC_API_KEY", "")


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = _get_api_key()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY が設定されていません。")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


GUIDELINE_TEXT = "\n".join(
    f"{i+1}. 【{g['name']}】: {g['description']}"
    for i, g in enumerate(GUIDELINES)
)

CHECK_PROMPT_TEMPLATE = """
あなたは「くらしのマーケット」の口コミ審査担当です。
以下の口コミが、投稿ガイドラインに違反しているかどうかを判定してください。

## 口コミ情報
- 投稿者名: {reviewer_name}
- サービス種別: {service_type}
- 投稿日: {posted_date}
- 評価: {rating}
- 口コミ本文:
「{review_text}」

## チェック対象ガイドライン
{guidelines}

## 判定指示
上記のガイドラインに照らして、この口コミを審査してください。

以下のJSON形式のみで回答してください（説明文は不要）:
{{
  "is_violation": true または false,
  "violations": [
    {{
      "category_id": "ガイドラインのid（personal_info/defamation/unverifiable_claims/privacy_violation/irrelevant_content/fake_review/lack_of_specificity/store_related のいずれか）",
      "category_name": "違反カテゴリ名",
      "severity": "high/medium/low",
      "reason": "なぜ違反と判定したか（具体的に、50文字以内）",
      "quote": "違反該当箇所の引用（30文字以内、なければ空文字）"
    }}
  ],
  "summary": "総合判定の要約（100文字以内）",
  "confidence": "high/medium/low（判定の確信度）"
}}

違反がない場合は violations を空配列にしてください。
""".strip()


def check_review(review_data: dict) -> dict:
    """
    口コミデータを受け取り、ガイドライン違反チェック結果を返す。

    Args:
        review_data: scraper.scrape_review() の返り値（success=True のもの）

    Returns:
        dict with keys:
            - is_violation (bool)
            - violations (list of dicts)
            - summary (str)
            - confidence (str)
            - error (str, only when failed)
    """
    prompt = CHECK_PROMPT_TEMPLATE.format(
        reviewer_name=review_data.get("reviewer_name", "不明"),
        service_type=review_data.get("service_type", "不明"),
        posted_date=review_data.get("posted_date", "不明"),
        rating=review_data.get("rating", "不明"),
        review_text=review_data.get("review_text", ""),
        guidelines=GUIDELINE_TEXT,
    )

    try:
        client = get_client()
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("JSONが見つかりませんでした")

        result = json.loads(raw[json_start:json_end])
        return result

    except json.JSONDecodeError as e:
        return {
            "is_violation": False,
            "violations": [],
            "summary": "解析エラー",
            "confidence": "low",
            "error": f"AIの応答をパースできませんでした: {e}",
        }
    except Exception as e:
        return {
            "is_violation": False,
            "violations": [],
            "summary": "チェックエラー",
            "confidence": "low",
            "error": str(e),
        }
