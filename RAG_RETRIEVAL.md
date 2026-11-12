# DOMO — 3-bosqichning lokal retrieval qismi

Sana: 2026-11-12. Bu hujjat faqat ma’lumotni topish qismi haqida. Groq, javob generatsiyasi va Telegram integratsiyasi amalga oshirilmadi.

## Nima yaratildi?

Oqim: mavjud katalogdagi 20 ta Markdown fayli → sarlavha bo‘yicha bo‘laklash → Sentence Transformers embedding → lokal ChromaDB → savolga mos bo‘laklar.

Mavjud FAQ, handlerlar, tasdiqlangan matnlar va Knowledge Base mazmuni o‘zgartirilmadi. Oldindan mavjud 37 ta `app/` va `knowledge_base/` fayli nazorat yig‘indilari bilan solishtirilib, o‘zgarish yo‘qligi tasdiqlandi. Telegram bot qayta ishga tushirilmadi. `.env` tahrirlanmadi va API kalitlari chiqarilmadi.

## Yangi fayllar

| Fayl | Vazifasi |
|---|---|
| `app/rag/chunking.py` | Mavjud `load_catalog()` orqali 20 ta indekslangan fayldan bo‘laklar yaratadi. |
| `app/rag/embeddings.py` | Sentence Transformers, E5 prefikslari, CPU, token chegarasi va lokal model keshi. |
| `app/rag/retrieval.py` | Chroma PersistentClient, indeks yaratish va cosine qidiruv. |
| `app/rag/settings.py` | Retrieval uchun alohida sozlamalar; bot tokeni talab qilinmaydi. |
| `app/rag/errors.py`, `app/rag/__init__.py` | Xavfsiz xatolik turi va mustaqil modul. |
| `app/rag/__main__.py` | `inspect`, `index`, `query` buyruqlari. |
| `scripts/retrieval_demo.py` | 16 ta ikki tilli kommunal savol va 4 ta aloqasiz savol bilan takrorlanadigan sinov. |
| `tests/test_rag_chunking.py` | Bo‘laklar, 20 fayl qamrovi, token chegaralari va manba ajratilishi. |
| `tests/test_rag_embeddings.py` | Model adapteri, prefikslar, lokal yuklash va xavfsiz xatoliklar; haqiqiy model yuklanmaydi. |
| `tests/test_rag_retrieval.py` | Haqiqiy lokal Chroma bilan indeks/qidiruv, test embeddinglari orqali. |
| `tests/test_rag_cli.py` | Model yuklamasdan tekshirish va buyruqlarning xatolik holatlari. |
| `requirements-rag.txt` | Asosiy retrieval paketlari; mavjud bot versiyalariga cheklov. |
| `requirements-rag-lock.txt` | Tekshirilgan to‘liq muhitning aniq paket versiyalari. |
| `data/retrieval_demo_results.json` | Haqiqiy model bilan o‘lchangan namuna natijalari. |

## Model va o‘rnatilgan versiyalar

- Model: `intfloat/multilingual-e5-small`, revision `614241f`.
- 384 o‘lchamli, normallashtirilgan embeddinglar; CPU ishlatiladi.
- E5 uchun savolga `query: `, hujjatga `passage: ` prefiksi qo‘shiladi. Bu modelning rasmiy [qo‘llash ko‘rsatmasiga](https://huggingface.co/intfloat/multilingual-e5-small) mos.
- Sentence Transformers: `6.3.0`.
- ChromaDB: `1.5.9`.
- PyTorch: `2.15.0+cpu`.
- Avvalgi aiogram `3.31.0`, Pydantic `2.13.5`, python-dotenv `1.2.4` va pytest `9.2.0` versiyalari saqlandi.

Modelning asosiy safetensors fayli [rasmiy repozitoriyda](https://huggingface.co/intfloat/multilingual-e5-small/tree/main) taxminan 471 MB. Bu muhitda model keshi jami 493 293 063 bayt bo‘ldi. Kutubxonalar uchun qo‘shimcha disk joyi kerak. Yuklash oldidan foydalanuvchiga aytildi. Windows symlink ogohlantirishi ishlashga to‘sqinlik qilmadi; kesh fayllari lokal saqlandi.

PyTorch CPU rasmiy manbasi `https://download.pytorch.org/whl/cpu`, model manbasi Hugging Face, qolgan paketlar PyPI orqali olindi. Model o‘qitilmadi.

## Bo‘laklash

- Faqat `index.json` ichida ro‘yxatlangan hujjatlar ishlatiladi; papkadagi README tasodifan indekslanmaydi.
- Har til va hujjat alohida; Markdown bo‘limlari bir-biriga qo‘shib yuborilmaydi.
- Sarlavha va bo‘lim nomi qidiriladigan matnga qo‘shiladi. Takroriy DEMO banneri, ID, til satri va manba havolalari ro‘yxati semantik matndan chiqariladi, tegishli ma’lumot metadata’da qoladi.
- Standart chegara to‘liq matn uchun 900 belgi; uzun bo‘laklarda 100 belgigacha qoplanish. Haqiqiy tokenizer bilan 480 token chegarasi ham tekshiriladi. Modelning 512 token chegarasida matn yashirin kesilmaydi.
- Shu 20 fayldan **66 ta bo‘lak** hosil bo‘ldi.
- Har bo‘lakda ID, hujjat IDsi, til, kategoriya, sarlavha, bo‘lim, nisbiy fayl yo‘li, kontent turi va manba IDlari bor.
- `document_source_ids` butun hujjatning manbalari; `source_ids` aynan bo‘lim uchun biriktirilgan manbalardir. Butun aralash DEMO hujjati rasmiy qoida deb belgilanmaydi. Masalan, gazning oddiy javobi manbasiz DEMO; gaz xavfsizligi bo‘limi `gas_advice` bilan bog‘langan.

## Lokal ChromaDB

Standart joy: `data/chroma/`. Unda `chroma.sqlite3` va HNSW indeks papkasi yaratiladi. Alohida server, Docker yoki bulut xizmati kerak emas. [PersistentClient](https://docs.trychroma.com/docs/run-chroma/clients) ishlatiladi.

Ushbu sinov kolleksiyasi: `domo_kb_367f576cea51375c9169a66f`. [Cosine](https://docs.trychroma.com/docs/collections/configure) masofasi tanlangan. Embeddinglar dastur tomonidan beriladi; Chroma’ning avtomatik embedding modeli o‘chirilgan. Chroma anonim telemetriyasi ham o‘chirilgan.

Kolleksiya nomi model/revision va barcha bo‘laklar izidan hisoblanadi. Takroriy indekslash tayyor nusxani qayta ishlatadi va dublikat qo‘shmaydi. Model yoki kontekst o‘zgarsa, boshqa indeks nomi kerak bo‘ladi; qidiruv eskisini jim ishlatmaydi. Indeks to‘liq yaratilmagan bo‘lsa, qidiruv rad etiladi. Oldingi to‘liq nusxalar avtomatik o‘chirilmaydi; bu kichik prototipda ular lokal kesh sifatida qoladi.

## Qidiruv

`Retriever.search(question, language="uz" yoki "ru", top_k=3)` kerakli tildagi eng yaqin bo‘laklarni qaytaradi. Natija `RetrievalHit`: bo‘lak va cosine o‘xshashlik balli. Moslik chegarasidan past natijalar chiqarilmaydi. Bo‘sh natija hech qanday javob mavjudligini anglatmaydi.

Standart `min_score=0.80`. Bu ehtimollik yoki to‘g‘rilik kafolati emas. Hozirgi kichik namuna bilan tekshirilgan boshlang‘ich chegara; kengroq real savollarda qayta baholash kerak. Faqat savol tili aniq beriladi; avtomatik til yoki xavf tasnifi qo‘shilmadi. So‘rovlar Chroma bazasiga yoki jurnalga yozilmaydi.

## PowerShell buyruqlari

Loyiha ildizida bajaring. Mavjud muhit allaqachon tayyor. Yangi muhitda tekshirilgan paketlarni o‘rnatish:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-rag-lock.txt
```

Modelni yuklamasdan hujjatlarni ko‘rish:

```powershell
.\.venv\Scripts\python.exe -m app.rag inspect
```

Birinchi indekslashda modelni yuklashga aniq ruxsat berish:

```powershell
.\.venv\Scripts\python.exe -m app.rag index --download-model
```

Model keshda bo‘lganda `--download-model` kerak emas. Internetni o‘chirgan holda tekshirish uchun:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
.\.venv\Scripts\python.exe -m app.rag query "To‘lovim kommunal hisobda ko‘rinmayapti" --language uz
.\.venv\Scripts\python.exe -m app.rag query "Как проверить задолженность?" --language ru
```

Takrorlanadigan model sinovi:

```powershell
.\.venv\Scripts\python.exe scripts/retrieval_demo.py --output data/retrieval_demo_results.json
```

Bu buyruqlar faqat bo‘laklarni topadi; yakuniy foydalanuvchi javobi yaratilmaydi. Tashqi API’ga savol yoki KB matni yuborilmaydi.

## Sozlamalar

Mavjud `.env` faylidagi yoki jarayon muhitidagi qiymatlar o‘qiladi; `.env` o‘zgartirilmagan. Retrieval bot tokeni yoki Groq kalitini talab qilmaydi va ulardan foydalanmaydi.

| Sozlama | Standart |
|---|---|
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` |
| `EMBEDDING_REVISION` | Shu model uchun `614241f`; boshqa modelga aniq revision berilishi kerak. `main` / `master` qabul qilinmaydi. |
| `EMBEDDING_CACHE_PATH` | `data/models` |
| `CHROMA_PATH` | `data/chroma` |
| `RAG_MIN_SCORE` | `0.80` |

Nisbiy yo‘llar loyiha ildiziga nisbatan olinadi. Telegram konfiguratsiyasi va eski `app/config.py` o‘zgartirilmagan.

## Haqiqatan bajarilgan testlar

1. Yangi bo‘laklash va real lokal Chroma testlari: **24 passed in 3.74s**. Vektorlar sun’iy va deterministik, model sifati haqida xulosa bermaydi.
2. Model adapteri va xatolik holatlari bilan barcha testlar: **141 passed in 5.89s**. Avvalgi 101 test ham shu to‘plamda bajarildi. Testlar model yuklamaydi va Groq/Telegram’ga ulanmaydi.
3. `pip check`: **No broken requirements found.**
4. Haqiqiy E5 modeli bilan alohida offline jarayonda: **16 ta kommunal savolda kerakli hujjat top-3 ichida; 4 ta aloqasiz savolda natijalar rad etildi.** Baholash mezoni shu sabab 20/20 bo‘ldi. Bu top-1 aniqligi degani emas.
5. Haqiqiy model bilan top-1 to‘g‘ri hujjat: **13/16**. Isitishning ikki savoli va gazning ruscha savolida kerakli hujjat 2–3-o‘rinda bo‘ldi.
6. Saqlangan indeksdan alohida `app.rag query` jarayonida ruscha to‘lov savoli tekshirildi: `payment_delay`, ball `0.8814`, javob yaratilmagan.

| Namuna savol | Til | Birinchi natija | Ball |
|---|---|---|---|
| Elektr hisobimdagi qoldiqni qayerdan tekshiraman? | uz | `electricity_balance` | 0.8822 |
| Как узнать остаток денег на счёте за электричество? | ru | `electricity_balance` | 0.8964 |
| Pul kartamdan yechildi, ammo kommunal hisobga tushmadi. Nima qilay? | uz | `payment_delay` | 0.8351 |
| Деньги списались, но платёж не появился на коммунальном счёте. | ru | `payment_delay` | 0.8814 |
| Kommunal xizmatlar bo‘yicha qarzimni qanday tekshiraman? | uz | `debt_check` | 0.9003 |
| Как проверить задолженность за коммунальные услуги? | ru | `debt_check` | 0.8922 |

Eng yuqori noto‘g‘ri namuna: ruscha gaz hidi savolida `heating_issues` 0.8556 bilan birinchi, kerakli `gas_issues` xavfsizlik bo‘limi 0.8478 bilan ikkinchi bo‘ldi. Shuning uchun faqat birinchi natijani favqulodda holat qarori sifatida ishlatish mumkin emas. Hozir hech qanday xavfsizlik tasnifi yoki AI javobi ulanmagan.

## Keyingi Groq qismiga nima tayyor?

Bo‘lak matni, hujjat IDsi, til, bo‘lim, DEMO turi, moslik balli va manba IDlarini olish tayyor. Keyingi bosqichda ularni tekshirilgan kontekst sifatida promptga uzatish, kontekst yetishmaganda rost zaxira javob berish va manbani to‘g‘ri ko‘rsatish kerak bo‘ladi. Groq chaqiruvi, promptlar va Telegram handleriga ulash bu vazifada bajarilmadi.
