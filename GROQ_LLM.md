# DOMO — mustaqil RAG + Groq xizmati

2026-11-12. Bu modul Telegram’ga ulanmagan. FAQ 1–5, Knowledge Base, mavjud
handlerlar va retrieval kodi o‘zgartirilmagan. Operator tizimi qo‘shilmadi.

## Oqim va javob shakli

`RagAnswerService.answer()` → mavjud `Retriever.search()` → lokal 20 tagacha
nomzoddan tasdiqlangan eng mos 3 bo‘lak → `GroundedLLMService` → `GroqClient`
→ tekshirilgan javob. Ichki yo‘riqnoma qidiruvning yuqori o‘rnida bo‘lsa ham,
undan pastdagi tasdiqlangan foydalanuvchi javobi tanlanishi mumkin.
Retrieval alohida oqimda bajariladi; mavjud asyncio ishini band qilmaydi.

Oddiy kommunal savollarda model tasdiqlangan ma’lumotni tabiiy, qisqa javobga
aylantiradi va dalil sifatida shu so‘rovdagi hujjat bo‘laklarining IDlarini
ko‘rsatadi. Butun kontekstni qayta ko‘chirish talab qilinmaydi. Noma’lum,
ichki yoki shu so‘rovda yuborilmagan bo‘lak IDsi rad etiladi. Eski ichki mijoz
iqtibos ham yuborsa, u asl matnga aynan teng bo‘lishi shart.
Xavfsizlik javoblari modeldan olinmaydi: ID orqali serverdagi to‘liq
tasdiqlangan matn qaytariladi.

- Faqat mavjud katalogdan qayta hisoblangan, barcha maydonlari mos bo‘laklar
  qabul qilinadi. Boshqa matn/ID/manba biriktirilgan `RetrievalHit` rad etiladi.
- Token chegarasi bilan bo‘laklangan haqiqiy retrieval uchun LLM xizmatiga ham
  shu embeddingning `token_counter=embedder.token_count` funksiyasi uzatiladi.
  Ikkala qism bir xil 900 belgi / 480 token chegaralarida ishlaydi.
  Agar xavfsizlik bo‘limi bir nechta bo‘lakka ajralsa, uning yarim javobi
  chiqarilmaydi; zaxira javob qaytariladi. Telegram’ga ulashda mavjud to‘liq
  tasdiqlangan xavfsizlik javobi yo‘li bundan alohida saqlanishi kerak.
- Til `uz` yoki `ru`. Argument berilmasa, ruscha kirill va o‘zbekcha lotin uchun
  sodda aniqlash bor; o‘zbek kirillidagi ў/қ/ғ/ҳ ham taniladi. Qisqa, aralash
  yoki boshqa yozuvdagi savol uchun `language`ni aniq berish ma’qul. Bu to‘liq
  til aniqlash modeli emas.
- Standart cosine chegarasi `0.80`; bu javob to‘g‘riligi ehtimolligi emas.
- Noto‘g‘ri, aralash tilli, takroriy, past balli yoki almashtirilgan kontekst
  chaqiruvsiz zaxira javobga tushadi. Ichki batafsil yo‘riqnomalar modelga
  yuborilmaydi; faqat tasdiqlangan mijoz javoblariga mos bo‘laklar beriladi.
- Bo‘sh qidiruvda ham model savol turini aniqlashi mumkin. Salomlashish,
  minnatdorchilik, aniqlashtirish, haqiqiy hisobga kira olmaslik va mavzudan
  tashqari savollar uchun serverdagi qisqa ikki tilli javoblar ishlatiladi.
  Bunday holatda modelning erkin matni chiqarilmaydi va manba biriktirilmaydi.
- Javob sxemasi: `mode`, `language`, `answer`, `clarification`, `evidence`.
  `grounded` rejimida dalil majburiy; boshqa rejimlarda dalil bo‘sh bo‘lishi shart.
  JSON/ID/til tekshiruvi o‘tmasa, `SAFE_FALLBACK[language]` qaytariladi.
  Model bergan URL, texnik ko‘rsatma, yangi raqam va hisob holati haqidagi
  aniqlangan asossiz da’volar ham rad etiladi.
- `AnswerResult`: `text`, `language`, `status`, `reason`, `references`,
  `retry_after`. `references` ichida `chunk_id`, `document_id`, `filename`,
  `source_ids`, `source_urls` bor. Havolalar modeldan olinmaydi; mahalliy
  katalogdan tiklanadi. Manbasiz umumiy DEMO yo‘riqnomasiga begona rasmiy
  xavfsizlik havolasi qo‘shilmaydi. Telegram oddiy javobdagi takroriy DEMO
  sarlavhasini olib tashlaydi; botning demo cheklovlari salomlashuvda qoladi.

## Konfiguratsiya

Haqiqiy kalit faqat mahalliy `.env`da saqlanadi. `load_llm_settings()` faylni
faqat aniq chaqirilganda o‘qiydi; importda kalit olinmaydi. Kalit uchun jarayon
muhitiga o‘tish yoki `${...}` almashtirish yo‘q. Kalit `SecretStr` bilan yashiriladi.
Mavjud `.gitignore` `.env` va `.env.*`ni allaqachon chiqarib tashlaydi;
`.env.example` faqat bo‘sh namunadir. Haqiqiy `.env` bu ishda o‘qilmadi va tahrirlanmadi.

| `.env` nomi | Qiymat / cheklov |
|---|---|
| `GROQ_API_KEY` | Majburiy; haqiqiy qiymatni kodga, hisobotga yoki testga yozmang. |
| `GROQ_MODEL` | Majburiy; tavsiya: `openai/gpt-oss-20b`. |
| `GROQ_TIMEOUT_SECONDS` | Standart `15`; `0.1`–`60` soniya. |
| `GROQ_MAX_OUTPUT_TOKENS` | Standart `1200`; `128`–`4096`. |

`openai/gpt-oss-20b` Groq’ning strict JSON Schema rejimini qo‘llab-quvvatlaydi.
Modelni o‘zgartirganda shu imkoniyatni tekshiring: [Groq structured outputs](https://console.groq.com/docs/structured-outputs).
Mos kelmaydigan modelda API xatosi qaytariladi; erkin matn rejimiga yashirin o‘tish yo‘q.
Model bilan jonli so‘rovlar ushbu muhitda muvaffaqiyatli tekshirilgan.

`httpx==0.28.1` ushbu virtual muhitda allaqachon bor; hech qanday yangi paket
o‘rnatilmadi. Yangi muhit uchun alohida `requirements-llm.txt` berilgan.
Retrieval paketlari avvalgidek `requirements-rag.txt` / lock faylida qoladi.

## Tashqi chaqiruvga ruxsat

`GroqClient(settings)` standart holatda jonli tarmoq chaqiruviga yo‘l qo‘ymaydi.
Test uchun faqat `httpx.MockTransport` yetarli. Haqiqiy xizmat uchun alohida
ruxsatdan keyin `GroqClient(settings, allow_live_api=True)` ishlatiladi.
Bu bayroq odam bergan ruxsatni o‘zi tekshirmaydi; chaqiruvchi uni faqat
kelishilgan jonli ish uchun yoqishi kerak.

Endpoint qat’iy: `https://api.groq.com/openai/v1/chat/completions`.
Kalit faqat Authorization sarlavhasida beriladi; promptga qo‘shilmaydi.
Jonli chaqiruvda savol va topilgan KB parchalari Groq’ga yuboriladi.
Hozirgi testlar faqat sun’iy kalit va soxta API bilan bajariladi.

Kutubxonadagi ulash tartibi (bu misol avtomatik bajarilmaydi):

```python
from app.faq import load_catalog
from app.llm import GroqClient, GroundedLLMService, RagAnswerService, load_llm_settings
from app.rag.chunking import build_chunks
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.retrieval import Retriever
from app.rag.settings import load_rag_settings

async def approved_live_question(question, language):
    catalog = load_catalog()
    rag = load_rag_settings()
    embedder = SentenceTransformerEmbedder(rag)  # Faqat mavjud lokal kesh.
    retriever = Retriever(
        build_chunks(catalog, token_counter=embedder.token_count),
        embedder, rag.chroma_path, min_score=rag.min_score,
    )  # Oldindan yaratilgan indeks; yangi model yuklash/indekslash yo‘q.
    async with GroqClient(load_llm_settings(), allow_live_api=True) as client:
        service = RagAnswerService(
            retriever, GroundedLLMService(
                client, catalog, min_score=rag.min_score,
                token_counter=embedder.token_count,
            ),
        )
        return await service.answer(question, language=language)
```

## Xatolar va prompt injection

- `auth_error`: 401/403; `rate_limited`: 429; `timeout`: belgilangan vaqt;
  `network_error`: ulanish; `api_error`: boshqa HTTP xatosi;
  `invalid_response`: buzilgan, juda katta, kesilgan yoki tool-call javobi.
- API xatosida matn xavfsiz zaxira javob bo‘ladi, `status="error"`, `reason`
  esa sabab kodi. Xato tanasi, kalit, savol va kontekst xabarga/jurnalga yozilmaydi.
- Avtomatik qayta so‘rov va boshqa manzilga redirect yo‘q. 429 dagi musbat
  soniyali `Retry-After` 300 soniyagacha qaytariladi; kutish/qayta chaqirish
  keyingi integratsiya siyosatiga qoldirilgan.
- Alohida system ko‘rsatmasi saqlanadi. Savol va kontekst faqat JSON ma’lumot
  sifatida user xabariga joylanadi; ular yangi system xabari yarata olmaydi.
- Tanish inglizcha/o‘zbekcha/ruscha buyruq almashtirish va kalit chiqarish
  urinishlari konservativ filtr bilan rad etiladi. Modelga tools berilmaydi.
- Noma’lum ID yoki berilgan eski dalil iqtibosining o‘zgarishi rad etiladi. Oddiy javob
  dalilga tayangan tabiiy matn bo‘lishi mumkin; xavfsizlik matni aynan saqlanadi.

Bu choralar barcha semantik prompt injectionlarni aniqlash kafolati emas.
Model noto‘g‘ri bo‘lakni tanlashi yoki noto‘g‘ri mazmun berishi mumkin. Manba
IDsi va raqam/til tekshiruvlari tabiiy javobning har bir jumlasi manbaga
mazmunan mosligini isbotlamaydi. Shuning uchun mutlaq to‘qimaslik kafolati
berilmaydi; haqiqiy model bilan alohida sifat sinovi kerak. Telegram yo‘li
`app/bot/ai.py` orqali ulangan, ammo kod o‘zgargach botni qayta ishga tushirish kerak.

## Testlar va keyingi ish

Yangi testlar: `test_llm_settings.py`, `test_llm_transport.py`,
`test_llm_service.py`, `test_llm_pipeline.py`, `test_llm_security.py`,
`test_llm_conversation.py`.
Ular ikki tilni, javobi bor/yo‘q kontekstni, haqiqiy lokal Chroma’dan soxta Groq’gacha
oqimni, ID/manbalarni, prompt hujumlarini, HTTP xatolarini va vaqt chegarasini tekshiradi.
Embeddinglar testda sun’iy; bu sinovlar haqiqiy LLM yoki embedding sifatini baholamaydi.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

Tabiiy suhbat o‘zgarishidan keyingi mahalliy tekshiruv: **379 passed, 0 failed**.
Testlar API uchun soxta mijozdan foydalanadi. Yangi paket o‘rnatilmadi; FAQ,
KB manbalari va RAG arxitekturasi saqlandi. Foydalanuvchi ruxsatidan keyin
salomlashish, aniqlashtirish, ikki tildagi to‘lov yo‘riqnomasi, haqiqiy hisob
cheklovi va mavzudan tashqari savol jonli tekshirildi. Dastlab bir so‘rovda
429 limit kuzatildi; keyingi qayta tekshiruvlar muvaffaqiyatli o‘tdi. Dalil
matnini ortiqcha ko‘chirish talabi IDga almashtirildi. Haqiqiy hisob summasini
so‘rashning aniq holatlari endi API chaqirmasdan halol cheklovga yo‘naltiriladi.
Bot yangi kod bilan qayta ishga tushirildi va `AI_ready=True` tasdiqlandi.
Operator tizimi bu vazifaga kirmaydi. Yangi kodni commit/push qilish avtomatik
bajarilmaydi.
