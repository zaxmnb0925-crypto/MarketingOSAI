from app.models.brand import Brand
from app.models.content_generation import ContentPlatform


# R23 AI prompt quality controls

PLATFORM_RULES = {
    ContentPlatform.facebook: (
        "適合 Facebook；內容清楚、有敘事感，可適度加入 CTA。"
    ),
    ContentPlatform.instagram: (
        "適合 Instagram；前兩行要有吸引力，"
        "內容易讀，可搭配適量 hashtag。"
    ),
    ContentPlatform.threads: (
        "適合 Threads；口吻自然、像真人分享，"
        "避免過度廣告化。"
    ),
    ContentPlatform.linkedin: (
        "適合 LinkedIn；專業、可信、有商業價值。"
    ),
    ContentPlatform.x: (
        "適合 X；精簡直接，快速傳達核心訊息。"
    ),
    ContentPlatform.google_business: (
        "適合 Google 商家貼文；資訊明確，"
        "強調服務、活動或最新消息。"
    ),
}

CONTENT_LENGTH_RULES = {
    "short": "精簡，約 50–100 字",
    "standard": "標準，約 100–220 字",
    "long": "完整，約 220–400 字",
}


def clean(value: str | None) -> str:
    return value.strip() if value else "未設定"


def build_brand_prompt(
    brand: Brand,
    platform: ContentPlatform,
    topic: str,
    objective: str | None,
    audience: str | None = None,
    tone: str | None = None,
    content_length: str | None = None,
    call_to_action: str | None = None,
    keywords: str | None = None,
) -> str:

    requested_length = CONTENT_LENGTH_RULES.get(
        (content_length or "standard").strip().lower(),
        CONTENT_LENGTH_RULES["standard"],
    )

    return f"""你是一位專業品牌社群內容編輯。

請嚴格依照以下品牌資料產生內容。

【品牌】
品牌名稱：{brand.name}
產業：{clean(brand.industry)}
品牌介紹：{clean(brand.description)}
國家/市場：{clean(brand.country)}
語言：{brand.language}

【品牌策略】
目標客群：{clean(brand.target_audience)}
品牌語氣：{clean(brand.brand_voice or brand.tone)}
價值主張：{clean(brand.value_proposition)}
產品/服務：{clean(brand.products_services)}
品牌關鍵字：{clean(brand.keywords)}
預設 CTA：{clean(brand.default_cta)}
品牌規範：{clean(brand.brand_guidelines)}

【禁止事項】
不得使用以下詞彙或宣稱：
{clean(brand.forbidden_words)}

【本次任務】
平台：{platform.value}
平台規則：{PLATFORM_RULES[platform]}
主題：{topic.strip()}
目的：{clean(objective)}

【本次創作控制】
目標客群：{clean(audience)}
指定語氣：{clean(tone or "沿用品牌語氣")}
內容篇幅：{requested_length}
指定 CTA：{clean(call_to_action)}
必帶關鍵字：{clean(keywords)}

【輸出要求】
1. 使用品牌指定語言；若為繁體中文，使用台灣繁體中文。
2. 先寫出符合平台的開頭 hook，再自然展開內容。
3. 遵守品牌語氣、品牌規範、目標客群與篇幅要求。
4. CTA 只有在指定或品牌預設 CTA 有資料時才能使用。
5. 關鍵字要自然融入，不可硬塞；沒有資料不得虛構。
6. 不得出現禁止詞彙或捏造價格、優惠、成效、客戶證言、連結或事實。
7. 只輸出可直接發布的社群文案正文，不要輸出分析或欄位說明。
""".strip()


def detect_forbidden_words(
    text: str,
    forbidden_words: str | None,
) -> list[str]:

    if not forbidden_words:
        return []

    words = [
        item.strip()
        for item in forbidden_words.replace("，", ",").split(",")
        if item.strip()
    ]

    return [
        word
        for word in words
        if word.lower() in text.lower()
    ]
