---
title: Платформа агентов Claude Code — что реально умеют сотрудники компании
status: VERIFIED
updated: 2026-11-20
owner: hr-director
tags: [claude-code, agents, subagents, memory, skills, hr]
sources:
  - https://code.claude.com/docs/en/setup и https://code.claude.com/docs/en/desktop-quickstart (прочитано 2026-11-20): установка на Windows
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
- Новый процесс Claude Code видит всех агентов сразу (проверено `claude -p`). В следующих сессиях агенты работают нативно. Подтверждено: после перезапуска рабочего процесса этой же облачной сессии все 10 агентов появились в инструменте Agent.
- Рабочий обходной путь внутри такой сессии: `claude -p "Делегируй агенту <имя>: …" --model haiku --permission-mode auto --output-format json`. Это отдельный процесс; агент работает со своим промптом, моделью и памятью, а JSON даёт стоимость и токены по моделям. Пример: аудит qa-lead — 97 с, $0.235 (haiku-оркестратор $0.007, sonnet-агент $0.228).

## Компания на ПК заказчика (Windows, проверено 2026-11-20)
- Установка Claude Code: PowerShell без прав администратора — `irm https://claude.ai/install.ps1 | iex` (обновляется сам) или `winget install Anthropic.ClaudeCode` (обновлять: `winget upgrade Anthropic.ClaudeCode`). Требование: Windows 10 1809+. Без терминала — приложение Claude, вкладка Code, среда **Local** и папка проекта.
- Git for Windows желателен: с ним у Claude есть Bash (Git Bash), без него — только PowerShell.
- Агенты, навыки и память — проектные (`.claude/agents`, `.claude/skills`, `.claude/agent-memory`): появляются, когда `claude` запущен в клоне репозитория на ветке компании. Проверка: `/agents`. Обновление с облачной сессии: `git pull`.
- `./dzm` на Windows: в Git Bash сам ищет `python3`, `python` или `py -3`; в PowerShell/CMD — `.\dzm.cmd`. Нужен Python 3.8+ (`winget install Python.Python.3.13`). Концы строк для `dzm` закреплены в `.gitattributes` (LF).
- Наблюдение: в локальной сессии заказчика по умолчанию включён auto mode; для правок файлов игры и сервера лучше обычный режим с подтверждением (Shift+Tab).

## Как проверено
Документация прочитана из контейнера, официальный валидатор прошёл. Тестовый запуск встроенного агента web-fetch вернул usage: 8 718 токенов. Новый процесс `claude -p` перечислил всех 10 агентов и выполнил делегирование нативному qa-lead.
