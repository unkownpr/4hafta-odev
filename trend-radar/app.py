"""ML Trend Radar — Tool Calling asistanı (Gradio + HF Inference API).

Model, kullanıcı sorusuna göre araçları kendisi seçip tetikler:
  - Hugging Face'te trend/en çok indirilen model & dataset'leri çeker,
  - GitHub'da tarih aralığına göre trend (en çok yıldızlı) repoları çeker,
  - beğendiklerini SQLite'taki kişisel takip listesine kaydeder / listeler.

Tüm sayısal veriler ve isimler araçlardan gelir; model kendisi uydurmaz.

Çalıştırmak için ortam değişkeni (HF Space secret) gerekir:
    HF_TOKEN     -> Hugging Face erişim token'ı (Inference Providers için)
İsteğe bağlı:
    MODEL        -> tool-calling destekli model (varsayılan: Qwen/Qwen2.5-72B-Instruct)
    GITHUB_TOKEN -> GitHub rate-limit'i yükseltmek için (opsiyonel)
"""

from __future__ import annotations

import json
import os

import gradio as gr
from huggingface_hub import InferenceClient

from tools import TOOL_SCHEMAS, dispatch

MODEL = os.environ.get("MODEL", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
MAX_TURNS = 6  # sonsuz araç döngüsüne karşı güvenlik sınırı

SYSTEM_PROMPT = (
    "Sen yapay zeka/ML dünyasındaki güncel trendleri takip eden bir asistansın. "
    "Kullanıcının sorularını YALNIZCA sana verilen araçlardan dönen gerçek veriyle "
    "yanıtla. Trend model/dataset veya repo listesi istendiğinde ilgili aracı çağır; "
    "asla ezberden model, repo adı, indirme sayısı veya yıldız sayısı UYDURMA. "
    "Kullanıcı bir şeyi kaydetmek isterse save_repo, kayıtlarını görmek isterse "
    "list_saved aracını kullan. Araçlardan veri gelmezse bunu dürüstçe söyle. "
    "Yanıtlarını Türkçe, kısa ve net ver."
)


def _client() -> InferenceClient:
    # provider="auto" -> HF, modeli destekleyen uygun sağlayıcıya yönlendirir
    return InferenceClient(provider="auto", api_key=HF_TOKEN)


def _fmt_args(args: dict) -> str:
    """Araç argümanlarını get_hf_trending(kind='model') gibi okunur yazar."""
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def _history_to_messages(history: list) -> list:
    """Gradio geçmişini (messages formatı) API mesajlarına çevirir."""
    msgs = []
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            msgs.append({"role": role, "content": content})
    return msgs


def respond(message: str, history: list):
    """Agentic döngü: model araç çağırır -> çalıştır -> geri besle -> nihai yanıt.

    Her adımda araç çağrı dökümünü (transcript) yield ederek kullanıcıya canlı
    olarak gösterir; böylece arka planda hangi tool-call'ların tetiklendiği net.
    """
    if not HF_TOKEN:
        yield (
            "⚠️ **HF_TOKEN bulunamadı.** Hugging Face Space ayarlarından "
            "*Settings → Variables and secrets* bölümüne `HF_TOKEN` ekleyin "
            "(huggingface.co/settings/tokens adresinden alınır)."
        )
        return

    client = _client()
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + _history_to_messages(history)
        + [{"role": "user", "content": message}]
    )

    transcript = ""
    for turn in range(1, MAX_TURNS + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001 - kullanıcıya hatayı göster
            yield transcript + f"\n\n❌ Model çağrısı başarısız: `{exc}`"
            return

        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)

        if not tool_calls:
            # Araç çağrısı yok -> nihai yanıt
            transcript += f"**[Turn {turn}] Nihai Yanıt:**\n\n{msg.content or ''}"
            yield transcript
            return

        # Asistanın tool_call mesajını geçmişe ekle (API şeması gereği)
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        transcript += f"**[Turn {turn}] Araç Çağrıları:**\n\n```\n"
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch(name, args)
            transcript += f"   -> {name}({_fmt_args(args)})\n"
            transcript += f"   <- {json.dumps(result, ensure_ascii=False)[:400]}\n"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        transcript += "```\n\n"
        yield transcript + "_düşünüyor..._"

    # Güvenlik sınırına ulaşıldı
    yield transcript + "\n⚠️ Maksimum tur sınırına ulaşıldı."


_chat_kwargs = dict(
    fn=respond,
    title="📡 ML Trend Radar — Tool Calling Asistanı",
    description=(
        "Hugging Face ve GitHub'daki güncel trendleri **canlı** çeken, "
        "beğendiklerini kişisel takip listesine kaydeden asistan. Model, "
        "sorunuza göre **get_hf_trending / get_github_trending / save_repo / "
        "list_saved** araçlarını kendisi tetikler; arka plandaki tool-call'lar "
        "yanıtla birlikte gösterilir."
    ),
    examples=[
        "Bugün Hugging Face'te trend olan 5 modeli listeler misin?",
        "Temmuz 2025'te GitHub'da en çok yıldız alan LLM repoları neler?",
        "En çok indirilen 3 dataset'i göster ve ilkini takip listeme ekle.",
        "Takip listemde neler var?",
    ],
)

# Gradio <6 varsayılanı 'tuples' -> messages formatını zorlamak için type gerekir.
# Gradio 6+ 'type' argümanını kaldırdı (messages zaten varsayılan). Her iki
# sürümde de çalışması için argümanı koşullu geçiyoruz.
try:
    demo = gr.ChatInterface(type="messages", **_chat_kwargs)
except TypeError:
    demo = gr.ChatInterface(**_chat_kwargs)


if __name__ == "__main__":
    # Render/bulut ortamları PORT env'i verir; yereldeyken 7860.
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
