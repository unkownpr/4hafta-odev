# 4. Hafta Ödevleri

İki ödev, iki alt klasör.

## 1) `chat-template/` — Custom Chat Template (Jinja2)

Modelin system/user/assistant/tool rollerini ve tool-calling çağrılarını
doğru sarmalayan ChatML tarzı Jinja2 şablonu (`chat_template.jinja`) +
render demosu. Detay: [chat-template/README.md](chat-template/README.md).

## 2) `trend-radar/` — Tool-Calling Destekli Asistan

Hugging Face ve GitHub'daki güncel trendleri canlı çeken, beğenilenleri
SQLite takip listesine kaydeden tool-calling asistanı (Gradio + HF Inference
API). Detay: [trend-radar/README.md](trend-radar/README.md).

İki ödev tematik olarak bağlı: chat-template'teki tool-calling formatı,
trend-radar asistanının kullandığı tool-call yapısının aynısı.
