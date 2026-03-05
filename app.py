import os
import re
import json
import sqlite3
import threading
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'heritage-sales-secret-2024'

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ADMIN_PASSWORD = 'Heritage@123'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_PATH = os.path.join(os.path.dirname(__file__), 'heritage.db')

CATEGORIES = [
    'Company Overview', 'Milk', 'Paneer', 'Curd & Yogurt', 'Lassi',
    'Butter & Ghee', 'Cheese', 'Sweets', 'Ice Cream', 'Beverages', 'Other'
]

# ── Product metadata ──────────────────────────────────────────────────────────
PRODUCT_INFO = {
    'Artboard 1.jpg':  {'title': 'Heritage Foods',                        'category': 'Company Overview'},
    'Artboard 2.jpg':  {'title': 'Heritage at a Glance',                  'category': 'Company Overview'},
    'Artboard 3.jpg':  {'title': 'Legacy of Heritage',                    'category': 'Company Overview'},
    'Artboard 40.jpg': {'title': 'Heritage of Dairy Excellence Since 1992','category': 'Company Overview'},
    'Artboard 4.jpg':  {'title': 'Milk Range',              'category': 'Milk'},
    'Artboard 5.jpg':  {'title': 'Milk Variants',           'category': 'Milk'},
    'Artboard 6.jpg':  {'title': 'UHT Milk Range',          'category': 'Milk'},
    'Artboard 7.jpg':  {'title': 'UHT Milk',                'category': 'Milk'},
    'Artboard 34.jpg': {'title': 'Skimmed Milk Powder',     'category': 'Milk'},
    'Artboard 35.jpg': {'title': 'Skimmed Milk Powder',     'category': 'Milk'},
    'Artboard 10.jpg': {'title': 'Paneer',                  'category': 'Paneer'},
    'Artboard 11.jpg': {'title': 'Fresh Paneer',            'category': 'Paneer'},
    'Artboard 8.jpg':  {'title': 'Curd Range',              'category': 'Curd & Yogurt'},
    'Artboard 9.jpg':  {'title': 'Curd',                    'category': 'Curd & Yogurt'},
    'Artboard 36.jpg': {'title': 'Livo Yogurt Range',       'category': 'Curd & Yogurt'},
    'Artboard 37.jpg': {'title': 'Livo Yogurt',             'category': 'Curd & Yogurt'},
    'Artboard 20.jpg': {'title': 'Lassi Range',             'category': 'Lassi'},
    'Artboard 21.jpg': {'title': 'Lassi',                   'category': 'Lassi'},
    'Artboard 12.jpg': {'title': 'Ghee Range',              'category': 'Butter & Ghee'},
    'Artboard 13.jpg': {'title': 'Ghee',                    'category': 'Butter & Ghee'},
    'Artboard 26.jpg': {'title': 'Butter Range',            'category': 'Butter & Ghee'},
    'Artboard 27.jpg': {'title': 'Butter',                  'category': 'Butter & Ghee'},
    'Artboard 28.jpg': {'title': 'Cheese Range',            'category': 'Cheese'},
    'Artboard 29.jpg': {'title': 'Cheese',                  'category': 'Cheese'},
    'Artboard 14.jpg': {'title': 'Buttermilk Range',        'category': 'Beverages'},
    'Artboard 15.jpg': {'title': 'Buttermilk',              'category': 'Beverages'},
    'Artboard 16.jpg': {'title': 'Flavoured Milk Range',    'category': 'Beverages'},
    'Artboard 17.jpg': {'title': 'Flavoured Milk',          'category': 'Beverages'},
    'Artboard 18.jpg': {'title': 'Milkshake Range',         'category': 'Beverages'},
    'Artboard 19.jpg': {'title': 'Milkshake',               'category': 'Beverages'},
    'Artboard 22.jpg': {'title': 'Cold Coffee Range',       'category': 'Beverages'},
    'Artboard 23.jpg': {'title': 'Cafe Latte',              'category': 'Beverages'},
    'Artboard 24.jpg': {'title': 'Gluco Shakti Range',      'category': 'Beverages'},
    'Artboard 25.jpg': {'title': 'Gluco Shakti',            'category': 'Beverages'},
    'Artboard 30.jpg': {'title': 'Sweets – Laddus',         'category': 'Sweets'},
    'Artboard 31.jpg': {'title': 'Ghee Laddus',             'category': 'Sweets'},
    'Artboard 32.jpg': {'title': 'Sweets Range',            'category': 'Sweets'},
    'Artboard 33.jpg': {'title': 'Sweets',                  'category': 'Sweets'},
    'Artboard 38.jpg': {'title': 'Ice Cream Range',         'category': 'Ice Cream'},
    'Artboard 39.jpg': {'title': 'Ice Cream',               'category': 'Ice Cream'},
}

# ── Seed content — used to pre-populate the DB on first run so day-1 works
# without any LLM call. Claude only fires when artworks change after that.
SEED_CONTENT = {
    'Company Overview': {
        'summary': "Heritage Foods works with over 3 lakh farmers for direct milk procurement and serves more than 1 crore consumers every day. The brand is present in 17 states with 18 state-of-the-art processing plants. Every batch goes through 5 quality checkpoints and 25 quality tests, with 120-layer micron milk filters. Heritage is ISO Food Safety System certified, has won the National Energy Conservation Award 8 times, and holds the Golden Peacock Award for Corporate Governance. Key pitch: scale, trust, and unmatched quality infrastructure.",
        'quiz': {"topic": "Company Overview", "qs": [
            {"q": "How many farmers are associated with Heritage for direct milk procurement?", "opts": ["1L+", "2L+", "3L+", "5L+"], "ans": 2, "expl": "Heritage works with 3L+ (3 lakh+) farmers for direct milk procurement."},
            {"q": "In how many states does Heritage have a presence?", "opts": ["10", "14", "17", "21"], "ans": 2, "expl": "Heritage is present in 17 states across India."},
            {"q": "How many quality tests does Heritage milk undergo?", "opts": ["10", "15", "20", "25"], "ans": 3, "expl": "Heritage milk undergoes 5 checkpoints and 25 quality tests."},
        ]}
    },
    'Milk': {
        'summary': "Heritage offers a clear fat ladder — Toned at 3%, Standardised at 4.5%, Full Cream at 6%, and A2 Buffalo at 7% — covering every consumer need. The UHT range requires no boiling and no refrigeration until opened: Farm Fresh lasts 180 days, and Toned Pouch lasts 90 days. Lite Fit at just 0.1% fat is ideal for calorie-conscious buyers. All variants are fortified with Vitamins A and D. Skimmed Milk Powder has a 12-month shelf life in 3 pack sizes — push it for hotels, restaurants, and food processing buyers.",
        'quiz': {"topic": "Milk", "qs": [
            {"q": "What is the fat% in Heritage Toned Milk?", "opts": ["1.5%", "3.0%", "4.5%", "6.0%"], "ans": 1, "expl": "Toned Milk has 3.0% fat."},
            {"q": "What is the fat% in Heritage Full Cream Milk?", "opts": ["3.0%", "4.5%", "6.0%", "7.0%"], "ans": 2, "expl": "Full Cream Milk has 6.0% fat."},
            {"q": "What is the fat% in Sampurna A2 Buffalo Milk?", "opts": ["4.5%", "5.5%", "6.0%", "7.0%"], "ans": 3, "expl": "A2 Buffalo Milk has 7.0% fat — the highest in the range."},
            {"q": "What is the shelf life of Heritage UHT Toned Milk Pouch?", "opts": ["30 days", "60 days", "90 days", "120 days"], "ans": 2, "expl": "UHT Toned Milk Pouch has a 90-day shelf life at ambient temperature."},
            {"q": "What is the fat% in Heritage Lite Fit Milk?", "opts": ["0.1%", "1.0%", "2.0%", "3.0%"], "ans": 0, "expl": "Lite Fit Milk has only 0.1% fat — designed for health-conscious consumers."},
        ]}
    },
    'Paneer': {
        'summary': "Heritage Fresh Paneer has a 30-day shelf life stored below 5 degrees — and this is critical: do NOT deep freeze, as it affects texture. Available in 200 grams, 500 grams, and 1 kilogram — covering retail, food service, and bulk buyers. It is rich in Protein and a source of Calcium, hygienically packed from freshly procured milk. Target grocery stores, restaurants, caterers, and cloud kitchens.",
        'quiz': {"topic": "Paneer", "qs": [
            {"q": "What is the shelf life of Heritage Fresh Paneer?", "opts": ["10 days", "20 days", "30 days", "45 days"], "ans": 2, "expl": "Fresh Paneer has a 30-day shelf life when stored below 5°C."},
            {"q": "Heritage Fresh Paneer is available in which pack sizes?", "opts": ["100g, 200g, 500g", "200g, 500g, 1kg", "500g, 1kg, 2kg", "200g, 1kg, 5kg"], "ans": 1, "expl": "Fresh Paneer comes in 200g, 500g, and 1kg packs."},
            {"q": "What is the key storage instruction for Heritage Paneer?", "opts": ["Room temperature", "Below 5°C, do not deep freeze", "Below -10°C", "Below 10°C only"], "ans": 1, "expl": "Store below 5°C and do not deep freeze to maintain quality."},
        ]}
    },
    'Curd & Yogurt': {
        'summary': "Heritage Total Curd has 3% fat for everyday use, while Creamilicious at 4.5% fat is the premium option — both taste like homemade curd. Key shelf life point: Pouch is 7 days, but Cup and Tub is 21 days — always push cup SKUs to retailers for longer channel life. Livo Yogurt is the high-protein play — 5.5 grams of protein with only 1.6% fat, targeting fitness-conscious consumers. Available in Strawberry, Blueberry, Mango, and Classic with no added sugar.",
        'quiz': {"topic": "Curd & Yogurt", "qs": [
            {"q": "What is the fat% in Heritage Creamilicious Curd?", "opts": ["3.0%", "3.5%", "4.0%", "4.5%"], "ans": 3, "expl": "Creamilicious Curd has 4.5% fat."},
            {"q": "What is the shelf life of Total Curd Pouch?", "opts": ["3 days", "5 days", "7 days", "21 days"], "ans": 2, "expl": "Total Curd Pouch has a 7-day shelf life when stored below 5°C."},
            {"q": "What is the shelf life of Total Curd Cup?", "opts": ["7 days", "14 days", "21 days", "30 days"], "ans": 2, "expl": "Total Curd Cup and Tub have a 21-day shelf life below 5°C."},
            {"q": "What is the protein content in Heritage Livo Yogurt?", "opts": ["2.5g", "3.3g", "4.0g", "5.5g"], "ans": 3, "expl": "Livo Yogurt has 5.5g of protein."},
            {"q": "What is the fat% in Heritage Livo Yogurt?", "opts": ["0.5%", "1.0%", "1.6%", "2.5%"], "ans": 2, "expl": "Livo Yogurt has only 1.6% fat."},
        ]}
    },
    'Lassi': {
        'summary': "Heritage Lassi comes in four variants — Sweet, Mango, Strawberry, and Sabja with Chia seeds. The UHT SIG Pack has a 180-day ambient shelf life, making it perfect for modern trade, gifting, and export channels. Sabja Lassi has prebiotic effects from Chia seeds — use this as a digestive wellness pitch to health-aware buyers. Overall positioning: a healthy and tasty substitute to carbonated beverages.",
        'quiz': {"topic": "Lassi", "qs": [
            {"q": "What seeds are in Heritage Sabja Lassi?", "opts": ["Flax seeds", "Chia (Sabja) seeds", "Sesame seeds", "Sunflower seeds"], "ans": 1, "expl": "Sabja Lassi contains Chia (Sabja) seeds with prebiotic effects that aid digestion."},
            {"q": "What is the shelf life of Heritage Sweet Lassi UHT SIG Pack?", "opts": ["7 days", "30 days", "90 days", "180 days"], "ans": 3, "expl": "The UHT SIG Pack variant of Sweet Lassi has a 180-day shelf life."},
            {"q": "What is the carb% in Heritage Mango/Strawberry Lassi?", "opts": ["12%", "15.8%", "17.5%", "20%"], "ans": 2, "expl": "Mango and Strawberry Lassi have 17.5% carbohydrates."},
        ]}
    },
    'Butter & Ghee': {
        'summary': "Heritage Cow Ghee is a source of carotenoids and antioxidants supporting eye health and cognitive function, with Vitamins A, D, and E. Shelf life is 9 months for Jar and Poly, and 12 months for Tin. Buffalo Ghee is white in colour with butyric acid for intestinal health. Hi-Aroma Ghee uses a slow extended cooking process for a long-lasting nutty aroma — position it as a premium offering. Table Butter has a 12-month shelf life. Cooking Butter at 4 months is ideal for bakeries, sweet shops, and dessert makers.",
        'quiz': {"topic": "Butter & Ghee", "qs": [
            {"q": "Which Heritage Ghee supports eye health and cognitive function?", "opts": ["Buffalo Ghee", "Hi-Aroma Ghee", "Cow Ghee", "Cooking Ghee"], "ans": 2, "expl": "Cow Ghee is a source of carotenoids & anti-oxidants that support eye health and cognitive function."},
            {"q": "What is the shelf life of Heritage Cow Ghee Jar?", "opts": ["6 months", "9 months", "12 months", "18 months"], "ans": 1, "expl": "Cow Ghee Jar has a 9-month shelf life in cool & dry conditions."},
            {"q": "What makes Heritage Hi-Aroma Ghee unique?", "opts": ["Made from buffalo milk", "White in colour", "Slow extended cooking, long-lasting nutty aroma", "6-month shelf life"], "ans": 2, "expl": "Hi-Aroma Ghee uses a slow extended cooking process giving it a distinct nutty aroma."},
            {"q": "What is the shelf life of Heritage Table Butter (below 4°C)?", "opts": ["4 months", "6 months", "9 months", "12 months"], "ans": 3, "expl": "Table Butter has a 12-month shelf life when stored below 4°C."},
        ]}
    },
    'Cheese': {
        'summary': "Heritage Cheese Slice has a 9-month shelf life below 4 degrees — convenient and consistent melt, ideal for sandwiches and burgers. Cheese Block comes in 200 grams, 400 grams, and 1 kilogram — flexible for retail slicing and food service. Mozzarella is ready to cook — target quick service restaurants and cloud kitchens for pizza, pasta, burgers, and sandwiches. All Heritage Cheese is made from the highest quality Heritage Milk — leverage brand trust to cross-sell from the dairy aisle.",
        'quiz': {"topic": "Cheese", "qs": [
            {"q": "What is the shelf life of Heritage Cheese Slice (below 4°C)?", "opts": ["3 months", "6 months", "9 months", "12 months"], "ans": 2, "expl": "Cheese Slice has a 9-month shelf life when stored below 4°C."},
            {"q": "Heritage Cheese Block is available in which pack sizes?", "opts": ["100g, 200g", "200g, 400g, 1kg", "500g, 1kg", "200g, 500g, 2kg"], "ans": 1, "expl": "Cheese Block comes in 200g, 400g, and 1kg pack sizes."},
            {"q": "Heritage Mozzarella Cheese is ideally used in?", "opts": ["Tea & coffee", "Bread spreads only", "Pizza, pasta & burgers", "Indian curries"], "ans": 2, "expl": "Mozzarella is ready to cook and ideal for pizza, pasta, burgers, and sandwiches."},
        ]}
    },
    'Beverages': {
        'summary': "Heritage Buttermilk comes in regular at 1.2 grams protein and A-One Probiotic at 4.1 grams protein — always upsell to the probiotic for a wellness angle. The SIG Pack has a 180-day shelf life. Flavoured Milk is 1.5% fat with a 120-day shelf life. Milkshake has 3.3 grams protein and a 180-day shelf life in 5 flavours. Cafe Latte can be served hot or cold, made with handpicked coffee beans. Gluco Shakti has 14.4% carbohydrates — push to gyms, sports events, and outdoor channels.",
        'quiz': {"topic": "Beverages", "qs": [
            {"q": "What is the protein content in A-One Probiotic Spiced Buttermilk?", "opts": ["1.2g", "2.5g", "4.1g", "5.0g"], "ans": 2, "expl": "A-One Probiotic has 4.1g protein."},
            {"q": "What is the shelf life of Spiced Buttermilk SIG Pack?", "opts": ["5 days", "30 days", "90 days", "180 days"], "ans": 3, "expl": "Spiced Buttermilk SIG Pack has a 180-day shelf life at ambient temperature."},
            {"q": "What is the fat% in Heritage Flavoured Milk?", "opts": ["0.5%", "1.0%", "1.5%", "2.0%"], "ans": 2, "expl": "Heritage Flavoured Milk has 1.5% fat."},
            {"q": "What is the shelf life of Heritage Milkshake?", "opts": ["30 days", "90 days", "120 days", "180 days"], "ans": 3, "expl": "Heritage Milkshake has a 180-day shelf life."},
            {"q": "What is the carb% in Heritage Gluco Shakti Orange?", "opts": ["10.5%", "12.0%", "14.4%", "17.5%"], "ans": 2, "expl": "All Gluco Shakti variants have 14.4% carbohydrates."},
        ]}
    },
    'Sweets': {
        'summary': "Heritage Ghee Laddus in Millet, Jowar, and Besan variants have a 60-day shelf life — no palm oil, no vegetable oil, made with Heritage Ghee and real almonds and cashews. Doodh Peda has a 30-day shelf life — available from 20 grams to 500 grams. Gulab Jamun and Rasgulla both have a 365-day shelf life — made with pure desi ghee, untouched by hands. Push these for festivals, wedding catering, and year-round retail.",
        'quiz': {"topic": "Sweets", "qs": [
            {"q": "What is the shelf life of Heritage Ghee Laddus?", "opts": ["15 days", "30 days", "60 days", "90 days"], "ans": 2, "expl": "All Ghee Laddus have a 60-day shelf life in cool & dry conditions."},
            {"q": "What is NOT used in Heritage Truly Good Laddus?", "opts": ["Heritage Ghee", "Almonds & Cashews", "Palm Oil or Vegetable Oil", "Real Nuts"], "ans": 2, "expl": "No Palm Oil or Vegetable Oil is used in Heritage Truly Good Laddus."},
            {"q": "What is the shelf life of Heritage Gulab Jamun?", "opts": ["30 days", "90 days", "180 days", "365 days"], "ans": 3, "expl": "Gulab Jamun has a 365-day shelf life in cool & dry conditions."},
            {"q": "What is the shelf life of Heritage Doodh Peda?", "opts": ["10 days", "20 days", "30 days", "60 days"], "ans": 2, "expl": "Doodh Peda has a 30-day shelf life in cool & dry conditions."},
        ]}
    },
    'Ice Cream': {
        'summary': "Heritage Ice Cream Cups come in 50, 70, and 90 ml — standard flavours plus the premium Alpenvie range. Stick products include Choco Bar, Tasty Kulfi, Juicy Sticks, Mango Masti, and Swiss Fantasy — target impulse and the kids segment. Novelties like Cassata, Mega Sundae, Belgium Chocolate, and Kohinoor Kulfi are your premium and gifting range in 125 ml to 950 ml. Family Packs from 700 ml to 4 litres in 5 flavours — highest margin per transaction.",
        'quiz': {"topic": "Ice Cream", "qs": [
            {"q": "Heritage Ice Cream Family Packs are available in which sizes?", "opts": ["200ml–500ml", "500ml–1ltr", "700ml–4ltr", "1ltr–5ltr"], "ans": 2, "expl": "Family Packs range from 700ml to 4 litres."},
            {"q": "Which is a Heritage Ice Cream Novelty product?", "opts": ["Swiss Fantasy Stick", "Juicy Sticks", "Cassata & Mega Sundae", "Choco Bar"], "ans": 2, "expl": "Cassata and Mega Sundae fall under the Novelties category (125ml–950ml)."},
            {"q": "Heritage Ice Cream cups come in which sizes?", "opts": ["30ml, 50ml, 70ml", "50ml, 70ml, 90ml", "70ml, 90ml, 110ml", "90ml, 125ml, 200ml"], "ans": 1, "expl": "Heritage Ice Cream Cups are available in 50ml, 70ml, and 90ml sizes."},
        ]}
    },
}


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def artboard_sort_key(filename):
    nums = re.findall(r'\d+', filename)
    return int(nums[0]) if nums else 9999


NUM_ORDER = "CAST(REPLACE(REPLACE(filename,'Artboard ',''),'.jpg','') AS INTEGER)"

CAT_ORDER = """
  CASE category
    WHEN 'Company Overview' THEN 0
    WHEN 'Milk'             THEN 1
    WHEN 'Paneer'           THEN 2
    WHEN 'Curd & Yogurt'    THEN 3
    WHEN 'Lassi'            THEN 4
    WHEN 'Butter & Ghee'    THEN 5
    WHEN 'Cheese'           THEN 6
    WHEN 'Sweets'           THEN 7
    WHEN 'Ice Cream'        THEN 8
    WHEN 'Beverages'        THEN 9
    ELSE                         10
  END
"""


def init_db():
    conn = get_db()

    # ── Artworks table ────────────────────────────────────────────────────────
    conn.execute('''CREATE TABLE IF NOT EXISTS artworks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT DEFAULT 'Other',
        order_index INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── Category content table ────────────────────────────────────────────────
    # summary   — plain text, spoken by TTS on the frontend
    # quiz_json — JSON string matching QUIZ_BANK format { topic, qs: [...] }
    # status    — 'ready' | 'generating' | 'error'
    # updated_at — when the content was last written (display in admin)
    conn.execute('''CREATE TABLE IF NOT EXISTS category_content (
        category   TEXT PRIMARY KEY,
        summary    TEXT DEFAULT '',
        quiz_json  TEXT DEFAULT '{}',
        status     TEXT DEFAULT 'ready',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()

    # ── Seed artworks if empty ────────────────────────────────────────────────
    count = conn.execute('SELECT COUNT(*) FROM artworks').fetchone()[0]
    if count == 0:
        files = sorted(
            [f for f in os.listdir(UPLOAD_FOLDER)
             if f.lower().endswith(('.jpg', '.jpeg', '.png'))],
            key=artboard_sort_key
        )
        for i, fname in enumerate(files):
            info = PRODUCT_INFO.get(fname, {})
            conn.execute(
                'INSERT INTO artworks (filename, title, description, category, order_index) VALUES (?,?,?,?,?)',
                (fname, info.get('title', fname), '', info.get('category', 'Other'), i)
            )
        conn.commit()
    else:
        for fname, info in PRODUCT_INFO.items():
            conn.execute(
                "UPDATE artworks SET title=?, description='', category=? WHERE filename=?",
                (info.get('title', fname), info.get('category', 'Other'), fname)
            )
        conn.execute("UPDATE artworks SET description=''")
        conn.commit()

    # ── Seed category_content from SEED_CONTENT if not already present ────────
    # This means day-1 works instantly — Claude only fires on future changes.
    for category, data in SEED_CONTENT.items():
        existing = conn.execute(
            'SELECT category FROM category_content WHERE category=?', (category,)
        ).fetchone()
        if not existing:
            conn.execute(
                '''INSERT INTO category_content (category, summary, quiz_json, status, updated_at)
                   VALUES (?, ?, ?, 'ready', CURRENT_TIMESTAMP)''',
                (category, data['summary'], json.dumps(data['quiz']))
            )
    conn.commit()
    conn.close()


# ── LLM content generation ────────────────────────────────────────────────────
def _call_gemini(category, slide_titles):
    """
    Call Google Gemini (via new google-genai SDK) to regenerate summary + quiz.
    Returns (summary_str, quiz_dict) or (None, None) on failure.
    """
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print('[heritage] GEMINI_API_KEY not set in .env — skipping generation')
        return None, None

    try:
        # Initialize the new Client
        client = genai.Client(api_key=api_key)

        slides_text = '\n'.join(f'- {t}' for t in slide_titles)

        prompt = f'''You are generating training content for Heritage Foods sales representatives about the "{category}" product category.

The following product slides are currently active in this category:
{slides_text}

Return ONLY valid JSON. Do not include markdown formatting.
The JSON object must strictly follow this schema:
{{
  "summary": "150-200 word audio summary for sales reps. Flowing spoken sentences, no bullet points or headers. Cover key products, differentiators, shelf life, and target customers.",
  "quiz": {{
    "topic": "{category}",
    "qs": [
      {{
        "q": "Question text ending in a question mark?",
        "opts": ["Option A", "Option B", "Option C", "Option D"],
        "ans": 0,
        "expl": "One sentence explaining why the correct answer is right."
      }}
    ]
  }}
}}

Rules:
- Generate 3 to 5 quiz questions based ONLY on the slide titles above.
- "ans" is the zero-based index of the correct option in "opts".
- Every question must have exactly 4 options.'''

        # Call the model using the new syntax
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # Parse the JSON response
        data = json.loads(response.text)
        return data.get('summary', ''), data.get('quiz', {})

    except Exception as e:
        print(f'[heritage] Gemini generation failed for "{category}": {e}')
        return None, None


def _regenerate_worker(category):
    """
    Background thread:
    1. Mark status='generating'
    2. Fetch active slide titles
    3. Call Gemini
    4. Write new content + status='ready'
    """
    # Create a fresh connection for this thread
    conn = sqlite3.connect(DB_PATH) 
    conn.row_factory = sqlite3.Row

    try:
        # Step 1 — mark generating
        conn.execute(
            "UPDATE category_content SET status='generating' WHERE category=?",
            (category,)
        )
        conn.execute(
            '''INSERT OR IGNORE INTO category_content (category, summary, quiz_json, status)
               VALUES (?, '', '{}', 'generating')''',
            (category,)
        )
        conn.commit()

        # Step 2 — get active slides
        rows = conn.execute(
            f"SELECT title FROM artworks WHERE is_active=1 AND category=? ORDER BY {NUM_ORDER}",
            (category,)
        ).fetchall()

        if not rows:
            conn.execute(
                '''UPDATE category_content
                   SET summary='', quiz_json='{}', status='ready', updated_at=CURRENT_TIMESTAMP
                   WHERE category=?''',
                (category,)
            )
            conn.commit()
            return

        # Step 3 — call Gemini
        titles = [r['title'] for r in rows]
        summary, quiz = _call_gemini(category, titles)

        # Step 4 — persist result
        if summary is not None and quiz is not None:
            conn.execute(
                '''UPDATE category_content
                   SET summary=?, quiz_json=?, status='ready', updated_at=CURRENT_TIMESTAMP
                   WHERE category=?''',
                (summary, json.dumps(quiz), category)
            )
            print(f'[heritage] Content successfully regenerated for: {category}')
        else:
            conn.execute(
                "UPDATE category_content SET status='error' WHERE category=?",
                (category,)
            )
            print(f'[heritage] Content generation failed for: {category}')
        
        conn.commit()

    except Exception as e:
        print(f"[heritage] Worker error: {e}")
    finally:
        conn.close()

def regenerate_async(category):
    """Kick off background regeneration — returns immediately."""
    t = threading.Thread(target=_regenerate_worker, args=(category,), daemon=True)
    t.start()


# ── Flask routes ──────────────────────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin')
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html', categories=CATEGORIES)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        pwd = (request.json.get('password') if request.is_json
               else request.form.get('password'))
        if pwd == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return (jsonify({'success': True}) if request.is_json
                    else redirect(url_for('admin')))
        return jsonify({'success': False, 'message': 'Invalid password'}), 401
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


# ── Artworks API ──────────────────────────────────────────────────────────────
@app.route('/api/artworks')
def api_artworks():
    category = request.args.get('category', '')
    conn = get_db()
    if category and category != 'All':
        rows = conn.execute(
            f"SELECT * FROM artworks WHERE is_active=1 AND category=? ORDER BY {NUM_ORDER}",
            (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM artworks WHERE is_active=1 ORDER BY {CAT_ORDER}, {NUM_ORDER}"
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/artworks/all')
def api_artworks_all():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute(
        f"SELECT * FROM artworks ORDER BY {NUM_ORDER}"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/categories')
def api_categories():
    conn = get_db()
    cats = conn.execute(
        'SELECT DISTINCT category FROM artworks WHERE is_active=1'
    ).fetchall()
    conn.close()
    all_cats = [c['category'] for c in cats]
    ordered = [c for c in CATEGORIES if c in all_cats]
    return jsonify(['All'] + ordered)


@app.route('/api/artwork', methods=['POST'])
def api_add_artwork():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    if f.filename == '' or not allowed_file(f.filename):
        return jsonify({'error': 'Invalid file'}), 400

    filename = secure_filename(f.filename)
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        filename = f'{base}_{counter}{ext}'
        counter += 1
    f.save(os.path.join(UPLOAD_FOLDER, filename))

    conn = get_db()
    max_order = conn.execute('SELECT MAX(order_index) FROM artworks').fetchone()[0] or 0
    info = PRODUCT_INFO.get(filename, {})
    category = request.form.get('category', info.get('category', 'Other'))
    conn.execute(
        'INSERT INTO artworks (filename, title, description, category, order_index) VALUES (?,?,?,?,?)',
        (filename, request.form.get('title', info.get('title', filename)), '', category, max_order + 1)
    )
    conn.commit()
    conn.close()

    # Regenerate content for the affected category in the background
    regenerate_async(category)

    return jsonify({'success': True, 'filename': filename})


@app.route('/api/artwork/<int:artwork_id>', methods=['PUT'])
def api_update_artwork(artwork_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json

    conn = get_db()
    old = conn.execute('SELECT category, is_active FROM artworks WHERE id=?', (artwork_id,)).fetchone()
    new_category = data.get('category')
    new_active   = data.get('is_active', 1)

    conn.execute(
        "UPDATE artworks SET title=?, description='', category=?, is_active=? WHERE id=?",
        (data.get('title'), new_category, new_active, artwork_id)
    )
    conn.commit()
    conn.close()

    # Regenerate if category changed or visibility toggled
    if old:
        if old['category'] != new_category:
            regenerate_async(old['category'])   # old category lost a slide
            regenerate_async(new_category)      # new category gained one
        elif old['is_active'] != new_active:
            regenerate_async(new_category)      # visibility changed

    return jsonify({'success': True})


@app.route('/api/artwork/<int:artwork_id>', methods=['DELETE'])
def api_delete_artwork(artwork_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    row = conn.execute('SELECT filename, category FROM artworks WHERE id=?', (artwork_id,)).fetchone()
    if row:
        category = row['category']
        conn.execute('DELETE FROM artworks WHERE id=?', (artwork_id,))
        conn.commit()
        filepath = os.path.join(UPLOAD_FOLDER, row['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    conn.close()

    if row:
        regenerate_async(category)

    return jsonify({'success': True})


@app.route('/api/reorder', methods=['POST'])
def api_reorder():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    order = request.json.get('order', [])
    conn = get_db()
    for i, artwork_id in enumerate(order):
        conn.execute('UPDATE artworks SET order_index=? WHERE id=?', (i, artwork_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── Content API ───────────────────────────────────────────────────────────────
@app.route('/api/content')
def api_content():
    """
    Returns all category summaries, quizzes, and generation statuses.
    Frontend consumes this once at load to replace the old hardcoded constants.
    Admin panel polls this while status='generating'.
    """
    conn = get_db()
    rows = conn.execute('SELECT * FROM category_content').fetchall()
    conn.close()

    summaries = {}
    quizzes   = {}
    statuses  = {}

    for row in rows:
        cat = row['category']
        summaries[cat] = row['summary']
        statuses[cat]  = {'status': row['status'], 'updated_at': row['updated_at']}
        try:
            quizzes[cat] = json.loads(row['quiz_json']) if row['quiz_json'] else {}
        except json.JSONDecodeError:
            quizzes[cat] = {}

    return jsonify({'summaries': summaries, 'quizzes': quizzes, 'statuses': statuses})


@app.route('/api/content/<path:category>/regenerate', methods=['POST'])
def api_regenerate(category):
    """Manual re-trigger from admin panel."""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    regenerate_async(category)
    return jsonify({'success': True, 'message': f'Regenerating content for "{category}"'})


@app.route('/static/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5050)