# 2-bosqich — FAQ va Knowledge Base hisoboti

Sana: 2026-11-11. Qamrov: faqat 2-bosqich. 3-bosqich boshlanmadi.

## Amalga oshirilgan natija

- Asosiy menyudagi mavjud beshta FAQ tugmasi o‘zbek va rus tillarida tasdiqlangan javoblarni chiqaradi.
- FAQ 1–4 ning matnlari aynan saqlangan. Ularning sakkizta tasdiqlangan matni mustaqil test nusxalari bilan belgima-belgi solishtirildi.
- 5-mavzu elektr, gaz, suv va isitish uchun alohida javoblar beradi.
- A–D xavfsizlik javoblari alohida tugmalar orqali ochiladi: gaz hidi, ochiq sim, yong‘in, suv-elektr xavfi. Har biri tegishli manba havolalarini ko‘rsatadi.
- 101 — yong‘in-qutqaruv, 104 — gaz avariya, 112 — yagona shoshilinch dispetcherlik, 1154 — faqat elektr tarmoqlari bo‘yicha murojaatlar sifatida saqlandi.
- Asosiy menyudagi besh tugma nomi saqlandi; operator barcha menyularda eng pastdagi qatorda qoldi.
- 10 ta bilim mavzusining 20 ta ikki tilli Markdown fayli yaratildi. DEMO matni va manbali xavfsizlik qismi ajratildi.
- Noma’lum savol AI yoki avtomatik xavf tahlili bajarilgandek ko‘rsatilmaydi. Xizmatlar hali ulanmagani tushuntiriladi.

## Yaratilgan ma’lumot fayllari

| Joy | Vazifasi |
|---|---|
| `knowledge_base/faq.json` | Aynan tasdiqlangan 5 FAQ, har biri uz / ru. |
| `knowledge_base/support.json` | 4 xizmat javobi, 4 xavfsizlik javobi, aloqa raqamlari va yordamchi menyu matnlari. |
| `knowledge_base/index.json` | 10 hujjat va 6 tashqi manba ro‘yxati. |
| `knowledge_base/electricity/balance.uz.md`, `.ru.md` | Elektr hisobidagi qoldiq bo‘yicha DEMO yo‘riqnoma. |
| `knowledge_base/electricity/issues.uz.md`, `.ru.md` | Elektr muammosi va ochiq sim xavfi. |
| `knowledge_base/gas/issues.uz.md`, `.ru.md` | Gaz muammosi va gaz sizishi yo‘riqnomasi. |
| `knowledge_base/water/issues.uz.md`, `.ru.md` | Suv muammosi va suv-elektr xavfi. |
| `knowledge_base/heating/issues.uz.md`, `.ru.md` | Isitish muammosi. |
| `knowledge_base/general/payments.uz.md`, `.ru.md` | Elektr, gaz, suv va isitish uchun umumiy to‘lov yo‘riqnomasi. |
| `knowledge_base/general/payment_delay.uz.md`, `.ru.md` | To‘lov ko‘rinmagan holat bo‘yicha yo‘riqnoma. |
| `knowledge_base/general/debt.uz.md`, `.ru.md` | Qarzdorlikni tekshirish bo‘yicha DEMO yo‘riqnoma. |
| `knowledge_base/general/fire_safety.uz.md`, `.ru.md` | Yong‘inda 101 / 112 va xavfsizlik javobi. |
| `knowledge_base/general/demo_scope.uz.md`, `.ru.md` | Demo chegaralari va rasmiy yordamga yo‘naltirish. |
| `knowledge_base/README.md` | Ma’lumotlarni ko‘rish, tekshirish va yangi hujjat qo‘shish tartibi. |

Qo‘shimcha A va B takliflari alohida yangi FAQ sifatida qo‘shilmadi. Tasdiqlanmagan kompaniya nomi, tarif, tiklanish vaqti, to‘lov muddati yoki telefon raqami o‘ylab topilmadi.

## Dasturdagi o‘zgarishlar

- `app/faq/models.py`: Pydantic bilan majburiy ikki til va ma’lumot tuzilmasini tekshirish.
- `app/faq/catalog.py`: fayllarni boshlanishda yuklash, manba / hujjat bog‘lanishlari, takroriy ID, noto‘g‘ri yo‘l va xabar uzunligini tekshirish; aniq FAQ savollarini topish.
- `app/faq/__main__.py`: `.env` va tarmoqqa murojaat qilmaydigan bilim bazasi tekshiruvi.
- `app/faq/__init__.py`: modulning ochiq interfeysi.
- `app/bot/handlers/__init__.py`: vaqtinchalik FAQ javoblari o‘rniga katalogdagi tasdiqlangan javoblarni chiqarish; xizmat / xavfsizlik / asosiy menyu navigatsiyasi.
- `app/bot/keyboards/__init__.py`: xizmat va xavfsizlik klaviaturalari, har birida operator tugmasi oxirgi qatorda.
- `app/bot/factory.py`: katalogni Dispatcher’ga berish va asosiy menyudagi savollar tasdiqlanganini tekshirish.
- `app/bot/texts.py`: salomlashuv, yordam va noma’lum savol javoblarini hozirgi imkoniyatlarga moslash. Bu yerda FAQ 1–4 javoblari qayta yozilmagan.
- `app/main.py`: bilim bazasi xatosini tushunarli ko‘rsatish; katalogni Telegram botini yaratishdan oldin tekshirish; 2-bosqich ishga tushirish yozuvi.
- `tests/conftest.py`, `tests/test_bot.py`, `tests/test_main.py`: mavjud testlarni yangi FAQ xatti-harakatiga moslash.
- `tests/test_faq.py`, `tests/test_faq_bot.py`: ma’lumot yaxlitligi va to‘liq menyu yo‘llari sinovlari.
- `README.md`: yangi imkoniyatlar, bilim bazasi joylashuvi, tekshirish va jonli sinov yo‘riqnomasi.

`.env` va API kalitlari o‘zgartirilmadi. Hech qanday paket o‘rnatilmadi yoki yangilanmadi. Kutubxona ro‘yxatlari o‘zgartirilmadi.

## Haqiqatan bajarilgan testlar

| Tekshiruv nuqtasi | Natija |
|---|---|
| O‘zgarishdan oldingi mavjud testlar | 41 passed in 1.15s |
| Yangi ma’lumotlar va katalog testlari | 34 passed in 1.85s |
| FAQ Telegram handlerlariga ulangandan keyin | 75 passed in 1.80s |
| To‘liq yangi foydalanuvchi yo‘llari qo‘shilgach | 91 passed in 2.67s |
| Yakuniy qayta tekshiruv | **91 passed in 1.63s** |
| `python -m pip check` | **No broken requirements found.** |
| `python -m app.faq` | **5 FAQ, 10 hujjat / 20 til fayli, 4 xavfsizlik javobi; API ishlatilmadi.** |

Testlar haqiqiy aiogram Dispatcher va tarmoqsiz sinov Telegram sessiyasi bilan bajarildi. Til almashtirish, boshqa tildagi eski tugmani tanlash, operatorga kirish, asosiy menyuga qaytish, manba havolalarining javobga qo‘shilishi va xatoliklar tekshirildi. FAQ 1–4 ning aniq matni va gaz jo‘mragi / eshik-deraza shartlari saqlangani tekshirildi. Elektrni o‘chirish uchun suvga kirmaslik va 1154 faqat elektr javobida kelishi ham tekshirildi.

Yetishmagan tarjima, hujjat va manba, qoralama javob, takroriy ID, noto‘g‘ri JSON, papkadan tashqariga chiqadigan fayl yo‘li hamda Telegram uchun ortiqcha uzun javob xavfsiz tarzda aniqlanishi sinaldi.

Bu bosqichdagi bajarilgan testlarda nosozlik topilmadi. Windows asinxron testlari avval aniqlangan mahalliy ulanish cheklovi sabab tegishli ruxsat bilan bajarildi.

## Telegram ish holati

- Ushbu loyiha uchun eski faol bot jarayoni topilmadi; boshqa jarayonlar to‘xtatilmadi.
- Telegram `getMe` tekshiruvi tokenni qabul qildi: `@DomoAI_SupportBot`.
- Webhook faol emasligi tekshirildi.
- Yangilangan bot yashirin fonda ishga tushirildi; jarayon faol va jurnalida `2-bosqich — FAQ` yozuvi borligi kuzatildi. Jarayon IDsi ishga tushirish paytida 15492 edi.
- Kalitlar chiqishga yozilmadi. Groq API chaqirilmadi.
- **Haqiqiy Telegram chatida inson tomonidan barcha tugmalarni bosib tekshirish hali bajarilmagan.** Bu avtomatik sinovlardan alohida tekshiruvdir; README’da ketma-ketligi berilgan.

## Qolayotgan chegaralar

Semantik qidiruv, RAG, Groq, embedding va ChromaDB yo‘q — 3-bosqich boshlanmadi. Erkin xabarda xavfni avtomatik aniqlash yo‘q — bu 4-bosqichga tegishli. Xavfsizlik javoblari faqat aniq menyu savolini tanlash orqali ochiladi. Ticket, operator yozishmasi va AI’ga qaytish oqimi 5-bosqichda qoladi.

Manba IDlari va HTTPS havolalari yaxlitligi tekshirildi; tashqi sahifalar ushbu amalga oshirishda qayta yuklanmadi. Tasdiqlangan manba ro‘yxati saqlandi. Hujjat tahriri qisqa FAQ javobini avtomatik o‘zgartirmaydi; ular alohida tekshirilib, bot qayta ishga tushiriladi.
