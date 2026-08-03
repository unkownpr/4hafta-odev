"""chat_template.jinja dosyasını örnek bir konuşma ile render eden küçük demo.

Amaç: modelin gerçekte göreceği ham metni (ChatML) gözle görmek ve
system / user / assistant / tool rollerinin + tool_call bloklarının
doğru sarmalandığını doğrulamak.

Çalıştır:
    pip install jinja2
    python render_demo.py

transformers ile gerçek bir tokenizer'a bağlamak istersen:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
    tok.chat_template = open("chat_template.jinja", encoding="utf-8").read()
    print(tok.apply_chat_template(messages, tools=TOOLS,
                                  add_generation_prompt=True, tokenize=False))
"""

import os
import json

from jinja2 import Environment, FileSystemLoader

HERE = os.path.dirname(os.path.abspath(__file__))


def load_template():
    # apply_chat_template ile aynı davranış için trim/lstrip açık
    env = Environment(
        loader=FileSystemLoader(HERE),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    # Jinja2'nin yerleşik tojson'ı HTML-escape yapıyor (< > " -> &lt; &#34;).
    # transformers.apply_chat_template escape'siz bir tojson kullanır; aynı
    # davranışı elde etmek için filtreyi düz json.dumps ile değiştiriyoruz.
    env.filters["tojson"] = lambda value, **kw: json.dumps(value, ensure_ascii=False)
    return env.get_template("chat_template.jinja")


# Modele verilecek örnek araç şeması (tool-calling testi için)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_hf_trending",
            "description": "Hugging Face'te o an trend olan model/dataset'leri getirir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["model", "dataset"]},
                    "limit": {"type": "integer"},
                },
                "required": ["kind"],
            },
        },
    }
]

# Uçtan uca örnek konuşma: system -> user -> (assistant tool_call) -> tool -> assistant
MESSAGES = [
    {"role": "system", "content": "Sen ML dünyasındaki güncel trendleri takip eden bir asistansın."},
    {"role": "user", "content": "Bugün Hugging Face'te trend olan 2 modeli söyler misin?"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "type": "function",
                "function": {
                    "name": "get_hf_trending",
                    "arguments": {"kind": "model", "limit": 2},
                },
            }
        ],
    },
    {
        "role": "tool",
        "content": json.dumps(
            [
                {"id": "meta-llama/Llama-3.3-70B-Instruct", "likes": 1893},
                {"id": "Qwen/Qwen2.5-Coder-32B-Instruct", "likes": 1420},
            ],
            ensure_ascii=False,
        ),
    },
    {
        "role": "assistant",
        "content": "Bugün trend olan iki model: meta-llama/Llama-3.3-70B-Instruct ve "
        "Qwen/Qwen2.5-Coder-32B-Instruct.",
    },
]


if __name__ == "__main__":
    template = load_template()
    rendered = template.render(
        messages=MESSAGES, tools=TOOLS, add_generation_prompt=True
    )
    print(rendered)
