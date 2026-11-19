# Сервер комментариев DawnLine (вход через Steam)

Маленький сервер на Cloudflare Workers (бесплатно). Он отвечает за две вещи:

- вход через Steam: проверяет ответ Steam, чтобы вход нельзя было подделать;
- хранит комментарии игроков под модами в базе Cloudflare D1.

Пока сервер не запущен, на сайте нет кнопки «Обсуждение», а всё остальное работает как обычно.

## Запуск через сайт Cloudflare (без установки программ)

1. Зарегистрируйся на https://dash.cloudflare.com (бесплатный тариф).
2. **База:** Storage & Databases → **D1** → Create → имя `dawnline-comments` → Create.
3. **Сервер:** Workers & Pages → Create → **Create Worker** → имя `dawnline-comments` → Deploy.
4. Нажми **Edit code**, удали пример, вставь весь файл `worker/src/index.js` и нажми **Deploy**.
5. Открой воркер → **Settings → Bindings → Add → D1 database**:
   - Variable name: `DB`;
   - база: `dawnline-comments`.
6. **Settings → Variables and Secrets → Add**:

   | Имя | Тип | Значение |
   |---|---|---|
   | `SITE_URL` | Text | `https://danill228228.github.io/rusforma_vehicles_cfgeventspawn/` |
   | `ADMIN_STEAM_IDS` | Text | твой Steam ID: 17 цифр, несколько — через запятую |
   | `SESSION_SECRET` | **Secret** | любая длинная случайная строка, не короче 24 символов |
   | `STEAM_API_KEY` | **Secret** | необязательно, см. ниже |

7. Скопируй адрес воркера, вида `https://dawnline-comments.<имя>.workers.dev`. Его нужно вписать в `index.html` в `CONFIG.commentsApi`, это сделает Claude.

### Где взять Steam ID

Steam → твой профиль → «Об аккаунте» (Account details). Там под ником написан Steam ID из 17 цифр, он начинается с `7656119…`. Ещё его видно в адресе профиля: `steamcommunity.com/profiles/7656119…`.

### Ключ Steam Web API (необязательно)

Нужен, чтобы ники и аватары игроков подтягивались надёжнее. Его можно получить на https://steamcommunity.com/dev/apikey: в поле домена укажи `danill228228.github.io`. Steam выдаёт ключ только аккаунтам, на которых было потрачено от $5. Без ключа ник берётся из публичного профиля игрока, а если это не получилось, игрок подписывается как «Игрок …1234».

## Что умеет сервер

- Игрок входит через Steam. Сайт получает только его Steam ID, ник и аватар, пароль остаётся у Steam.
- Комментарий — не больше 1000 символов. Писать можно не чаще одного раза в 20 секунд.
- Игрок может удалить свой комментарий.
- Администраторы из `ADMIN_STEAM_IDS` могут удалить любой комментарий и заблокировать игрока. После блокировки все его комментарии удаляются, и писать он больше не может.
- Таблицы в базе создаются сами при первом запросе.

## Запуск из командной строки (для разработчика)

```
cd worker
npx wrangler d1 create dawnline-comments   # вставь database_id в wrangler.toml
npx wrangler secret put SESSION_SECRET
npx wrangler deploy
```
