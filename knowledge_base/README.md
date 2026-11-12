# DOMO AI bilim bazasi — 2-bosqich

Bu papka siz o‘qiy oladigan kontekst va tasdiqlangan FAQ matnlarini saqlaydi. Haqiqiy mijoz hisoblari yoki shaxsiy ma’lumotlar yo‘q. Hujjatlar DEMO deb belgilangan; rasmiy xavfsizlik tavsiyalarining manbalari alohida ko‘rsatilgan.

## Qaysi faylni ochaman?

| Fayl | Vazifasi |
|---|---|
| `faq.json` | Tasdiqlangan 5 savolning bot yuboradigan qisqa javoblari. |
| `support.json` | Elektr, gaz, suv, isitish javoblari; A–D xavfsizlik matnlari; raqamlar va navigatsiya. |
| `index.json` | Bilim hujjatlari va rasmiy manbalar ro‘yxati. |
| `electricity/*.md` | Elektr balansi, uzilish va sim xavfi. |
| `gas/*.md` | Gaz ta’minoti va gaz sizishi. |
| `water/*.md` | Suv ta’minoti va suv-elektr xavfi. |
| `heating/*.md` | Markaziy isitish yoki alohida qurilma muammosi. |
| `general/*.md` | To‘lov, to‘lov kechikishi, qarz, yong‘in va DEMO chegaralari. |

`.uz.md` — o‘zbekcha, `.ru.md` — ruscha. 10 ta bilim mavzusining 20 ta til fayli mavjud. Ularni oddiy matn muharririda ko‘rish mumkin.

## FAQ yozuvi

`id` — o‘zgarmaydigan belgi; `category` — xizmat; `question` va `answer` — `uz` / `ru` matnlari; `source_ids` — **bilim hujjatlarining IDlari**; `requires_account_data` — shaxsiy hisob ma’lumoti zarurligi haqidagi belgi, uni olish imkoniyati emas; `status` — `draft` yoki `approved`; `content_type` — `demo_guidance`; `updated_at` — tasdiqlangan yangilanish sanasi.

FAQ 1–4 matnlari foydalanuvchi tomonidan aynan tasdiqlangan. Ularni yangi tasdiqsiz o‘zgartirmang. Sakkizta matn uchun avtomatik o‘zgarmaslik tekshiruvi bor. `draft` yozuvi foydalanuvchiga javob sifatida ko‘rsatilmaydi. Asosiy menyudagi besh savolning har biriga tasdiqlangan javob kerak.

## Manbalar qanday bog‘langan?

`index.json` dagi `sources` tashqi rasmiy manbalarning IDsi, ikki tilli nomi, HTTPS havolasi va qo‘llanish hududini saqlaydi. `documents` esa ikki tilli Markdown fayllari, mavzu va manbalarni bog‘laydi. Hujjatdagi `source_ids` tashqi manbalarga tegishli.

`support.json` dagi javoblarda `document_ids` bilim hujjatlariga, `source_ids` esa rasmiy tashqi manbalarga tegishli. Har bir xavfsizlik javobining o‘z manbalari Telegram’da javobdan keyin ko‘rsatiladi. Manbalarning manzili tarmoq orqali avtomatik tekshirilmaydi; ular foydalanuvchi tasdiqlagan ro‘yxatdan olingan.

CDC faqat umumiy texnik elektr-suv xavfsizligi uchun ishlatiladi. Undagi xorijiy telefon raqamlari olinmagan. 101, 104, 112 va 1154 vazifalari O‘zbekiston manbalariga bog‘langan. 1154 faqat elektr tarmoqlari haqidagi javoblarda ishlatiladi.

## Yangi bilim hujjatini qanday qo‘shaman?

1. Ma’lumotning to‘g‘riligini va manbasini aniqlang. Rasmiy tartib noma’lum bo‘lsa, uni noma’lum deb belgilang; muddat, tarif yoki telefon raqamini taxmin qilmang.
2. Tegishli kategoriya ichida o‘zbekcha va ruscha `.md` fayl yarating. Sarlavha va `DEMO` belgisi bo‘lsin. Rasmiy xavfsizlik qismini umumiy demo ko‘rsatmasidan ajrating.
3. `index.json` dagi `documents` ro‘yxatiga noyob ID, kategoriya, ikki tilli sarlavha va fayl yo‘llarini qo‘shing. Barcha yo‘llar shu papka ichidagi `.md` fayllariga olib borishi kerak.
4. Rasmiy havola bo‘lsa `sources` ga qo‘shing va tegishli hujjatga bog‘lang. Manba mavjud bo‘lmasa soxta havola yaratmang.
5. Yangi FAQ savoli kerak bo‘lsa, ikki tildagi javobni alohida tasdiqlating. Yangi asosiy tugma qo‘shish interfeys o‘zgarishini talab qiladi; faqat hujjat qo‘shish tugma yaratmaydi.
6. Loyiha ildizida `.\.venv\Scripts\python.exe -m app.faq` va `.\.venv\Scripts\python.exe -m pytest -q` ni bajaring.
7. Tekshiruvlar muvaffaqiyatli bo‘lgach, botning yagona nusxasini qayta ishga tushiring. Bot ma’lumotlarni faqat boshlanishida yuklaydi.

## Hozirgi cheklov

Markdown hujjatlari tayyor va tekshiriladi, lekin ulardan erkin matn bo‘yicha semantik qidiruv hali yo‘q. Bot faqat aniq FAQ savoli yoki tugma nomiga mos tayyor javobni tanlaydi. RAG, Groq va vektor bazasi — 3-bosqich. Erkin xabardagi xavfni avtomatik aniqlash — 4-bosqich. Operatorga ulanish — 5-bosqich. Bu bosqichlar hozir boshlanmagan.
