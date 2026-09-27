# گزارش Scout بازار سهام ایران — ۵ مهر ۱۴۰۵

**REPORT_ID:** `2026-09-27-IR-TSE-1200`  
**زمان تهیه:** ۱۲:۰۲ تهران  
**وضعیت اقدام:** **مثبت اما انتخابی؛ تعقیب صف‌ها ممنوع**

> اصلاح بنیادی: امتیاز بنیادی هسته از این پس فقط از State پایدار Git در `state/fundamentals/iran-stocks/<SYMBOL>.json` خوانده می‌شود. امتیازهای بنیادی اسکرینرهای بیرونی فقط Reference هستند و حق ایجاد برچسب `FUNDAMENTAL_GEM`، `EARLY_CANDIDATE` یا `PRIME_CANDIDATE` ندارند.

## جمع‌بندی اجرایی

بازار در نیمه روز بسیار مثبت بود: ۹۲۸ نماد مثبت، ۷۶ نماد منفی و ۹۴ نماد بدون تغییر از ۱٬۰۹۸ نماد معامله‌شده. در snapshot ساعت ۰۹:۱۸، شاخص کل ۷٬۲۳۰٬۸۵۲ واحد (`+1.09%`) و شاخص هم‌وزن ۱٬۹۴۹٬۶۳۵ واحد (`+1.03%`) ثبت شد.

با وجود پهنای مثبت، بسیاری از لیدرها نزدیک سقف روزانه یا سقف ۵۲ هفته بودند. نتیجه عملی Scout: **انتخاب محدود، پولبک/تثبیت، و عدم تعقیب صف**.

## فهرست منتخب اصلاح‌شده

| رتبه | نماد | برچسب | Tape | R/R | وضعیت بنیادی |
|---:|---|---|---:|---:|---|
| ۱ | **خبهمن** | EARLY_WATCH | ۹۰ | ۲٫۲۸ سناریویی | `INITIAL_BASELINE_NOT_ESTABLISHED` |
| ۲ | **فزر** | BREAKOUT_WATCH | ۸۶ | نامعتبر | `INITIAL_BASELINE_NOT_ESTABLISHED` |
| ۳ | **وصندوق** | BREAKOUT_WATCH | ۸۴ | ۱٫۲۷ | `INITIAL_BASELINE_NOT_ESTABLISHED` |
| ۴ | **فصبا** | MOMENTUM_WATCH | ۸۲ | ۰٫۱۸ | `FUNDAMENTAL_REVIEW_REQUIRED` |
| ۵ | **شاملا** | MOMENTUM_WATCH | ۷۸ | نامعتبر | `INITIAL_BASELINE_NOT_ESTABLISHED` |

## اصلاح مهم فزر

در نسخه اولیه، امتیاز بنیادی خارجی `85.63` از یک اسکرینر بیرونی به‌اشتباه به‌عنوان Core Fundamental استفاده و برچسب `FUNDAMENTAL_GEM` صادر شده بود. چون فایل Canonical بنیادی برای فزر در State وجود ندارد، این برچسب **حذف شد**.

- امتیاز خارجی 85.63 فقط `REFERENCE_ONLY_NOT_CANONICAL` است.
- Core Fundamental فزر: `DATA_NOT_VERIFIED`
- Fundamental Status: `INITIAL_BASELINE_NOT_ESTABLISHED`
- برچسب معتبر فعلی: `BREAKOUT_WATCH`

## کاندیداها

### خبهمن
- Last: 2,543
- Buyer/Seller Power: 3.25x
- Tape: 90
- R/R سناریویی: 2.28
- Core Fundamental: `DATA_NOT_VERIFIED`
- نتیجه: فقط EARLY_WATCH، نه Early Candidate رسمی.

### فزر
- Last: 321,000 در سقف ۵۲ هفته
- Buyer/Seller Power: 2.99x
- Tape: 86
- RSI reference: 84.74
- Core Fundamental: `DATA_NOT_VERIFIED`
- نتیجه: BREAKOUT_WATCH؛ بدون Fundamental Gem.

### وصندوق
- Last: 25,070
- Buyer/Seller Power: 3.15x
- Tape: 84
- R/R: 1.27
- Core Fundamental: `DATA_NOT_VERIFIED`
- نتیجه: BREAKOUT_WATCH؛ R/R زیر استاندارد 2.

### فصبا
- Last: 4,050
- Buyer/Seller Power: 12.87x
- Tape: 82
- R/R: 0.18
- گزارش ماهانه جدید منتشر شده و باید در مرحله Auditor بررسی شود.
- Core Fundamental تا قبل از بررسی filing **تغییر نمی‌کند**.

### شاملا
- Last: 41,800 در سقف ۵۲ هفته
- Buyer/Seller Power: 2.21x
- Tape: 78
- Core Fundamental: `DATA_NOT_VERIFIED`
- نتیجه: MOMENTUM_WATCH؛ بدون R/R معتبر.

## خروجی آستانه‌های رسمی

- **Best Early Candidate: NONE**
- **Best Momentum Hunter: NONE**
- **Best Potential Prime: NONE**

هیچ برچسبی که به Core Fundamental وابسته باشد بدون State بنیادی معتبر صادر نمی‌شود.

## قانون ثابت از این به بعد

1. بنیاد هر روز از صفر محاسبه نمی‌شود.
2. اگر State بنیادی وجود دارد و گزارش بنیادی جدید نیامده: Score عیناً حفظ می‌شود و `UNCHANGED` ثبت می‌شود.
3. اگر گزارش بنیادی جدید آمده: فقط `Fundamental Review Required = YES` می‌شود تا Auditor بررسی کند.
4. اگر State وجود ندارد: `DATA_NOT_VERIFIED` یا `INITIAL_BASELINE` معتبر؛ نه Score حدسی و نه UNCHANGED ساختگی.
5. تغییرات روزانه قیمت، Tape، صف، تکنیکال یا جو بازار Core Fundamental را تغییر نمی‌دهد.

این گزارش توصیه خرید یا فروش نیست.
