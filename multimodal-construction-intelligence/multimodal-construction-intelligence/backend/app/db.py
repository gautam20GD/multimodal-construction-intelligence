import sqlite3, json
from pathlib import Path
from datetime import datetime, timezone
from .config import get_settings

def connect():
    p=Path(get_settings().database_path)
    if not p.is_absolute(): p=Path(__file__).resolve().parent.parent/p
    p.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(p); c.row_factory=sqlite3.Row; return c

def init_db():
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS analyses(
          id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT, title TEXT, summary TEXT,
          risk_level TEXT, payload TEXT, created_at TEXT)''')

def save(mode,data):
    now=datetime.now(timezone.utc).isoformat()
    with connect() as c:
        cur=c.execute("INSERT INTO analyses(mode,title,summary,risk_level,payload,created_at) VALUES(?,?,?,?,?,?)",
          (mode,data["title"],data["summary"],data["risk_level"],json.dumps(data),now))
        return cur.lastrowid,now

def listing(limit=40):
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT id,mode,title,summary,risk_level,created_at FROM analyses ORDER BY id DESC LIMIT ?",(limit,))]

def get(aid):
    with connect() as c: r=c.execute("SELECT * FROM analyses WHERE id=?",(aid,)).fetchone()
    if not r: return None
    d=json.loads(r["payload"]); d.update(analysis_id=r["id"],created_at=r["created_at"]); return d
