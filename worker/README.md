# Сервер магазина DAWNLINE

Небольшой сервер на Cloudflare Workers (бесплатный тариф). Все данные хранятся в самом воркере: это Durable Object со встроенной базой SQLite.

Что он делает:
- **вход через Steam**: проверяет ответ Steam, чтобы вход нельзя было подделать;
- **продукты мастерской**: название, описание, цена, фото, ссылка на скачивание. Всё это добавляется в админке на сайте;
- **верификацию покупателей**: название проекта, Discord ID, IP, Port, QPort и рассказ о проекте. Заявку одобряет администратор;
- **баланс**: онлайн через Google Pay (Stripe) или вручную по заявке (Boosty или перевод);
- **покупки**: деньги списываются одной транзакцией, ссылку на скачивание видят только покупатели;
- **отзывы** (только от покупателей) и **лайки**;
- **админку**: верификация, пополнения, продукты, игроки, возвраты, блокировка.

## Переменные воркера

| Имя | Тип | Значение |
|---|---|---|
| `SITE_URL` | Text | `https://danill228228.github.io/rusforma_vehicles_cfgeventspawn/` |
| `SESSION_SECRET` | Secret | длинная случайная строка (не короче 24 символов) |
| `ADMIN_CLAIM_CODE` | Secret | одноразовый код администратора: вводится в кабинете → «Я владелец магазина» |
| `STRIPE_SECRET_KEY` | Secret | ключ Stripe с правами PaymentIntents: Write, см. ниже |
| `STRIPE_PUBLISHABLE_KEY` | Text | публичный ключ Stripe `pk_…` для кнопки Google Pay |
| `STEAM_API_KEY` | Secret | необязательно: ник и аватар игрока подтягиваются надёжнее |
| `ADMIN_STEAM_IDS` | Text | необязательно: Steam ID администраторов через запятую |
| `CURRENCY` / `CURRENCY_SIGN` | Text | `usd` / `$` |

Привязка хранилища: Durable Object `SHOP` → класс `Shop` (SQLite).

## Подключить оплату через Google Pay (Stripe)

Магазин работает в долларах (USD). Онлайн-оплата — только через Google Pay: в кабинете показывается кнопка Google Pay, формы для ввода карты нет.

1. Зарегистрируйся на https://dashboard.stripe.com/register, укажи свою страну и счёт для выплат.
2. **Settings → Payment methods → Google Pay**: включи.
3. **Settings → Payment methods → Payment method domains → Add domain**: `danill228228.github.io`. Без этого кнопка Google Pay на сайте не появится.
4. **Developers → API keys**:
   - **Publishable key** (`pk_live_…`) — публичный ключ, его не нужно скрывать. Добавь в Cloudflare как **Text**-переменную `STRIPE_PUBLISHABLE_KEY`.
   - **Create restricted key**: права **PaymentIntents: Write**, остальное None. Ключ `rk_live_…` добавь в Cloudflare как **Secret** `STRIPE_SECRET_KEY`.
5. Cloudflare → Workers & Pages → `dawnline` → **Settings → Variables and Secrets** → **Deploy**.

Баланс пополняется только после того, как Stripe подтвердил оплату. Google Pay доступен в Chrome на Android и на компьютере, если в аккаунте Google сохранена карта. На iPhone кнопки не будет: там вместо Google Pay работает Apple Pay.

## Ручное пополнение (Boosty или перевод)

Админка → «Ручное пополнение»: укажи ссылку на Boosty и/или реквизиты. Игрок создаёт заявку с кодом `TOP-…` и указывает этот код при оплате. Когда деньги придут, нажми в админке «Деньги пришли».

## Обновить сервер из командной строки

```
cd worker
npx wrangler deploy
```
