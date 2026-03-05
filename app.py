import os
import re
import sqlite3
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'heritage-sales-secret-2024'

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ADMIN_PASSWORD = 'Heritage@2024'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_PATH = os.path.join(os.path.dirname(__file__), 'heritage.db')

CATEGORIES = [
    'Company Overview', 'Milk', 'Paneer', 'Curd & Yogurt', 'Lassi',
    'Butter & Ghee', 'Cheese', 'Sweets', 'Ice Cream', 'Beverages', 'Other'
]

# ── Product metadata ──────────────────────────────────────────────────────────
# Descriptions removed — category tags and ordering are the source of truth.
# All 40 artboards mapped: even numbers = image/intro slides, odd = spec slides
# (except the Company Overview group which follows its own pattern).
PRODUCT_INFO = {

    # ── Company Overview ───────────────────────────────────────────────────────
    'Artboard 1.jpg':  {'title': 'Heritage Foods',                        'category': 'Company Overview'},
    'Artboard 2.jpg':  {'title': 'Heritage at a Glance',                  'category': 'Company Overview'},
    'Artboard 3.jpg':  {'title': 'Legacy of Heritage',                    'category': 'Company Overview'},
    'Artboard 40.jpg': {'title': 'Heritage of Dairy Excellence Since 1992','category': 'Company Overview'},

    # ── Milk ───────────────────────────────────────────────────────────────────
    'Artboard 4.jpg':  {'title': 'Milk Range',              'category': 'Milk'},
    'Artboard 5.jpg':  {'title': 'Milk Variants',           'category': 'Milk'},
    'Artboard 6.jpg':  {'title': 'UHT Milk Range',          'category': 'Milk'},
    'Artboard 7.jpg':  {'title': 'UHT Milk',                'category': 'Milk'},
    'Artboard 34.jpg': {'title': 'Skimmed Milk Powder',     'category': 'Milk'},
    'Artboard 35.jpg': {'title': 'Skimmed Milk Powder',     'category': 'Milk'},

    # ── Paneer ─────────────────────────────────────────────────────────────────
    'Artboard 10.jpg': {'title': 'Paneer',                  'category': 'Paneer'},
    'Artboard 11.jpg': {'title': 'Fresh Paneer',            'category': 'Paneer'},

    # ── Curd & Yogurt ──────────────────────────────────────────────────────────
    'Artboard 8.jpg':  {'title': 'Curd Range',              'category': 'Curd & Yogurt'},
    'Artboard 9.jpg':  {'title': 'Curd',                    'category': 'Curd & Yogurt'},
    'Artboard 36.jpg': {'title': 'Livo Yogurt Range',       'category': 'Curd & Yogurt'},
    'Artboard 37.jpg': {'title': 'Livo Yogurt',             'category': 'Curd & Yogurt'},

    # ── Lassi ──────────────────────────────────────────────────────────────────
    'Artboard 20.jpg': {'title': 'Lassi Range',             'category': 'Lassi'},
    'Artboard 21.jpg': {'title': 'Lassi',                   'category': 'Lassi'},

    # ── Butter & Ghee ──────────────────────────────────────────────────────────
    'Artboard 12.jpg': {'title': 'Ghee Range',              'category': 'Butter & Ghee'},
    'Artboard 13.jpg': {'title': 'Ghee',                    'category': 'Butter & Ghee'},
    'Artboard 26.jpg': {'title': 'Butter Range',            'category': 'Butter & Ghee'},
    'Artboard 27.jpg': {'title': 'Butter',                  'category': 'Butter & Ghee'},

    # ── Cheese ─────────────────────────────────────────────────────────────────
    'Artboard 28.jpg': {'title': 'Cheese Range',            'category': 'Cheese'},
    'Artboard 29.jpg': {'title': 'Cheese',                  'category': 'Cheese'},

    # ── Beverages ──────────────────────────────────────────────────────────────
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

    # ── Sweets ─────────────────────────────────────────────────────────────────
    'Artboard 30.jpg': {'title': 'Sweets – Laddus',         'category': 'Sweets'},
    'Artboard 31.jpg': {'title': 'Ghee Laddus',             'category': 'Sweets'},
    'Artboard 32.jpg': {'title': 'Sweets Range',            'category': 'Sweets'},
    'Artboard 33.jpg': {'title': 'Sweets',                  'category': 'Sweets'},

    # ── Ice Cream ──────────────────────────────────────────────────────────────
    'Artboard 38.jpg': {'title': 'Ice Cream Range',         'category': 'Ice Cream'},
    'Artboard 39.jpg': {'title': 'Ice Cream',               'category': 'Ice Cream'},
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def artboard_sort_key(filename):
    nums = re.findall(r'\d+', filename)
    return int(nums[0]) if nums else 9999


def init_db():
    conn = get_db()
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
    conn.commit()

    count = conn.execute('SELECT COUNT(*) FROM artworks').fetchone()[0]
    if count == 0:
        # Fresh seed: insert all files found in uploads folder
        files = sorted(
            [f for f in os.listdir(UPLOAD_FOLDER)
             if f.lower().endswith(('.jpg', '.jpeg', '.png'))],
            key=artboard_sort_key
        )
        for i, fname in enumerate(files):
            info = PRODUCT_INFO.get(fname, {})
            conn.execute(
                'INSERT INTO artworks (filename, title, description, category, order_index) '
                'VALUES (?,?,?,?,?)',
                (fname,
                 info.get('title', fname),
                 '',   # descriptions always empty
                 info.get('category', 'Other'),
                 i)
            )
        conn.commit()
    else:
        # ── Sync pass: update title + category for every known artboard ────────
        # This ensures PRODUCT_INFO changes are reflected even on existing DBs.
        for fname, info in PRODUCT_INFO.items():
            conn.execute(
                'UPDATE artworks SET title=?, description=\'\', category=? WHERE filename=?',
                (info.get('title', fname), info.get('category', 'Other'), fname)
            )
        # Also blank out descriptions for any records not in PRODUCT_INFO
        conn.execute("UPDATE artworks SET description=''")
        conn.commit()

    conn.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ───────────────────────────────────────────────────────────────────
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


# ── API ──────────────────────────────────────────────────────────────────────
# Canonical category sort order — matches the CATEGORIES list in app and QUIZ_BANK in frontend
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

NUM_ORDER = "CAST(REPLACE(REPLACE(filename,'Artboard ',''),'.jpg','') AS INTEGER)"

@app.route('/api/artworks')
def api_artworks():
    category = request.args.get('category', '')
    conn = get_db()
    if category and category != 'All':
        rows = conn.execute(
            f"SELECT * FROM artworks WHERE is_active=1 AND category=? "
            f"ORDER BY {NUM_ORDER}",
            (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM artworks WHERE is_active=1 "
            f"ORDER BY {CAT_ORDER}, {NUM_ORDER}"
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/artworks/all')
def api_artworks_all():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM artworks "
        "ORDER BY CAST(REPLACE(REPLACE(filename,'Artboard ',''),'.jpg','') AS INTEGER)"
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

    # Return in the canonical CATEGORIES order, only including categories
    # that actually have active artworks
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
        filename = f"{base}_{counter}{ext}"
        counter += 1
    f.save(os.path.join(UPLOAD_FOLDER, filename))
    conn = get_db()
    max_order = conn.execute('SELECT MAX(order_index) FROM artworks').fetchone()[0] or 0
    info = PRODUCT_INFO.get(filename, {})
    conn.execute(
        'INSERT INTO artworks (filename, title, description, category, order_index) VALUES (?,?,?,?,?)',
        (filename,
         request.form.get('title', info.get('title', filename)),
         '',   # no descriptions
         request.form.get('category', info.get('category', 'Other')),
         max_order + 1)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'filename': filename})


@app.route('/api/artwork/<int:artwork_id>', methods=['PUT'])
def api_update_artwork(artwork_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    conn = get_db()
    conn.execute(
        'UPDATE artworks SET title=?, description=\'\', category=?, is_active=? WHERE id=?',
        (data.get('title'), data.get('category'), data.get('is_active', 1), artwork_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/artwork/<int:artwork_id>', methods=['DELETE'])
def api_delete_artwork(artwork_id):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    row = conn.execute('SELECT filename FROM artworks WHERE id=?', (artwork_id,)).fetchone()
    if row:
        conn.execute('DELETE FROM artworks WHERE id=?', (artwork_id,))
        conn.commit()
        filepath = os.path.join(UPLOAD_FOLDER, row['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    conn.close()
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


@app.route('/static/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5050)