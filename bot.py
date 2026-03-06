import asyncio
import aiohttp
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- НАСТРОЙКИ ---
TOKEN = "8654465825:AAEibW0lW1CHhEpza3cFtzqxatzIjnlT_Fg"
SERPER_API_KEY = "764e054924dc96b2431d3030243dd4f1eb761337"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- ФУНКЦИЯ ПОИСКА ---
async def search_marketplaces(query):
    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    # Ищем только лоты на Grailed и eBay
    adv_query = f"(site:grailed.com/listings/ OR site:ebay.com/itm/) {query} -inurl:forum -inurl:blog"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json={"q": adv_query, "num": 5}, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for item in data.get('organic', []):
                        link = item.get('link', '')
                        if "/listings/" in link or "/itm/" in link:
                            snippet = item.get('snippet', '').lower()
                            title = item.get('title', '')
                            # Ищем цену и размер
                            price = re.search(r'\$\d+(?:[\.,]\d+)?', title + " " + snippet)
                            size = re.search(r'(?:size|sz|us|eu)[:\s]+([a-zA-Z0-9\.\/]+)', (title + " " + snippet).lower())
                            
                            results.append({
                                'title': title, 
                                'link': link, 
                                'image': item.get('imageUrl'),
                                'price': price.group(0) if price else "N/A",
                                'size': size.group(1).upper() if size else "N/A",
                                'source': 'Grailed' if 'grailed.com' in link else 'eBay'
                            })
                    return results
                return []
        except Exception as e:
            logging.error(f"Search error: {e}")
            return []

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ ---

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("🎯 **Снайпер mozge в Termux запущен!**\nПросто напиши название вещи (например: Jordan 1 Retro):")

@dp.message_handler()
async def handle_search(message: types.Message):
    # Игнорируем команды
    if message.text.startswith('/'): return
    
    status = await message.answer(f"🔎 Ищу лоты для: `{message.text}`...")
    results = await search_marketplaces(message.text)
    
    if not results:
        await status.edit_text("📭 Ничего не найдено. Попробуй уточнить модель.")
        return

    await status.delete()
    for res in results:
        source_emoji = "💎" if res['source'] == 'Grailed' else "📦"
        caption = (
            f"{source_emoji} **{res['source']}**\n"
            f"━━━━━━━━━━━━\n"
            f"📌 **Лот:** `{res['title']}`\n"
            f"💰 **Цена:** `{res['price']}`\n"
            f"📏 **Размер:** `{res['size']}`\n"
            f"━━━━━━━━━━━━\n"
            f"🔗 [ОТКРЫТЬ ТОВАР]({res['link']})"
        )
        try:
            if res['image']:
                await message.answer_photo(res['image'], caption=caption, parse_mode="Markdown")
            else:
                await message.answer(caption, parse_mode="Markdown")
        except:
            await message.answer(caption, parse_mode="Markdown")

# --- ЗАПУСК ---
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
