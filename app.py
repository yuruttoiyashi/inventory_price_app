import os
import math
import sqlite3
from datetime import datetime, date

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# =========================================================
# 基本設定
# =========================================================
st.set_page_config(
    page_title="副業・せどり在庫管理＆価格調査アプリ Pro",
    page_icon="📦",
    layout="wide"
)

DB_PATH = "inventory_app.db"

PLATFORM_FEES = {
    "メルカリ": 0.10,
    "ラクマ": 0.06,
    "ヤフーフリマ": 0.05,
    "その他": 0.10,
}

STATUS_OPTIONS = ["在庫中", "出品中", "売却済み"]
CONDITION_OPTIONS = ["新品", "未使用に近い", "目立った傷なし", "傷や汚れあり"]
PLATFORM_OPTIONS = list(PLATFORM_FEES.keys())
CATEGORY_OPTIONS = ["家電", "本・ゲーム", "ファッション", "コスメ", "雑貨", "ホビー", "食品", "その他"]

if "ai_advice_text" not in st.session_state:
    st.session_state.ai_advice_text = ""


# =========================================================
# CSS
# =========================================================
def load_css():
    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
    }

    .block-container {
        padding-top: 3.2rem;
        padding-bottom: 2rem;
    }

    .app-title {
        font-size: 2.05rem;
        font-weight: 800;
        color: #10233f;
        margin-bottom: 0.35rem;
        line-height: 1.25;
    }

    .app-subtitle {
        color: #5f6f86;
        font-size: 0.98rem;
        margin-bottom: 1.1rem;
    }

    .hero-box {
        background: linear-gradient(135deg, #ffffff 0%, #f4f8ff 100%);
        border: 1px solid #dce8f7;
        border-radius: 24px;
        padding: 22px 24px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
        margin-bottom: 18px;
    }

    .hero-title {
        font-size: 1.65rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 0.35rem;
    }

    .hero-text {
        color: #5f6f86;
        font-size: 0.98rem;
        line-height: 1.7;
    }

    .kpi-card {
        background: rgba(255,255,255,0.98);
        border: 1px solid #dbe7f4;
        border-radius: 22px;
        padding: 18px 18px 16px 18px;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
        min-height: 122px;
        margin-bottom: 10px;
    }

    .kpi-label {
        color: #64748b;
        font-size: 0.92rem;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .kpi-value {
        color: #0f172a;
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1.2;
        white-space: nowrap;
        margin-bottom: 6px;
    }

    .kpi-sub {
        color: #64748b;
        font-size: 0.82rem;
    }

    .section-title {
        font-size: 1.28rem;
        font-weight: 800;
        color: #10233f;
        margin: 10px 0 14px 0;
    }

    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-right: 6px;
        margin-bottom: 4px;
    }

    .badge-blue { background: #dbeafe; color: #1d4ed8; }
    .badge-green { background: #dcfce7; color: #166534; }
    .badge-yellow { background: #fef3c7; color: #92400e; }
    .badge-red { background: #fee2e2; color: #b91c1c; }
    .badge-slate { background: #e2e8f0; color: #334155; }

    .card-meta {
        color: #5f6f86;
        font-size: 0.92rem;
        line-height: 1.9;
    }

    .status-box-good {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        color: #166534;
        border-radius: 14px;
        padding: 12px;
        font-weight: 700;
    }

    .status-box-warn {
        background: #fff7ed;
        border: 1px solid #fed7aa;
        color: #9a3412;
        border-radius: 14px;
        padding: 12px;
        font-weight: 700;
    }

    .status-box-danger {
        background: #fef2f2;
        border: 1px solid #fecaca;
        color: #b91c1c;
        border-radius: 14px;
        padding: 12px;
        font-weight: 700;
    }

    .ai-box {
        background: linear-gradient(135deg, #eff6ff 0%, #f8fbff 100%);
        border: 1px solid #bfdbfe;
        border-radius: 18px;
        padding: 16px;
        color: #1e3a8a;
        line-height: 1.8;
        font-weight: 500;
    }

    .market-box {
        background: linear-gradient(135deg, #fff7ed 0%, #ffffff 100%);
        border: 1px solid #fed7aa;
        border-radius: 18px;
        padding: 16px;
        color: #9a3412;
        line-height: 1.8;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)


# =========================================================
# DB関連
# =========================================================
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            category TEXT,
            purchase_date TEXT,
            purchase_price REAL DEFAULT 0,
            shipping_cost REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            platform TEXT,
            condition TEXT,
            storage_location TEXT,
            status TEXT DEFAULT '在庫中',
            listed_date TEXT,
            sold_date TEXT,
            sold_price REAL,
            memo TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            checked_date TEXT,
            old_price REAL,
            new_price REAL,
            reason TEXT,
            ai_comment TEXT,
            market_summary TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# ユーティリティ
# =========================================================
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def html_escape(text):
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def format_yen(value) -> str:
    return f"{safe_float(value):,.0f}円"


def calc_fee_rate(platform: str) -> float:
    return PLATFORM_FEES.get(platform, 0.10)


def calc_fee(price: float, platform: str) -> float:
    return safe_float(price) * calc_fee_rate(platform)


def calc_expected_profit(selling_price: float, purchase_price: float, shipping_cost: float, platform: str) -> float:
    fee = calc_fee(selling_price, platform)
    return safe_float(selling_price) - fee - safe_float(shipping_cost) - safe_float(purchase_price)


def calc_profit_rate(selling_price: float, purchase_price: float, shipping_cost: float, platform: str) -> float:
    selling_price = safe_float(selling_price)
    if selling_price <= 0:
        return 0.0
    profit = calc_expected_profit(selling_price, purchase_price, shipping_cost, platform)
    return (profit / selling_price) * 100


def calc_actual_profit(row) -> float:
    sold_price = safe_float(row["sold_price"])
    if sold_price <= 0:
        return 0.0
    fee = calc_fee(sold_price, row["platform"])
    return sold_price - fee - safe_float(row["shipping_cost"]) - safe_float(row["purchase_price"])


def days_since(date_text: str):
    if not date_text:
        return None
    try:
        d = datetime.strptime(date_text, "%Y-%m-%d").date()
        return (date.today() - d).days
    except Exception:
        return None


def get_review_level(days_passed: int):
    if days_passed is None:
        return "未判定"
    if days_passed >= 21:
        return "優先見直し"
    if days_passed >= 14:
        return "値下げ候補"
    if days_passed >= 7:
        return "様子見"
    return "良好"


def get_discount_rate(days_passed: int):
    if days_passed is None:
        return 0.0
    if days_passed >= 21:
        return 0.08
    if days_passed >= 14:
        return 0.05
    if days_passed >= 7:
        return 0.03
    return 0.0


def get_profit_level(profit: float, profit_rate: float) -> str:
    if safe_float(profit) < 0:
        return "negative"
    if safe_float(profit_rate) < 15:
        return "low"
    return "good"


def calc_recommended_price(
    selling_price: float,
    purchase_price: float,
    shipping_cost: float,
    platform: str,
    listed_days: int,
    min_profit=500,
    min_profit_rate=15
):
    selling_price = safe_float(selling_price)
    purchase_price = safe_float(purchase_price)
    shipping_cost = safe_float(shipping_cost)

    if selling_price <= 0:
        return selling_price, "販売価格未設定"

    discount_rate = get_discount_rate(listed_days)
    if discount_rate <= 0:
        return selling_price, "現価格維持"

    candidate = math.floor(selling_price * (1 - discount_rate))

    while candidate > 0:
        profit = calc_expected_profit(candidate, purchase_price, shipping_cost, platform)
        rate = calc_profit_rate(candidate, purchase_price, shipping_cost, platform)

        if profit >= min_profit and rate >= min_profit_rate:
            return candidate, f"{int(discount_rate * 100)}%値下げ提案"

        candidate += 1
        if candidate >= selling_price:
            break

    return selling_price, "値下げ非推奨（利益確保不可）"


# =========================================================
# OpenAI / secrets
# =========================================================
def get_openai_api_key() -> str:
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return os.getenv("OPENAI_API_KEY", "")


def get_openai_model() -> str:
    try:
        return st.secrets["OPENAI_MODEL"]
    except Exception:
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# =========================================================
# CRUD
# =========================================================
def add_price_history(
    product_id: int,
    old_price: float,
    new_price: float,
    reason: str = "",
    ai_comment: str = "",
    market_summary: str = ""
):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO price_history (
            product_id, checked_date, old_price, new_price, reason, ai_comment, market_summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        product_id,
        date.today().strftime("%Y-%m-%d"),
        old_price,
        new_price,
        reason,
        ai_comment,
        market_summary
    ))
    conn.commit()
    conn.close()


def insert_product(data: dict):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (
            product_name, category, purchase_date, purchase_price, shipping_cost,
            selling_price, platform, condition, storage_location, status,
            listed_date, sold_date, sold_price, memo, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["product_name"],
        data["category"],
        data["purchase_date"],
        data["purchase_price"],
        data["shipping_cost"],
        data["selling_price"],
        data["platform"],
        data["condition"],
        data["storage_location"],
        data["status"],
        data["listed_date"],
        data["sold_date"],
        data["sold_price"],
        data["memo"],
        now_str(),
        now_str()
    ))
    conn.commit()
    conn.close()


def update_product(product_id: int, data: dict):
    conn = get_connection()
    cur = conn.cursor()

    current = cur.execute("SELECT selling_price FROM products WHERE id = ?", (product_id,)).fetchone()
    old_price = current["selling_price"] if current else None

    cur.execute("""
        UPDATE products
        SET product_name = ?,
            category = ?,
            purchase_date = ?,
            purchase_price = ?,
            shipping_cost = ?,
            selling_price = ?,
            platform = ?,
            condition = ?,
            storage_location = ?,
            status = ?,
            listed_date = ?,
            sold_date = ?,
            sold_price = ?,
            memo = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        data["product_name"],
        data["category"],
        data["purchase_date"],
        data["purchase_price"],
        data["shipping_cost"],
        data["selling_price"],
        data["platform"],
        data["condition"],
        data["storage_location"],
        data["status"],
        data["listed_date"],
        data["sold_date"],
        data["sold_price"],
        data["memo"],
        now_str(),
        product_id
    ))
    conn.commit()

    if old_price is not None and safe_float(old_price) != safe_float(data["selling_price"]):
        add_price_history(
            product_id=product_id,
            old_price=safe_float(old_price),
            new_price=safe_float(data["selling_price"]),
            reason="手動価格変更"
        )

    conn.close()


def delete_product(product_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM price_history WHERE product_id = ?", (product_id,))
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def fetch_products() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM products ORDER BY id DESC", conn)
    conn.close()
    return df


def fetch_product_by_id(product_id: int):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return row


def fetch_price_history(product_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT checked_date, old_price, new_price, reason, ai_comment, market_summary
        FROM price_history
        WHERE product_id = ?
        ORDER BY id DESC
    """, conn, params=(product_id,))
    conn.close()
    return df


def apply_recommended_price(product_id: int, new_price: float, reason: str, ai_comment: str = "", market_summary: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT selling_price FROM products WHERE id = ?", (product_id,)).fetchone()
    if row:
        old_price = safe_float(row["selling_price"])
        cur.execute("""
            UPDATE products
            SET selling_price = ?, updated_at = ?
            WHERE id = ?
        """, (new_price, now_str(), product_id))
        conn.commit()

        add_price_history(
            product_id=product_id,
            old_price=old_price,
            new_price=new_price,
            reason=reason,
            ai_comment=ai_comment,
            market_summary=market_summary
        )
    conn.close()


# =========================================================
# AI市場調査風コメント
# =========================================================
def generate_ai_market_advice(product_row: dict) -> tuple[str, str]:
    """
    戻り値:
    (market_summary, ai_advice)
    """
    api_key = get_openai_api_key()
    if not api_key:
        return "", "OPENAI_API_KEY が未設定のため、AIアドバイスは利用できません。"

    if OpenAI is None:
        return "", "openai ライブラリが見つかりません。requirements.txt を確認してください。"

    try:
        client = OpenAI(api_key=api_key)
        model_name = get_openai_model()

        listed_days = days_since(product_row.get("listed_date"))
        current_price = safe_float(product_row.get("selling_price", 0))
        purchase_price = safe_float(product_row.get("purchase_price", 0))
        shipping_cost = safe_float(product_row.get("shipping_cost", 0))
        platform = product_row.get("platform", "その他")

        expected_profit = calc_expected_profit(current_price, purchase_price, shipping_cost, platform)
        profit_rate = calc_profit_rate(current_price, purchase_price, shipping_cost, platform)
        rec_price, rec_label = calc_recommended_price(
            current_price,
            purchase_price,
            shipping_cost,
            platform,
            listed_days if listed_days is not None else 0
        )

        prompt = f"""
あなたはフリマ販売の市場調査アシスタントです。
実際のWeb検索はせず、与えられた情報から「市場感」「価格見直しの考え方」「売れやすさ」を推定して、
日本語で次の2つを作ってください。

1. market_summary:
100〜180文字程度。
この商品の市場感を簡潔にまとめる。
例: 需要の有無、回転率の考え方、価格帯の見方、競争の強さなど。

2. ai_advice:
120〜220文字程度。
現在価格を維持すべきか、値下げすべきか、値下げするならどんな考え方で調整するかを、初心者にも分かるように具体的に説明する。

必ずJSONだけで返してください。
説明文や前置きやコードブロックは不要です。
形式:
{{
  "market_summary": "...",
  "ai_advice": "..."
}}

商品情報:
- 商品名: {product_row.get("product_name", "")}
- カテゴリ: {product_row.get("category", "")}
- 販売先: {platform}
- 状態: {product_row.get("condition", "")}
- 現在価格: {current_price}円
- 仕入価格: {purchase_price}円
- 送料: {shipping_cost}円
- 想定利益: {round(expected_profit, 2)}円
- 利益率: {round(profit_rate, 2)}%
- 出品経過日数: {listed_days}
- 見直し判定: {get_review_level(listed_days) if listed_days is not None else "未判定"}
- 推奨価格: {rec_price}円
- 提案内容: {rec_label}

条件:
- 利益が薄いなら無理な値下げを勧めすぎない
- 長期在庫なら価格以外に、タイトル見直し・写真・説明文も触れてよい
- やさしく、実務的に
"""

        response = client.responses.create(
            model=model_name,
            input=prompt
        )

        text = getattr(response, "output_text", "").strip()

        if not text:
            return "", "AIコメントの生成に失敗しました。"

        # -------------------------------------------------
        # コードブロック除去
        # -------------------------------------------------
        cleaned = text.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[7:].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        # JSON本体だけ切り出し
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]

        import json
        try:
            data = json.loads(cleaned)
            market_summary = str(data.get("market_summary", "")).strip()
            ai_advice = str(data.get("ai_advice", "")).strip()

            return market_summary, ai_advice

        except Exception:
            # JSONとして読めなかったら、そのままアドバイス欄に逃がす
            return "", cleaned

    except Exception as e:
        return "", f"AIコメント生成エラー: {e}"

# =========================================================
# CSV
# =========================================================
def normalize_csv_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "商品名": "product_name",
        "カテゴリ": "category",
        "仕入日": "purchase_date",
        "仕入価格": "purchase_price",
        "送料": "shipping_cost",
        "販売価格": "selling_price",
        "販売先": "platform",
        "状態": "condition",
        "保管場所": "storage_location",
        "ステータス": "status",
        "出品日": "listed_date",
        "売却日": "sold_date",
        "売却価格": "sold_price",
        "メモ": "memo",
    }
    return df.rename(columns=rename_map)


def insert_products_from_csv(df: pd.DataFrame):
    required_defaults = {
        "product_name": "",
        "category": "その他",
        "purchase_date": "",
        "purchase_price": 0,
        "shipping_cost": 0,
        "selling_price": 0,
        "platform": "メルカリ",
        "condition": "目立った傷なし",
        "storage_location": "",
        "status": "在庫中",
        "listed_date": "",
        "sold_date": "",
        "sold_price": None,
        "memo": "",
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    for _, row in df.iterrows():
        if str(row["product_name"]).strip() == "":
            continue

        insert_product({
            "product_name": str(row["product_name"]),
            "category": str(row["category"]),
            "purchase_date": str(row["purchase_date"]) if pd.notna(row["purchase_date"]) else "",
            "purchase_price": safe_float(row["purchase_price"]),
            "shipping_cost": safe_float(row["shipping_cost"]),
            "selling_price": safe_float(row["selling_price"]),
            "platform": str(row["platform"]),
            "condition": str(row["condition"]),
            "storage_location": str(row["storage_location"]),
            "status": str(row["status"]),
            "listed_date": str(row["listed_date"]) if pd.notna(row["listed_date"]) else "",
            "sold_date": str(row["sold_date"]) if pd.notna(row["sold_date"]) else "",
            "sold_price": safe_float(row["sold_price"]) if pd.notna(row["sold_price"]) else None,
            "memo": str(row["memo"]),
        })


# =========================================================
# データ整形
# =========================================================
def enrich_products_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    df["想定手数料"] = df.apply(lambda r: round(calc_fee(r["selling_price"], r["platform"]), 2), axis=1)
    df["想定利益"] = df.apply(
        lambda r: round(calc_expected_profit(r["selling_price"], r["purchase_price"], r["shipping_cost"], r["platform"]), 2),
        axis=1
    )
    df["利益率(%)"] = df.apply(
        lambda r: round(calc_profit_rate(r["selling_price"], r["purchase_price"], r["shipping_cost"], r["platform"]), 2),
        axis=1
    )
    df["出品経過日数"] = df["listed_date"].apply(days_since)
    df["見直し判定"] = df["出品経過日数"].apply(get_review_level)

    recommended_prices = []
    recommendation_labels = []

    for _, r in df.iterrows():
        rec_price, rec_label = calc_recommended_price(
            r["selling_price"],
            r["purchase_price"],
            r["shipping_cost"],
            r["platform"],
            r["出品経過日数"] if pd.notna(r["出品経過日数"]) else 0
        )
        recommended_prices.append(rec_price)
        recommendation_labels.append(rec_label)

    df["推奨価格"] = recommended_prices
    df["提案内容"] = recommendation_labels

    actual_profits = []
    for _, r in df.iterrows():
        if r["status"] == "売却済み" and pd.notna(r["sold_price"]):
            actual_profits.append(round(calc_actual_profit(r), 2))
        else:
            actual_profits.append(None)
    df["実利益"] = actual_profits

    return df


# =========================================================
# UI部品
# =========================================================
def page_header(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div style="margin-top: 0.4rem; margin-bottom: 1rem;">
            <div class="app-title">{html_escape(title)}</div>
            <div class="app-subtitle">{html_escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def section_title(text: str):
    st.markdown(f'<div class="section-title">{html_escape(text)}</div>', unsafe_allow_html=True)


def hero_panel(title: str, text: str):
    st.markdown(f"""
    <div class="hero-box">
        <div class="hero-title">{html_escape(title)}</div>
        <div class="hero-text">{html_escape(text)}</div>
    </div>
    """, unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = ""):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{html_escape(label)}</div>
        <div class="kpi-value">{html_escape(value)}</div>
        <div class="kpi-sub">{html_escape(sub)}</div>
    </div>
    """, unsafe_allow_html=True)


def alert_box(text: str, level: str = "warning"):
    if level == "danger":
        st.markdown(f'<div class="status-box-danger">{html_escape(text)}</div>', unsafe_allow_html=True)
    elif level == "good":
        st.markdown(f'<div class="status-box-good">{html_escape(text)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="status-box-warn">{html_escape(text)}</div>', unsafe_allow_html=True)


def badge_html(text: str, cls: str) -> str:
    return f'<span class="badge {cls}">{html_escape(text)}</span>'


def review_badge(level: str) -> str:
    if level == "優先見直し":
        return badge_html("優先見直し", "badge-red")
    if level == "値下げ候補":
        return badge_html("値下げ候補", "badge-yellow")
    if level == "様子見":
        return badge_html("様子見", "badge-slate")
    return badge_html("良好", "badge-green")


def status_badge(status: str) -> str:
    if status == "売却済み":
        return badge_html("売却済み", "badge-green")
    if status == "出品中":
        return badge_html("出品中", "badge-blue")
    return badge_html("在庫中", "badge-slate")


def profit_badge(profit: float, rate: float) -> str:
    level = get_profit_level(profit, rate)
    if level == "negative":
        return badge_html("赤字", "badge-red")
    if level == "low":
        return badge_html("利益薄め", "badge-yellow")
    return badge_html("利益良好", "badge-green")


def render_inventory_card(row, key_suffix=""):
    review = row["見直し判定"]
    profit_value = safe_float(row["実利益"]) if row["status"] == "売却済み" and pd.notna(row["実利益"]) else safe_float(row["想定利益"])
    profit_rate = safe_float(row["利益率(%)"])
    listed_days = "—" if pd.isna(row["出品経過日数"]) else f"{int(row['出品経過日数'])}日"

    title_text = f"#{int(row['id'])} {row['product_name']}"
    if review == "優先見直し":
        st.error(title_text)
    elif review == "値下げ候補":
        st.warning(title_text)
    else:
        st.info(title_text)

    with st.container(border=True):
        st.markdown(
            status_badge(row["status"]) + review_badge(review) + profit_badge(profit_value, profit_rate),
            unsafe_allow_html=True
        )

        top_left, top_right = st.columns(2)

        with top_left:
            st.markdown(
                f"""
                <div class="card-meta">
                    <b>カテゴリ</b>: {html_escape(row["category"])}<br>
                    <b>販売先</b>: {html_escape(row["platform"])}<br>
                    <b>状態</b>: {html_escape(row["condition"])}
                </div>
                """,
                unsafe_allow_html=True
            )

        with top_right:
            st.markdown(
                f"""
                <div class="card-meta">
                    <b>出品経過日数</b>: {html_escape(listed_days)}<br>
                    <b>推奨価格</b>: {format_yen(row["推奨価格"])}<br>
                    <b>保管場所</b>: {html_escape(row["storage_location"] if row["storage_location"] else "未設定")}
                </div>
                """,
                unsafe_allow_html=True
            )

        st.caption("価格と利益")

        r1c1, r1c2 = st.columns(2)
        r1c1.metric("仕入価格", format_yen(row["purchase_price"]))
        r1c2.metric("現在価格", format_yen(row["selling_price"]))

        r2c1, r2c2 = st.columns(2)
        r2c1.metric("利益", format_yen(profit_value))
        r2c2.metric("利益率", f"{profit_rate:.1f}%")

        with st.expander("詳細を見る"):
            d1, d2 = st.columns(2)
            with d1:
                st.write(f"**提案内容**: {row['提案内容']}")
                st.write(f"**送料**: {format_yen(row['shipping_cost'])}")
            with d2:
                st.write(f"**メモ**: {row['memo'] if row['memo'] else 'なし'}")

        if profit_value < 0:
            st.error("この商品は赤字です。価格設定や送料を見直した方がよさそうです。")
        elif profit_rate < 15:
            st.warning("この商品は利益率が低めです。値下げしすぎに注意です。")
        else:
            st.success("利益はしっかり確保できています。")


def prepare_review_table(df: pd.DataFrame) -> pd.DataFrame:
    table_df = df.copy()
    table_df["商品ID"] = table_df["id"]
    table_df["商品名"] = table_df["product_name"]
    table_df["見直し判定"] = table_df["見直し判定"]
    table_df["現在価格"] = table_df["selling_price"].apply(format_yen)
    table_df["推奨価格"] = table_df["推奨価格"].apply(format_yen)
    table_df["想定利益"] = table_df["想定利益"].apply(format_yen)
    table_df["利益率"] = table_df["利益率(%)"].apply(lambda x: f"{safe_float(x):.1f}%")
    table_df["出品経過日数"] = table_df["出品経過日数"].apply(lambda x: "—" if pd.isna(x) else f"{int(x)}日")
    table_df["提案内容"] = table_df["提案内容"]

    return table_df[
        ["商品ID", "商品名", "見直し判定", "現在価格", "推奨価格", "想定利益", "利益率", "出品経過日数", "提案内容"]
    ]


# =========================================================
# 画面
# =========================================================
def sidebar_navigation():
    st.sidebar.markdown('<div class="section-title" style="font-size:1.15rem;">📦 在庫管理 Pro</div>', unsafe_allow_html=True)
    menu = st.sidebar.radio(
        "メニュー",
        ["ダッシュボード", "商品登録", "在庫一覧", "価格見直し", "売上分析", "CSV入出力"]
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("副業・せどり・メルカリ販売向け")
    return menu


def dashboard_page(df: pd.DataFrame):
    page_header("📊 ダッシュボード", "在庫・利益・見直し候補をひと目で把握できます。")

    if df.empty:
        hero_panel("まずは商品を登録しよう", "商品がまだありません。CSV取込や商品登録からスタートできます。")
        return

    inventory_count = len(df[df["status"] != "売却済み"])
    listed_count = len(df[df["status"] == "出品中"])
    sold_count = len(df[df["status"] == "売却済み"])

    current_month = date.today().strftime("%Y-%m")
    sold_this_month = df[
        (df["status"] == "売却済み") &
        (df["sold_date"].fillna("").astype(str).str.startswith(current_month))
    ].copy()

    month_sales = sold_this_month["sold_price"].fillna(0).sum()
    month_profit = sold_this_month["実利益"].fillna(0).sum()
    avg_profit_rate = ((month_profit / month_sales) * 100) if month_sales > 0 else 0

    review_df = df[
        (df["status"] == "出品中") &
        (df["見直し判定"].isin(["値下げ候補", "優先見直し"]))
    ].copy()

    long_term_df = df[
        (df["status"] == "出品中") &
        (df["出品経過日数"].fillna(0) >= 14)
    ].copy()

    low_profit_df = df[
        (df["status"] == "出品中") &
        (df["利益率(%)"].fillna(0) < 15)
    ].copy()

    hero_panel(
        "売れる在庫だけを残すための管理画面",
        "利益、長期在庫、値下げ候補をまとめて確認できるから、次に手をつける商品がすぐ分かります。"
    )

    c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1.15, 1.15, 1.15])
    with c1:
        kpi_card("在庫数", f"{inventory_count}件", "売却済み以外")
    with c2:
        kpi_card("出品中", f"{listed_count}件", "販売中の商品")
    with c3:
        kpi_card("売却済み", f"{sold_count}件", "累計")
    with c4:
        kpi_card("今月売上", format_yen(month_sales), "当月の売却金額")
    with c5:
        kpi_card("今月利益", format_yen(month_profit), "実利益ベース")
    with c6:
        kpi_card("平均利益率", f"{avg_profit_rate:.1f}%", "今月売却分")

    left_info, right_info = st.columns([1.15, 1])

    with left_info:
        section_title("今すぐ見るべきポイント")
        if len(review_df) > 0:
            alert_box(f"価格見直し候補が {len(review_df)} 件あります。『価格見直し』画面で優先対応できます。", "warning")
        else:
            alert_box("現在、強い価格見直し候補はありません。全体的に安定しています。", "good")

        if len(long_term_df) > 0:
            alert_box(f"14日以上の長期在庫が {len(long_term_df)} 件あります。売れ残り対策をすると利益改善につながりやすいです。", "danger")

        if len(low_profit_df) > 0:
            alert_box(f"利益率15%未満の商品が {len(low_profit_df)} 件あります。値下げ前に利益ラインの確認がおすすめです。", "warning")

    with right_info:
        section_title("ダッシュボード要約")
        with st.container(border=True):
            st.write(f"**見直し候補**: {len(review_df)}件")
            st.write(f"**長期在庫**: {len(long_term_df)}件")
            st.write(f"**利益薄め商品**: {len(low_profit_df)}件")
            st.write(f"**今月利益率**: {avg_profit_rate:.1f}%")

    left, right = st.columns([1.2, 1])

    with left:
        section_title("見直し候補一覧")
        if review_df.empty:
            st.success("現在、強い見直し候補はありません。")
        else:
            review_table = prepare_review_table(review_df)
            st.data_editor(
                review_table,
                use_container_width=True,
                height=340,
                hide_index=True,
                disabled=True
            )

    with right:
        section_title("最近登録した商品")
        recent_df = df.copy().head(6)
        recent_show = pd.DataFrame({
            "商品ID": recent_df["id"],
            "商品名": recent_df["product_name"],
            "現在価格": recent_df["selling_price"].apply(format_yen),
            "ステータス": recent_df["status"]
        })
        st.data_editor(
            recent_show,
            use_container_width=True,
            height=340,
            hide_index=True,
            disabled=True
        )


def product_form_page():
    page_header("📝 商品登録", "仕入れた商品や出品情報を登録します。")

    with st.container(border=True):
        with st.form("product_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            product_name = col1.text_input("商品名 *")
            category = col2.selectbox("カテゴリ", CATEGORY_OPTIONS)
            platform = col3.selectbox("販売先", PLATFORM_OPTIONS)

            col4, col5, col6 = st.columns(3)
            purchase_date = col4.date_input("仕入日", value=date.today())
            purchase_price = col5.number_input("仕入価格", min_value=0.0, step=100.0, value=0.0)
            shipping_cost = col6.number_input("送料", min_value=0.0, step=50.0, value=0.0)

            col7, col8, col9 = st.columns(3)
            selling_price = col7.number_input("販売価格", min_value=0.0, step=100.0, value=0.0)
            condition = col8.selectbox("状態", CONDITION_OPTIONS)
            status = col9.selectbox("ステータス", STATUS_OPTIONS, index=0)

            col10, col11, col12 = st.columns(3)
            listed_date_val = col10.date_input("出品日", value=date.today())
            storage_location = col11.text_input("保管場所", placeholder="棚A / クローゼット / 箱1")
            sold_price = col12.number_input("売却価格", min_value=0.0, step=100.0, value=0.0)

            sold_date_input = st.date_input("売却日", value=date.today())
            memo = st.text_area("メモ", placeholder="仕入れ先、商品の状態、補足など")

            submitted = st.form_submit_button("登録する", use_container_width=True)

            if submitted:
                if not product_name.strip():
                    st.error("商品名は必須です。")
                else:
                    actual_sold_price = sold_price if status == "売却済み" else None
                    actual_sold_date = sold_date_input.strftime("%Y-%m-%d") if status == "売却済み" else ""

                    insert_product({
                        "product_name": product_name.strip(),
                        "category": category,
                        "purchase_date": purchase_date.strftime("%Y-%m-%d"),
                        "purchase_price": purchase_price,
                        "shipping_cost": shipping_cost,
                        "selling_price": selling_price,
                        "platform": platform,
                        "condition": condition,
                        "storage_location": storage_location,
                        "status": status,
                        "listed_date": listed_date_val.strftime("%Y-%m-%d") if status in ["出品中", "売却済み"] else "",
                        "sold_date": actual_sold_date,
                        "sold_price": actual_sold_price,
                        "memo": memo,
                    })
                    st.success("商品を登録しました。")


def inventory_list_page(df: pd.DataFrame):
    page_header("📋 在庫一覧", "商品を一覧・編集・削除できます。")

    if df.empty:
        st.info("商品データがありません。")
        return

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        keyword = col1.text_input("検索", placeholder="商品名で検索")
        status_filter = col2.selectbox("ステータス絞り込み", ["すべて"] + STATUS_OPTIONS)
        category_filter = col3.selectbox("カテゴリ絞り込み", ["すべて"] + CATEGORY_OPTIONS)
        sort_key = col4.selectbox("並び順", ["ID降順", "利益が高い順", "出品経過日数が長い順", "販売価格が高い順"])

    filtered = df.copy()

    if keyword.strip():
        filtered = filtered[filtered["product_name"].str.contains(keyword, case=False, na=False)]

    if status_filter != "すべて":
        filtered = filtered[filtered["status"] == status_filter]

    if category_filter != "すべて":
        filtered = filtered[filtered["category"] == category_filter]

    if sort_key == "利益が高い順":
        filtered = filtered.sort_values(by="想定利益", ascending=False)
    elif sort_key == "出品経過日数が長い順":
        filtered = filtered.sort_values(by="出品経過日数", ascending=False, na_position="last")
    elif sort_key == "販売価格が高い順":
        filtered = filtered.sort_values(by="selling_price", ascending=False)
    else:
        filtered = filtered.sort_values(by="id", ascending=False)

    section_title("カード表示")
    if filtered.empty:
        st.info("条件に一致する商品がありません。")
    else:
        rows = list(filtered.iterrows())
        for i in range(0, len(rows), 2):
            col_left, col_right = st.columns(2)

            with col_left:
                _, row_left = rows[i]
                render_inventory_card(row_left, key_suffix=f"left_{i}")

            if i + 1 < len(rows):
                with col_right:
                    _, row_right = rows[i + 1]
                    render_inventory_card(row_right, key_suffix=f"right_{i}")

            st.markdown("")

    section_title("表形式")
    show_table = pd.DataFrame({
        "商品ID": filtered["id"],
        "商品名": filtered["product_name"],
        "カテゴリ": filtered["category"],
        "販売先": filtered["platform"],
        "仕入価格": filtered["purchase_price"].apply(format_yen),
        "現在価格": filtered["selling_price"].apply(format_yen),
        "想定利益": filtered["想定利益"].apply(format_yen),
        "利益率": filtered["利益率(%)"].apply(lambda x: f"{safe_float(x):.1f}%"),
        "ステータス": filtered["status"],
        "出品経過日数": filtered["出品経過日数"].apply(lambda x: "—" if pd.isna(x) else f"{int(x)}日"),
        "見直し判定": filtered["見直し判定"]
    })
    st.data_editor(show_table, use_container_width=True, hide_index=True, disabled=True)

    section_title("商品編集・削除")
    product_ids = filtered["id"].tolist()
    if not product_ids:
        return

    selected_id = st.selectbox("編集する商品ID", product_ids)
    row = fetch_product_by_id(selected_id)

    if row:
        with st.container(border=True):
            with st.form("edit_product_form"):
                c1, c2, c3 = st.columns(3)
                product_name = c1.text_input("商品名", value=row["product_name"] or "")
                category = c2.selectbox(
                    "カテゴリ",
                    CATEGORY_OPTIONS,
                    index=max(0, CATEGORY_OPTIONS.index(row["category"]) if row["category"] in CATEGORY_OPTIONS else 0)
                )
                platform = c3.selectbox(
                    "販売先",
                    PLATFORM_OPTIONS,
                    index=max(0, PLATFORM_OPTIONS.index(row["platform"]) if row["platform"] in PLATFORM_OPTIONS else 0)
                )

                c4, c5, c6 = st.columns(3)
                purchase_date_val = datetime.strptime(row["purchase_date"], "%Y-%m-%d").date() if row["purchase_date"] else date.today()
                purchase_date_input = c4.date_input("仕入日", value=purchase_date_val)
                purchase_price = c5.number_input("仕入価格", min_value=0.0, step=100.0, value=safe_float(row["purchase_price"]))
                shipping_cost = c6.number_input("送料", min_value=0.0, step=50.0, value=safe_float(row["shipping_cost"]))

                c7, c8, c9 = st.columns(3)
                selling_price = c7.number_input("販売価格", min_value=0.0, step=100.0, value=safe_float(row["selling_price"]))
                condition = c8.selectbox(
                    "状態",
                    CONDITION_OPTIONS,
                    index=max(0, CONDITION_OPTIONS.index(row["condition"]) if row["condition"] in CONDITION_OPTIONS else 0)
                )
                status = c9.selectbox(
                    "ステータス",
                    STATUS_OPTIONS,
                    index=max(0, STATUS_OPTIONS.index(row["status"]) if row["status"] in STATUS_OPTIONS else 0)
                )

                c10, c11, c12 = st.columns(3)
                listed_date_val = datetime.strptime(row["listed_date"], "%Y-%m-%d").date() if row["listed_date"] else date.today()
                listed_date_input = c10.date_input("出品日", value=listed_date_val)
                storage_location = c11.text_input("保管場所", value=row["storage_location"] or "")
                sold_price_value = safe_float(row["sold_price"]) if row["sold_price"] is not None else 0.0
                sold_price = c12.number_input("売却価格", min_value=0.0, step=100.0, value=sold_price_value)

                sold_date_val = datetime.strptime(row["sold_date"], "%Y-%m-%d").date() if row["sold_date"] else date.today()
                sold_date_input = st.date_input("売却日", value=sold_date_val)
                memo = st.text_area("メモ", value=row["memo"] or "")

                col_btn1, col_btn2 = st.columns(2)
                update_btn = col_btn1.form_submit_button("更新する", use_container_width=True)
                delete_btn = col_btn2.form_submit_button("削除する", use_container_width=True)

                if update_btn:
                    if not product_name.strip():
                        st.error("商品名は必須です。")
                    else:
                        actual_sold_price = sold_price if status == "売却済み" else None
                        actual_sold_date = sold_date_input.strftime("%Y-%m-%d") if status == "売却済み" else ""

                        update_product(selected_id, {
                            "product_name": product_name.strip(),
                            "category": category,
                            "purchase_date": purchase_date_input.strftime("%Y-%m-%d"),
                            "purchase_price": purchase_price,
                            "shipping_cost": shipping_cost,
                            "selling_price": selling_price,
                            "platform": platform,
                            "condition": condition,
                            "storage_location": storage_location,
                            "status": status,
                            "listed_date": listed_date_input.strftime("%Y-%m-%d") if status in ["出品中", "売却済み"] else "",
                            "sold_date": actual_sold_date,
                            "sold_price": actual_sold_price,
                            "memo": memo,
                        })
                        st.success("更新しました。")
                        st.rerun()

                if delete_btn:
                    delete_product(selected_id)
                    st.success("削除しました。")
                    st.rerun()

        section_title("価格変更履歴")
        history_df = fetch_price_history(selected_id)
        if history_df.empty:
            st.caption("まだ価格変更履歴はありません。")
        else:
            history_show = pd.DataFrame({
                "確認日": history_df["checked_date"],
                "変更前価格": history_df["old_price"].apply(format_yen),
                "変更後価格": history_df["new_price"].apply(format_yen),
                "理由": history_df["reason"],
                "市場感メモ": history_df["market_summary"].fillna(""),
                "AIコメント": history_df["ai_comment"].fillna("")
            })
            st.data_editor(history_show, use_container_width=True, hide_index=True, disabled=True)


def price_review_page(df: pd.DataFrame):
    page_header("💰 価格見直し", "AIに市場感を踏まえた価格見直しアドバイスを出させます。")

    target_df = df[df["status"] == "出品中"].copy()
    if target_df.empty:
        st.info("出品中の商品がありません。")
        return

    review_order_map = {
        "優先見直し": 0,
        "値下げ候補": 1,
        "様子見": 2,
        "良好": 3,
        "未判定": 4
    }
    target_df["review_order"] = target_df["見直し判定"].map(review_order_map).fillna(99)
    target_df = target_df.sort_values(
        by=["review_order", "出品経過日数"],
        ascending=[True, False],
        na_position="last"
    )

    urgent_df = target_df[target_df["見直し判定"] == "優先見直し"].copy()
    candidate_df = target_df[target_df["見直し判定"] == "値下げ候補"].copy()
    watch_df = target_df[target_df["見直し判定"] == "様子見"].copy()

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("優先見直し", f"{len(urgent_df)}件", "最優先で確認")
    with c2:
        kpi_card("値下げ候補", f"{len(candidate_df)}件", "価格調整候補")
    with c3:
        kpi_card("様子見", f"{len(watch_df)}件", "今後の確認対象")

    if len(urgent_df) > 0:
        alert_box(f"優先見直し商品が {len(urgent_df)} 件あります。長期在庫の可能性が高いです。", "danger")
    elif len(candidate_df) > 0:
        alert_box(f"値下げ候補が {len(candidate_df)} 件あります。価格見直しで回転率アップが狙えます。", "warning")
    else:
        alert_box("いまのところ大きな見直し候補はありません。", "good")

    section_title("見直し候補一覧")
    review_table = prepare_review_table(target_df)
    st.data_editor(
        review_table,
        use_container_width=True,
        height=420,
        hide_index=True,
        disabled=True
    )

    section_title("対象商品の詳細")
    selected_id = st.selectbox(
        "確認する商品ID",
        target_df["id"].tolist(),
        format_func=lambda x: f"商品ID {x}｜{target_df[target_df['id'] == x].iloc[0]['product_name']}"
    )
    selected_row = target_df[target_df["id"] == selected_id].iloc[0]

    render_inventory_card(selected_row, key_suffix="review")

    section_title("価格調整アクション")
    c_btn1, c_btn2 = st.columns(2)

    if c_btn1.button("AIに市場調査アドバイスを作らせる", use_container_width=True):
        market_summary, ai_advice = generate_ai_market_advice(selected_row.to_dict())
        st.session_state.ai_market_summary = market_summary
        st.session_state.ai_advice_text = ai_advice

    if c_btn2.button("推奨価格を適用する", use_container_width=True):
        if safe_float(selected_row["selling_price"]) == safe_float(selected_row["推奨価格"]):
            st.warning("現在価格と推奨価格が同じため、変更はありません。")
        else:
            apply_recommended_price(
                product_id=int(selected_row["id"]),
                new_price=safe_float(selected_row["推奨価格"]),
                reason=selected_row["提案内容"],
                ai_comment=st.session_state.get("ai_advice_text", ""),
                market_summary=st.session_state.get("ai_market_summary", "")
            )
            st.success("推奨価格を適用しました。")
            st.rerun()

    section_title("AI市場感メモ")
    market_summary = st.session_state.get("ai_market_summary", "")
    if market_summary:
        st.markdown(
            f'<div class="market-box">{html_escape(market_summary)}</div>',
            unsafe_allow_html=True
        )
    else:
        st.info("まだ市場感メモは生成されていません。")

    section_title("AI価格アドバイス")
    st.caption("※ OPENAI_API_KEY を Streamlit secrets に設定すると使えます。")
    if st.session_state.ai_advice_text:
        st.markdown(
            f'<div class="ai-box">{html_escape(st.session_state.ai_advice_text)}</div>',
            unsafe_allow_html=True
        )
    else:
        st.info("まだAIコメントは生成されていません。")


def sales_analysis_page(df: pd.DataFrame):
    page_header("📈 売上分析", "売上・利益・カテゴリ別の傾向を確認できます。")

    if df.empty:
        st.info("商品データがありません。")
        return

    sold_df = df[df["status"] == "売却済み"].copy()

    if sold_df.empty:
        st.info("まだ売却済みデータがありません。")
        return

    sold_df["sold_month"] = sold_df["sold_date"].fillna("").astype(str).str[:7]
    sold_df = sold_df[sold_df["sold_month"] != ""]

    monthly_sales = sold_df.groupby("sold_month")["sold_price"].sum().reset_index()
    monthly_profit = sold_df.groupby("sold_month")["実利益"].sum().reset_index()
    category_profit = sold_df.groupby("category")["実利益"].sum().reset_index()
    platform_sales = sold_df.groupby("platform")["sold_price"].sum().reset_index()

    total_sales = sold_df["sold_price"].sum()
    total_profit = sold_df["実利益"].sum()
    average_profit_rate = ((total_profit / total_sales) * 100) if total_sales > 0 else 0
    inventory_turnover = len(sold_df) / len(df) * 100 if len(df) > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("累計売上", format_yen(total_sales))
    with c2:
        kpi_card("累計利益", format_yen(total_profit))
    with c3:
        kpi_card("平均利益率", f"{average_profit_rate:.1f}%")
    with c4:
        kpi_card("在庫回転率", f"{inventory_turnover:.1f}%")

    left, right = st.columns(2)
    with left:
        section_title("月別売上")
        sales_chart = monthly_sales.rename(columns={"sold_month": "月", "sold_price": "売上"})
        st.bar_chart(sales_chart.set_index("月"))

    with right:
        section_title("月別利益")
        profit_chart = monthly_profit.rename(columns={"sold_month": "月", "実利益": "利益"})
        st.bar_chart(profit_chart.set_index("月"))

    left2, right2 = st.columns(2)
    with left2:
        section_title("カテゴリ別利益")
        category_chart = category_profit.rename(columns={"category": "カテゴリ", "実利益": "利益"})
        st.bar_chart(category_chart.set_index("カテゴリ"))

    with right2:
        section_title("販売先別売上")
        platform_chart = platform_sales.rename(columns={"platform": "販売先", "sold_price": "売上"})
        st.bar_chart(platform_chart.set_index("販売先"))


def csv_page(df: pd.DataFrame):
    page_header("📂 CSV入出力", "CSVでまとめて取り込み・書き出しができます。")

    with st.container(border=True):
        section_title("CSVインポート")
        uploaded_file = st.file_uploader("CSVをアップロード", type=["csv"])

        if uploaded_file is not None:
            try:
                import_df = pd.read_csv(uploaded_file)
                import_df = normalize_csv_columns(import_df)

                st.write("### 読み込みプレビュー")
                st.dataframe(import_df.head(), use_container_width=True, hide_index=True)

                if st.button("このCSVを取り込む", use_container_width=True):
                    insert_products_from_csv(import_df)
                    st.success("CSVを取り込みました。")
                    st.rerun()
            except Exception as e:
                st.error(f"CSV取り込みエラー: {e}")

    with st.container(border=True):
        section_title("CSVエクスポート")

        if df.empty:
            st.info("エクスポートできるデータがありません。")
        else:
            export_df = df.copy()
            export_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="在庫データをCSVダウンロード",
                data=export_bytes,
                file_name=f"inventory_export_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

            st.markdown("### 取込用CSVサンプル列")
            sample_df = pd.DataFrame([{
                "商品名": "サンプル商品",
                "カテゴリ": "家電",
                "仕入日": "2026-03-31",
                "仕入価格": 1000,
                "送料": 210,
                "販売価格": 2500,
                "販売先": "メルカリ",
                "状態": "目立った傷なし",
                "保管場所": "棚A",
                "ステータス": "出品中",
                "出品日": "2026-03-31",
                "売却日": "",
                "売却価格": "",
                "メモ": "サンプル"
            }])
            st.data_editor(sample_df, use_container_width=True, hide_index=True, disabled=True)


# =========================================================
# メイン
# =========================================================
def main():
    load_css()
    init_db()

    menu = sidebar_navigation()

    raw_df = fetch_products()
    df = enrich_products_df(raw_df)

    if menu == "ダッシュボード":
        dashboard_page(df)
    elif menu == "商品登録":
        product_form_page()
    elif menu == "在庫一覧":
        inventory_list_page(df)
    elif menu == "価格見直し":
        price_review_page(df)
    elif menu == "売上分析":
        sales_analysis_page(df)
    elif menu == "CSV入出力":
        csv_page(df)


if __name__ == "__main__":
    main()
