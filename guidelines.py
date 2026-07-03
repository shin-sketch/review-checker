GUIDELINES = [
    {
        "id": "personal_info",
        "name": "個人情報の記載",
        "description": "氏名・住所・電話番号・メールアドレスなど、個人を特定できる情報が含まれている",
        "examples": ["田中太郎さんという方が", "〇〇市〇〇町に住む", "090-XXXX-XXXXに連絡"],
        "severity": "high",
    },
    {
        "id": "defamation",
        "name": "誹謗中傷・過度な批判",
        "description": "特定の個人（作業員・店舗スタッフ等）を著しく傷つける表現、人格否定、侮辱的な言葉が含まれている",
        "examples": ["最低な人間", "詐欺師", "人としておかしい"],
        "severity": "high",
    },
    {
        "id": "unverifiable_claims",
        "name": "事実確認困難な主観的断定",
        "description": "「やる気がない」「悪意がある」「わざとやった」など、事実として検証できない主観的な断定が含まれている",
        "examples": ["絶対に手を抜いている", "わざと壊した", "こちらを騙そうとしている"],
        "severity": "medium",
    },
    {
        "id": "privacy_violation",
        "name": "プライバシー侵害",
        "description": "本人の同意なく個人の私生活・プライバシーに関わる情報を暴露している",
        "examples": ["この業者は離婚していて", "副業でやっているらしく"],
        "severity": "high",
    },
    {
        "id": "irrelevant_content",
        "name": "サービスと無関係な内容",
        "description": "依頼したサービスの内容と全く関係のない話題・情報が主体となっている",
        "examples": ["政治的な意見", "他の無関係なサービスの宣伝", "個人的な日記"],
        "severity": "medium",
    },
    {
        "id": "fake_review",
        "name": "虚偽情報・やらせ投稿の可能性",
        "description": "実際の体験に基づいていない可能性が高い内容。過度に絶賛しすぎていて宣伝文のようになっている、または明らかに誇張された否定的内容",
        "examples": ["100点満点以上の完璧な仕事", "人生最悪の体験でした（根拠なし）"],
        "severity": "medium",
    },
    {
        "id": "lack_of_specificity",
        "name": "具体性の欠如",
        "description": "一文のみ・意味のある評価ができない極端に短い・内容がない投稿",
        "examples": ["良かったです。", "普通", "まあまあ"],
        "severity": "low",
    },
    {
        "id": "store_related",
        "name": "店舗関係者による投稿の可能性",
        "description": "店舗スタッフ・知人・サクラによる自作自演が疑われる不自然に宣伝的な内容",
        "examples": ["ぜひ皆さんもご利用ください！", "完璧な業者です必ず使ってください！"],
        "severity": "medium",
    },
]

GUIDELINE_MAP = {g["id"]: g for g in GUIDELINES}

SEVERITY_LABELS = {
    "high": "🔴 高",
    "medium": "🟡 中",
    "low": "🟢 低",
}
