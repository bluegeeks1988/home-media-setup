import os, sqlite3, secrets, time, threading, logging
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse
import requests
from flask import Flask, request, session, redirect, url_for, flash, render_template_string, abort
from werkzeug.security import check_password_hash

app=Flask(__name__)
app.secret_key=os.environ.get('SESSION_SECRET','')
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',SESSION_COOKIE_SECURE=False,MAX_CONTENT_LENGTH=16384)
BASE=os.environ.get('SEERR_URL','http://seerr:5055').rstrip('/')
KEY=os.environ.get('SEERR_API_KEY','')
PASSWORD=os.environ.get('ROLE_MANAGER_PASSWORD','')
DB=os.environ.get('DATABASE_PATH','/data/roles.sqlite')
if not app.secret_key or len(app.secret_key)<32 or not KEY or not PASSWORD or len(PASSWORD)<12:
    raise RuntimeError('Set SEERR_API_KEY, SESSION_SECRET (32+ chars) and ROLE_MANAGER_PASSWORD (12+ chars)')
if not BASE.startswith('http://') and not BASE.startswith('https://'):
    raise RuntimeError('Invalid SEERR_URL')

@contextmanager
def db():
    con=sqlite3.connect(DB,timeout=10)
    con.row_factory=sqlite3.Row
    try:
        yield con
        con.commit()
    finally: con.close()

def initdb():
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS roles(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,permissions INTEGER NOT NULL,movie_limit INTEGER,movie_days INTEGER,tv_limit INTEGER,tv_days INTEGER,updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assignments(user_id INTEGER PRIMARY KEY,role_id INTEGER NOT NULL REFERENCES roles(id));
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,created TEXT NOT NULL,action TEXT NOT NULL,detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observed_users(user_id INTEGER PRIMARY KEY, first_seen TEXT NOT NULL);''')

def get_setting(key,default=''):
    with db() as c:
        row=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return row['value'] if row else default

def put_setting(key,value):
    with db() as c:
        c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(key,str(value)))

def automatic_scan():
    if get_setting('auto_enabled') != '1': return
    role_id=get_setting('default_role')
    if not role_id: return
    with db() as c:
        role=c.execute('SELECT * FROM roles WHERE id=?',(role_id,)).fetchone()
    if role is None: return
    everyone=users()
    for u in everyone:
        uid=int(u['id'])
        with db() as c:
            seen=c.execute('SELECT 1 FROM observed_users WHERE user_id=?',(uid,)).fetchone()
            assigned=c.execute('SELECT 1 FROM assignments WHERE user_id=?',(uid,)).fetchone()
        if seen: continue
        # Mark before network writes, so a failed update never loops endlessly and overwrites later manual changes.
        with db() as c:
            c.execute('INSERT OR IGNORE INTO observed_users(user_id,first_seen) VALUES(?,?)',(uid,datetime.now(timezone.utc).isoformat()))
        if is_protected(u) or assigned:continue
        try:
            sync_user(uid,role,everyone)
            with db() as c:
                c.execute('INSERT OR IGNORE INTO assignments(user_id,role_id) VALUES(?,?)',(uid,int(role_id)))
            audit('auto-assign',f'user {uid} ← {role["name"]}')
        except Exception as e:
            audit('auto-assign-failed',f'user {uid}: {type(e).__name__}: {e}')
            app.logger.warning('Automatic assignment failed for user %s: %s',uid,e)

def scan_loop():
    while True:
        try: automatic_scan()
        except Exception as e:app.logger.warning('Automatic scan failed: %s',e)
        time.sleep(max(60,int(os.environ.get('ROLE_SYNC_POLL_SECONDS','300'))))

def audit(action,detail):
    with db() as c: c.execute('INSERT INTO audit(created,action,detail) VALUES(?,?,?)',(datetime.now(timezone.utc).isoformat(),action,detail[:500]))

def api(method,path,payload=None,params=None):
    r=requests.request(method,BASE+'/api/v1'+path,headers={'X-Api-Key':KEY,'Accept':'application/json'},json=payload,params=params,timeout=15)
    r.raise_for_status()
    return r.json() if r.content else {}

def users():
    out=[]; offset=0
    while True:
        data=api('GET','/user',params={'take':100,'skip':offset})
        batch=data.get('results',[])
        out.extend(batch)
        offset+=len(batch)
        total=data.get('pageInfo',{}).get('results',0)
        if not batch or offset>=total or offset>=10000: break
    return out

def is_protected(u):
    # Never change administrator records: administrator is bit 2 in Seerr; id 1 additionally protected.
    return int(u.get('id',0))==1 or bool(int(u.get('permissions') or 0)&2)

def sync_user(uid,role,known_users=None):
    allusers=known_users if known_users is not None else users()
    target=next((u for u in allusers if int(u['id'])==int(uid)),None)
    if target is None: raise ValueError('User no longer exists in Seerr')
    if is_protected(target): raise ValueError('Administrator account protected: no modifications allowed')
    settings=api('GET',f'/user/{uid}/settings/main')
    # Preserve existing general settings rather than overwriting username, email or preferences.
    for key,value in [('movieQuotaLimit',role['movie_limit']),('movieQuotaDays',role['movie_days']),('tvQuotaLimit',role['tv_limit']),('tvQuotaDays',role['tv_days'])]:
        settings[key]=value
    allowed=['username','email','locale','discoverRegion','streamingRegion','originalLanguage','movieQuotaLimit','movieQuotaDays','tvQuotaLimit','tvQuotaDays','watchlistSyncMovies','watchlistSyncTv']
    body={k:settings.get(k) for k in allowed if k in settings}
    # Permissions first. Individual failures recorded, not silently ignored.
    api('POST',f'/user/{uid}/settings/permissions',{'permissions':int(role['permissions'])})
    api('POST',f'/user/{uid}/settings/main',body)
    audit('sync',f'user {uid} ← {role["name"]}')

def loggedin(f):
    @wraps(f)
    def wrapped(*a,**kw):
        if not session.get('auth'):return redirect(url_for('login'))
        return f(*a,**kw)
    return wrapped

@app.before_request
def csrf():
    if request.method=='POST' and request.endpoint!='login':
        if not session.get('auth') or not secrets.compare_digest(request.form.get('csrf',''),session.get('csrf','')): abort(403)

STYLE='''<style>body{font-family:Inter,system-ui,Arial;background:#0e1424;color:#e7e9f3;margin:0}.wrap{max-width:1100px;margin:35px auto;padding:0 20px}nav{display:flex;gap:20px;align-items:center;margin-bottom:30px}a{color:#b6a2ff;text-decoration:none}h1{font-size:28px}h2{font-size:20px}.card{background:#1b2538;border:1px solid #344057;border-radius:14px;padding:20px;margin:18px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:15px}input,select{background:#10192a;color:white;border:1px solid #4b5870;border-radius:7px;padding:10px;max-width:100%;box-sizing:border-box}input[type=number]{width:100px}label{display:block;font-size:13px;color:#b8c2d8;margin:10px 0 4px}button,.btn{background:#7853e9;color:white;border:0;padding:10px 15px;border-radius:8px;cursor:pointer;font-size:14px}.danger{background:#a5354d}.muted{color:#a4b0c5;font-size:13px}table{width:100%;border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #344057;text-align:left}form.inline{display:inline}.msg{padding:12px;background:#263753;border-radius:6px;margin:8px 0}.small{font-size:12px}.actions{display:flex;gap:12px;flex-wrap:wrap}.perm-group{border:1px solid #344057;border-radius:9px;margin:17px 0;padding:12px}.perm-group legend{font-weight:700;color:#d0baff}.perm-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:6px 14px}.perm{display:flex;align-items:center;gap:8px;margin:5px 0;color:#eee}.perm input{accent-color:#7853e9}.perm input:disabled{opacity:.4}</style>'''
SHELL='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Seerr Role Manager</title>'''+STYLE+'''</head><body><main class="wrap"><nav><b>◉ Seerr Role Manager</b>{% if session.get('auth') %}<a href="/">Dashboard</a><a href="/roles/new">Create role</a><a href="/settings">Automation</a><a href="/audit">Audit log</a><form class="inline" method="post" action="/logout"><input type="hidden" name="csrf" value="{{csrf}}"><button>Log out</button></form>{% endif %}</nav>{% for msg in get_flashed_messages() %}<div class="msg">{{msg}}</div>{% endfor %}{{ content|safe }}</main></body></html>'''
def page(inner,**vars):
    content=render_template_string(inner,csrf=session.get('csrf',''),**vars)
    return render_template_string(SHELL,content=content,csrf=session.get('csrf',''))

@app.get('/health')
def health():return {'ok':True}
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        supplied=request.form.get('password','')
        valid=check_password_hash(PASSWORD,supplied) if PASSWORD.startswith(('scrypt:','pbkdf2:')) else secrets.compare_digest(PASSWORD,supplied)
        if valid:
            session.clear();session['auth']=True;session['csrf']=secrets.token_urlsafe(24)
            return redirect('/')
        time.sleep(.4);flash('Invalid password')
    return page('<div class="card"><h1>Administrator login</h1><form method="post"><label>Password</label><input type="password" name="password" required autofocus><button>Sign in</button></form></div>')
@app.post('/logout')
@loggedin
def logout():session.clear();return redirect('/login')

@app.get('/')
@loggedin
def index():
    with db() as c:
        roles=[dict(r) for r in c.execute('SELECT * FROM roles ORDER BY name')]
        assigned={r['user_id']:r['role_id'] for r in c.execute('SELECT * FROM assignments')}
    try: everyone=users(); error=None
    except Exception as e: everyone=[];error=str(e)
    return page('''<h1>Users & roles</h1><p class="muted">Seerr API: {{base}} · Assign a role to synchronise it immediately. Administrators are protected.</p>{% if error %}<div class="msg">Cannot contact Seerr: {{error}}</div>{% endif %}<div class="grid">{% for role in roles %}<div class="card"><h2>{{role.name}}</h2><p class="muted">Movies: {{role.movie_limit if role.movie_limit is not none else 'global'}} / {{role.movie_days if role.movie_days is not none else '—'}} days<br>Series: {{role.tv_limit if role.tv_limit is not none else 'global'}} / {{role.tv_days if role.tv_days is not none else '—'}} days</p><div class="actions"><a href="/roles/{{role.id}}">Edit</a><form class="inline" method="post" action="/roles/{{role.id}}/sync"><input type="hidden" name="csrf" value="{{csrf}}"><button>Sync assigned users</button></form></div></div>{% else %}<div class="card">No roles created yet. Select Create role to configure its permissions.</div>{% endfor %}</div><h2>Seerr users</h2><div class="card"><table><tr><th>Account</th><th>Role</th><th>Action</th></tr>{% for u in everyone %}<tr><td>{{u.username or u.email or u.id}} <span class="muted">#{{u.id}}</span>{% if u.id == 1 or (u.permissions|int) % 4 >= 2 %}<span class="muted"> · Protected admin</span>{% endif %}</td><td>{{role_names.get(assigned.get(u.id),'Not assigned')}}</td><td>{% if u.id != 1 and (u.permissions|int) % 4 < 2 %}<form method="post" action="/assign"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="uid" value="{{u.id}}"><select name="rid"><option value="">No role</option>{% for r in roles %}<option value="{{r.id}}" {% if assigned.get(u.id)==r.id %}selected{% endif %}>{{r.name}}</option>{% endfor %}</select><button>Apply</button></form>{% endif %}</td></tr>{% endfor %}</table></div>''',base=BASE,error=error,roles=roles,everyone=everyone,assigned=assigned,role_names={r['id']:r['name'] for r in roles})

# Permission values verified against Seerr's server/lib/permissions.ts (develop, 2026-10-28).
# The master and child capabilities are separate bits, matching Seerr's editor.
PERMISSION_GROUPS = [
 ('Administration', [('Admin',2),('Manage Users',8),('Manage Requests',16),('Advanced Requests',8192),('View Requests',16384),('View Recently Added',67108864),('View Jellyfin Watchlists',134217728)]),
 ('Requests', [('Request',32),('Request Movies',262144),('Request Series',524288),('Auto-Approve',128),('Auto-Approve Movies',256),('Auto-Approve Series',512),('Auto-Request',8388608),('Auto-Request Movies',16777216),('Auto-Request Series',33554432)]),
 ('4K Requests', [('Request 4K',1024),('Request 4K Movies',2048),('Request 4K Series',4096),('Auto-Approve 4K',32768),('Auto-Approve 4K Movies',65536),('Auto-Approve 4K Series',131072)]),
 ('Issues & Blocklist', [('Manage Issues',1048576),('Report Issues',4194304),('View Issues',2097152),('Manage Blocklist',268435456),('View Blocklisted Media',1073741824)])
]
KNOWN_BITS=sum(value for _,fields in PERMISSION_GROUPS for _,value in fields)
# ADMIN is deliberately prohibited in templates: admin accounts must be managed directly in Seerr.
PROHIBITED_ROLE_BITS=2 | 4  # ADMIN and internal MANAGE_SETTINGS

ROLE_FORM='''<h1>{{'Edit role' if role else 'Create role'}}</h1>
<div class="card"><p class="muted">Configure a reusable permission profile using the same capabilities shown by Seerr. Changes to existing users take effect only when you click Sync assigned users.</p>
<form method="post"><input type="hidden" name="csrf" value="{{csrf}}">
<label>Role name</label><input name="name" maxlength="60" required value="{{role.name if role else ''}}">
<label>Optionally copy permissions from an existing non-admin Seerr user</label>
<select id="source" name="source"><option value="">Use the checkboxes below</option>{% for u in everyone if u.id != 1 and (u.permissions|int) % 4 < 2 %}<option value="{{u.id}}" data-permissions="{{u.permissions}}">{{u.username or u.email or u.id}} (#{{u.id}})</option>{% endfor %}</select>
<p class="muted">Selecting a user fills the permission checkboxes. You can then customise them. Administrator permissions cannot be assigned through role templates.</p>
{% for group, fields in groups %}<fieldset class="perm-group"><legend>{{group}}</legend><div class="perm-grid">
{% for label, bit in fields %}<label class="perm"><input class="perm-checkbox" type="checkbox" name="permission" value="{{bit}}" {% if (selected_bits|int) // bit % 2 == 1 %}checked{% endif %} {% if bit == 2 %}disabled title="Administrator permission cannot be assigned using a role template"{% endif %}><span>{{label}}</span></label>{% endfor %}
</div></fieldset>{% endfor %}
<div class="grid"><div><label>Movies allowed (blank = Seerr global quota)</label><input name="ml" type="number" min="0" value="{{role.movie_limit if role and role.movie_limit is not none else ''}}"><label>Movie quota days</label><input name="md" type="number" min="1" value="{{role.movie_days if role and role.movie_days is not none else ''}}"></div><div><label>TV seasons allowed (blank = Seerr global quota)</label><input name="tl" type="number" min="0" value="{{role.tv_limit if role and role.tv_limit is not none else ''}}"><label>TV quota days</label><input name="td" type="number" min="1" value="{{role.tv_days if role and role.tv_days is not none else ''}}"></div></div>
<p><button>Save role</button></p></form></div>
<script>const source=document.getElementById('source');source?.addEventListener('change',()=>{if(!source.value)return;const value=Number(source.selectedOptions[0].dataset.permissions||0);document.querySelectorAll('.perm-checkbox').forEach(el=>{if(!el.disabled)el.checked=(value & Number(el.value))!==0})});</script>'''
@app.route('/roles/new',methods=['GET','POST'])
@app.route('/roles/<int:rid>',methods=['GET','POST'])
@loggedin
def role_form(rid=None):
    with db() as c:
        old=c.execute('SELECT * FROM roles WHERE id=?',(rid,)).fetchone() if rid else None
    if rid and old is None:abort(404)
    if request.method=='POST':
        try:
            name=request.form['name'].strip()
            if not name or len(name)>60:raise ValueError('Invalid role name')
            def quota(k,d):
                value=request.form.get(k,'').strip();days=request.form.get(d,'').strip()
                if bool(value)!=bool(days):raise ValueError('Both quota limit and days must be set together')
                if not value:return None,None
                n,period=int(value),int(days)
                if not (0<=n<=100000 and 1<=period<=365):raise ValueError('Invalid quota range')
                return n,period
            ml,md=quota('ml','md');tl,td=quota('tl','td')
            permissions=0
            for raw in request.form.getlist('permission'):
                bit=int(raw)
                if bit<=0 or not (KNOWN_BITS & bit) or (bit & (bit-1)) !=0:raise ValueError('Unknown permission value')
                permissions|=bit
            if permissions & PROHIBITED_ROLE_BITS:raise ValueError('Administrator privileges cannot be assigned by a role template')
            # Preserve any forward-compatible bits already stored in the role, but never silently grant unknown bits on new roles.
            if old:permissions |= (int(old['permissions']) & ~KNOWN_BITS & ~PROHIBITED_ROLE_BITS)
            with db() as c:
                if rid:c.execute('UPDATE roles SET name=?,permissions=?,movie_limit=?,movie_days=?,tv_limit=?,tv_days=?,updated=? WHERE id=?',(name,permissions,ml,md,tl,td,datetime.now(timezone.utc).isoformat(),rid))
                else:c.execute('INSERT INTO roles(name,permissions,movie_limit,movie_days,tv_limit,tv_days,updated) VALUES(?,?,?,?,?,?,?)',(name,permissions,ml,md,tl,td,datetime.now(timezone.utc).isoformat()))
            audit('role-save',name);flash('Role saved. Click Sync assigned users to apply updated permissions to existing assignments.')
            return redirect('/')
        except Exception as e:flash('Could not save role: '+str(e))
    try:everyone=users()
    except Exception as e:everyone=[];flash('Seerr API unavailable: '+str(e))
    selected_bits=int(old['permissions']) if old else 0
    return page(ROLE_FORM,role=dict(old) if old else None,everyone=everyone,groups=PERMISSION_GROUPS,selected_bits=selected_bits)

@app.post('/assign')
@loggedin
def assign():
    try:
        uid=int(request.form['uid']); rid=request.form.get('rid','')
        if not rid:
            with db() as c:c.execute('DELETE FROM assignments WHERE user_id=?',(uid,))
            audit('unassign',str(uid));flash('Assignment removed. Existing Seerr permissions left unchanged.')
        else:
            with db() as c:role=c.execute('SELECT * FROM roles WHERE id=?',(int(rid),)).fetchone()
            if role is None:raise ValueError('Unknown role')
            sync_user(uid,role)
            with db() as c:c.execute('INSERT OR REPLACE INTO assignments(user_id,role_id) VALUES(?,?)',(uid,int(rid)))
            flash('Role applied to Seerr user')
    except Exception as e:flash('Apply failed: '+str(e))
    return redirect('/')

@app.post('/roles/<int:rid>/sync')
@loggedin
def sync_role(rid):
    try:
        with db() as c:
            role=c.execute('SELECT * FROM roles WHERE id=?',(rid,)).fetchone()
            ids=[x['user_id'] for x in c.execute('SELECT user_id FROM assignments WHERE role_id=?',(rid,))]
        if role is None:abort(404)
        everyone=users();ok=0;failed=[]
        for uid in ids:
            try:sync_user(uid,role,everyone);ok+=1
            except Exception as e:failed.append(f'{uid}: {e}')
        flash(f'Synced {ok} users. '+('; '.join(failed[:3]) if failed else ''))
    except Exception as e:flash('Sync failed: '+str(e))
    return redirect('/')

@app.route('/settings',methods=['GET','POST'])
@loggedin
def settings_page():
    if request.method=='POST':
        try:
            enabled=request.form.get('enabled')=='1'
            chosen=request.form.get('default_role','').strip()
            with db() as c:
                role=c.execute('SELECT id FROM roles WHERE id=?',(chosen,)).fetchone() if chosen else None
            if enabled and role is None:raise ValueError('Choose a valid role to enable automatic assignment')
            # Safety baseline: existing users at activation will never be automatically changed.
            if enabled and get_setting('auto_enabled') != '1':
                existing=users()  # Fail closed if API is unavailable.
                with db() as c:
                    for u in existing:
                        c.execute('INSERT OR IGNORE INTO observed_users(user_id,first_seen) VALUES(?,?)',(int(u['id']),datetime.now(timezone.utc).isoformat()))
                audit('automation-baseline',f'Existing users protected: {len(existing)}')
            put_setting('default_role',chosen)
            put_setting('auto_enabled','1' if enabled else '0')
            audit('automation-settings',f'enabled={enabled},role={chosen}')
            flash('Automation settings saved. Existing Seerr users are not modified.')
        except Exception as e:flash('Could not save automation settings: '+str(e))
        return redirect('/settings')
    with db() as c:
        roles=[dict(r) for r in c.execute('SELECT id,name FROM roles ORDER BY name')]
        observed=c.execute('SELECT COUNT(*) FROM observed_users').fetchone()[0]
    return page('''<h1>Automatic default roles</h1><div class="card">
<p>When enabled, the manager checks Seerr for newly created or imported users approximately every five minutes. Only users appearing after activation receive the default role. Existing accounts and administrator accounts are protected.</p>
<form method="post"><input type="hidden" name="csrf" value="{{csrf}}">
<label>Default role for new users</label><select name="default_role"><option value="">Select a role</option>{% for r in roles %}<option value="{{r.id}}" {% if selected==r.id|string %}selected{% endif %}>{{r.name}}</option>{% endfor %}</select>
<label class="perm"><input type="checkbox" name="enabled" value="1" {% if enabled %}checked{% endif %}> Enable automatic assignment</label>
<p class="muted">{{observed}} user IDs have been observed. Previously seen users are never automatically reassigned. Failed automatic assignments appear in Audit log for manual review.</p>
<button>Save automation settings</button></form></div>''',roles=roles,selected=get_setting('default_role'),enabled=get_setting('auto_enabled')=='1',observed=observed)

@app.get('/audit')
@loggedin
def view_audit():
    with db() as c:rows=[dict(x) for x in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]
    return page('''<h1>Recent changes</h1><div class="card"><table><tr><th>Time (UTC)</th><th>Action</th><th>Detail</th></tr>{% for r in rows %}<tr><td>{{r.created}}</td><td>{{r.action}}</td><td>{{r.detail}}</td></tr>{% endfor %}</table></div>''',rows=rows)

initdb()
threading.Thread(target=scan_loop,daemon=True,name="seerr-role-poller").start()
