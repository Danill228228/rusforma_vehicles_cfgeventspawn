# Память агента hr-director

- 2026-11-20: штат 10 субагентов + CEO (основная сессия) + client. Триггеры найма — Company/HR/STAFFING_PLAN.md.
- Платформа: агенты подхватываются без перезапуска; вложенность до 3 уровней; memory: project → .claude/agent-memory. Проверка: ./dzm roster --check и claude plugin validate .claude/agents.
