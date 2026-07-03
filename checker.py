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
    f"{i+1}. 【{g['name']}】: {g['description']}\n   検出ヒント: {', '.join(g['detection_hints'][:3])}"
    for i, g in enumerate(GUIDELINES)
)

CHECK_PROMPT_TEMPLATE = """
あなたはくらしのマーケットの運営担当者です。
お客様が投稿した口コミを読んで、その口コミの内容から「出店者がくらしのマーケットのガイドラインに違反する行為をしていないか」を判定してください。

## 口コミ情報
- サービス種別: {service_type}
- 投稿日: {posted_date}
- 評価（星）: {rating}
- 口コミ本文:
「{review_text}」

## 出店者ガイドライン（参照元: faq.curama.jp/docs/shop/guidelines/）
{guidelines}

## 判定指示

口コミの内容から、出店者が以下のような違反行為をした形跡がないかを判定してください。

### 特に重要な違反（必ず検出する）
- **名刺の授受（原則すべて違反）**: 出店者が顧客に名刺を渡した・もらったという記述は、原則として `direct_transaction` 違反として検出すること。
  - **例外（違反としない）**: 口コミに「くらしのマーケットの名刺」「くらまの名刺」など、くらしのマーケットが提供する公式名刺であることが明示されている場合のみ違反としない。公式名刺には連絡先が記載されておらず問題ない。
  - 例外に当たるかどうか不明な場合は違反として検出すること。
- **LINE・電話・メール等での直接連絡（文脈を問わず違反）**: 「LINEで」「LINEにて」「直接LINE」「電話で連絡」など、くらしのマーケットを介さずに出店者と顧客が直接やり取りしていることが示唆される表現はすべて `direct_transaction` 違反として検出すること。
  - 例：「LINEにて日程調整」「直接LINEで連絡してもらえる」「LINEで予約できる」→ 違反
  - 例：「次回もLINEで」「息子と直にLINEで」→ 違反
  - くらしのマーケットのメッセージ機能・予約システム以外での連絡はすべて違反。
- **将来の直接取引の約束・誘導**: 「次回は直接〇〇する」「今後は直に〇〇してもらえる」など、今後くらしのマーケットを介さず取引・連絡することが約束・示唆されている場合も `direct_transaction` 違反として検出すること。
  - 例：「今後は直にLINEで日程調整をしてお掃除をしてくださる」→ LINE連絡先の交換＋直接取引の両方の違反
- **連絡先の開示**: 「電話番号を教えてもらった」「LINEを交換した」→ 直接取引誘導の違反
- **直接取引の誘導**: 「次回は直接連絡してと言われた」「くらしのマーケット以外で予約してと言われた」→ 直接取引の違反
- **料金の不正**: 「見積もりと違う金額」「当日に追加料金」「出張費を請求された」→ 料金ルール違反
- **高速代・有料道路代の別途請求**: 「高速代を別途請求された」「有料道路代を取られた」→ 対応エリア内での別途請求は禁止
- **当日・即日の追加料金**: 「当日だからと追加料金を言われた」→ 当日予約を理由にした加算は禁止
- **女性スタッフ・スタッフ指定の追加料金**: 「女性スタッフを頼んだら追加料金」「指名料を取られた」→ 禁止
- **待機料金の請求**: 「待っていただけなのに料金を請求された」→ 禁止
- **カード拒否・現金優遇**: 「現金なら安くすると言われた」「カードは使えないと言われた」→ 禁止
- **物販・商品販売**: 「サプリを売られた」「器具を購入するよう勧められた」→ 出張サービス中の物販は禁止
- **独自会員サービスの勧誘**: 「会員になりませんかと言われた」「独自のアフターフォロープランを勧められた」→ くらしのマーケット外サービスへの勧誘は禁止
- **無応答・無断キャンセル**: 「連絡が来なかった」「当日来なかった」→ 対応義務違反
- **口コミの誘導**: 「星5をつけてほしいと言われた」「良い口コミを書くよう頼まれた」→ 口コミ操作違反
- **資格外・無断外注**: 「別の業者が来た」「資格がなさそうだった」→ 外注ルール違反

### 判定の注意点
- 口コミに明示的に書かれていなくても、文脈から強く示唆される場合は違反として報告する
- 例：「また直接頼みたいです」という口コミ → 業者が直接取引を誘導した可能性が高い
- 例：「名刺を渡されました」→ 連絡先開示の明確な違反
- 複数の違反がある場合はすべて報告する

以下のJSON形式のみで回答してください（説明文は不要）:
{{
  "is_violation": true または false,
  "violations": [
    {{
      "category_id": "direct_transaction/price_violation/response_violation/service_misrepresentation/inappropriate_conduct/review_manipulation/unauthorized_subcontracting/prohibited_sales_solicitation のいずれか",
      "category_name": "違反カテゴリ名",
      "severity": "high/medium/low",
      "reason": "口コミのどの記述から違反と判定したか（具体的に、70文字以内）",
      "quote": "口コミ内の根拠となる箇所を引用（40文字以内、なければ空文字）"
    }}
  ],
  "summary": "運営担当者への総合コメント（違反の概要と推奨アクションを含めて150文字以内）",
  "confidence": "high/medium/low（判定の確信度）"
}}

違反が検出されない場合は violations を空配列にしてください。
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
