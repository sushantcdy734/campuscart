from flask import Flask, request, jsonify, session, send_from_directory, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import sqlite3, os, uuid, hashlib, hmac, base64, json, requests, re
try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get('CAMPUS_DB_PATH', os.path.join(BASE, 'campuscart.db'))
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
USING_POSTGRES = bool(DATABASE_URL)
UPLOAD_DIR = os.path.join(BASE, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
STATIC_DIR = os.path.join(BASE, 'static')
os.makedirs(STATIC_DIR, exist_ok=True)

app = Flask(__name__, static_folder=os.path.join(BASE, 'static'), static_url_path='/static')
app.secret_key = os.environ.get('CAMPUS_SECRET_KEY') or ('campuscart-dev-secret-change-me' if os.environ.get('FLASK_ENV') != 'production' else os.urandom(32).hex())
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

ESEWA_ENV = os.environ.get('ESEWA_ENV', 'uat').strip().lower()
ESEWA_PRODUCT_CODE = os.environ.get('ESEWA_PRODUCT_CODE', 'EPAYTEST').strip()
ESEWA_SECRET_KEY = os.environ.get('ESEWA_SECRET_KEY', '8gBm/:&EnhH.1/q').strip()
KHALTI_ENV = os.environ.get('KHALTI_ENV', 'test').strip().lower()
KHALTI_SECRET_KEY = os.environ.get('KHALTI_SECRET_KEY', '')
BASE_URL = os.environ.get('CAMPUS_BASE_URL', '').rstrip('/')

ESEWA_FORM_URL = 'https://epay.esewa.com.np/api/epay/main/v2/form' if ESEWA_ENV == 'production' else 'https://rc-epay.esewa.com.np/api/epay/main/v2/form'
ESEWA_STATUS_URL = 'https://epay.esewa.com.np/api/epay/transaction/status/' if ESEWA_ENV == 'production' else 'https://rc.esewa.com.np/api/epay/transaction/status/'
KHALTI_BASE_URL = 'https://khalti.com/api/v2' if KHALTI_ENV == 'production' else 'https://dev.khalti.com/api/v2'

SEED = [
 ('Data Structures Textbook','Books',850,'📘','Clean used copy · BSc CSIT'),
 ('Scientific Calculator','Others',1200,'🧮','Good condition · Casio'),
 ('Wireless Headphones','Electronics',1850,'🎧','Lightly used · Bluetooth'),
 ('DBMS Complete Notes','Notes',450,'📝','Semester notes · Printed'),
 ('Study Table','Furniture',3200,'🪑','Solid wood · Pickup available'),
 ('Programming in C Book','Books',650,'📗','Good condition · Beginner friendly'),
 ('College Hoodie','Clothing',1100,'👕','Size M · Like new'),
 ('Mechanical Keyboard','Electronics',2400,'⌨️','RGB · USB wired')]

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ORDER_STATUSES = ('Payment Pending', 'Pending', 'Confirmed', 'Ready', 'Delivered', 'Cancelled')


class PgCursorCompat:
    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None
    def _sql(self, sql):
        sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT INTO', sql, flags=re.I)
        if 'INSERT OR IGNORE' in sql.upper():
            sql = sql.replace('INSERT OR IGNORE', 'INSERT')
        # qmark placeholders used by the original SQLite app.
        sql = sql.replace('?', '%s')
        # SQLite AUTOINCREMENT syntax for schema scripts.
        sql = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'BIGSERIAL PRIMARY KEY', sql, flags=re.I)
        if re.match(r'^\s*INSERT\s+INTO\s+(?!wishlists\b)', sql, flags=re.I) and 'RETURNING ' not in sql.upper() and ' ON CONFLICT ' not in sql.upper():
            sql = sql.rstrip().rstrip(';') + ' RETURNING id'
        elif re.match(r'^\s*INSERT\s+INTO\s+', sql, flags=re.I) and 'INSERT OR IGNORE' in sql.upper():
            sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
        return sql
    def execute(self, sql, params=None):
        original = sql
        if str(sql).strip().upper().startswith('PRAGMA'):
            return self
        converted = self._sql(sql)
        # Handle INSERT OR IGNORE after conversion.
        if re.search(r'^\s*INSERT\s+INTO\s+', converted, re.I) and 'OR IGNORE' in original.upper() and 'ON CONFLICT' not in converted.upper():
            converted = converted.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
        self._cur.execute(converted, params or ())
        if ' RETURNING ID' in converted.upper():
            row = self._cur.fetchone()
            self.lastrowid = row['id'] if row else None
        return self
    def executemany(self, sql, params_seq):
        converted = self._sql(sql)
        # Seed inserts do not need generated ids.
        converted = re.sub(r'\s+RETURNING\s+id\s*$', '', converted, flags=re.I)
        self._cur.executemany(converted, params_seq)
        return self
    def fetchone(self): return self._cur.fetchone()
    def fetchall(self): return self._cur.fetchall()

class PgConnectionCompat:
    def __init__(self):
        self._conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        self._cur = self._conn.cursor()
    def cursor(self): return PgCursorCompat(self._conn.cursor())
    def execute(self, sql, params=None):
        c = PgCursorCompat(self._conn.cursor())
        return c.execute(sql, params)
    def executemany(self, sql, params_seq):
        c = PgCursorCompat(self._conn.cursor())
        return c.executemany(sql, params_seq)
    def executescript(self, script):
        for statement in script.split(';'):
            if statement.strip():
                self.execute(statement)
        return self
    def commit(self): self._conn.commit()
    def rollback(self): self._conn.rollback()
    def close(self): self._conn.close()

def db():
    if USING_POSTGRES:
        if not psycopg:
            raise RuntimeError('PostgreSQL DATABASE_URL is configured but psycopg is not installed.')
        return PgConnectionCompat()
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('buyer','seller','admin')),
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      category TEXT NOT NULL,
      price REAL NOT NULL,
      icon TEXT DEFAULT '📦',
      description TEXT,
      stock INTEGER NOT NULL DEFAULT 1,
      seller_id INTEGER,
      image_url TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(seller_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS orders(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      buyer_id INTEGER NOT NULL,
      total REAL NOT NULL,
      payment_method TEXT NOT NULL,
      payment_status TEXT NOT NULL DEFAULT 'Pending',
      status TEXT NOT NULL DEFAULT 'Pending',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(buyer_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS order_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      seller_id INTEGER,
      quantity INTEGER NOT NULL,
      price REAL NOT NULL,
      FOREIGN KEY(order_id) REFERENCES orders(id),
      FOREIGN KEY(product_id) REFERENCES products(id),
      FOREIGN KEY(seller_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS payments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id INTEGER NOT NULL,
      provider TEXT NOT NULL,
      transaction_uuid TEXT UNIQUE,
      pidx TEXT UNIQUE,
      amount REAL NOT NULL,
      status TEXT NOT NULL DEFAULT 'Initiated',
      reference_id TEXT,
      raw_response TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    ''')

    # Safe upgrades for databases created by the previous SQLite version.
    if not USING_POSTGRES:
        product_cols = {r['name'] for r in c.execute('PRAGMA table_info(products)').fetchall()}
        if 'image_url' not in product_cols:
            c.execute('ALTER TABLE products ADD COLUMN image_url TEXT')
        order_cols = {r['name'] for r in c.execute('PRAGMA table_info(orders)').fetchall()}
        if 'payment_status' not in order_cols:
            c.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'Pending'")
    if c.execute('SELECT COUNT(*) n FROM products').fetchone()['n'] == 0:
        c.executemany(
            'INSERT INTO products(name,category,price,icon,description,stock,seller_id,image_url) VALUES(?,?,?,?,?,?,NULL,NULL)',
            [(a,b,c,d,e,10) for a,b,c,d,e in SEED]
        )
    c.commit(); c.close()


# Initialize schema when imported by Gunicorn or another WSGI server.
init_db()


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    c = db(); u = c.execute('SELECT id,name,email,role FROM users WHERE id=?', (uid,)).fetchone(); c.close()
    return u


def login_required(role=None):
    u = current_user()
    if not u:
        return None, (jsonify(error='Please login first.'), 401)
    if role and u['role'] != role:
        return None, (jsonify(error=f'{role.title()} account required.'), 403)
    return u, None


def absolute_url(path):
    if BASE_URL:
        return BASE_URL + path
    return url_for(path.lstrip('/'), _external=True) if False else request.url_root.rstrip('/') + path


def make_esewa_signature(total_amount, transaction_uuid):
    message = f'total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={ESEWA_PRODUCT_CODE}'
    digest = hmac.new(ESEWA_SECRET_KEY.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify_esewa_response(data):
    signed = data.get('signed_field_names', '')
    if not signed:
        return False
    parts = signed.split(',')
    message = ','.join(f'{p}={data.get(p, "")}' for p in parts)
    digest = hmac.new(ESEWA_SECRET_KEY.encode(), message.encode(), hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), data.get('signature', ''))


def json_response_message(message, status=200):
    return jsonify(message=message), status


def create_order(c, buyer_id, validated, method, status='Payment Pending', payment_status='Pending'):
    total = round(sum(p['price'] * qty for p, qty in validated), 2)
    cur = c.execute(
        'INSERT INTO orders(buyer_id,total,payment_method,payment_status,status) VALUES(?,?,?,?,?)',
        (buyer_id, total, method, payment_status, status)
    )
    oid = cur.lastrowid
    for p, qty in validated:
        c.execute(
            'INSERT INTO order_items(order_id,product_id,seller_id,quantity,price) VALUES(?,?,?,?,?)',
            (oid, p['id'], p['seller_id'], qty, p['price'])
        )
        c.execute('UPDATE products SET stock=stock-? WHERE id=?', (qty, p['id']))
    return oid, total


def restore_stock(c, order_id):
    items = c.execute('SELECT product_id, quantity FROM order_items WHERE order_id=?', (order_id,)).fetchall()
    for item in items:
        c.execute('UPDATE products SET stock=stock+? WHERE id=?', (item['quantity'], item['product_id']))




@app.get('/static/<path:filename>')
def static_file(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/')
def home():
    return send_from_directory(BASE, 'index.html')


@app.get('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.post('/api/register')
def register():
    d=request.get_json() or {}; name=d.get('name','').strip(); email=d.get('email','').strip().lower(); password=d.get('password',''); role=d.get('role','buyer')
    if not name or not email or len(password)<6 or role not in ('buyer','seller'):
        return jsonify(error='Enter valid details. Password must be at least 6 characters.'),400
    c=db()
    try:
        cur=c.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',(name,email,generate_password_hash(password),role)); c.commit(); session['user_id']=cur.lastrowid
    except (sqlite3.IntegrityError, psycopg.IntegrityError if psycopg else sqlite3.IntegrityError):
        c.close(); return jsonify(error='An account with this email already exists.'),409
    c.close(); return jsonify(message='Account created')


@app.post('/api/login')
def login():
    d=request.get_json() or {}; email=d.get('email','').strip().lower(); password=d.get('password','')
    c=db(); u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); c.close()
    if not u or not check_password_hash(u['password_hash'],password): return jsonify(error='Invalid email or password.'),401
    session['user_id']=u['id']; return jsonify(message='Logged in',user={'name':u['name'],'role':u['role']})


@app.get('/api/me')
def me():
    u=current_user(); return jsonify(user=dict(u) if u else None)


@app.post('/api/logout')
def logout():
    session.clear(); return jsonify(message='Logged out')


@app.get('/api/products')
def products():
    c=db(); rows=c.execute('SELECT p.*,u.name seller_name,COALESCE((SELECT AVG(r.rating) FROM reviews r WHERE r.product_id=p.id),0) rating,COALESCE((SELECT COUNT(*) FROM reviews r WHERE r.product_id=p.id),0) review_count FROM products p LEFT JOIN users u ON u.id=p.seller_id WHERE p.stock>0 ORDER BY p.id DESC').fetchall(); c.close(); return jsonify(products=[dict(x) for x in rows])


@app.post('/api/products')
def add_product():
    u,err=login_required('seller')
    if err:return err
    # Multipart form for image upload.
    form = request.form
    name=form.get('name','').strip(); category=form.get('category','Others'); price=form.get('price'); stock=form.get('stock',1); icon=form.get('icon','📦'); desc=form.get('description','').strip()
    try: price=float(price); stock=int(stock)
    except (TypeError,ValueError): return jsonify(error='Price and stock must be numbers.'),400
    if not name or price<=0 or stock<1:return jsonify(error='Enter a product name, valid price and stock.'),400
    image_url=None
    image=request.files.get('image')
    if image and image.filename:
        ext=image.filename.rsplit('.',1)[-1].lower() if '.' in image.filename else ''
        if ext not in ALLOWED_IMAGE_EXTENSIONS:return jsonify(error='Allowed images: PNG, JPG, JPEG, WEBP or GIF.'),400
        filename=f"{uuid.uuid4().hex}.{ext}"
        image.save(os.path.join(UPLOAD_DIR, secure_filename(filename)))
        image_url=f'/uploads/{filename}'
    c=db(); c.execute('INSERT INTO products(name,category,price,icon,description,stock,seller_id,image_url) VALUES(?,?,?,?,?,?,?,?)',(name,category,price,icon,desc,stock,u['id'],image_url)); c.commit(); c.close(); return jsonify(message='Product listed',image_url=image_url)


@app.get('/api/seller/products')
def seller_products():
    u,err=login_required('seller')
    if err:return err
    c=db(); rows=c.execute('SELECT * FROM products WHERE seller_id=? ORDER BY id DESC',(u['id'],)).fetchall(); c.close(); return jsonify(products=[dict(x) for x in rows])


@app.delete('/api/products/<int:pid>')
def delete_product(pid):
    u,err=login_required('seller')
    if err:return err
    c=db(); p=c.execute('SELECT * FROM products WHERE id=? AND seller_id=?',(pid,u['id'])).fetchone()
    if not p: c.close(); return jsonify(error='Product not found or not owned by you.'),404
    # Keep historical order references intact; hiding a listing sets stock to zero.
    c.execute('UPDATE products SET stock=0 WHERE id=? AND seller_id=?',(pid,u['id'])); c.commit(); c.close()
    return jsonify(message='Product removed from marketplace')


@app.get('/api/orders')
def orders():
    u=current_user()
    if not u:return jsonify(error='Please login first.'),401
    c=db(); result=[]
    if u['role']=='buyer':
        rows=c.execute('SELECT * FROM orders WHERE buyer_id=? ORDER BY id DESC',(u['id'],)).fetchall()
        for o in rows:
            items=c.execute("SELECT oi.*,p.name,p.icon,p.image_url,COALESCE(s.name,'CampusCart') seller_name FROM order_items oi JOIN products p ON p.id=oi.product_id LEFT JOIN users s ON s.id=oi.seller_id WHERE oi.order_id=?",(o['id'],)).fetchall()
            x=dict(o); x['items']=[dict(i) for i in items]; result.append(x)
    elif u['role']=='seller':
        rows=c.execute('SELECT DISTINCT o.*,b.name buyer_name,b.email buyer_email FROM orders o JOIN order_items oi ON oi.order_id=o.id JOIN users b ON b.id=o.buyer_id WHERE oi.seller_id=? ORDER BY o.id DESC',(u['id'],)).fetchall()
        for o in rows:
            items=c.execute('SELECT oi.*,p.name,p.icon,p.image_url FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=? AND oi.seller_id=?',(o['id'],u['id'])).fetchall()
            x=dict(o); x['items']=[dict(i) for i in items]; x['seller_total']=round(sum(float(i['price'])*int(i['quantity']) for i in items),2); result.append(x)
    c.close(); return jsonify(orders=result)


@app.post('/api/checkout')
def checkout():
    u,err=login_required('buyer')
    if err:return err
    d=request.get_json() or {}; items=d.get('items',[]); method=d.get('payment_method','COD')
    if method not in ('eSewa','Khalti','COD'):return jsonify(error='Unsupported payment method.'),400
    if not items:return jsonify(error='Cart is empty.'),400
    c=db(); validated=[]; total=0
    try:
        for item in items:
            pid=int(item['id']); qty=int(item['qty'])
            if qty < 1: raise ValueError('Invalid quantity.')
            p=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
            if not p or p['stock']<qty:raise ValueError(f'Not enough stock for {p["name"] if p else "a product"}.')
            validated.append((p,qty)); total+=p['price']*qty
        total=round(total,2)
        if method == 'COD':
            oid,total=create_order(c,u['id'],validated,method,status='Pending',payment_status='COD - Pending')
            c.commit(); c.close(); return jsonify(message='Order placed successfully',order_id=oid,total=total,payment_method=method)
        if method == 'eSewa':
            oid,total=create_order(c,u['id'],validated,method,status='Payment Pending',payment_status='Initiated')
            tx=f'CC-{oid}-{uuid.uuid4().hex[:12]}'
            c.execute('INSERT INTO payments(order_id,provider,transaction_uuid,amount,status) VALUES(?,?,?,?,?)',(oid,'eSewa',tx,total,'Initiated'))
            c.commit(); c.close()
            success=absolute_url('/payment/esewa/success'); failure=absolute_url('/payment/esewa/failure')
            return jsonify(payment='redirect',provider='eSewa',order_id=oid,action=ESEWA_FORM_URL,fields={
                'amount':f'{total:.2f}','tax_amount':'0','total_amount':f'{total:.2f}','transaction_uuid':tx,
                'product_code':ESEWA_PRODUCT_CODE,'product_service_charge':'0','product_delivery_charge':'0',
                'success_url':success,'failure_url':failure,'signed_field_names':'total_amount,transaction_uuid,product_code',
                'signature':make_esewa_signature(f'{total:.2f}',tx)})
        # Khalti
        if not KHALTI_SECRET_KEY:
            c.rollback(); c.close(); return jsonify(error='Khalti is not configured. Set KHALTI_SECRET_KEY in .env.'),503
        oid,total=create_order(c,u['id'],validated,method,status='Payment Pending',payment_status='Initiated')
        purchase=f'CampusCart Order #{oid}'
        c.commit();
        return_url=absolute_url('/payment/khalti/return')
        website_url=BASE_URL or request.url_root.rstrip('/')
        payload={'return_url':return_url,'website_url':website_url,'amount':int(round(total*100)),'purchase_order_id':str(oid),'purchase_order_name':purchase,'customer_info':{'name':u['name'],'email':u['email']}}
        try:
            r=requests.post(f'{KHALTI_BASE_URL}/epayment/initiate/',json=payload,headers={'Authorization':f'Key {KHALTI_SECRET_KEY}','Content-Type':'application/json'},timeout=20)
            data=r.json()
        except Exception as ex:
            c.rollback(); c.close(); return jsonify(error=f'Khalti connection failed: {ex}'),502
        if r.status_code >= 400 or not data.get('pidx'):
            restore_stock(c, oid)
            c.execute('DELETE FROM order_items WHERE order_id=?', (oid,))
            c.execute('DELETE FROM orders WHERE id=?', (oid,))
            c.commit(); c.close(); return jsonify(error=data.get('detail') or data.get('error_key') or 'Khalti could not initiate the payment.'),502
        c.execute('INSERT INTO payments(order_id,provider,pidx,amount,status,raw_response) VALUES(?,?,?,?,?,?)',(oid,'Khalti',data['pidx'],total,'Initiated',json.dumps(data)))
        c.commit(); c.close(); return jsonify(payment='redirect',provider='Khalti',order_id=oid,payment_url=data['payment_url'])
    except (ValueError,KeyError,TypeError) as e:
        c.rollback(); c.close(); return jsonify(error=str(e)),400


@app.get('/payment/esewa/success')
def esewa_success():
    encoded=request.args.get('data','')
    try:
        decoded=base64.b64decode(encoded).decode('utf-8')
        data=json.loads(decoded)
    except Exception:
        return 'Invalid eSewa payment response.',400
    if not verify_esewa_response(data): return 'Payment verification failed.',400
    tx=data.get('transaction_uuid'); status=data.get('status'); total=float(data.get('total_amount',0))
    c=db(); pay=c.execute('SELECT * FROM payments WHERE provider=? AND transaction_uuid=?',( 'eSewa',tx)).fetchone()
    if not pay: c.close(); return 'Payment record not found.',404
    if abs(pay['amount']-total)>0.01: c.close(); return 'Payment amount mismatch.',400
    # Server-to-server verification with eSewa status API.
    try:
        vr=requests.get(ESEWA_STATUS_URL,params={'product_code':ESEWA_PRODUCT_CODE,'total_amount':f'{total:.2f}','transaction_uuid':tx},timeout=15)
        v=vr.json()
    except Exception as ex:
        c.close(); return f'Payment verification service unavailable: {ex}',502
    verified=v.get('status')=='COMPLETE' and status=='COMPLETE'
    if verified:
        c.execute("UPDATE payments SET status='Complete',reference_id=?,raw_response=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(v.get('ref_id') or data.get('transaction_code'),json.dumps(data),pay['id']))
        c.execute("UPDATE orders SET payment_status='Paid',status='Pending' WHERE id=? AND payment_status!='Paid'",(pay['order_id'],))
        c.commit(); c.close(); return redirect('/?payment=success&order='+str(pay['order_id']))
    c.execute("UPDATE payments SET status=?,raw_response=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status or 'Failed',json.dumps(data),pay['id']))
    restore_stock(c,pay['order_id']); c.execute("UPDATE orders SET payment_status='Failed',status='Cancelled' WHERE id=?",(pay['order_id'],)); c.commit(); c.close()
    return redirect('/?payment=failed&order='+str(pay['order_id']))


@app.get('/payment/esewa/failure')
def esewa_failure():
    tx=request.args.get('transaction_uuid')
    c=db()
    if tx:
        pay=c.execute('SELECT * FROM payments WHERE provider=? AND transaction_uuid=?',( 'eSewa',tx)).fetchone()
        if pay:
            restore_stock(c,pay['order_id']); c.execute("UPDATE payments SET status='Failed',updated_at=CURRENT_TIMESTAMP WHERE id=?",(pay['id'],)); c.execute("UPDATE orders SET payment_status='Failed',status='Cancelled' WHERE id=?",(pay['order_id'],))
    c.commit(); c.close(); return redirect('/?payment=failed')


@app.get('/payment/khalti/return')
def khalti_return():
    pidx=request.args.get('pidx'); purchase_order_id=request.args.get('purchase_order_id')
    if not pidx: return redirect('/?payment=failed')
    c=db(); pay=c.execute('SELECT * FROM payments WHERE provider=? AND pidx=?',( 'Khalti',pidx)).fetchone()
    if not pay: c.close(); return 'Payment record not found.',404
    if not KHALTI_SECRET_KEY: c.close(); return 'Khalti is not configured.',503
    try:
        r=requests.post(f'{KHALTI_BASE_URL}/epayment/lookup/',json={'pidx':pidx},headers={'Authorization':f'Key {KHALTI_SECRET_KEY}','Content-Type':'application/json'},timeout=20)
        data=r.json()
    except Exception as ex:
        c.close(); return f'Khalti verification service unavailable: {ex}',502
    amount_paisa=data.get('total_amount')
    success=data.get('status')=='Completed' and amount_paisa is not None and abs(float(amount_paisa)/100 - pay['amount']) < 0.01 and (not purchase_order_id or str(purchase_order_id)==str(pay['order_id']))
    if success:
        c.execute("UPDATE payments SET status='Complete',reference_id=?,raw_response=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(data.get('transaction_id') or data.get('pidx'),json.dumps(data),pay['id']))
        c.execute("UPDATE orders SET payment_status='Paid',status='Pending' WHERE id=? AND payment_status!='Paid'",(pay['order_id'],)); c.commit(); c.close(); return redirect('/?payment=success&order='+str(pay['order_id']))
    c.execute("UPDATE payments SET status=?,raw_response=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(data.get('status','Failed'),json.dumps(data),pay['id']))
    restore_stock(c,pay['order_id']); c.execute("UPDATE orders SET payment_status='Failed',status='Cancelled' WHERE id=?",(pay['order_id'],)); c.commit(); c.close(); return redirect('/?payment=failed&order='+str(pay['order_id']))


@app.patch('/api/orders/<int:oid>/status')
def order_status(oid):
    u,err=login_required('seller')
    if err:return err
    d=request.get_json() or {}; status=d.get('status')
    allowed=('Pending','Confirmed','Ready','Delivered','Cancelled')
    if status not in allowed:return jsonify(error='Invalid order status.'),400
    c=db(); exists=c.execute('SELECT 1 FROM order_items WHERE order_id=? AND seller_id=?',(oid,u['id'])).fetchone()
    if not exists:c.close(); return jsonify(error='Order not found.'),404
    c.execute('UPDATE orders SET status=? WHERE id=?',(status,oid)); c.commit(); c.close(); return jsonify(message='Order status updated')


@app.get('/api/health')
def health(): return jsonify(status='ok',service='CampusCart API',payments={'eSewa':True,'Khalti':bool(KHALTI_SECRET_KEY)})


# ===== CampusCart Pro Upgrade: wishlist, reviews, profile, notifications, analytics =====
def _upgrade_features():
    c=db(); c.executescript('''
    CREATE TABLE IF NOT EXISTS wishlists(user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,product_id));
    CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, user_id INTEGER NOT NULL, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), comment TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(product_id,user_id));
    CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, message TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    '''); c.commit(); c.close()

_upgrade_features()

@app.get('/api/wishlist')
def get_wishlist():
    u,err=login_required()
    if err:return err
    c=db(); rows=c.execute('SELECT p.* FROM wishlists w JOIN products p ON p.id=w.product_id WHERE w.user_id=? ORDER BY w.created_at DESC',(u['id'],)).fetchall(); c.close(); return jsonify(products=[dict(x) for x in rows])

@app.post('/api/wishlist/<int:pid>')
def toggle_wishlist(pid):
    u,err=login_required()
    if err:return err
    c=db(); exists=c.execute('SELECT 1 FROM wishlists WHERE user_id=? AND product_id=?',(u['id'],pid)).fetchone()
    if exists: c.execute('DELETE FROM wishlists WHERE user_id=? AND product_id=?',(u['id'],pid)); saved=False
    else: c.execute('INSERT OR IGNORE INTO wishlists(user_id,product_id) VALUES(?,?)',(u['id'],pid)); saved=True
    c.commit(); c.close(); return jsonify(saved=saved)

@app.get('/api/products/<int:pid>/reviews')
def get_reviews(pid):
    c=db(); rows=c.execute('SELECT r.*,u.name FROM reviews r JOIN users u ON u.id=r.user_id WHERE r.product_id=? ORDER BY r.id DESC',(pid,)).fetchall(); avg=c.execute('SELECT COALESCE(AVG(rating),0) a,COUNT(*) n FROM reviews WHERE product_id=?',(pid,)).fetchone(); c.close(); return jsonify(reviews=[dict(x) for x in rows],average=round(avg['a'],1),count=avg['n'])

@app.post('/api/products/<int:pid>/reviews')
def add_review(pid):
    u,err=login_required('buyer')
    if err:return err
    d=request.get_json() or {}; rating=int(d.get('rating',0)); comment=str(d.get('comment','')).strip()[:500]
    if rating<1 or rating>5:return jsonify(error='Rating must be between 1 and 5.'),400
    c=db(); c.execute('INSERT INTO reviews(product_id,user_id,rating,comment) VALUES(?,?,?,?) ON CONFLICT(product_id,user_id) DO UPDATE SET rating=excluded.rating,comment=excluded.comment,created_at=CURRENT_TIMESTAMP',(pid,u['id'],rating,comment)); c.commit(); c.close(); return jsonify(message='Review saved')

@app.patch('/api/profile')
def update_profile():
    u,err=login_required()
    if err:return err
    d=request.get_json() or {}; name=str(d.get('name','')).strip()
    if len(name)<2:return jsonify(error='Please enter a valid name.'),400
    c=db(); c.execute('UPDATE users SET name=? WHERE id=?',(name,u['id'])); c.commit(); c.close(); return jsonify(message='Profile updated')

@app.get('/api/notifications')
def notifications():
    u,err=login_required()
    if err:return err
    c=db(); rows=c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 30',(u['id'],)).fetchall(); c.close(); return jsonify(notifications=[dict(x) for x in rows])

@app.get('/api/seller/analytics')
def seller_analytics():
    u,err=login_required('seller')
    if err:return err
    c=db(); r=c.execute("SELECT COUNT(DISTINCT oi.order_id) orders,COALESCE(SUM(CASE WHEN o.status!='Cancelled' THEN oi.price*oi.quantity ELSE 0 END),0) revenue,COALESCE(SUM(oi.quantity),0) units FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.seller_id=?",(u['id'],)).fetchone(); c.close(); return jsonify(orders=r['orders'],revenue=round(r['revenue'],2),units=r['units'])

@app.patch('/api/products/<int:pid>')
def edit_product(pid):
    u,err=login_required('seller')
    if err:return err
    d=request.get_json() or {}; fields=[]; vals=[]
    for k in ('name','category','description','icon','price','stock'):
        if k in d:
            fields.append(k+'=?'); vals.append(d[k])
    if not fields:return jsonify(error='Nothing to update.'),400
    vals.extend([pid,u['id']]); c=db(); c.execute('UPDATE products SET '+','.join(fields)+' WHERE id=? AND seller_id=?',vals); c.commit(); c.close(); return jsonify(message='Product updated')



# Messaging and marketplace support tables
def _ultimate_upgrade():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sender_id INTEGER NOT NULL,
      receiver_id INTEGER NOT NULL,
      product_id INTEGER,
      body TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      is_read INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS product_images(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      product_id INTEGER NOT NULL,
      image_url TEXT NOT NULL,
      sort_order INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS coupons(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      code TEXT UNIQUE NOT NULL,
      discount_type TEXT NOT NULL DEFAULT 'percent',
      discount_value REAL NOT NULL,
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS reports(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      reporter_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      reason TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Open',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_messages_sender_receiver ON messages(sender_id, receiver_id, id);
    CREATE INDEX IF NOT EXISTS idx_messages_receiver_read ON messages(receiver_id, is_read, id);
    """)
    c.execute("INSERT OR IGNORE INTO coupons(code,discount_type,discount_value,active) VALUES('CAMPUS10','percent',10,1)")
    c.commit(); c.close()

_ultimate_upgrade()

@app.post('/api/messages')
def send_message():
 u,err=login_required()
 if err:return err
 d=request.get_json(silent=True) or {}
 try: rid=int(d.get('receiver_id',0) or 0)
 except (TypeError,ValueError): return jsonify(error='Invalid receiver.'),400
 body=str(d.get('body','')).strip()[:1000]
 if not rid or not body:return jsonify(error='Receiver and message are required.'),400
 if rid==u['id']:return jsonify(error='You cannot message yourself. Please use a different buyer or seller account to test messaging.'),400
 c=db()
 try:
  receiver=c.execute('SELECT id,name,role FROM users WHERE id=?',(rid,)).fetchone()
  if not receiver:return jsonify(error='Receiver not found.'),404
  product_id=d.get('product_id')
  try: product_id=int(product_id) if product_id not in (None,'',0) else None
  except (TypeError,ValueError):return jsonify(error='Invalid product.'),400
  if product_id is not None and not c.execute('SELECT id FROM products WHERE id=?',(product_id,)).fetchone():return jsonify(error='Product not found.'),404
  cur=c.execute('INSERT INTO messages(sender_id,receiver_id,product_id,body) VALUES(?,?,?,?)',(u['id'],rid,product_id,body))
  mid=cur.lastrowid;c.commit();row=c.execute('SELECT * FROM messages WHERE id=?',(mid,)).fetchone()
  return jsonify(message='Message sent',saved_message=dict(row),conversation_user=dict(receiver))
 except Exception as ex:
  c.rollback();return jsonify(error='Could not save message: '+str(ex)),500
 finally:c.close()

@app.get('/api/messages/<int:other_id>')
def get_messages(other_id):
 u,err=login_required()
 if err:return err
 if other_id==u['id']:return jsonify(error='You cannot open a conversation with yourself.'),400
 c=db()
 try:
  other=c.execute('SELECT id,name,role FROM users WHERE id=?',(other_id,)).fetchone()
  if not other:return jsonify(error='User not found.'),404
  rows=c.execute('SELECT * FROM messages WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?) ORDER BY id ASC',(u['id'],other_id,other_id,u['id'])).fetchall()
  c.execute('UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=? AND is_read=0',(other_id,u['id']));c.commit()
  return jsonify(user=dict(other),messages=[dict(r) for r in rows])
 finally:c.close()

@app.get('/api/messages/contacts')
def message_contacts():
 u,err=login_required()
 if err:return err
 c=db()
 try:
  if u['role']=='buyer':
   rows=c.execute('SELECT u.id,u.name,u.email,u.role,COUNT(p.id) product_count FROM users u JOIN products p ON p.seller_id=u.id AND p.stock>0 WHERE u.role=? AND u.id<>? GROUP BY u.id,u.name,u.email,u.role ORDER BY product_count DESC,u.name',('seller',u['id'])).fetchall()
  else:
   rows=c.execute('SELECT u.id,u.name,u.email,u.role,0 product_count FROM users u WHERE u.role=? AND u.id<>? ORDER BY u.name',('buyer',u['id'])).fetchall()
  return jsonify(contacts=[dict(r) for r in rows])
 finally:c.close()

@app.get('/api/messages/conversations')
def message_conversations():
 u,err=login_required()
 if err:return err
 c=db()
 try:
  rows=c.execute('SELECT m.*, CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END AS other_id FROM messages m WHERE m.sender_id=? OR m.receiver_id=? ORDER BY m.id DESC',(u['id'],u['id'],u['id'])).fetchall()
  seen=set();out=[]
  for m in rows:
   oid=m['other_id']
   if oid in seen:continue
   seen.add(oid);other=c.execute('SELECT id,name,email,role FROM users WHERE id=?',(oid,)).fetchone()
   if not other:continue
   unread=c.execute('SELECT COUNT(*) n FROM messages WHERE sender_id=? AND receiver_id=? AND is_read=0',(oid,u['id'])).fetchone()['n']
   out.append({'user':dict(other),'last':{'body':m['body'],'created_at':m['created_at']},'unread':unread})
  return jsonify(conversations=out)
 finally:c.close()

@app.post('/api/messages/<int:other_id>/read')
def mark_messages_read(other_id):
 u,err=login_required()
 if err:return err
 c=db()
 try:
  c.execute('UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=?',(other_id,u['id']));c.commit();return jsonify(message='Messages marked as read')
 finally:c.close()

@app.post('/api/coupons/validate')
def validate_coupon():
 d=request.get_json() or {}; code=str(d.get('code','')).strip().upper(); total=float(d.get('total',0) or 0)
 c=db(); cp=c.execute('SELECT * FROM coupons WHERE code=? AND active=1',(code,)).fetchone(); c.close()
 if not cp:return jsonify(error='Invalid coupon.'),404
 discount=min(total,total*cp['discount_value']/100 if cp['discount_type']=='percent' else cp['discount_value'])
 return jsonify(code=code,discount=round(discount,2),total=round(total-discount,2))

@app.post('/api/reports')
def report_product():
 u,err=login_required()
 if err:return err
 d=request.get_json() or {}; reason=str(d.get('reason','')).strip()[:500]; pid=int(d.get('product_id',0) or 0)
 if not pid or not reason:return jsonify(error='Product and reason are required.'),400
 c=db(); c.execute('INSERT INTO reports(reporter_id,product_id,reason) VALUES(?,?,?)',(u['id'],pid,reason)); c.commit(); c.close(); return jsonify(message='Report submitted')

@app.post('/api/products/<int:pid>/images')
def extra_image(pid):
 u,err=login_required('seller')
 if err:return err
 im=request.files.get('image')
 if not im or not im.filename:return jsonify(error='Choose an image.'),400
 ext=im.filename.rsplit('.',1)[-1].lower() if '.' in im.filename else ''
 if ext not in ALLOWED_IMAGE_EXTENSIONS:return jsonify(error='Invalid image type.'),400
 c=db(); own=c.execute('SELECT 1 FROM products WHERE id=? AND seller_id=?',(pid,u['id'])).fetchone()
 if not own:c.close();return jsonify(error='Product not found.'),404
 fn=uuid.uuid4().hex+'.'+ext; im.save(os.path.join(UPLOAD_DIR,fn)); url='/uploads/'+fn; c.execute('INSERT INTO product_images(product_id,image_url) VALUES(?,?)',(pid,url));c.commit();c.close();return jsonify(image_url=url)

@app.get('/api/admin/analytics')
def admin_analytics():
 u=current_user()
 if not u or u['email'] not in ('admin@campuscart.local','admin@campuscart.com'):return jsonify(error='Admin access required.'),403
 c=db(); data={};
 for k,t in [('users','users'),('products','products'),('orders','orders'),('reports','reports')]:data[k]=c.execute('SELECT COUNT(*) n FROM '+t).fetchone()['n']
 c.close();return jsonify(data)


# ===== Daraz-style marketplace expansion =====
def _daraz_upgrade():
    c=db(); c.executescript("""
    CREATE TABLE IF NOT EXISTS stores(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER UNIQUE NOT NULL,store_name TEXT NOT NULL,description TEXT DEFAULT '',logo_url TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS addresses(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,label TEXT NOT NULL,full_address TEXT NOT NULL,phone TEXT,city TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS product_variants(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER NOT NULL,name TEXT NOT NULL,value TEXT NOT NULL,extra_price REAL DEFAULT 0,stock INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS order_tracking(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER NOT NULL,status TEXT NOT NULL,note TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    """); c.commit(); c.close()
_daraz_upgrade()

@app.get('/api/marketplace/filters')
def marketplace_filters():
    c=db(); rows=c.execute('SELECT category,COUNT(*) n FROM products GROUP BY category ORDER BY category').fetchall(); brands=c.execute("SELECT DISTINCT COALESCE(icon,'Other') b FROM products LIMIT 20").fetchall(); c.close(); return jsonify(categories=[dict(r) for r in rows],brands=[r['b'] for r in brands])

@app.get('/api/stores/<int:seller_id>')
def get_store(seller_id):
    c=db(); seller=c.execute("SELECT id,name,email FROM users WHERE id=? AND role='seller'",(seller_id,)).fetchone()
    if not seller: c.close(); return jsonify(error='Store not found'),404
    store=c.execute('SELECT * FROM stores WHERE seller_id=?',(seller_id,)).fetchone(); products=c.execute('SELECT * FROM products WHERE seller_id=? ORDER BY id DESC',(seller_id,)).fetchall(); c.close(); return jsonify(seller=dict(seller),store=dict(store) if store else {'store_name':seller['name']+" Store",'description':'CampusCart verified seller'},products=[dict(x) for x in products])

@app.post('/api/store')
def save_store():
    u,err=login_required('seller')
    if err:return err
    d=request.get_json() or {}; name=str(d.get('store_name','')).strip()[:80]; desc=str(d.get('description','')).strip()[:500]
    if len(name)<2:return jsonify(error='Store name is required'),400
    c=db(); c.execute('INSERT INTO stores(seller_id,store_name,description) VALUES(?,?,?) ON CONFLICT(seller_id) DO UPDATE SET store_name=excluded.store_name,description=excluded.description',(u['id'],name,desc)); c.commit(); c.close(); return jsonify(message='Store saved')

@app.get('/api/addresses')
def get_addresses():
    u,err=login_required()
    if err:return err
    c=db(); rows=c.execute('SELECT * FROM addresses WHERE user_id=? ORDER BY id DESC',(u['id'],)).fetchall(); c.close(); return jsonify(addresses=[dict(r) for r in rows])

@app.post('/api/addresses')
def add_address():
    u,err=login_required()
    if err:return err
    d=request.get_json() or {}; label=str(d.get('label','Home'))[:30]; address=str(d.get('full_address','')).strip()[:300]; phone=str(d.get('phone','')).strip()[:30]; city=str(d.get('city','')).strip()[:60]
    if len(address)<5:return jsonify(error='Enter a complete address'),400
    c=db(); cur=c.execute('INSERT INTO addresses(user_id,label,full_address,phone,city) VALUES(?,?,?,?,?)',(u['id'],label,address,phone,city)); c.commit(); c.close(); return jsonify(message='Address saved',id=cur.lastrowid)

@app.get('/api/orders/<int:oid>/tracking')
def order_tracking(oid):
    u,err=login_required()
    if err:return err
    c=db(); o=c.execute('SELECT buyer_id FROM orders WHERE id=?',(oid,)).fetchone();
    if not o: c.close(); return jsonify(error='Order not found'),404
    owns_order = o['buyer_id']==u['id'] or c.execute('SELECT 1 FROM order_items WHERE order_id=? AND seller_id=?',(oid,u['id'])).fetchone()
    if not owns_order: c.close(); return jsonify(error='Order not found'),404
    rows=c.execute('SELECT * FROM order_tracking WHERE order_id=? ORDER BY id',(oid,)).fetchall(); c.close(); return jsonify(tracking=[dict(r) for r in rows])

@app.post('/api/orders/<int:oid>/tracking')
def add_tracking(oid):
    u,err=login_required('seller')
    if err:return err
    d=request.get_json() or {}; status=str(d.get('status','Processing'))[:50]; note=str(d.get('note',''))[:300]
    c=db(); owns=c.execute('SELECT 1 FROM order_items WHERE order_id=? AND seller_id=?',(oid,u['id'])).fetchone()
    if not owns: c.close(); return jsonify(error='Order not found.'),404
    c.execute('INSERT INTO order_tracking(order_id,status,note) VALUES(?,?,?)',(oid,status,note)); c.commit(); c.close(); return jsonify(message='Tracking updated')

if __name__ == '__main__':
 init_db(); app.run(host=os.environ.get('CAMPUS_HOST','0.0.0.0'), port=int(os.environ.get('CAMPUS_PORT','5000')), debug=os.environ.get('FLASK_DEBUG','1')=='1')
