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

## Как проверено
Документация прочитана из контейнера, официальный валидатор прошёл. Тестовый запуск встроенного агента web-fetch вернул usage: 8 718 токенов.
