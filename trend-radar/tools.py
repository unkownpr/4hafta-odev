"""Araç (tool) tanımları ve gerçek implementasyonları — ML Trend Radar.

Dört araç:
  - get_hf_trending(kind, sort, limit)   -> Hugging Face Hub API (dış API, okuma)
  - get_github_trending(...)             -> GitHub Search API (dış API, okuma)
  - save_repo(name, url, source, note)   -> SQLite watchlist'e yaz (yazma)
  - list_saved(source)                   -> SQLite watchlist'ten oku (okuma)

Her araç için hem çalıştırılabilir Python fonksiyonu hem de modele verilecek
OpenAI uyumlu JSON şeması (TOOL_SCHEMAS) bulunur. Model yalnızca bu araçlardan
dönen gerçek veriyi kullanır; değer/isim uydurmaz.
"""

from __future__ import annotations

import json  # noqa: F401  (log/debug amaçlı elde tutuyorum)
import os
from datetime import date, timedelta

import requests

from db import get_conn

HF_API = "https://huggingface.co/api"
GITHUB_SEARCH = "https://api.github.com/search/repositories"

# Opsiyonel: token verilirse GitHub rate-limit'i 10/dk -> 30/dk'ya çıkar
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# HF API'de sıralama anahtarları farklı isimlerde -> kullanıcı dostu isimden eşle
_HF_SORT = {
    "trending": "trendingScore",
    "downloads": "downloads",
    "likes": "likes",
}


def get_hf_trending(kind: str = "model", sort: str = "trending", limit: int = 5) -> dict:
    """Hugging Face'te trend olan / en çok indirilen model ya da dataset'leri getirir.

    kind : "model" veya "dataset"
    sort : "trending" (varsayılan), "downloads" veya "likes"
    limit: kaç sonuç dönsün (1-20 arası mantıklı)
    """
    kind = (kind or "model").lower()
    if kind not in ("model", "dataset"):
        return {"error": f"kind 'model' veya 'dataset' olmalı, gelen: {kind!r}"}

    sort_key = _HF_SORT.get((sort or "trending").lower())
    if sort_key is None:
        return {"error": f"sort 'trending', 'downloads' veya 'likes' olmalı, gelen: {sort!r}"}

    endpoint = f"{HF_API}/{'models' if kind == 'model' else 'datasets'}"
    try:
        resp = requests.get(
            endpoint,
            params={"sort": sort_key, "direction": -1, "limit": max(1, min(int(limit), 20))},
            timeout=15,
        )
        # print(resp.url)  # debug
        resp.raise_for_status()
        rows = resp.json()
    except requests.RequestException as exc:
        return {"error": f"HF API isteği başarısız: {exc}"}

    items = []
    for r in rows:
        rid = r.get("id")
        base = "https://huggingface.co/" + ("" if kind == "model" else "datasets/")
        items.append(
            {
                "id": rid,
                "downloads": r.get("downloads", 0),
                "likes": r.get("likes", 0),
                "url": base + rid,
            }
        )
    return {"kind": kind, "sort": sort, "count": len(items), "results": items}


def get_github_trending(
    query: str = "",
    since: str = "",
    until: str = "",
    language: str = "",
    limit: int = 5,
) -> dict:
    """GitHub'da bir tarih aralığında en çok yıldız alan (≈ trend) repoları getirir.

    query   : opsiyonel anahtar kelime (örn. "llm agent")
    since   : YYYY-MM-DD başlangıç (boşsa son 7 gün)
    until   : YYYY-MM-DD bitiş (opsiyonel)
    language: opsiyonel dil filtresi (örn. "python")
    limit   : kaç repo dönsün

    Not: GitHub repolarında "indirilme" metriği yok; trend karşılığı olarak
    yıldız (stars) kullanılıyor.
    """
    if not since:
        since = (date.today() - timedelta(days=7)).isoformat()

    # GitHub search sorgusu: created:BAŞLANGIÇ..BİTİŞ + sort:stars
    if until:
        q_parts = [f"created:{since}..{until}"]
    else:
        q_parts = [f"created:>={since}"]
    if language:
        q_parts.append(f"language:{language}")
    if query:
        q_parts.append(query)
    q = " ".join(q_parts)

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        resp = requests.get(
            GITHUB_SEARCH,
            params={"q": q, "sort": "stars", "order": "desc", "per_page": max(1, min(int(limit), 20))},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # GitHub bazen rate-limit döndürüyor, kullanıcıya iletelim
        return {"error": f"GitHub API isteği başarısız: {exc}"}

    items = []
    for r in data.get("items", []):
        items.append(
            {
                "name": r.get("full_name"),
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language"),
                "description": r.get("description"),
                "url": r.get("html_url"),
            }
        )
    return {"query": q, "count": len(items), "results": items}


def save_repo(name: str, url: str = "", source: str = "", note: str = "") -> dict:
    """Bir model/dataset/repo'yu kişisel takip listesine (SQLite) kaydeder."""
    if not name or not name.strip():
        return {"error": "name parametresi boş olamaz"}

    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO watchlist (name, url, source, note) VALUES (?, ?, ?, ?)",
        (name.strip(), url, source, note),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"saved": True, "id": new_id, "name": name.strip()}


def list_saved(source: str = "") -> dict:
    """Takip listesindeki kayıtları döndürür. source verilirse ('hf'/'github') filtreler."""
    conn = get_conn()
    if source:
        rows = conn.execute(
            "SELECT id, name, url, source, note, added_at FROM watchlist "
            "WHERE source = ? ORDER BY id DESC",
            (source,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, url, source, note, added_at FROM watchlist ORDER BY id DESC"
        ).fetchall()
    conn.close()
    items = [dict(r) for r in rows]
    return {"count": len(items), "results": items}


# ---------------------------------------------------------------------------
# Modele verilecek OpenAI uyumlu tool/function tanımları
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_hf_trending",
            "description": (
                "Hugging Face'te o an trend olan ya da en çok indirilen model / "
                "dataset listesini getirir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["model", "dataset"],
                        "description": "Model mi dataset mi listelensin",
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["trending", "downloads", "likes"],
                        "description": "Sıralama ölçütü (varsayılan: trending)",
                    },
                    "limit": {"type": "integer", "description": "Kaç sonuç (1-20)"},
                },
                "required": ["kind"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_trending",
            "description": (
                "GitHub'da bir tarih aralığında en çok yıldız alan (trend) repoları "
                "getirir. Tarih verilmezse son 7 gün."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Anahtar kelime (opsiyonel)"},
                    "since": {"type": "string", "description": "Başlangıç tarihi YYYY-MM-DD"},
                    "until": {"type": "string", "description": "Bitiş tarihi YYYY-MM-DD (opsiyonel)"},
                    "language": {"type": "string", "description": "Dil filtresi, örn. python"},
                    "limit": {"type": "integer", "description": "Kaç repo (1-20)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_repo",
            "description": "Bir model/dataset/repo'yu kişisel takip listesine kaydeder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Model/dataset id veya repo adı"},
                    "url": {"type": "string", "description": "Bağlantı (opsiyonel)"},
                    "source": {
                        "type": "string",
                        "enum": ["hf", "github"],
                        "description": "Kaynak: hf veya github",
                    },
                    "note": {"type": "string", "description": "Kısa not (opsiyonel)"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_saved",
            "description": "Takip listesine kaydedilmiş öğeleri listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["hf", "github"],
                        "description": "Kaynağa göre filtrele (opsiyonel)",
                    }
                },
                "required": [],
            },
        },
    },
]

# İsim -> fonksiyon eşlemesi
TOOL_REGISTRY = {
    "get_hf_trending": get_hf_trending,
    "get_github_trending": get_github_trending,
    "save_repo": save_repo,
    "list_saved": list_saved,
}


def dispatch(name: str, arguments: dict) -> dict:
    """Model tarafından istenen aracı adıyla çalıştırır."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"bilinmeyen araç: {name}"}
    try:
        return fn(**arguments)
    except TypeError as exc:
        return {"error": f"geçersiz argümanlar: {exc}"}
