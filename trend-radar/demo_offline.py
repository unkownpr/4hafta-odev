"""HF_TOKEN olmadan araçların çalıştığını gösteren küçük offline demo.

LLM çağırmadan, araçları elle sırayla tetikleyip app.py'deki ile aynı
transcript formatını basar. Amaç: tool-call boru hattının (API + SQLite)
uçtan uca çalıştığını görmek / ekran görüntüsü almak.

    python demo_offline.py
"""

import json

from tools import dispatch

# Senaryo: model sırayla şu araç çağrılarını yapmış gibi davran
SCENARIO = [
    ("get_hf_trending", {"kind": "model", "sort": "trending", "limit": 3}),
    ("get_github_trending", {"query": "llm", "since": "2025-07-01", "until": "2025-07-31", "limit": 3}),
    ("save_repo", {"name": "moonshotai/Kimi-K3", "url": "https://huggingface.co/moonshotai/Kimi-K3", "source": "hf", "note": "denenecek"}),
    ("list_saved", {}),
]


def main():
    for turn, (name, args) in enumerate(SCENARIO, start=1):
        arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        result = dispatch(name, args)
        print(f"[Turn {turn}] Araç Çağrısı:")
        print(f"   -> {name}({arg_str})")
        print(f"   <- {json.dumps(result, ensure_ascii=False)[:500]}")
        print()


if __name__ == "__main__":
    main()
