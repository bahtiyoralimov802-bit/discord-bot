import discord
import asyncio
import random
import re
import os
from threading import Thread
from flask import Flask
from groq import AsyncGroq

# --- МИНИ-СЕРВЕР ДЛЯ БЕСПЛАТНОГО ХОСТИНГА RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Tony_Falcon is alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- НАСТРОЙКИ БОТА ---
USER_TOKEN = os.environ.get("USER_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
ALLOWED_CHANNEL_ID = int(os.environ.get("ALLOWED_CHANNEL_ID", "0"))

SYSTEM_PROMPT = (
    "Ты нормальный, сообразительный парень 16 лет в русском Discord-чате. "
    "Общайся живо, развёрнуто и интересно (2-4 предложения в ответе), поддерживай тему, задавай встречные вопросы или шути по делу. "
    "Пиши грамотно по-русски, но расслабленно, с маленькой буквы, как в реальной переписке с друзьями. "
    "Никогда не говори что ты бот или ИИ."
)

client = discord.Client()
groq_client = AsyncGroq(api_key=GROQ_API_KEY)
chat_history = {}
AVAILABLE_MODELS = []

async def load_models():
    global AVAILABLE_MODELS
    try:
        models_list = await groq_client.models.list()
        all_ids = [
            m.id for m in models_list.data
            if "guard" not in m.id.lower() and "whisper" not in m.id.lower() and "tts" not in m.id.lower()
        ]
        priority = ["gpt-oss-120b", "qwen", "70b", "versatile", "llama"]
        sorted_models = []
        for kw in priority:
            for m_id in all_ids:
                if kw in m_id.lower() and m_id not in sorted_models:
                    sorted_models.append(m_id)
        for m_id in all_ids:
            if m_id not in sorted_models:
                sorted_models.append(m_id)

        AVAILABLE_MODELS = sorted_models
        print(f"[+] Основная модель: {AVAILABLE_MODELS}")
    except Exception as e:
        print(f"[!] Ошибка загрузки моделей: {e}")

@client.event
async def on_ready():
    await load_models()
    await client.change_presence(status=discord.Status.online)
    print(f"[+] {client.user} запущен на сервере и готов к общению!")

@client.event
async def on_message(message):
    if message.author.id == client.user.id or message.author.bot:
        return

    if message.channel.id != ALLOWED_CHANNEL_ID or not AVAILABLE_MODELS:
        return

    content = message.content.strip()
    if not content:
        return

    is_mentioned = client.user in message.mentions
    is_reply_to_me = (
        message.reference is not None
        and message.reference.resolved is not None
        and message.reference.resolved.author.id == client.user.id
    )

    if is_mentioned or is_reply_to_me or random.random() < 0.45:
        await asyncio.sleep(random.uniform(1.5, 3.0))
        
        async with message.channel.typing():
            history = chat_history.setdefault(message.channel.id, [])
            clean_text = content.replace(f"<@{client.user.id}>", "").strip()
            history.append({"role": "user", "content": f"{message.author.display_name}: {clean_text}"})
            
            if len(history) > 12:
                history.pop(0)

            bot_reply = None
            for model_name in AVAILABLE_MODELS[:3]:
                try:
                    response = await groq_client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
                        max_tokens=1000,
                        temperature=0.75
                    )
                    raw_text = response.choices.message.content or ""
                    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
                    if cleaned:
                        bot_reply = cleaned.lower()[:1950]  # Страховка от лимита 2000 символов Discord
                        break
                except Exception as e:
                    print(f"[!] Модель {model_name} занята ({e}), пробую запасную...")
                    await asyncio.sleep(0.5)

            if not bot_reply:
                return

            if bot_reply.endswith("."):
                bot_reply = bot_reply[:-1]

            history.append({"role": "assistant", "content": bot_reply})

            typing_delay = min(len(bot_reply) * 0.03, 4.5)
            await asyncio.sleep(typing_delay)

            if is_mentioned or is_reply_to_me or random.random() < 0.65:
                await message.reply(bot_reply, mention_author=True)
            else:
                await message.channel.send(bot_reply)

keep_alive()
client.run(USER_TOKEN)
