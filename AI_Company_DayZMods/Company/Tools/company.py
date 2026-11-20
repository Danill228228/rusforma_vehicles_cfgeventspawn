#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dzm — операционная система AI Company DayZMods.

Задачи, проекты, баги QA, ростер агентов (HR), база знаний, учёт ресурсов и отчёты.
Только стандартная библиотека Python 3.9+. Все данные — JSON/Markdown внутри репозитория,
поэтому они переживают сессии через git (облачный контейнер эфемерен: коммитьте и пушьте).

Запуск из корня репозитория:  ./dzm <команда> ...
Справка:                      ./dzm -h   |   ./dzm task -h   |   ./dzm task add -h
Тестовый запуск в песочнице:  DZM_ROOT=/tmp/x/AI_Company_DayZMods DZM_REPO=/tmp/x ./dzm init
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(os.environ.get("DZM_ROOT") or Path(__file__).resolve().parents[2])  # .../AI_Company_DayZMods
REPO = Path(os.environ.get("DZM_REPO") or ROOT.parent)                           # корень git-репозитория


def P(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


TASKS_DB = P("Company", "Tasks", "tasks.json")
RUNS_LOG = P("Company", "Tasks", "runs.jsonl")
BOARD_MD = P("Company", "Tasks", "BOARD.md")
ROSTER_DB = P("Company", "HR", "roster.json")
ROSTER_MD = P("Company", "HR", "ROSTER.md")
AGENT_TEMPLATE = P("Company", "HR", "templates", "AGENT_TEMPLATE.md")
RETIRED_DIR = P("Company", "HR", "retired")
BUGS_DB = P("QA", "Bugs", "bugs.json")
BUGS_MD = P("QA", "Bugs", "BUGS.md")
KB_DIR = P("Knowledge_Base")
KB_INDEX = P("Knowledge_Base", "INDEX.md")
PROJECT_TEMPLATE = P("Projects", "TEMPLATE_PROJECT.md")
AGENTS_DIR = REPO / ".claude" / "agents"
MEMORY_DIR = REPO / ".claude" / "agent-memory"

TREE = [
    "Company/CEO", "Company/HR/templates", "Company/HR/retired", "Company/Departments",
    "Company/Rules", "Company/Tasks", "Company/Tools",
    "Knowledge_Base/DayZ_Engine", "Knowledge_Base/Enforce_Script", "Knowledge_Base/Configs",
    "Knowledge_Base/Modding", "Knowledge_Base/Networking", "Knowledge_Base/Animations",
    "Knowledge_Base/Vehicles", "Knowledge_Base/Research", "Knowledge_Base/Tools",
    "Projects/Active", "Projects/Completed", "Projects/Archived",
    "Development/Source", "Development/Models", "Development/Textures", "Development/Scripts",
    "Development/Configs", "Development/Builds",
    "QA/Tests", "QA/Bugs", "QA/Reports",
    "Media/Scripts", "Media/Storyboards", "Media/Footage", "Media/Finished",
    "Reports/Daily", "Reports/Weekly", "Reports/Project_Reports",
]

STATUSES = ["NEW", "PLANNING", "RESEARCH", "IN_PROGRESS", "REVIEW", "TESTING", "FIXING", "COMPLETED", "BLOCKED"]
STATUS_RU = {
    "NEW": "новая", "PLANNING": "планирование", "RESEARCH": "исследование", "IN_PROGRESS": "выполняется",
    "REVIEW": "проверка", "TESTING": "тестирование", "FIXING": "исправление", "COMPLETED": "завершено",
    "BLOCKED": "заблокировано",
}
TRANSITIONS = {
    "NEW": {"PLANNING", "RESEARCH", "IN_PROGRESS", "BLOCKED"},
    "PLANNING": {"NEW", "RESEARCH", "IN_PROGRESS", "BLOCKED"},
    "RESEARCH": {"PLANNING", "IN_PROGRESS", "REVIEW", "BLOCKED"},
    "IN_PROGRESS": {"RESEARCH", "REVIEW", "BLOCKED"},
    "REVIEW": {"TESTING", "FIXING", "COMPLETED", "BLOCKED"},
    "TESTING": {"FIXING", "COMPLETED", "BLOCKED"},
    "FIXING": {"REVIEW", "TESTING", "BLOCKED"},
    "BLOCKED": {"NEW", "PLANNING", "RESEARCH", "IN_PROGRESS", "REVIEW", "TESTING", "FIXING"},
    "COMPLETED": {"FIXING"},  # переоткрытие при регрессии (только с --note)
}
WORK_STATES = {"RESEARCH", "IN_PROGRESS", "REVIEW", "TESTING", "FIXING", "COMPLETED"}
ACTIVE_STATES = {"PLANNING", "RESEARCH", "IN_PROGRESS", "REVIEW", "TESTING", "FIXING"}
PRIORITIES = ["P0", "P1", "P2", "P3"]
TASK_TYPES = ["research", "dev", "config", "art", "build", "qa", "media", "planning", "hr", "ops"]
QA_REQUIRED_TYPES = {"dev", "config", "art", "build"}  # такие задачи закрывает только отдел QA
SEVERITIES = {"S1": "Критическая", "S2": "Серьёзная", "S3": "Средняя", "S4": "Низкая"}
BUG_STATUSES = ["OPEN", "FIXING", "RETEST", "CLOSED", "WONTFIX"]
BUG_TRANSITIONS = {
    "OPEN": {"FIXING", "RETEST", "WONTFIX"},
    "FIXING": {"RETEST", "WONTFIX", "OPEN"},
    "RETEST": {"FIXING"},           # CLOSED — только через `bug retest --result PASS`
    "CLOSED": {"FIXING"},           # регрессия
    "WONTFIX": {"OPEN"},
}
KB_MIN_SOURCES = {"VERIFIED": 2, "PARTIAL": 1, "HYPOTHESIS": 0, "OUTDATED": 0}
KB_SKIP = {"README.md", "INDEX.md", "SOURCES.md"}
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")


class DzmError(Exception):
    pass


# ----------------------------------------------------------------------------- утилиты
def today() -> str:
    return dt.date.today().isoformat()


def now() -> str:
    return dt.datetime.now().isoformat(timespec="minutes")


def check_date(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        raise DzmError(f"Неверная дата '{value}', нужен формат ГГГГ-ММ-ДД")


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in re.split(r"[,\s]+", value) if x.strip()]


def short(text: str, n: int = 70) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def md_cell(text) -> str:
    return str(text if text not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
     "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"],
))


def slugify(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch in TRANSLIT:
            out.append(TRANSLIT[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    slug = re.sub(r"_+", "_", "".join(out)).strip("_")
    return slug[:48] or "project"


def parse_frontmatter(text: str) -> dict:
    """Минимальный парсер YAML-подмножества: `key: value`, `key: [a, b]`, блочные списки `- item`."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    data: dict = {}
    key = None
    for raw in text[3:end].splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s+-\s+(.*)$", line)
        if m and key:
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(m.group(1).strip().strip("'\""))
            continue
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                data[key] = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
            elif val in (">", "|", ">-", "|-"):
                data[key] = ""
            else:
                data[key] = val.strip("'\"")
        elif key and isinstance(data.get(key), str):
            data[key] = (data[key] + " " + line.strip()).strip()  # продолжение многострочного значения
    return data


# ----------------------------------------------------------------------------- хранилища
def tasks_db() -> dict:
    return load_json(TASKS_DB, {"version": 1, "next_task": 1, "next_project": 1, "projects": [], "tasks": []})


def roster_db() -> dict:
    return load_json(ROSTER_DB, {"version": 1, "agents": {}})


def bugs_db() -> dict:
    return load_json(BUGS_DB, {"version": 1, "next": 1, "bugs": []})


def load_runs() -> list[dict]:
    if not RUNS_LOG.exists():
        return []
    runs = []
    for n, line in enumerate(RUNS_LOG.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                raise DzmError(f"runs.jsonl: битая строка {n}")
    return runs


def find(items: list[dict], id_: str, what: str) -> dict:
    for it in items:
        if it["id"] == id_.upper():
            return it
    raise DzmError(f"{what} {id_} не найден(а)")


def check_actor(name: str, roster: dict | None = None) -> dict:
    roster = roster or roster_db()
    agent = roster["agents"].get(name)
    if not agent:
        raise DzmError(f"Неизвестный сотрудник '{name}'. Список: ./dzm roster")
    if agent.get("status") == "RETIRED":
        raise DzmError(f"Сотрудник '{name}' выведен из штата (RETIRED)")
    return agent


def log_event(item: dict, by: str, kind: str, text: str, to: str | None = None) -> None:
    entry = {"at": now(), "by": by, "kind": kind, "text": text}
    if to:
        entry["to"] = to
    item.setdefault("log", []).append(entry)
    item["updated"] = now()


def save_tasks(d: dict) -> None:
    save_json(TASKS_DB, d)
    render_board(d)


def save_roster(r: dict) -> None:
    save_json(ROSTER_DB, r)
    render_roster(r)


def save_bugs(b: dict) -> None:
    save_json(BUGS_DB, b)
    render_bugs(b)


# ----------------------------------------------------------------------------- задачи
def deps_cycle(tasks: list[dict]) -> list[str] | None:
    graph = {t["id"]: t.get("deps", []) for t in tasks}
    state: dict[str, int] = {}
    stack: list[str] = []

    def dfs(node: str):
        state[node] = 1
        stack.append(node)
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt):] + [nxt]
            if state.get(nxt) is None and nxt in graph:
                found = dfs(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = 2
        return None

    for node in graph:
        if state.get(node) is None:
            found = dfs(node)
            if found:
                return found
    return None


def pending_deps(d: dict, t: dict) -> list[str]:
    return [dep for dep in t.get("deps", []) if find(d["tasks"], dep, "Задача")["status"] != "COMPLETED"]


def completion_problem(t: dict, roster: dict) -> str | None:
    if not t.get("reviews"):
        return (f"{t['id']}: нет отчёта о проверке. Сначала: ./dzm task review {t['id']} "
                f"--by <проверяющий> --verdict PASS --report \"...\"")
    last = t["reviews"][-1]
    if last["verdict"] != "PASS":
        return f"{t['id']}: последняя проверка — {last['verdict']}. Нужны исправление и повторная проверка"
    if last["by"] == t["assignee"]:
        return f"{t['id']}: самопроверка не засчитывается — проверяющий должен отличаться от исполнителя"
    if t["type"] in QA_REQUIRED_TYPES:
        dept = roster["agents"].get(last["by"], {}).get("department")
        if dept != "QA":
            return f"{t['id']}: задачи типа '{t['type']}' закрывает только отдел QA (проверял {last['by']})"
    return None


def set_status(d: dict, t: dict, new: str, by: str, note: str | None, roster: dict) -> None:
    new = new.upper()
    old = t["status"]
    if new not in STATUSES:
        raise DzmError(f"Неизвестный статус {new}. Допустимо: {', '.join(STATUSES)}")
    if new == old:
        raise DzmError(f"{t['id']} уже в статусе {old}")
    if new not in TRANSITIONS[old]:
        raise DzmError(f"Переход {old} → {new} запрещён. Из {old} можно: {', '.join(sorted(TRANSITIONS[old]))}")
    if new == "BLOCKED" and not note:
        raise DzmError("Для BLOCKED обязательна причина: --note \"...\"")
    if old == "COMPLETED" and not note:
        raise DzmError("Переоткрытие завершённой задачи требует причину: --note \"...\"")
    if new in WORK_STATES:
        pend = pending_deps(d, t)
        if pend:
            raise DzmError(f"Нельзя перевести {t['id']} в {new}: не завершены зависимости {', '.join(pend)}")
    if new == "REVIEW" and not t.get("result"):
        raise DzmError(f"{t['id']}: перед проверкой заполните результат: ./dzm task update {t['id']} --result \"...\"")
    if new == "COMPLETED":
        problem = completion_problem(t, roster)
        if problem:
            raise DzmError(problem)
    t["status"] = new
    if new == "BLOCKED":
        t["blocked_reason"] = note
    elif old == "BLOCKED":
        t.pop("blocked_reason", None)
    if new == "COMPLETED":
        t["completed"] = now()
    log_event(t, by, "status", f"{old} → {new}" + (f": {note}" if note else ""))


def cmd_task_add(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.by, r)
    check_actor(a.assignee, r)
    project = None
    if a.project:
        project = find(d["projects"], a.project, "Проект")["id"]
    deps = [x.upper() for x in split_list(a.deps)]
    for dep in deps:
        find(d["tasks"], dep, "Задача-зависимость")
    tid = f"T-{d['next_task']:04d}"
    t = {
        "id": tid, "title": a.title, "description": a.desc or "", "project": project, "type": a.type,
        "assignee": a.assignee, "priority": a.priority, "status": "NEW", "due": check_date(a.due),
        "deps": deps, "budget": a.budget, "result": "", "files": split_list(a.files), "reviews": [],
        "log": [], "created": now(), "updated": now(),
    }
    log_event(t, a.by, "create", "задача создана")
    d["tasks"].append(t)
    d["next_task"] += 1
    save_tasks(d)
    print(f"{tid} создана: {a.title} → {a.assignee} [{a.priority}, {a.type}]" + (f", зависит от {', '.join(deps)}" if deps else ""))


def cmd_task_status(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.by, r)
    t = find(d["tasks"], a.id, "Задача")
    old = t["status"]
    set_status(d, t, a.status, a.by, a.note, r)
    save_tasks(d)
    print(f"{t['id']}: {old} → {t['status']}")


def cmd_task_update(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.by, r)
    t = find(d["tasks"], a.id, "Задача")
    changes = []
    for field, value in (("title", a.title), ("description", a.desc), ("priority", a.priority), ("type", a.type)):
        if value is not None:
            t[field] = value
            changes.append(field)
    if a.assignee:
        check_actor(a.assignee, r)
        t["assignee"] = a.assignee
        changes.append("assignee")
    if a.project is not None:
        t["project"] = find(d["projects"], a.project, "Проект")["id"] if a.project else None
        changes.append("project")
    if a.due is not None:
        t["due"] = check_date(a.due)
        changes.append("due")
    if a.budget is not None:
        t["budget"] = a.budget
        changes.append("budget")
    if a.result is not None:
        t["result"] = a.result
        changes.append("result")
    if a.files:
        t["files"] = sorted(set(t.get("files", [])) | set(split_list(a.files)))
        changes.append("files")
    if a.deps is not None or a.add_deps:
        deps = [x.upper() for x in split_list(a.deps)] if a.deps is not None else list(t["deps"])
        deps += [x.upper() for x in split_list(a.add_deps) if x.upper() not in deps]
        for dep in deps:
            if dep == t["id"]:
                raise DzmError("Задача не может зависеть сама от себя")
            find(d["tasks"], dep, "Задача-зависимость")
        old_deps, t["deps"] = t["deps"], deps
        cycle = deps_cycle(d["tasks"])
        if cycle:
            t["deps"] = old_deps
            raise DzmError("Циклическая зависимость: " + " → ".join(cycle))
        changes.append("deps")
    if not changes:
        raise DzmError("Нечего менять: укажите хотя бы одно поле")
    log_event(t, a.by, "update", "изменено: " + ", ".join(changes))
    save_tasks(d)
    print(f"{t['id']} обновлена: {', '.join(changes)}")


def cmd_task_review(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.by, r)
    t = find(d["tasks"], a.id, "Задача")
    verdict = a.verdict.upper()
    if t["status"] not in ("REVIEW", "TESTING"):
        raise DzmError(f"Проверка возможна в статусах REVIEW/TESTING (сейчас {t['status']})")
    if a.by == t["assignee"]:
        raise DzmError("Исполнитель не может проверять собственную задачу")
    t["reviews"].append({"at": now(), "by": a.by, "verdict": verdict, "report": a.report})
    log_event(t, a.by, "review", f"{verdict}: {short(a.report, 200)}")
    if verdict == "FAIL":
        set_status(d, t, "FIXING", a.by, "проверка не пройдена", r)
    elif a.complete:
        set_status(d, t, "COMPLETED", a.by, None, r)
    save_tasks(d)
    print(f"{t['id']}: проверка {verdict} от {a.by} → статус {t['status']}")


def cmd_task_comment(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.by, r)
    if a.to:
        check_actor(a.to, r)
    t = find(d["tasks"], a.id, "Задача")
    log_event(t, a.by, "comment", a.text, to=a.to)
    save_tasks(d)
    print(f"{t['id']}: комментарий от {a.by}" + (f" для {a.to}" if a.to else ""))


def task_line(t: dict) -> str:
    deps = ",".join(t.get("deps", [])) or "-"
    due = t.get("due") or "-"
    return f"{t['id']}  {t['status']:<11} {t['priority']}  {t['assignee']:<22} {due:<10}  {short(t['title'], 60)}  [deps: {deps}]"


def cmd_task_list(a):
    d = tasks_db()
    items = d["tasks"]
    if a.status:
        wanted = {s.upper() for s in split_list(a.status)}
        items = [t for t in items if t["status"] in wanted]
    elif not a.all:
        items = [t for t in items if t["status"] != "COMPLETED"]
    if a.assignee:
        items = [t for t in items if t["assignee"] == a.assignee]
    if a.project:
        items = [t for t in items if (t.get("project") or "") == a.project.upper()]
    if not items:
        print("Задач не найдено")
        return
    for t in sorted(items, key=lambda t: (PRIORITIES.index(t["priority"]), t["id"])):
        print(task_line(t))
    print(f"— всего: {len(items)}")


def cmd_task_show(a):
    d = tasks_db()
    t = find(d["tasks"], a.id, "Задача")
    print(f"{t['id']} — {t['title']}")
    for key in ("status", "priority", "type", "assignee", "project", "due", "budget", "created", "updated"):
        print(f"  {key:<10}: {t.get(key) if t.get(key) not in (None, '') else '—'}")
    if t.get("blocked_reason"):
        print(f"  blocked   : {t['blocked_reason']}")
    print(f"  deps      : {', '.join(t['deps']) or '—'}" + (f"  (не завершены: {', '.join(pending_deps(d, t))})" if pending_deps(d, t) else ""))
    print(f"  files     : {', '.join(t.get('files', [])) or '—'}")
    print(f"  описание  : {t.get('description') or '—'}")
    print(f"  результат : {t.get('result') or '—'}")
    for rv in t.get("reviews", []):
        print(f"  проверка  : {rv['at']} {rv['by']} {rv['verdict']}: {rv['report']}")
    print("  журнал:")
    for e in t.get("log", [])[-15:]:
        to = f" → {e['to']}" if e.get("to") else ""
        print(f"    {e['at']} [{e['kind']}] {e['by']}{to}: {e['text']}")


def cmd_inbox(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.agent, r)
    mine = [t for t in d["tasks"] if t["assignee"] == a.agent and t["status"] != "COMPLETED"]
    print(f"Входящие для {a.agent}")
    if mine:
        print("Задачи:")
        for t in sorted(mine, key=lambda t: (PRIORITIES.index(t["priority"]), t["id"])):
            ready = "готова к работе" if not pending_deps(d, t) else "ждёт: " + ",".join(pending_deps(d, t))
            print("  " + task_line(t) + f"  ({ready})")
    else:
        print("Задачи: нет")
    msgs = [(e, t["id"]) for t in d["tasks"] for e in t.get("log", []) if e.get("kind") == "comment" and e.get("to") == a.agent]
    msgs.sort(key=lambda x: x[0]["at"])
    print("Сообщения:" if msgs else "Сообщения: нет")
    for e, tid in msgs[-a.limit:]:
        print(f"  {e['at']} {tid} от {e['by']}: {e['text']}")


# ----------------------------------------------------------------------------- проекты
def cmd_project_add(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.owner, r)
    pid = f"PRJ-{d['next_project']:04d}"
    folder = P("Projects", "Active", f"{pid}_{slugify(a.name)}")
    if folder.exists():
        raise DzmError(f"Папка {rel(folder)} уже существует")
    template = PROJECT_TEMPLATE.read_text(encoding="utf-8") if PROJECT_TEMPLATE.exists() else "# {{ID}} — {{NAME}}\n\n{{DESCRIPTION}}\n"
    text = (template.replace("{{ID}}", pid).replace("{{NAME}}", a.name).replace("{{OWNER}}", a.owner)
            .replace("{{DATE}}", today()).replace("{{DESCRIPTION}}", a.desc or "—"))
    write_text(folder / "PROJECT.md", text)
    d["projects"].append({"id": pid, "name": a.name, "description": a.desc or "", "owner": a.owner,
                          "status": "ACTIVE", "created": today(), "dir": rel(folder)})
    d["next_project"] += 1
    save_tasks(d)
    print(f"{pid} создан: {a.name} → {rel(folder)}")


def project_progress(d: dict, pid: str) -> tuple[int, int]:
    items = [t for t in d["tasks"] if t.get("project") == pid]
    return sum(1 for t in items if t["status"] == "COMPLETED"), len(items)


def cmd_project_list(a):
    d = tasks_db()
    if not d["projects"]:
        print("Проектов нет")
    for p in d["projects"]:
        done, total = project_progress(d, p["id"])
        print(f"{p['id']}  {p['status']:<9} {done}/{total} задач  {p['owner']:<16} {p['name']}  ({p['dir']})")


def move_project(d: dict, p: dict, bucket: str) -> None:
    src = REPO / p["dir"]
    dst = P("Projects", bucket, src.name)
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    p["dir"] = rel(dst)


def cmd_project_close(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.by, r)
    p = find(d["projects"], a.id, "Проект")
    if p["status"] != "ACTIVE":
        raise DzmError(f"{p['id']} не активен ({p['status']})")
    opened = [t["id"] for t in d["tasks"] if t.get("project") == p["id"] and t["status"] != "COMPLETED"]
    if opened:
        raise DzmError(f"Нельзя закрыть {p['id']}: не завершены задачи {', '.join(opened)}")
    move_project(d, p, "Completed")
    p.update(status="COMPLETED", closed=today(), closed_by=a.by, note=a.note or "")
    save_tasks(d)
    print(f"{p['id']} завершён → {p['dir']}")


def cmd_project_archive(a):
    d, r = tasks_db(), roster_db()
    check_actor(a.by, r)
    p = find(d["projects"], a.id, "Проект")
    move_project(d, p, "Archived")
    p.update(status="ARCHIVED", archived=today(), note=a.note)
    save_tasks(d)
    print(f"{p['id']} в архиве → {p['dir']}")


# ----------------------------------------------------------------------------- баги (QA)
def cmd_bug_add(a):
    b, r = bugs_db(), roster_db()
    check_actor(a.by, r)
    if a.assignee:
        check_actor(a.assignee, r)
    sev = a.severity.upper()
    if sev not in SEVERITIES:
        raise DzmError(f"Критичность: {', '.join(f'{k} ({v})' for k, v in SEVERITIES.items())}")
    for field in ("title", "repro", "cause", "location", "fix"):
        if not (getattr(a, field) or "").strip():
            raise DzmError(f"Поле --{field} обязательно (стандарт отчёта об ошибке, Company/Rules/QUALITY_GATES.md)")
    if a.task:
        find(tasks_db()["tasks"], a.task, "Задача")
    bid = f"BUG-{b['next']:04d}"
    bug = {"id": bid, "title": a.title, "severity": sev, "status": "OPEN", "repro": a.repro, "cause": a.cause,
           "location": a.location, "fix": a.fix, "retests": [], "task": a.task.upper() if a.task else None,
           "found_by": a.by, "assignee": a.assignee, "created": now(), "updated": now(), "log": []}
    log_event(bug, a.by, "create", "ошибка зарегистрирована")
    b["bugs"].append(bug)
    b["next"] += 1
    save_bugs(b)
    print(f"{bid} [{sev}] зарегистрирована: {a.title}")


def cmd_bug_update(a):
    b, r = bugs_db(), roster_db()
    check_actor(a.by, r)
    bug = find(b["bugs"], a.id, "Ошибка")
    changes = []
    for field in ("title", "repro", "cause", "location", "fix"):
        value = getattr(a, field)
        if value:
            bug[field] = value
            changes.append(field)
    if a.assignee:
        check_actor(a.assignee, r)
        bug["assignee"] = a.assignee
        changes.append("assignee")
    if a.status:
        new = a.status.upper()
        if new == "CLOSED":
            raise DzmError("Закрыть ошибку можно только повторным тестом: ./dzm bug retest ID --result PASS ...")
        if new not in BUG_STATUSES or new not in BUG_TRANSITIONS[bug["status"]]:
            raise DzmError(f"Переход {bug['status']} → {new} запрещён. Можно: {', '.join(sorted(BUG_TRANSITIONS[bug['status']]))}")
        if new == "WONTFIX" and not a.note:
            raise DzmError("WONTFIX требует обоснования: --note \"...\"")
        changes.append(f"status {bug['status']} → {new}")
        bug["status"] = new
    if not changes:
        raise DzmError("Нечего менять")
    log_event(bug, a.by, "update", "; ".join(changes) + (f" ({a.note})" if a.note else ""))
    save_bugs(b)
    print(f"{bug['id']} обновлена: {'; '.join(changes)}")


def cmd_bug_retest(a):
    b, r = bugs_db(), roster_db()
    agent = check_actor(a.by, r)
    if agent.get("department") != "QA":
        raise DzmError("Повторное тестирование выполняет отдел QA")
    bug = find(b["bugs"], a.id, "Ошибка")
    result = a.result.upper()
    bug["retests"].append({"at": now(), "by": a.by, "result": result, "notes": a.notes})
    bug["status"] = "CLOSED" if result == "PASS" else "FIXING"
    log_event(bug, a.by, "retest", f"{result}: {a.notes}")
    save_bugs(b)
    print(f"{bug['id']}: повторный тест {result} → {bug['status']}")


def cmd_bug_list(a):
    b = bugs_db()
    items = b["bugs"] if a.all else [x for x in b["bugs"] if x["status"] not in ("CLOSED", "WONTFIX")]
    if not items:
        print("Ошибок нет" if a.all else "Открытых ошибок нет")
    for x in sorted(items, key=lambda x: (x["severity"], x["id"])):
        print(f"{x['id']}  {x['severity']}  {x['status']:<8} {x.get('assignee') or '-':<20} {short(x['title'], 70)}")


def cmd_bug_show(a):
    bug = find(bugs_db()["bugs"], a.id, "Ошибка")
    print(bug_markdown(bug))


def bug_markdown(x: dict) -> str:
    retest = "; ".join(f"{rt['result']} {rt['at']} ({rt['by']}): {rt['notes']}" for rt in x.get("retests", [])) or "ещё не проводилось"
    return "\n".join([
        f"### {x['id']} — {x['title']}",
        f"1. **Название:** {x['title']}",
        f"2. **Критичность:** {x['severity']} ({SEVERITIES[x['severity']]})",
        f"3. **Условия воспроизведения:** {x['repro']}",
        f"4. **Причина:** {x['cause']}",
        f"5. **Файл и место:** {x['location']}",
        f"6. **Предлагаемое исправление:** {x['fix']}",
        f"7. **Повторное тестирование:** {retest}",
        "",
        f"Статус: **{x['status']}** · нашёл: {x['found_by']} · исполнитель: {x.get('assignee') or '—'} · "
        f"задача: {x.get('task') or '—'} · создано: {x['created']}",
    ])


# ----------------------------------------------------------------------------- ростер и HR
def agent_files() -> dict[str, tuple[Path, dict]]:
    found: dict[str, tuple[Path, dict]] = {}
    if AGENTS_DIR.exists():
        for f in sorted(AGENTS_DIR.rglob("*.md")):
            fm = parse_frontmatter(f.read_text(encoding="utf-8"))
            found[fm.get("name") or f"<без имени:{f.name}>"] = (f, fm)
    return found


def roster_problems(r: dict) -> list[str]:
    problems = []
    files = agent_files()
    for name, (f, fm) in files.items():
        if name.startswith("<без имени"):
            problems.append(f"{rel(f)}: во frontmatter нет поля name")
            continue
        if not fm.get("description"):
            problems.append(f"{rel(f)}: во frontmatter нет description")
        entry = r["agents"].get(name)
        if not entry or entry.get("kind") != "subagent":
            problems.append(f"{name}: файл агента есть ({rel(f)}), но в ростере нет записи kind=subagent")
        elif entry.get("status") == "RETIRED":
            problems.append(f"{name}: уволен в ростере, но файл всё ещё в .claude/agents")
        elif fm.get("model") and entry.get("model") and fm["model"] != entry["model"]:
            problems.append(f"{name}: модель в файле ({fm['model']}) ≠ модель в ростере ({entry['model']})")
    for name, entry in r["agents"].items():
        if entry.get("kind") == "subagent" and entry.get("status") != "RETIRED" and name not in files:
            problems.append(f"{name}: в ростере, но нет файла в .claude/agents")
        if entry.get("reports_to") and entry["reports_to"] not in r["agents"]:
            problems.append(f"{name}: руководитель '{entry['reports_to']}' не найден в ростере")
    return problems


def tokens_by(runs: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for run in runs:
        k = run.get(key) or "—"
        out[k] = out.get(k, 0) + int(run.get("tokens") or 0)
    return out


def cmd_roster(a):
    r, d = roster_db(), tasks_db()
    tok = tokens_by(load_runs(), "agent")
    print(f"{'агент':<24} {'отдел':<12} {'модель':<8} {'статус':<8} {'акт.':>4} {'токены':>8}  должность")
    for name, ag in sorted(r["agents"].items(), key=lambda x: (x[1].get("department", ""), x[0])):
        active = sum(1 for t in d["tasks"] if t["assignee"] == name and t["status"] in ACTIVE_STATES)
        print(f"{name:<24} {ag.get('department', '-'):<12} {ag.get('model', '-'):<8} {ag.get('status', '-'):<8} "
              f"{active:>4} {tok.get(name, 0):>8}  {ag.get('title', '')}")
    if a.check:
        problems = roster_problems(r)
        print("\nПроверка ростера: " + ("OK" if not problems else f"{len(problems)} проблем(ы)"))
        for p in problems:
            print("  - " + p)
        if problems:
            raise SystemExit(1)


DEFAULT_AGENT_TEMPLATE = """---
name: {{NAME}}
description: {{DESCRIPTION}}
tools: {{TOOLS}}
model: {{MODEL}}
memory: project
---
Ты — {{TITLE}} (отдел {{DEPARTMENT}}) в AI Company DayZMods. Руководитель: {{REPORTS_TO}}.

## Зона ответственности
- (HR: заполнить)

## Порядок работы
1. `./dzm inbox {{NAME}}` и `./dzm task show <ID>` — прочитай задачу и зависимости.
2. `./dzm kb search "<тема>"` — не повторяй уже сделанные исследования.
3. Выполни работу, сохрани файлы в папки проекта, заполни результат: `./dzm task update <ID> --result "..." --files ...`.
4. Передай на проверку: `./dzm task status <ID> REVIEW --by {{NAME}}`.
5. Запиши в свою память 1–3 устойчивых вывода (не пересказ задачи).

Отчёт руководителю — формат «Короткий отчёт» из CLAUDE.md.
"""


def cmd_hr_hire(a):
    r = roster_db()
    check_actor(a.by, r)
    if not NAME_RE.match(a.name):
        raise DzmError("Имя агента: строчные латинские буквы, цифры и дефис, начинается с буквы (например vehicle-systems-engineer)")
    if a.name in r["agents"]:
        raise DzmError(f"'{a.name}' уже есть в ростере")
    if a.reports_to:
        check_actor(a.reports_to, r)
    if a.helper_of:
        check_actor(a.helper_of, r)
    path = AGENTS_DIR / f"{a.name}.md"
    if path.exists():
        raise DzmError(f"Файл {rel(path)} уже существует")
    template = AGENT_TEMPLATE.read_text(encoding="utf-8") if AGENT_TEMPLATE.exists() else DEFAULT_AGENT_TEMPLATE
    text = template
    for key, value in {
        "NAME": a.name, "DESCRIPTION": a.description, "TOOLS": a.tools, "MODEL": a.model, "TITLE": a.title,
        "DEPARTMENT": a.dept, "REPORTS_TO": a.reports_to or a.helper_of or "ceo",
    }.items():
        text = text.replace("{{" + key + "}}", value)
    write_text(path, text)
    r["agents"][a.name] = {
        "title": a.title, "department": a.dept, "model": a.model, "kind": "subagent", "status": "ACTIVE",
        "reports_to": a.reports_to or a.helper_of or "ceo", "helper_of": a.helper_of, "created": today(),
        "created_by": a.by, "reason": a.reason, "file": rel(path),
    }
    mem = MEMORY_DIR / a.name / "MEMORY.md"
    if not mem.exists():
        write_text(mem, f"# Память агента {a.name}\n\n- {today()}: нанят ({a.by}). Причина: {a.reason}\n")
    save_roster(r)
    print(f"Нанят {a.name} ({a.title}, {a.dept}, {a.model}) → {rel(path)}. Доступен для делегирования без перезапуска.")


def cmd_hr_retire(a):
    r = roster_db()
    check_actor(a.by, r)
    ag = check_actor(a.name, r)
    if ag.get("kind") != "subagent":
        raise DzmError("Выводить из штата можно только субагентов")
    src = AGENTS_DIR / f"{a.name}.md"
    if src.exists():
        RETIRED_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(RETIRED_DIR / src.name))
    ag.update(status="RETIRED", retired=today(), retire_reason=a.reason, file=rel(RETIRED_DIR / src.name))
    save_roster(r)
    print(f"{a.name} выведен из штата, файл перемещён в {rel(RETIRED_DIR)}")


# ----------------------------------------------------------------------------- база знаний
def kb_entries():
    if not KB_DIR.exists():
        return
    for f in sorted(KB_DIR.rglob("*.md")):
        if f.parent == KB_DIR and f.name in KB_SKIP:
            continue
        text = f.read_text(encoding="utf-8")
        yield f, parse_frontmatter(text), text


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return value
    return [value] if value else []


def kb_problems() -> list[str]:
    problems = []
    for f, fm, _ in kb_entries():
        name = rel(f)
        if not fm:
            problems.append(f"{name}: нет frontmatter (см. Company/Rules/RESEARCH_PROTOCOL.md)")
            continue
        kind = fm.get("kind", "entry")
        for key in ("title", "updated", "owner"):
            if not fm.get(key):
                problems.append(f"{name}: нет поля {key}")
        if kind == "document":
            continue
        status = fm.get("status")
        if status not in KB_MIN_SOURCES:
            problems.append(f"{name}: статус '{status}' вне {', '.join(KB_MIN_SOURCES)}")
            continue
        n = len(as_list(fm.get("sources")))
        if n < KB_MIN_SOURCES[status]:
            problems.append(f"{name}: статус {status} требует минимум {KB_MIN_SOURCES[status]} источника(ов), указано {n}")
    return problems


def cmd_kb_search(a):
    terms = [t.lower() for t in a.query.split() if t.strip()]
    hits = []
    for f, fm, text in kb_entries():
        low = text.lower()
        if not all(t in low for t in terms):
            continue
        title = (fm.get("title") or f.stem).lower()
        tags = " ".join(as_list(fm.get("tags"))).lower()
        score = sum(5 * (t in title) + 3 * (t in tags) + min(low.count(t), 10) for t in terms)
        snippet = next((ln.strip() for ln in text.splitlines()
                        if any(t in ln.lower() for t in terms) and not ln.startswith(("title:", "tags:"))), "")
        hits.append((score, f, fm, snippet))
    if not hits:
        print(f"По запросу «{a.query}» в базе знаний ничего нет → можно ставить исследование (./dzm task add --type research ...)")
        return
    for score, f, fm, snippet in sorted(hits, key=lambda h: -h[0])[: a.limit]:
        print(f"[{fm.get('status', fm.get('kind', '?'))}] {rel(f)} — {fm.get('title', f.stem)} (обновлено {fm.get('updated', '?')})")
        if snippet:
            print(f"    … {short(snippet, 150)}")


def cmd_kb_index(a=None):
    rows: dict[str, list] = {}
    counts: dict[str, int] = {}
    for f, fm, _ in kb_entries():
        section = f.parent.relative_to(KB_DIR).as_posix() if f.parent != KB_DIR else "."
        status = fm.get("status") or fm.get("kind", "?")
        counts[status] = counts.get(status, 0) + 1
        rows.setdefault(section, []).append((f, fm, status))
    lines = [
        "# Индекс базы знаний", "",
        f"_Автогенерация: `./dzm kb index` · {now()}_", "",
        "Статусы: **VERIFIED** — ≥2 независимых источника или источник + эксперимент; **PARTIAL** — 1 источник; "
        "**HYPOTHESIS** — не подтверждено, нужен эксперимент; **OUTDATED** — устарело.", "",
        "Сводка: " + (" · ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "пусто"), "",
    ]
    for section in sorted(rows):
        lines += [f"## {section}", "", "| Запись | Статус | Обновлено | Владелец | Источников |", "|---|---|---|---|---|"]
        for f, fm, status in rows[section]:
            link = f.relative_to(KB_DIR).as_posix()
            lines.append(f"| [{md_cell(fm.get('title', f.stem))}]({link}) | {status} | {fm.get('updated', '—')} | "
                         f"{fm.get('owner', '—')} | {len(as_list(fm.get('sources')))} |")
        lines.append("")
    write_text(KB_INDEX, "\n".join(lines))
    if a is not None:
        print(f"Индекс обновлён: {rel(KB_INDEX)} ({sum(counts.values())} записей)")


def cmd_kb_new(a):
    target = KB_DIR / a.path
    if target.suffix != ".md":
        target = target.with_suffix(".md")
    if target.exists():
        raise DzmError(f"{rel(target)} уже существует — дополняйте её, а не дублируйте")
    status = a.status.upper()
    if status not in KB_MIN_SOURCES:
        raise DzmError(f"Статус: {', '.join(KB_MIN_SOURCES)}")
    sources = split_list(a.sources)
    tags = split_list(a.tags)
    text = "\n".join([
        "---", f"title: {a.title}", f"status: {status}", f"updated: {today()}", f"owner: {a.owner}",
        f"tags: [{', '.join(tags)}]", "sources:", *[f"  - {s}" for s in sources], "---", "",
        f"# {a.title}", "", "## Кратко", "", "## Подробно", "", "## Как проверено", "",
        "## Ограничения и открытые вопросы", "",
    ])
    write_text(target, text + "\n")
    cmd_kb_index()
    print(f"Создана запись {rel(target)} [{status}] — заполните разделы")


# ----------------------------------------------------------------------------- ресурсы
def cmd_run_log(a):
    r = roster_db()
    agent = r["agents"].get(a.agent)
    if not agent and not a.agent.startswith("builtin:"):
        raise DzmError(f"Неизвестный агент '{a.agent}' (для встроенных агентов используйте builtin:<тип>)")
    if a.task:
        find(tasks_db()["tasks"], a.task, "Задача")
    run = {"at": now(), "agent": a.agent, "task": a.task.upper() if a.task else None,
           "model": a.model or (agent or {}).get("model", "?"), "tokens": a.tokens,
           "cost_usd": a.cost_usd, "tool_uses": a.tool_uses, "duration_ms": a.duration_ms, "note": a.note or ""}
    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(run, ensure_ascii=False) + "\n")
    print(f"Запуск учтён: {a.agent} {a.tokens} токенов" + (f" по {run['task']}" if run["task"] else ""))


def total_cost(runs: list[dict]) -> float:
    return round(sum(float(x.get("cost_usd") or 0) for x in runs), 4)


def cmd_run_list(a):
    runs = load_runs()
    for run in runs[-a.limit:]:
        cost = f"${float(run['cost_usd']):.4f}" if run.get("cost_usd") is not None else "-"
        print(f"{run['at']}  {run['agent']:<26} {run.get('model', '?'):<7} {int(run.get('tokens') or 0):>8} {cost:>9}  "
              f"{run.get('task') or '-':<7} {short(run.get('note', ''), 60)}")
    print(f"— всего запусков: {len(runs)}, токенов: {sum(int(x.get('tokens') or 0) for x in runs)}, "
          f"стоимость (где известна): ${total_cost(runs)}")


# ----------------------------------------------------------------------------- витрины (Markdown)
def render_board(d: dict) -> None:
    counts = {s: sum(1 for t in d["tasks"] if t["status"] == s) for s in STATUSES}
    lines = ["# Доска задач", "", f"_Автогенерация `./dzm board` · {now()} · не редактировать вручную_", "",
             "Сводка: " + " · ".join(f"{s} {n}" for s, n in counts.items() if n), ""]
    groups = [(p["id"], f"{p['id']} — {p['name']} [{p['status']}]") for p in d["projects"]] + [(None, "Без проекта")]
    for pid, header in groups:
        items = [t for t in d["tasks"] if t.get("project") == pid]
        if not items:
            continue
        done = sum(1 for t in items if t["status"] == "COMPLETED")
        lines += [f"## {header} — {done}/{len(items)}", "",
                  "| ID | Статус | P | Исполнитель | Срок | Зависит от | Задача |", "|---|---|---|---|---|---|---|"]
        order = {s: i for i, s in enumerate(["BLOCKED", "FIXING", "TESTING", "REVIEW", "IN_PROGRESS", "RESEARCH", "PLANNING", "NEW", "COMPLETED"])}
        for t in sorted(items, key=lambda t: (order[t["status"]], PRIORITIES.index(t["priority"]), t["id"])):
            title = md_cell(t["title"]) + (f" ⛔ {md_cell(t['blocked_reason'])}" if t.get("blocked_reason") else "")
            lines.append(f"| {t['id']} | {t['status']} | {t['priority']} | {t['assignee']} | {md_cell(t.get('due'))} | "
                         f"{md_cell(', '.join(t['deps']))} | {title} |")
        lines.append("")
    write_text(BOARD_MD, "\n".join(lines))


def render_roster(r: dict) -> None:
    lines = ["# Ростер сотрудников", "", f"_Автогенерация `./dzm roster` · {now()} · данные: roster.json_", "",
             "| Агент | Должность | Отдел | Модель | Руководитель | Статус | Создан | Файл |", "|---|---|---|---|---|---|---|---|"]
    for name, ag in sorted(r["agents"].items(), key=lambda x: (x[1].get("department", ""), x[0])):
        lines.append(f"| `{name}` | {md_cell(ag.get('title'))} | {md_cell(ag.get('department'))} | {md_cell(ag.get('model'))} | "
                     f"{md_cell(ag.get('reports_to'))} | {md_cell(ag.get('status'))} | {md_cell(ag.get('created'))} | {md_cell(ag.get('file'))} |")
    write_text(ROSTER_MD, "\n".join(lines) + "\n")


def render_bugs(b: dict) -> None:
    lines = ["# Реестр ошибок QA", "", f"_Автогенерация `./dzm bug ...` · {now()} · данные: bugs.json_", "",
             "| ID | Критичность | Статус | Название | Задача | Исполнитель |", "|---|---|---|---|---|---|"]
    for x in sorted(b["bugs"], key=lambda x: x["id"]):
        lines.append(f"| {x['id']} | {x['severity']} | {x['status']} | {md_cell(x['title'])} | {md_cell(x.get('task'))} | {md_cell(x.get('assignee'))} |")
    lines.append("")
    for x in sorted(b["bugs"], key=lambda x: x["id"]):
        lines += [bug_markdown(x), ""]
    write_text(BUGS_MD, "\n".join(lines))


def cmd_board(a):
    d = tasks_db()
    render_board(d)
    print(f"Доска обновлена: {rel(BOARD_MD)}")


# ----------------------------------------------------------------------------- отчёты
def completed_at(t: dict) -> str | None:
    return t.get("completed") or next((e["at"] for e in reversed(t.get("log", [])) if e["kind"] == "status" and e["text"].endswith("COMPLETED")), None)


def ready_tasks(d: dict) -> list[dict]:
    items = [t for t in d["tasks"] if t["status"] in ("NEW", "PLANNING") and not pending_deps(d, t)]
    return sorted(items, key=lambda t: (PRIORITIES.index(t["priority"]), t.get("due") or "9999", t["id"]))


def overdue_tasks(d: dict) -> list[dict]:
    return [t for t in d["tasks"] if t.get("due") and t["due"] < today() and t["status"] != "COMPLETED"]


def build_ceo_report(days: int) -> str:
    d, r, b, runs = tasks_db(), roster_db(), bugs_db(), load_runs()
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    L = [f"# ОТЧЁТ AI COMPANY DAYZMODS — {today()}", "",
         f"_Сформирован `./dzm report ceo` по данным репозитория; период активности: последние {days} дн. (с {since})._", ""]

    L += ["## 1. Активные проекты", ""]
    active = [p for p in d["projects"] if p["status"] == "ACTIVE"]
    for p in active:
        done, total = project_progress(d, p["id"])
        L.append(f"- **{p['id']} — {p['name']}** (владелец {p['owner']}): {done}/{total} задач завершено · `{p['dir']}`")
    L += (["- нет"] if not active else []) + [""]

    L += ["## 2. Выполненные задачи", ""]
    done_all = [t for t in d["tasks"] if t["status"] == "COMPLETED"]
    done_recent = [t for t in done_all if (completed_at(t) or "") >= since]
    L.append(f"Всего завершено: {len(done_all)}; за период: {len(done_recent)}.")
    for t in done_recent:
        L.append(f"- {t['id']} {t['title']} — {t['assignee']}; проверил {t['reviews'][-1]['by'] if t.get('reviews') else '—'}")
    L.append("")

    L += ["## 3. Задачи в разработке", ""]
    wip = [t for t in d["tasks"] if t["status"] in ACTIVE_STATES]
    for t in sorted(wip, key=lambda t: (PRIORITIES.index(t["priority"]), t["id"])):
        L.append(f"- {t['id']} [{t['status']}, {t['priority']}] {t['title']} — {t['assignee']}" + (f", срок {t['due']}" if t.get("due") else ""))
    L += (["- нет"] if not wip else []) + [""]

    L += ["## 4. Найденные ошибки", ""]
    open_bugs = [x for x in b["bugs"] if x["status"] not in ("CLOSED", "WONTFIX")]
    by_sev = {s: sum(1 for x in open_bugs if x["severity"] == s) for s in SEVERITIES}
    L.append(f"Открыто: {len(open_bugs)} ({', '.join(f'{s}: {n}' for s, n in by_sev.items())}); всего зарегистрировано: {len(b['bugs'])}. Реестр: `QA/Bugs/BUGS.md`.")
    for x in sorted(open_bugs, key=lambda x: (x["severity"], x["id"])):
        L.append(f"- {x['id']} [{x['severity']} {SEVERITIES[x['severity']]}, {x['status']}] {x['title']}")
    L.append("")

    L += ["## 5. Проблемы и блокировки", ""]
    blocked = [t for t in d["tasks"] if t["status"] == "BLOCKED"]
    for t in blocked:
        L.append(f"- ⛔ {t['id']} {t['title']} — {t.get('blocked_reason', 'причина не указана')}")
    for t in overdue_tasks(d):
        L.append(f"- ⏰ просрочена {t['id']} {t['title']} (срок {t['due']}, {t['status']})")
    crit = [x for x in open_bugs if x["severity"] == "S1"]
    for x in crit:
        L.append(f"- 🔴 критическая ошибка {x['id']}: {x['title']}")
    problems = roster_problems(r) + kb_problems()
    if problems:
        L.append(f"- ⚠ проблемы целостности данных: {len(problems)} (см. `./dzm validate`)")
    if not (blocked or overdue_tasks(d) or crit or problems):
        L.append("- нет")
    L.append("")

    L += ["## 6. Результаты исследований DayZ Engine", ""]
    entries = [(f, fm) for f, fm, _ in kb_entries() if fm.get("kind", "entry") == "entry"]
    counts: dict[str, int] = {}
    for _, fm in entries:
        counts[fm.get("status", "?")] = counts.get(fm.get("status", "?"), 0) + 1
    L.append(f"Записей в базе знаний: {len(entries)} ({', '.join(f'{k}: {v}' for k, v in sorted(counts.items())) or 'нет'}). Индекс: `Knowledge_Base/INDEX.md`.")
    for f, fm in entries:
        if (fm.get("updated") or "") >= since:
            L.append(f"- [{fm.get('status')}] {fm.get('title')} — `{rel(f)}`")
    L.append("")

    L += ["## 7. Новые созданные агенты", ""]
    new_agents = [(n, ag) for n, ag in r["agents"].items() if (ag.get("created") or "") >= since]
    for n, ag in sorted(new_agents):
        L.append(f"- `{n}` — {ag.get('title')} ({ag.get('department')}, модель {ag.get('model')}): {ag.get('reason', '')}")
    L += (["- нет"] if not new_agents else []) + [""]

    L += ["## 8. Загруженность отделов", "", "| Отдел | Сотрудников | В работе | В очереди | Заблокировано |", "|---|---|---|---|---|"]
    depts: dict[str, list[str]] = {}
    for n, ag in r["agents"].items():
        if ag.get("status") != "RETIRED":
            depts.setdefault(ag.get("department", "—"), []).append(n)
    for dept, members in sorted(depts.items()):
        mine = [t for t in d["tasks"] if t["assignee"] in members]
        L.append(f"| {dept} | {len(members)} | {sum(t['status'] in ACTIVE_STATES for t in mine)} | "
                 f"{sum(t['status'] == 'NEW' for t in mine)} | {sum(t['status'] == 'BLOCKED' for t in mine)} |")
    L.append("")

    L += ["## 9. Расход вычислительных ресурсов", ""]
    period_runs = [x for x in runs if x["at"] >= since]
    total = sum(int(x.get("tokens") or 0) for x in period_runs)
    L.append(f"Учтённых запусков агентов за период: {len(period_runs)}, токенов: {total}, "
             f"стоимость там, где она известна: ${total_cost(period_runs)} "
             f"(за всю историю: {sum(int(x.get('tokens') or 0) for x in runs)} токенов, ${total_cost(runs)}). "
             "Расход основной сессии (CEO) агенту не виден — смотрите /usage в Claude Code.")
    for agent, n in sorted(tokens_by(period_runs, "agent").items(), key=lambda x: -x[1]):
        cost = total_cost([x for x in period_runs if x.get("agent") == agent])
        L.append(f"- {agent}: {n}" + (f" (${cost})" if cost else ""))
    for model, n in sorted(tokens_by(period_runs, "model").items(), key=lambda x: -x[1]):
        L.append(f"- модель {model}: {n}")
    by_task = tokens_by(runs, "task")
    for t in d["tasks"]:
        if t.get("budget") and by_task.get(t["id"], 0) > t["budget"]:
            L.append(f"- ⚠ перерасход {t['id']}: {by_task[t['id']]} из бюджета {t['budget']}")
    L.append("")

    L += ["## 10. Следующие запланированные задачи", ""]
    nxt = ready_tasks(d)[:10]
    for t in nxt:
        L.append(f"- {t['id']} [{t['priority']}] {t['title']} → {t['assignee']}")
    L += (["- очередь пуста"] if not nxt else []) + [""]
    return "\n".join(L)


def build_daily_report(day: str) -> str:
    d, b, runs = tasks_db(), bugs_db(), load_runs()
    L = [f"# Ежедневный отчёт — {day}", "", "_Автогенерация `./dzm report daily`_", "", "## Изменения задач", ""]
    events = [(e, t) for t in d["tasks"] for e in t.get("log", []) if e["at"].startswith(day)]
    for e, t in sorted(events, key=lambda x: x[0]["at"]):
        L.append(f"- {e['at'][11:]} {t['id']} [{e['kind']}] {e['by']}: {short(e['text'], 140)}")
    L += (["- нет"] if not events else []) + ["", "## Ошибки", ""]
    bug_events = [(e, x) for x in b["bugs"] for e in x.get("log", []) if e["at"].startswith(day)]
    for e, x in bug_events:
        L.append(f"- {x['id']} [{x['severity']}] {e['kind']}: {short(e['text'], 120)}")
    L += (["- нет"] if not bug_events else []) + ["", "## Запуски агентов", ""]
    day_runs = [x for x in runs if x["at"].startswith(day)]
    for x in day_runs:
        L.append(f"- {x['agent']} ({x.get('model')}) {x.get('tokens')} ток. {x.get('task') or ''} {short(x.get('note', ''), 80)}")
    L.append(f"Итого токенов: {sum(int(x.get('tokens') or 0) for x in day_runs)}")
    L += ["", "## База знаний", ""]
    kb_today = [(f, fm) for f, fm, _ in kb_entries() if fm.get("updated") == day]
    for f, fm in kb_today:
        L.append(f"- [{fm.get('status', fm.get('kind'))}] {fm.get('title')} — `{rel(f)}`")
    L += (["- без изменений"] if not kb_today else []) + ["", "## Готово к старту", ""]
    for t in ready_tasks(d)[:5]:
        L.append(f"- {t['id']} [{t['priority']}] {t['title']} → {t['assignee']}")
    return "\n".join(L) + "\n"


def build_project_report(pid: str) -> str:
    d, b, runs = tasks_db(), bugs_db(), load_runs()
    p = find(d["projects"], pid, "Проект")
    items = [t for t in d["tasks"] if t.get("project") == p["id"]]
    ids = {t["id"] for t in items}
    done, total = project_progress(d, p["id"])
    L = [f"# Отчёт по проекту {p['id']} — {p['name']}", "", f"Статус: {p['status']} · владелец: {p['owner']} · прогресс: {done}/{total} · папка: `{p['dir']}`", "",
         "| ID | Статус | P | Исполнитель | Задача | Проверка |", "|---|---|---|---|---|---|"]
    for t in items:
        rv = t["reviews"][-1] if t.get("reviews") else None
        review = "{} ({})".format(rv["verdict"], rv["by"]) if rv else None
        L.append(f"| {t['id']} | {t['status']} | {t['priority']} | {t['assignee']} | {md_cell(t['title'])} | "
                 f"{md_cell(review)} |")
    linked = [x for x in b["bugs"] if x.get("task") in ids]
    L += ["", f"Ошибок по задачам проекта: {len(linked)} (открыто {sum(x['status'] not in ('CLOSED', 'WONTFIX') for x in linked)})",
          f"Токенов по задачам проекта: {sum(int(x.get('tokens') or 0) for x in runs if x.get('task') in ids)}"]
    return "\n".join(L) + "\n"


def cmd_report(a):
    if a.kind == "ceo":
        text = build_ceo_report(a.days)
        out = P("Reports", "Weekly", f"CEO_REPORT_{today()}.md")
    elif a.kind == "daily":
        day = check_date(a.date) or today()
        text = build_daily_report(day)
        out = P("Reports", "Daily", f"{day}.md")
    else:
        if not a.project:
            raise DzmError("Укажите --project PRJ-XXXX")
        text = build_project_report(a.project)
        out = P("Reports", "Project_Reports", f"{a.project.upper()}_{today()}.md")
    if a.save:
        write_text(out, text)
        print(f"Сохранено: {rel(out)}")
    else:
        print(text)


# ----------------------------------------------------------------------------- статус, проверка, init
def cmd_status(a):
    d, b = tasks_db(), bugs_db()
    counts = {s: sum(1 for t in d["tasks"] if t["status"] == s) for s in STATUSES}
    print("AI Company DayZMods — статус на " + now())
    print("Задачи: " + (" · ".join(f"{s} {n}" for s, n in counts.items() if n) or "нет"))
    for p in d["projects"]:
        if p["status"] == "ACTIVE":
            done, total = project_progress(d, p["id"])
            print(f"Проект {p['id']} {p['name']}: {done}/{total}")
    for t in d["tasks"]:
        if t["status"] == "BLOCKED":
            print(f"⛔ {t['id']} {short(t['title'], 60)} — {short(t.get('blocked_reason', ''), 90)}")
    for t in overdue_tasks(d):
        print(f"⏰ {t['id']} просрочена (срок {t['due']})")
    for t in d["tasks"]:
        if t["status"] in ("IN_PROGRESS", "REVIEW", "TESTING", "FIXING"):
            print(f"▶ {t['id']} [{t['status']}] {short(t['title'], 60)} — {t['assignee']}")
    open_bugs = [x for x in b["bugs"] if x["status"] not in ("CLOSED", "WONTFIX")]
    if open_bugs:
        print("Открытые ошибки: " + ", ".join(f"{x['id']}({x['severity']})" for x in sorted(open_bugs, key=lambda x: x["severity"])))
    ready = ready_tasks(d)[:5]
    if ready:
        print("Готово к старту: " + "; ".join(f"{t['id']} [{t['priority']}] {short(t['title'], 45)} → {t['assignee']}" for t in ready))
    reports = sorted(P("Reports", "Daily").glob("*.md")) if P("Reports", "Daily").exists() else []
    print("Последний ежедневный отчёт: " + (reports[-1].stem if reports else "нет"))


def cmd_validate(a):
    d, r, b = tasks_db(), roster_db(), bugs_db()
    errors: list[str] = []
    ids = [t["id"] for t in d["tasks"]]
    if len(ids) != len(set(ids)):
        errors.append("Повторяющиеся ID задач")
    known = set(ids)
    for t in d["tasks"]:
        tid = t["id"]
        if t["status"] not in STATUSES:
            errors.append(f"{tid}: неизвестный статус {t['status']}")
        if t["priority"] not in PRIORITIES:
            errors.append(f"{tid}: неизвестный приоритет {t['priority']}")
        if t["type"] not in TASK_TYPES:
            errors.append(f"{tid}: неизвестный тип {t['type']}")
        if t["assignee"] not in r["agents"]:
            errors.append(f"{tid}: исполнитель {t['assignee']} не в ростере")
        for dep in t.get("deps", []):
            if dep not in known:
                errors.append(f"{tid}: зависимость {dep} не существует")
        if t.get("project") and t["project"] not in {p["id"] for p in d["projects"]}:
            errors.append(f"{tid}: проект {t['project']} не существует")
        if t["status"] == "BLOCKED" and not t.get("blocked_reason"):
            errors.append(f"{tid}: BLOCKED без причины")
        if t["status"] == "COMPLETED":
            problem = completion_problem(t, r)
            if problem:
                errors.append(problem)
    cycle = deps_cycle(d["tasks"])
    if cycle:
        errors.append("Циклическая зависимость: " + " → ".join(cycle))
    for p in d["projects"]:
        if not (REPO / p["dir"]).exists():
            errors.append(f"{p['id']}: нет папки {p['dir']}")
    errors += roster_problems(r)
    for x in b["bugs"]:
        for field in ("title", "severity", "repro", "cause", "location", "fix"):
            if not x.get(field):
                errors.append(f"{x['id']}: пустое поле {field}")
        if x["status"] == "CLOSED" and not any(rt["result"] == "PASS" for rt in x.get("retests", [])):
            errors.append(f"{x['id']}: закрыта без успешного повторного теста")
    errors += kb_problems()
    try:
        load_runs()
    except DzmError as e:
        errors.append(str(e))
    if errors:
        print(f"Проверка: {len(errors)} ошибок")
        for e in errors:
            print("  - " + e)
        raise SystemExit(1)
    print(f"Проверка: OK (задач {len(d['tasks'])}, проектов {len(d['projects'])}, агентов {len(r['agents'])}, "
          f"ошибок QA {len(b['bugs'])}, записей БЗ {sum(1 for _ in kb_entries())})")


def cmd_init(a):
    created = 0
    for sub in TREE:
        folder = P(sub)
        if not folder.exists():
            folder.mkdir(parents=True)
            created += 1
        if not any(folder.iterdir()):
            (folder / ".gitkeep").touch()
    for path, default in ((TASKS_DB, tasks_db()), (ROSTER_DB, roster_db()), (BUGS_DB, bugs_db())):
        if not path.exists():
            save_json(path, default)
    render_board(tasks_db())
    render_roster(roster_db())
    render_bugs(bugs_db())
    cmd_kb_index()
    print(f"Структура компании готова: {rel(ROOT)} (создано папок: {created})")


# ----------------------------------------------------------------------------- CLI
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="dzm", description="Операционная система AI Company DayZMods")
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp.add_parser("init", help="создать/досоздать структуру папок и файлов").set_defaults(func=cmd_init)
    sp.add_parser("status", help="краткий статус компании (запускать в начале сессии)").set_defaults(func=cmd_status)
    sp.add_parser("board", help="перегенерировать Company/Tasks/BOARD.md").set_defaults(func=cmd_board)
    sp.add_parser("validate", help="проверка целостности всех данных").set_defaults(func=cmd_validate)

    task = sp.add_parser("task", help="задачи").add_subparsers(dest="sub", required=True)
    x = task.add_parser("add", help="создать задачу")
    x.add_argument("--title", required=True)
    x.add_argument("--desc")
    x.add_argument("--assignee", required=True)
    x.add_argument("--type", choices=TASK_TYPES, required=True)
    x.add_argument("--priority", choices=PRIORITIES, default="P2")
    x.add_argument("--project")
    x.add_argument("--due", help="ГГГГ-ММ-ДД")
    x.add_argument("--deps", help="T-0001,T-0002")
    x.add_argument("--budget", type=int, help="бюджет токенов")
    x.add_argument("--files")
    x.add_argument("--by", default="ceo")
    x.set_defaults(func=cmd_task_add)
    x = task.add_parser("list", help="список задач (по умолчанию незавершённые)")
    x.add_argument("--status")
    x.add_argument("--assignee")
    x.add_argument("--project")
    x.add_argument("--all", action="store_true")
    x.set_defaults(func=cmd_task_list)
    x = task.add_parser("show", help="карточка задачи")
    x.add_argument("id")
    x.set_defaults(func=cmd_task_show)
    x = task.add_parser("status", help="сменить статус (с проверкой переходов и зависимостей)")
    x.add_argument("id")
    x.add_argument("status", type=str.upper, choices=STATUSES)
    x.add_argument("--by", required=True)
    x.add_argument("--note")
    x.set_defaults(func=cmd_task_status)
    x = task.add_parser("update", help="изменить поля задачи")
    x.add_argument("id")
    x.add_argument("--title")
    x.add_argument("--desc")
    x.add_argument("--assignee")
    x.add_argument("--type", choices=TASK_TYPES)
    x.add_argument("--priority", choices=PRIORITIES)
    x.add_argument("--project")
    x.add_argument("--due")
    x.add_argument("--deps", help="заменить список зависимостей")
    x.add_argument("--add-deps", help="добавить зависимости")
    x.add_argument("--budget", type=int)
    x.add_argument("--result")
    x.add_argument("--files", help="добавить файлы (через запятую)")
    x.add_argument("--by", required=True)
    x.set_defaults(func=cmd_task_update)
    x = task.add_parser("review", help="записать отчёт о проверке")
    x.add_argument("id")
    x.add_argument("--by", required=True)
    x.add_argument("--verdict", type=str.upper, choices=["PASS", "FAIL"], required=True)
    x.add_argument("--report", required=True)
    x.add_argument("--complete", action="store_true", help="при PASS сразу перевести в COMPLETED")
    x.set_defaults(func=cmd_task_review)
    x = task.add_parser("comment", help="сообщение по задаче (межагентная переписка)")
    x.add_argument("id")
    x.add_argument("--by", required=True)
    x.add_argument("--to")
    x.add_argument("--text", required=True)
    x.set_defaults(func=cmd_task_comment)

    x = sp.add_parser("inbox", help="задачи и сообщения сотрудника")
    x.add_argument("agent")
    x.add_argument("--limit", type=int, default=15)
    x.set_defaults(func=cmd_inbox)

    proj = sp.add_parser("project", help="проекты").add_subparsers(dest="sub", required=True)
    x = proj.add_parser("add")
    x.add_argument("--name", required=True)
    x.add_argument("--owner", required=True)
    x.add_argument("--desc")
    x.set_defaults(func=cmd_project_add)
    proj.add_parser("list").set_defaults(func=cmd_project_list)
    x = proj.add_parser("close")
    x.add_argument("id")
    x.add_argument("--by", required=True)
    x.add_argument("--note")
    x.set_defaults(func=cmd_project_close)
    x = proj.add_parser("archive")
    x.add_argument("id")
    x.add_argument("--by", required=True)
    x.add_argument("--note", required=True)
    x.set_defaults(func=cmd_project_archive)

    bug = sp.add_parser("bug", help="реестр ошибок QA").add_subparsers(dest="sub", required=True)
    x = bug.add_parser("add", help="зарегистрировать ошибку (все 6 полей обязательны)")
    x.add_argument("--title", required=True)
    x.add_argument("--severity", required=True, help="S1 критическая … S4 низкая")
    x.add_argument("--repro", required=True, help="условия воспроизведения")
    x.add_argument("--cause", required=True, help="причина (или 'НЕИЗВЕСТНО: гипотеза …')")
    x.add_argument("--location", required=True, help="файл и место")
    x.add_argument("--fix", required=True, help="предлагаемое исправление")
    x.add_argument("--task")
    x.add_argument("--assignee")
    x.add_argument("--by", required=True)
    x.set_defaults(func=cmd_bug_add)
    x = bug.add_parser("list")
    x.add_argument("--all", action="store_true")
    x.set_defaults(func=cmd_bug_list)
    x = bug.add_parser("show")
    x.add_argument("id")
    x.set_defaults(func=cmd_bug_show)
    x = bug.add_parser("update")
    x.add_argument("id")
    for field in ("title", "repro", "cause", "location", "fix", "assignee", "note"):
        x.add_argument(f"--{field}")
    x.add_argument("--status", type=str.upper)
    x.add_argument("--by", required=True)
    x.set_defaults(func=cmd_bug_update)
    x = bug.add_parser("retest", help="повторное тестирование (только QA)")
    x.add_argument("id")
    x.add_argument("--by", required=True)
    x.add_argument("--result", type=str.upper, choices=["PASS", "FAIL"], required=True)
    x.add_argument("--notes", required=True)
    x.set_defaults(func=cmd_bug_retest)

    run = sp.add_parser("run", help="учёт запусков агентов и токенов").add_subparsers(dest="sub", required=True)
    x = run.add_parser("log")
    x.add_argument("--agent", required=True, help="имя из ростера или builtin:<тип>")
    x.add_argument("--tokens", type=int, required=True,
                   help="новые токены: input + cache_creation + output (повторное чтение кэша не считаем)")
    x.add_argument("--cost-usd", type=float, help="стоимость запуска, если известна (claude -p --output-format json)")
    x.add_argument("--task")
    x.add_argument("--model")
    x.add_argument("--tool-uses", type=int)
    x.add_argument("--duration-ms", type=int)
    x.add_argument("--note")
    x.set_defaults(func=cmd_run_log)
    x = run.add_parser("list")
    x.add_argument("--limit", type=int, default=20)
    x.set_defaults(func=cmd_run_list)

    x = sp.add_parser("roster", help="сотрудники и их загрузка")
    x.add_argument("--check", action="store_true", help="сверить ростер с файлами .claude/agents")
    x.set_defaults(func=cmd_roster)

    hr = sp.add_parser("hr", help="найм и увольнение агентов").add_subparsers(dest="sub", required=True)
    x = hr.add_parser("hire", help="создать агента из шаблона и внести в ростер")
    x.add_argument("--name", required=True)
    x.add_argument("--title", required=True)
    x.add_argument("--dept", required=True)
    x.add_argument("--model", choices=["haiku", "sonnet", "opus", "inherit"], default="sonnet")
    x.add_argument("--description", required=True, help="когда CEO должен делегировать этому агенту")
    x.add_argument("--tools", default="Read, Grep, Glob, Bash, Write, Edit")
    x.add_argument("--reports-to")
    x.add_argument("--helper-of", help="для подчинённых помощников")
    x.add_argument("--reason", required=True)
    x.add_argument("--by", default="hr-director")
    x.set_defaults(func=cmd_hr_hire)
    x = hr.add_parser("retire")
    x.add_argument("name")
    x.add_argument("--reason", required=True)
    x.add_argument("--by", default="hr-director")
    x.set_defaults(func=cmd_hr_retire)

    kb = sp.add_parser("kb", help="база знаний").add_subparsers(dest="sub", required=True)
    x = kb.add_parser("search", help="поиск (все слова запроса должны встретиться)")
    x.add_argument("query")
    x.add_argument("--limit", type=int, default=10)
    x.set_defaults(func=cmd_kb_search)
    kb.add_parser("index", help="перегенерировать Knowledge_Base/INDEX.md").set_defaults(func=cmd_kb_index)
    x = kb.add_parser("new", help="создать запись по шаблону")
    x.add_argument("--path", required=True, help="например Vehicles/crew_seats.md")
    x.add_argument("--title", required=True)
    x.add_argument("--status", default="HYPOTHESIS")
    x.add_argument("--owner", default="research-lead")
    x.add_argument("--tags")
    x.add_argument("--sources", help="URL или experiment:/file: ссылки через запятую")
    x.set_defaults(func=cmd_kb_new)

    x = sp.add_parser("report", help="отчёты: ceo | daily | project")
    x.add_argument("kind", choices=["ceo", "daily", "project"])
    x.add_argument("--days", type=int, default=7)
    x.add_argument("--date")
    x.add_argument("--project")
    x.add_argument("--save", action="store_true")
    x.set_defaults(func=cmd_report)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except DzmError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
