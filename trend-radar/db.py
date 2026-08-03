"""SQLite bağlantısı ve şema.

Tek tablo: `watchlist` — kullanıcının kaydettiği HF modeli/dataset'i veya
GitHub reposu (kişisel "takip listesi"). Uygulama açılışında tablo otomatik
oluşturulur.
"""

import os
import sqlite3

DB_PATH = os.environ.get(
    "DB_PATH", os.path.join(os.path.dirname(__file__), "watchlist.db")
)


def get_conn():
    """Row'lara sütun adıyla erişebilmek için row_factory ayarlı bağlantı."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            url      TEXT,
            source   TEXT,          -- 'hf' | 'github'
            note     TEXT,
            added_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.commit()
    conn.close()


# modül import edilir edilmez tabloyu hazırla
init_db()
