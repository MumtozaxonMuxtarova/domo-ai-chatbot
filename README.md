# DOMO AI — Telegram yordamchi (DEMO)

Kommunal xizmatlar bo‘yicha yordamchi bot prototipi. Hozir **1-bosqich — loyiha asosi va 2-bosqich — FAQ / Knowledge Base** amalga oshirilgan. Haqiqiy mijoz bazasi, hisob, qarz yoki to‘lov tizimiga ulanish yo‘q.

## Hozir nimalar ishlaydi?

- `/start`: birinchi kirishda o‘zbek yoki rus tilini tanlash; keyingi kirishda menyu.
- `/language`: tilni istalgan payt almashtirish.
- `/help`: tanlangan tilda ko‘rsatma.
- Doimiy Telegram menyusi: FAQ bo‘limlari, til, yordam va eng pastda operator tugmasi.
- Tasdiqlangan 5 ta FAQ javobi o‘zbek va rus tillarida. FAQ 1–4 ning tasdiqlangan matnlari aynan saqlangan.
- Kommunal muammolar bo‘limida elektr, gaz, suv va isitish uchun alohida tayyor javoblar.
- Alohida tugmalar orqali gaz sizishi, ochiq sim, yong‘in va suv-elektr xavfi bo‘yicha manbali yo‘riqnomalar.
- 10 ta bilim mavzusi, har biri o‘zbekcha va ruscha: jami 20 ta o‘qiladigan Markdown fayli.
- Erkin matn, noma’lum buyruq va matn bo‘lmagan xabarlar uchun tushunarli javob.
- `.env` sozlamalarini tekshirish, so‘rov vaqti chegarasi va sirlarni yashiradigan konsol jurnali.
- Telegram’ga ulanmasdan bajariladigan avtomatik testlar.

**Javoblar tayyor FAQ ma’lumotlaridan olinadi.** Erkin matn uchun AI, RAG va xavfni avtomatik aniqlash hali ulanmagan. Operator tugmasi xizmat hali ulanmaganini aytadi: murojaat yaratmaydi va hech kimga xabar yubormaydi. Xavfsizlik matnlari menyudan tanlanadi; bu avtomatik risk detektori degani emas.

Til aiogram’ning `MemoryStorage` xotirasida saqlanadi. Har bir foydalanuvchi o‘z tilini tanlaydi. Bot qayta ishga tushirilsa, tanlov qayta qilinadi. Bu bosqichda ma’lumotlar bazasi va xabarlar tarixi yaratilmaydi.

## Texnologiyalar va tuzilma

Python 3.11+, aiogram 3, Pydantic 2, python-dotenv, Python logging, pytest va pytest-asyncio ishlatiladi. Joriy o‘rnatish Python 3.12.7 (Windows, 64-bit) bilan tekshirilgan. Kutubxonalarning tekshirilgan asosiy versiyalari `requirements` fayllarida belgilangan; barcha o‘rnatilgan bog‘liqliklar `requirements-lock.txt` faylida qayd etiladi.

```text
app/
  main.py                  Ishga tushirish, buyruqlarni ro‘yxatlash, to‘xtatish
  config.py                .env o‘qish va sozlamalarni xavfsiz tekshirish
  logging_config.py        Xabar matni va sirlarni jurnalga chiqarmaslik
  bot/
    factory.py             Bot va Dispatcher yaratish
    texts.py               O‘zbekcha va ruscha matnlar
    handlers/__init__.py   Buyruq, til, menyu va xatolik javoblari
    keyboards/__init__.py  Doimiy menyu va til klaviaturalari
  faq/
    models.py             Ikki tilli ma’lumotlar tuzilmasi
    catalog.py            FAQ va Markdown hujjatlarini tekshirish / yuklash
    __main__.py           Bilim bazasini tarmoqsiz tekshirish
knowledge_base/
  faq.json                Tasdiqlangan 5 savol-javob; FAQ 1–4 matni o‘zgarmaydi
  support.json            4 xizmat, 4 xavfsizlik javobi va aloqa raqamlari
  index.json              Hujjatlar va tasdiqlangan manbalar ro‘yxati
  electricity/            Balans, elektr muammosi va sim xavfi (uz / ru)
  gas/                    Gaz muammosi va sizish xavfi (uz / ru)
  water/                  Suv muammosi va elektr xavfi (uz / ru)
  heating/                Isitish muammosi (uz / ru)
  general/                To‘lov, qarz, yong‘in va DEMO chegaralari (uz / ru)
  README.md               Bilim ma’lumotlarini ko‘rish va qo‘shish tartibi
tests/
  conftest.py              Haqiqiy tarmoq o‘rniga sinov Telegram sessiyasi
  test_config.py           Sozlamalar va xatoliklarda sirlarni yashirish
  test_logging.py          Jurnal xavfsizligi
  test_bot.py              Haqiqiy Dispatcher orqali xabar yo‘naltirish
  test_main.py             Ishga tushirish, xatolik va resurslarni yopish
  test_faq.py              Tasdiqlangan matn, manba va hujjat yaxlitligi
  test_faq_bot.py          FAQ / xizmat / xavfsizlik menyularining to‘liq yo‘li
.env.example               Sirlar bo‘lmagan sozlama namunasi
requirements.txt           Bot uchun asosiy kutubxonalar
requirements-dev.txt       Asosiy kutubxonalar va test vositalari
requirements-lock.txt      Tekshirilgan muhitning aniq paket versiyalari
```

Hozirgi oqim: `Telegram → Dispatcher → til/xabar handleri → tasdiqlangan FAQ javobi → Telegram`. Bilim fayllari bot boshlanishida tekshiriladi va xotiraga yuklanadi; har xabarda disk o‘qilmaydi. Telegram long polling ishlatiladi, alohida veb-server kerak emas. Bir foydalanuvchining xabarlari ketma-ket ishlanadi. LLM, embedding, ChromaDB va semantik qidiruv ishlatilmaydi. Yangi paket o‘rnatilmagan.

## Windows / PowerShell orqali tayyorlash

PowerShell’ni loyiha papkasida oching:

```powershell
Set-Location 'D:\WORK\example10.11.2026\Domo AI chat bot'
python --version
```

Yangi o‘rnatishda virtual muhit yarating. Bu papkada `.venv` allaqachon mavjud bo‘lsa, qayta yaratish shart emas:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

`requirements-lock.txt` test vositalarini ham o‘rnatadi. Faqat bot uchun `requirements.txt`, ishlab chiqish uchun `requirements-dev.txt` ishlatilishi mumkin. Har safar `.venv\Scripts\python.exe` yo‘lidan foydalanish muhitni faollashtirish talabini olib tashlaydi.

Ixtiyoriy faollashtirish:

```powershell
.\.venv\Scripts\Activate.ps1
```

PowerShell faollashtirishga ruxsat bermasa, yuqoridagi to‘liq Python yo‘lidan foydalaning; tizim xavfsizlik sozlamalarini o‘zgartirish shart emas.

## Telegram tokenini sozlash

1. Telegram’da rasmiy `@BotFather` hisobini oching.
2. `/newbot` yuboring va ko‘rsatmalar orqali yangi bot yarating.
3. Olingan tokenni faqat kompyuteringizdagi `.env` fayliga kiriting. Uni chat, skrinshot yoki GitHub’da ulashmang.

`.env` mavjud bo‘lmasa nusxa yarating; mavjud fayl ustiga yozmang:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
notepad .env
```

`BOT_TOKEN=` dan keyin BotFather bergan qiymatni yozing. Hozir boshqa API kalitlari kerak emas.

| Sozlama | Hozirgi vazifasi |
|---|---|
| `BOT_TOKEN` | Majburiy. Telegram bot tokeni. |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` yoki `CRITICAL`. Standart: `INFO`. |
| `REQUEST_TIMEOUT` | Telegram HTTP so‘rovi chegarasi: 5–120 soniya. Standart: 30. |
| `GROQ_API_KEY`, `GROQ_MODEL` | Keyingi AI bosqichi uchun; hozir o‘qilmaydi va talab qilinmaydi. |
| `OPERATOR_CHAT_ID` | Operator bosqichi uchun; hozir operatorga hech narsa yuborilmaydi. |
| `DATABASE_PATH`, `CHROMA_PATH`, `EMBEDDING_MODEL` | Keyingi bosqichlar uchun joy ajratilgan. Hozir ishlatilmaydi. |

`.env` har doim loyiha ildizidan o‘qiladi. Tizimdagi muhit o‘zgaruvchilari `.env` qiymatlaridan ustun turadi. `.env`, `.venv`, ma’lumotlar va vaqtinchalik papkalar `.gitignore` ichida chiqarib tashlangan. Hali Git repozitori yaratilmagan.

Sozlamalarni **Telegram’ga ulanmasdan** tekshirish:

```powershell
.\.venv\Scripts\python.exe -m app.main --check-config
```

Bu tekshiruv tokenning faqat yozilish formatini tekshiradi. Token haqiqiyligini Telegram tasdiqlashi kerak. Token bo‘sh yoki noto‘g‘ri bo‘lsa, tuzatish uchun tushunarli xabar chiqadi; qiymatning o‘zi chiqarilmaydi.

## Ishga tushirish va qo‘lda tekshirish

```powershell
.\.venv\Scripts\python.exe -m app.main
```

Bot bilan **shaxsiy chatda** quyidagilarni sinang:

1. `/start` yuboring va `🇺🇿 O‘zbekcha` tugmasini bosing.
2. O‘zbekcha salomlashuv va menyu chiqishini tekshiring.
3. `/language` orqali `🇷🇺 Русский` ni tanlang, keyin `/help` yuboring.
4. Birinchi to‘rtta FAQ tugmasini bosing: tasdiqlangan qisqa javoblar chiqishi kerak; haqiqiy balans yoki qarz summasi ko‘rsatilmaydi.
5. `🔧 Elektr, gaz yoki suv bo‘yicha muammo` tugmasini bosing. Elektr, gaz, suv va isitish variantlarini tekshiring.
6. Shu bo‘limdan `⚠️ Xavfsizlik yo‘riqnomalari` ni tanlang. A–D javoblarini oching: tegishli manba havolalari va operatorni kutmaslik ko‘rsatmasi chiqishi kerak. Test uchun favqulodda raqamlarga qo‘ng‘iroq qilmang.
7. Asosiy menyuga qaytish, tilni almashtirish va operator tugmasini tekshiring. Operator hali ulanmaganini aytishi kerak.
8. Oddiy matn, noma’lum buyruq va rasm yuboring: mos zaxira javob chiqadi. Erkin matnni AI yoki risk detektori tahlil qilmaydi.
9. `/start` yuboring: oldin tanlangan til saqlangan bo‘lishi kerak.

To‘xtatish: `Ctrl+C`. Bir token bilan botning bitta nusxasini ishlating. Oldin webhook o‘rnatilgan bo‘lsa, uni alohida tekshirish kerak; dastur webhook’ni yoki navbatdagi xabarlarni avtomatik o‘chirmaydi.

## Testlar

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m app.faq
```

Testlar soxta token va tarmoqsiz Telegram sessiyasidan foydalanadi. `.env` dagi haqiqiy tokenni ishlatmaydi, haqiqiy foydalanuvchilarga xabar yubormaydi. Testlar buyruqlar, ikkala til, foydalanuvchilar holatining ajratilishi, FAQ javoblari, operator tugmasining joylashuvi, zaxira javoblar, sozlamalar, jurnallar va ulanish xatolarini qamrab oladi. FAQ 1–4 ning har bir tildagi matni alohida tasdiqlangan nusxa bilan aynan solishtiriladi. Buzilgan JSON, yo‘q tarjima, manba, hujjat yoki noto‘g‘ri fayl yo‘li ham tekshiriladi. Ular haqiqiy Telegram sinovining o‘rnini bosmaydi.

1-bosqichning tarixiy natijalari `PHASE1_REPORT.md`, 2-bosqichniki `PHASE2_REPORT.md` faylida keltiriladi. `python -m app.faq` `.env` va API’larga murojaat qilmasdan ma’lumot fayllarini tekshiradi.

## Kontekstni qayerda ko‘raman?

`knowledge_base` papkasini oching. `.uz.md` fayllari o‘zbekcha, `.ru.md` fayllari ruscha. Ular batafsil DEMO yo‘riqnomalaridir. `faq.json` dagi `answer.uz` va `answer.ru` esa bot yuboradigan qisqa javoblardir. `support.json` xizmatlar va xavfsizlik javoblarini, `index.json` ularning hujjat va manbalarini bog‘laydi.

Hujjat qo‘shish va tahrirlash tartibi `knowledge_base/README.md` da. Faqat Markdown’ni tahrirlash FAQ qisqa javobini avtomatik o‘zgartirmaydi. Matnlar va havolalar tekshirilgach, botni qayta ishga tushirish kerak. FAQ 1–4 matni yangi alohida tasdiqsiz o‘zgartirilmaydi.

## O‘rnatishdagi mumkin bo‘lgan xatolar

- **`py` Python’ni topmayapti:** `python` va `.venv\Scripts\python.exe` dan foydalaning.
- **Vaqtinchalik papkaga yozish rad etildi:** loyiha ichida vaqtinchalik papka belgilab, oldingi buyruqni qayta bajaring:

  ```powershell
  New-Item -ItemType Directory -Path .local-tmp -Force | Out-Null
  $env:TEMP = Join-Path (Get-Location) '.local-tmp'
  $env:TMP = $env:TEMP
  ```

- **`getaddrinfo failed`:** paketlar saytiga ulanish bo‘lmagan; internet va tarmoq ruxsatlarini tekshiring. Bu xabar paket versiyasi mavjud emasligini o‘z-o‘zidan isbotlamaydi.
- **Windows asinxron testi boshlanishida kutib qolish:** cheklangan ish muhitida Python’ga kerak bo‘ladigan mahalliy ulanish ham bloklanishi mumkin. Oddiy mahalliy PowerShell’da testlarni qayta bajaring; buning uchun koddagi asinxron mexanizmni o‘zgartirish kerak emas.

## Cheklovlar va keyingi bosqichlar

Hozir tasdiqlangan FAQ va mahalliy Knowledge Base ishlatiladi. Groq, RAG, embedding, ChromaDB, erkin matnni tushunish, avtomatik xavf aniqlash, ticketlar va operator yozishmalari amalga oshirilmagan. Foydalanuvchi matni jurnalga yozilmaydi va qaytarib ko‘rsatilmaydi. Xavfsizlik menyusi tayyor ko‘rsatmalarni ochadi; maxsus aniqlash qoidalari 4-bosqichda qo‘shiladi. Bot favqulodda xizmatga qo‘ng‘iroq qilmaydi, brigada yubormaydi va kompaniya hisoblarini ko‘rmaydi.

Operator bilan suhbatni tugatib AI yordamchisiga qaytish talabi qayd etilgan. U 5-bosqichda, suhbat holati va ticketlar bilan birga amalga oshiriladi; hozir ishlaydigan imkoniyat sifatida ko‘rsatilmaydi.

Keyingi bosqich — 3-bosqich: RAG va Groq. Uni boshlash uchun loyiha egasining alohida tasdig‘i kerak. Hozir unga o‘tilmagan. Qo‘shimcha FAQ mavzulari A va B ham alohida FAQ sifatida qo‘shilmagan.

## Texnik manbalar

- [aiogram: long polling](https://docs.aiogram.dev/en/latest/dispatcher/long_polling.html)
- [aiogram: ReplyKeyboardMarkup](https://docs.aiogram.dev/en/latest/api/types/reply_keyboard_markup.html)
- [aiogram: MemoryStorage](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/storages.html)
