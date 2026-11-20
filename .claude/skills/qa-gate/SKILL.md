---
name: qa-gate
description: Провести результат через контроль качества (10 стадий) перед приёмкой — делегировать qa-lead, записать вердикт, при FAIL вернуть на исправление. Используй, когда задача переходит в REVIEW или заказчик спрашивает, готово ли.
argument-hint: "[T-XXXX]"
---
1. `./dzm task show $ARGUMENTS`: есть результат и файлы, статус REVIEW (если нет — исполнитель сначала переводит задачу).
2. Делегируй qa-lead: ID задачи, файлы, применимые стадии из `AI_Company_DayZMods/Company/Rules/QUALITY_GATES.md`, критерии приёмки из PROJECT.md. Вердикт — через `./dzm task review`, ошибки — через `./dzm bug add`.
3. `./dzm run log --agent qa-lead --tokens <usage> --task $ARGUMENTS`.
4. FAIL: задача уходит в FIXING. Делегируй исполнителю исправление с номерами BUG-XXXX, затем снова запусти этот скилл. PASS: `./dzm task status $ARGUMENTS COMPLETED --by ceo`, если QA не закрыл задачу сам (`--complete`).
5. Стадии NOT RUN (нужен ПК заказчика) — выдай заказчику сценарий ручного теста. Не объявляй «готово», пока они не пройдены или заказчик явно не принял риск.
