import asyncio
import aiohttp
import logging
import os
import re
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command
from aiogram.types import URLInputFile
from aiogram.client.default import DefaultBotProperties

# Загружаем переменные (для локального теста из .env, на хостинге из настроек)
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
SERPER_API_KEY = os.getenv("SERPER_KEY")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

if not TOKEN or not SERPER_API_KEY:
    logger.error("КРИТИЧЕСКАЯ ОШИБКА: Токены не найдены в переменных окружения!")
    exit(1)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

async def search_single_site(session, site_url, query, source_name):
    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    payload = {
        "q": f"site:{site_url} {query} -sold -ended",
        "num": 15
    }

    try:
        async with session.post(url, headers=headers, json=payload, timeout=15) as resp:
            if resp.status == 200:
                data = await resp.json()
                organic = data.get('organic', [])
                results = []
                
                dead_markers = ["sold", "sold out", "out of stock", "ended", "no longer available", "продан"]
                
                for item in organic:
                    link = item.get('link', '')
                    title = item.get('title', '')
                    snippet = item.get('snippet', '')
                    full_content = (title + " " + snippet).lower()
                    
                    if any(marker in full_content for marker in dead_markers):
                        continue
                    
                    price = "Цена не указана"
                    price_match = re.search(r'(\$\d+(?:[\.,]\d+)?|\d+\s?USD|£\d+)', title + " " + snippet, re.IGNORECASE)
                    if price_match:
                        price = price_match.group(0)
                        
                    size = "Размер не определен"
                    size_match = re.search(r'(?:size|sz|us|eu|uk)[:\s-]*([a-zA-Z0-9\.\/]+)|\b(XS|S|M|L|XL|XXL)\b', full_content, re.IGNORECASE)
                    if size_match:
                        size = size_match.group(1) if size_match.group(1) else size_match.group(2)
                        size = size.upper()

                    results.append({
                        'title': title,
                        'link': link,
                        'image': item.get('imageUrl'),
                        'price': price,
                        'size': size,
                        'desc': snippet[:130] + "..." if len(snippet) > 130 else snippet,
                        'source': source_name
                    })
                return results
            return []
    except Exception as e:
        logger.error(f"Ошибка поиска на {source_name}: {e}")
        return []

async def search_all_marketplaces(query):
    async with aiohttp.ClientSession() as session:
        tasks = [
            search_single_site(session, "grailed.com/listings/", query, "GRAILED"),
            search_single_site(session, "ebay.com/itm/", query, "EBAY"),
            search_single_site(session, "depop.com/products/", query, "DEPOP")
        ]
        all_results = await asyncio.gather(*tasks)
        combined = []
        for res_list in all_results:
            combined.extend(res_list)
        return combined

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Здравствуйте мой генерал! 🫡\nСистема возвращена в стабильное состояние. Дизайн сообщений обновлен. Жду вашу цель!")

@dp.message(F.text)
async def handle_search(message: types.Message):
    if message.text.startswith('/'): return
    
    status = await message.answer(f"🛰️ **Разведка запущена:** `{message.text}`...")
    results = await search_all_marketplaces(message.text)
    
    if not results:
        await status.edit_text("❌ По вашему запросу живых лотов не найдено.")
        return

    await status.delete()

    for res in results[:10]:
        icon = "💠" if "GRAILED" in res['source'] else "📦" if "EBAY" in res['source'] else "🧧"
        
        card = (
            f"{icon} **ИСТОЧНИК:** `{res['source']}`\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🏷 **НАЗВАНИЕ:**\n`{res['title']}`\n\n"
            f"💰 **ЦЕНА:** `{res['price']}`\n"
            f"📏 **РАЗМЕР:** `{res['size']}`\n"
            f"📝 **ИНФО:** _{res['desc']}_\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🔗 [ОТКРЫТЬ ОБЪЯВЛЕНИЕ]({res['link']})"
        )
        
        try:
            if res.get('image'):
                await message.answer_photo(photo=URLInputFile(res['image']), caption=card)
            else:
                await message.answer(card)
        except Exception:
            await message.answer(card)

async def main():
    logger.info("Штаб запущен. Генерал на связи!")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Штаб свернут.")
