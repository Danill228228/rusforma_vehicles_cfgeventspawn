---
title: Платформа агентов Claude Code — что реально умеют сотрудники компании
status: VERIFIED
updated: 2026-11-20
owner: hr-director
tags: [claude-code, agents, subagents, memory, skills, hr]
sources:
  - https://code.claude.com/docs/en/sub-agents (прочитано 2026-11-20, Claude Code 2.1.329)
  - https://code.claude.com/docs/en/skills
  - experiment:2026-11-20 claude plugin validate .claude/agents → Validation passed; запуск агента через Agent вернул usage (токены, вызовы инструментов, длительность)
  - experiment:2026-11-20 claude -p в новом процессе видит все 10 агентов; аудит qa-lead через claude -p — 97 с, $0.235 (QA/Reports/EVIDENCE-2026-11-20-pipelines.md)
---
# Платформа агентов Claude Code

## Кратко
Сотрудник — это Markdown-файл в `.claude/agents/` с YAML-шапкой (name, description, tools, model, memory…) и системным промптом в теле. Изменения подхватываются без перезапуска. Субагенты могут вызывать своих субагентов до 3 уровней вниз. Память `memory: project` хранится в `.claude/agent-memory/<имя>/` (в git); первые 200 строк MEMORY.md подгружаются автоматически.

## Подробно
- Поля шапки: name и description (обязательны), tools, disallowedTools, model (sonnet, opus, haiku, fable, полный ID, inherit), permissionMode, maxTurns, skills, mcpServers, hooks, memory (user, project, local), background, effort, isolation (worktree), color, initialPrompt, omitClaudeMd. Неизвестные поля молча игнорируются.
- Субагент получает свой промпт, CLAUDE.md проекта и git status, но не историю чата CEO.
- Основная сессия по умолчанию запускает субагентов в фоне. У фоновых урезанный набор инструментов: Read, Grep, Glob, Bash, Edit, Write, WebFetch, WebSearch, Skill, SendMessage и другие.
- Глубина вложенности по умолчанию 3 уровня (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`), одновременно до 20 субагентов.
- SendMessage возобновляет завершённого агента с полным контекстом.
- Субагентам недоступны AskUserQuestion (вопросы заказчику задаёт только CEO) и режим планирования.
- Скиллы: `.claude/skills/<имя>/SKILL.md` (name, description, argument-hint, allowed-tools, model, context: fork…), вызываются командой `/<имя>`.
- Результат запуска агента содержит usage: токены, число вызовов инструментов и длительность. Это источник данных для `./dzm run log`.

## Наблюдение в облачной сессии (2026-11-20)
- В сессии, где папки `.claude/` не было на старте, агенты, созданные по ходу работы, в инструменте Agent не появились («Agent type not found»), хотя документация обещает отслеживание без перезапуска. Видимо, наблюдатель не следит за папкой, которой не было при запуске (гипотеза).
- Новый процесс Claude Code видит всех агентов сразу (проверено `claude -p`). В следующих сессиях агенты работают нативно.
- Рабочий обходной путь внутри такой сессии: `claude -p "Делегируй агенту <имя>: …" --model haiku --permission-mode auto --output-format json`. Это отдельный процесс; агент работает со своим промптом, моделью и памятью, а JSON даёт стоимость и токены по моделям. Пример: аудит qa-lead — 97 с, $0.235 (haiku-оркестратор $0.007, sonnet-агент $0.228).

## Как проверено
Документация прочитана из контейнера, официальный валидатор прошёл. Тестовый запуск встроенного агента web-fetch вернул usage: 8 718 токенов. Новый процесс `claude -p` перечислил всех 10 агентов и выполнил делегирование нативному qa-lead.
