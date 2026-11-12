"""Interface text; approved FAQ answers live in knowledge_base/faq.json."""

from dataclasses import dataclass
from enum import StrEnum


class Language(StrEnum):
    UZ = "uz"
    RU = "ru"


LANGUAGE_BUTTONS = {"🇺🇿 O‘zbekcha": Language.UZ, "🇷🇺 Русский": Language.RU}
CHOOSE_LANGUAGE = "Tilni tanlang / Выберите язык:"


@dataclass(frozen=True)
class Texts:
    welcome: str
    help: str
    language_saved: str
    operator_pending: str
    fallback: str
    unsupported: str
    error: str
    placeholder: str
    electricity: str
    payment: str
    delayed_payment: str
    debt: str
    utilities: str
    language: str
    help_button: str
    operator: str

    @property
    def faq_buttons(self) -> tuple[str, ...]:
        return (self.electricity, self.payment, self.delayed_payment, self.debt, self.utilities)


TEXTS = {
    Language.UZ: Texts(
        welcome="DOMO AI\n🟢 Bot ishlayapti · DEMO\n\nAssalomu alaykum! Men DOMO AI yordamchisiman.\n"
        "Sizga qanday yordam bera olaman?\n\nTasdiqlangan FAQ javoblari va ikki tildagi menyu ishlaydi. "
        "Kommunal muammolar bo‘limida xizmatlar va xavfsizlik yo‘riqnomalarini tanlashingiz mumkin. "
        "Oddiy savolingizni matn bilan yozishingiz ham mumkin. "
        "Ayrim xavfli iboralar uchun tayyor xavfsizlik javobi beriladi. Operator xizmati hali ulanmagan. "
        "Demo haqiqiy hisoblar, qarzlar yoki to‘lovlarni tekshira olmaydi.",
        help="DOMO AI — demo yordamchi.\n\n/start — boshlash va menyu\n"
        "/language — tilni almashtirish\n/help — yordam\n\n"
        "Menyudagi tugmani bosing yoki savolingizni yozing. "
        "FAQ tugmalari tayyor javoblarni ochadi. Kommunal muammolar bo‘limida "
        "elektr, gaz, suv, isitish va xavfsizlik yo‘riqnomalari bor. "
        "Erkin savollarga AI faqat mavjud bilim bazasi asosida javob beradi. "
        "Ayrim xavfli iboralar tayyor xavfsizlik javobiga yo‘naltiriladi; bu barcha xavflarni aniqlash kafolati emas. "
        "Operator xizmati hali ulanmagan.\n\n"
        "Parol, PIN, CVV, SMS-kod yoki to‘liq karta ma’lumotlarini yubormang.",
        language_saved="O‘zbek tili tanlandi.",
        operator_pending="Operator xizmati hali ulanmagan. Hozir murojaat yaratilmaydi "
        "va operatorga xabar yuborilmaydi.",
        fallback="Hozir bu savolga javob bera olmadim. Savolni aniqlashtiring yoki "
        "FAQ tugmalaridan foydalaning. Xavfsizlik yo‘riqnomalari kommunal muammolar bo‘limida. "
        "/start, /help va /language buyruqlari ham mavjud.",
        unsupported="Hozir matnli xabarlar va menyu tugmalaridan foydalaning. "
        "Rasm, ovoz va hujjatlar qayta ishlanmaydi.",
        error="So‘rovni bajarishda xatolik yuz berdi. Iltimos, birozdan keyin qayta urinib ko‘ring.",
        placeholder="Murojaatingizni yozing...",
        electricity="⚡ Elektr hisobimda qancha pul bor?",
        payment="💳 To‘lovni qanday amalga oshiraman?",
        delayed_payment="🧾 To‘lov qildim, lekin hisobga tushmadi",
        debt="📄 Qarzdorligimni qanday tekshiraman?",
        utilities="🔧 Elektr, gaz yoki suv bo‘yicha muammo",
        language="🌐 Tilni o‘zgartirish",
        help_button="ℹ️ Yordam",
        operator="🎧 Operator bilan bog‘lanish",
    ),
    Language.RU: Texts(
        welcome="DOMO AI\n🟢 Бот работает · ДЕМО\n\nЗдравствуйте! Я помощник DOMO AI.\n"
        "Чем я могу помочь?\n\nРаботают утверждённые ответы FAQ и меню на двух языках. "
        "В разделе коммунальных проблем можно выбрать услугу и инструкцию по безопасности. "
        "Вы также можете написать обычный вопрос текстом. "
        "Некоторые опасные ситуации по тексту направляются к готовому ответу по безопасности. Оператор пока не подключён. "
        "Демо не может проверить реальные счета, задолженность или платежи.",
        help="DOMO AI — демонстрационный помощник.\n\n/start — начало и меню\n"
        "/language — сменить язык\n/help — помощь\n\n"
        "Нажмите кнопку меню или напишите вопрос. "
        "Кнопки FAQ открывают готовые ответы. В разделе коммунальных проблем есть "
        "электричество, газ, вода, отопление и инструкции по безопасности. "
        "ИИ отвечает на свободные вопросы только по имеющейся базе знаний. "
        "Некоторые опасные формулировки направляются к готовому ответу по безопасности; это не гарантия выявления всех опасностей. "
        "Оператор пока не подключён.\n\n"
        "Не отправляйте пароли, PIN, CVV, SMS-коды и полные данные карты.",
        language_saved="Выбран русский язык.",
        operator_pending="Оператор пока не подключён. Обращение сейчас не создаётся, "
        "сообщение оператору не отправляется.",
        fallback="Сейчас не удалось ответить на этот вопрос. Уточните вопрос или "
        "используйте кнопки FAQ. Инструкции по безопасности находятся в разделе коммунальных проблем. "
        "Также доступны /start, /help и /language.",
        unsupported="Пока используйте текстовые сообщения и кнопки меню. "
        "Фото, голосовые сообщения и документы не обрабатываются.",
        error="Не удалось обработать запрос. Пожалуйста, повторите попытку немного позже.",
        placeholder="Напишите ваш вопрос...",
        electricity="⚡ Как проверить баланс за электричество?",
        payment="💳 Как оплатить коммунальные услуги?",
        delayed_payment="🧾 Платёж не поступил на счёт",
        debt="📄 Как проверить задолженность?",
        utilities="🔧 Проблема с электричеством, газом или водой",
        language="🌐 Изменить язык",
        help_button="ℹ️ Помощь",
        operator="🎧 Связаться с оператором",
    ),
}


def default_language(telegram_code: str | None) -> Language:
    return Language.RU if (telegram_code or "").lower().startswith("ru") else Language.UZ
