# 1-bosqich hisoboti

Sana: 2026-11-10. Muhit: Windows, Python 3.12.7, 64-bit.

## Natija

1-bosqichning dasturiy asosi yaratildi va avtomatik testlardan o‘tdi. Haqiqiy Telegram chatidagi sinov token kiritilgandan keyin bajarilishi kerak. 2–7-bosqichlar boshlanmadi.

## Yaratilgan fayllar va vazifalari

| Fayl yoki papka | Vazifasi |
|---|---|
| `app/main.py` | Ishga tushirish, `/start`, `/help`, `/language` buyruqlarini Telegram menyusiga kiritish, tarmoqsiz sozlama tekshiruvi, xatolik va to‘xtatish. |
| `app/config.py` | `.env` ni o‘qish, Pydantic orqali token formati, jurnal darajasi va so‘rov vaqtini tekshirish; xatolarda qiymatlarni yashirish. |
| `app/logging_config.py` | Konsol jurnali, tokenlarni yashirish, foydalanuvchi matni tushishi mumkin bo‘lgan tashqi kutubxona xabarlarini chiqarib tashlash. |
| `app/bot/factory.py` | Bot, Dispatcher, vaqtinchalik til xotirasi va bir foydalanuvchi xabarlarini ketma-ket ishlash sozlamalari. |
| `app/bot/texts.py` | O‘zbekcha va ruscha interfeys matnlari. |
| `app/bot/handlers/__init__.py` | Boshlash, yordam, til tanlash/almashtirish, menyu va kutilmagan xabarlarga javob. |
| `app/bot/keyboards/__init__.py` | Doimiy menyu va til tanlash klaviaturasi; operator har doim eng pastdagi qatorda. |
| `app/__init__.py`, `app/bot/__init__.py` | Python paketlarini belgilash. |
| `.env.example` | Sirlar bo‘lmagan namuna va keyingi bosqichlar uchun sozlama nomlari. |
| `.env` | Mahalliy namuna nusxasi; haqiqiy token kiritilmagan. |
| `.gitignore` | Sirlar, virtual muhit, kesh va mahalliy ma’lumotlarni Git’dan chiqarish qoidalari. |
| `requirements.txt`, `requirements-dev.txt` | Tekshirilgan asosiy va test kutubxonalari versiyalari. |
| `requirements-lock.txt` | O‘rnatilgan barcha loyiha paketlarining aniq versiyalari; global Python o‘zgartirilmagan. |
| `pytest.ini`, `tests/` | Sozlama, jurnal, buyruq, til, menyu, xatolik va ishga tushirish testlari. |
| `README.md` | O‘zbekcha tushuntirish, PowerShell buyruqlari, BotFather va mahalliy sozlash ko‘rsatmalari. |

`.venv` yaratildi, paketlar shu muhitga o‘rnatildi. Git repozitori yaratilmadi. Groq, embedding modeli, ChromaDB va ma’lumotlar bazasi qo‘shilmadi.

## Haqiqatan bajarilgan tekshiruvlar

1. Sozlama va jurnal o‘zgarishlaridan so‘ng: **12 ta test o‘tdi**.
2. Bot handlerlari qo‘shilgandan so‘ng: **41 ta test o‘tdi**.
3. Versiyalar, mahalliy `.env` va qo‘llanma tayyorlangandan so‘ng yakuniy qayta tekshiruv: **41 passed in 0.61s**.
4. `python -m pip check`: **No broken requirements found.**
5. Haqiqiy token kiritilmagan holatda `python -m app.main --check-config`: `BOT_TOKEN kiritilmagan` degan tushunarli xabar chiqdi. Bu kutilgan natija; dastur ichida qaytish kodi 2.
6. Alohida jarayonda sintetik token bilan `--check-config`: format to‘g‘ri ekanini va token Telegram orqali tekshirilmaganini bildirdi; chiqish kodi 0. Telegram’ga so‘rov yuborilmadi.

Testlar haqiqiy aiogram Dispatcher va soxta Telegram sessiyasi bilan bajarildi. Ikkala til, foydalanuvchilar tilining ajratilishi, tilni qayta almashtirish, menyu joylashuvi, xabarni qaytarib ko‘rsatmaslik, matn bo‘lmagan xabarlar, guruh xabarlarini e’tiborsiz qoldirish, Telegram so‘rov xatolari va resurslarni yopish tekshirildi.

## Uchragan muammolar va yechimlar

- Virtual muhitning birinchi yaratilishi vaqtinchalik papkaga yozish rad etilgani sabab tugamadi. `ensurepip` xatosi tekshirildi, vaqtinchalik papka loyiha ichiga yo‘naltirildi va virtual muhit muvaffaqiyatli yaratildi.
- Paketlar birinchi urinishda tarmoq nomini aniqlash xatosi sabab yuklanmadi. Tarmoq ruxsati bilan qayta o‘rnatish muvaffaqiyatli bo‘ldi.
- Cheklangan muhitda asinxron testlar Windows mahalliy ulanishini yaratishda kutib qoldi. Diagnostika bot handleri hali ishga tushmaganini ko‘rsatdi. O‘sha kod tegishli ruxsat bilan qayta tekshirildi va barcha testlar o‘tdi. Kutib qolgan tekshiruv jarayonlari to‘xtatildi.

## Qolgan cheklovlar

- Haqiqiy BotFather tokeni yo‘q: Telegram autentifikatsiyasi, haqiqiy klaviatura ko‘rinishi va jonli polling tekshirilmagan. README’da qo‘lda tekshirish ketma-ketligi bor.
- Til bot ishlayotgan vaqt davomida xotirada saqlanadi; qayta ishga tushirishda yo‘qoladi.
- FAQ va operator tugmalari faqat hali ulanmagan xizmat haqida xabar beradi. Ticket yaratilmaydi, hech kimga operator xabari yuborilmaydi, LLM javobi berilmaydi.
- Operator suhbatini tugatib AI’ga qaytish talabi qayd etildi. Amalga oshirish 5-bosqichga tegishli.

Keyingi bosqich faqat loyiha egasining alohida tasdig‘idan so‘ng boshlanadi.
