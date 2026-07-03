import io
import pandas as pd
import streamlit as st
from checker import check_review
from guidelines import SEVERITY_LABELS
from scraper import scrape_review

st.set_page_config(
    page_title="くらしのマーケット 出店者違反チェッカー",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 くらしのマーケット 出店者ガイドライン違反チェッカー")
st.caption("口コミURLを入力すると、口コミ内容から出店者のガイドライン違反行為を自動検出します。")

st.markdown("---")

with st.expander("📋 チェック対象ガイドライン（クリックで展開）"):
    from guidelines import GUIDELINES
    for g in GUIDELINES:
        severity_label = SEVERITY_LABELS.get(g["severity"], g["severity"])
        st.markdown(f"**{g['name']}** {severity_label}")
        st.caption(g["description"])

st.caption("1行に1つのURLを入力してください。複数のURLを同時にチェックできます。")

url_input = st.text_area(
    label="口コミURL",
    placeholder="https://curama.jp/aircon/wall/SER000000000/review/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\nhttps://curama.jp/...",
    height=150,
    label_visibility="collapsed",
)

col1, col2 = st.columns([1, 4])
with col1:
    run_button = st.button("🚀 チェック開始", type="primary", use_container_width=True)

if run_button:
    urls = [u.strip() for u in url_input.strip().splitlines() if u.strip()]

    if not urls:
        st.warning("URLを1件以上入力してください。")
        st.stop()

    st.markdown("---")
    st.markdown(f"### 📊 チェック結果（{len(urls)} 件）")

    results = []
    progress_bar = st.progress(0, text="チェック準備中...")
    status_text = st.empty()

    for i, url in enumerate(urls):
        progress_bar.progress(i / len(urls), text=f"処理中 {i + 1}/{len(urls)}: {url[:60]}...")
        status_text.info(f"⏳ スクレイピング中: {url[:80]}")

        scraped = scrape_review(url)

        if not scraped["success"]:
            results.append({
                "url": url,
                "status": "❌ 取得失敗",
                "review_text": "",
                "reviewer_name": "",
                "posted_date": "",
                "is_violation": None,
                "violation_count": 0,
                "violation_categories": "",
                "max_severity": "",
                "summary": scraped.get("error", "不明なエラー"),
                "details": [],
            })
            continue

        status_text.info(f"🤖 AI解析中: {url[:80]}")
        check_result = check_review(scraped)

        violations = check_result.get("violations", [])
        violation_categories = "、".join(v.get("category_name", "") for v in violations)
        severity_order = {"high": 0, "medium": 1, "low": 2}
        max_severity = (
            min(violations, key=lambda v: severity_order.get(v.get("severity", "low"), 9)).get("severity", "low")
            if violations else ""
        )
        is_violation = check_result.get("is_violation", False)
        can_apply_deletion = check_result.get("can_apply_deletion", False)
        error_msg = check_result.get("error", "")

        if error_msg:
            status_str = "⚠️ チェックエラー"
        elif is_violation:
            status_str = "🚨 出店者違反の疑い"
        else:
            status_str = "✅ 違反なし"

        results.append({
            "url": url,
            "status": status_str,
            "review_text": scraped.get("review_text", "")[:100]
                + ("..." if len(scraped.get("review_text", "")) > 100 else ""),
            "reviewer_name": scraped.get("reviewer_name", ""),
            "posted_date": scraped.get("posted_date", ""),
            "is_violation": is_violation,
            "can_apply_deletion": can_apply_deletion,
            "violation_count": len(violations),
            "violation_categories": violation_categories,
            "max_severity": SEVERITY_LABELS.get(max_severity, "") if max_severity else "",
            "summary": error_msg if error_msg else check_result.get("summary", ""),
            "details": violations,
        })

    progress_bar.progress(1.0, text="完了！")
    status_text.success(f"✅ {len(urls)} 件のチェックが完了しました。")

    violation_count = sum(1 for r in results if r["is_violation"])
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("チェック件数", len(results))
    col_b.metric("出店者違反の疑い", violation_count)
    col_c.metric("違反なし", len(results) - violation_count)

    st.markdown("#### 結果一覧")
    for r in results:
        with st.container():
            col_status, col_url = st.columns([1, 5])
            with col_status:
                st.markdown(f"**{r['status']}**")
            with col_url:
                st.markdown(f"[{r['url'][:60]}{'...' if len(r['url']) > 60 else ''}]({r['url']})")

            if r["review_text"]:
                st.caption(f"口コミ: {r['review_text']}")

            if r["details"]:
                for v in r["details"]:
                    severity_label = SEVERITY_LABELS.get(v.get("severity", ""), "")
                    quote = v.get("quote", "")
                    quote_str = f" 「{quote}」" if quote else ""
                    st.warning(
                        f"{severity_label} **{v.get('category_name', '')}**{quote_str}\n\n"
                        f"{v.get('reason', '')}"
                    )
            elif r["summary"]:
                st.caption(f"判定: {r['summary']}")

            st.markdown("---")

    st.markdown("#### CSVダウンロード")
    csv_rows = []
    for r in results:
        for v in r["details"] if r["details"] else [{}]:
            csv_rows.append({
                "URL": r["url"],
                "判定": r["status"],
                "口コミ（抜粋）": r["review_text"],
                "投稿者": r["reviewer_name"],
                "投稿日": r["posted_date"],
                "違反件数": r["violation_count"],
                "違反カテゴリ": v.get("category_name", ""),
                "重要度": SEVERITY_LABELS.get(v.get("severity", ""), ""),
                "違反箇所": v.get("quote", ""),
                "判定理由": v.get("reason", ""),
                "総合コメント": r["summary"],
            })

    if not csv_rows:
        csv_rows = [
            {
                "URL": r["url"],
                "判定": r["status"],
                "口コミ（抜粋）": r["review_text"],
                "投稿者": r["reviewer_name"],
                "投稿日": r["posted_date"],
                "違反件数": r["violation_count"],
                "違反カテゴリ": r["violation_categories"],
                "重要度": r["max_severity"],
                "違反箇所": "",
                "判定理由": "",
                "総合コメント": r["summary"],
            }
            for r in results
        ]

    df = pd.DataFrame(csv_rows)
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 CSV ダウンロード",
        data=csv_buffer.getvalue(),
        file_name="review_check_result.csv",
        mime="text/csv",
    )
