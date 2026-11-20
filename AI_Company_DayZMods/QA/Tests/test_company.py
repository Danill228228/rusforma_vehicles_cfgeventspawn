"""Автотесты инфраструктуры AI Company DayZMods (CLI ./dzm).

Каждый тест работает в изолированной песочнице (временная папка), поэтому реальные данные компании не трогаются.
Запуск: python3 -m unittest discover -s AI_Company_DayZMods/QA/Tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parents[2] / "Company" / "Tools" / "company.py"

ROSTER = {
    "version": 1,
    "agents": {
        "client": {"title": "Заказчик", "department": "Client", "model": "-", "kind": "human", "status": "ACTIVE", "reports_to": None, "created": "2026-01-01"},
        "ceo": {"title": "CEO", "department": "CEO", "model": "inherit", "kind": "main-session", "status": "ACTIVE", "reports_to": "client", "created": "2026-01-01"},
        "qa-lead": {"title": "QA", "department": "QA", "model": "sonnet", "kind": "subagent", "status": "ACTIVE", "reports_to": "ceo", "created": "2026-01-01"},
        "dev-agent": {"title": "Dev", "department": "Engineering", "model": "opus", "kind": "subagent", "status": "ACTIVE", "reports_to": "ceo", "created": "2026-01-01"},
        "research-lead": {"title": "Research", "department": "Research", "model": "sonnet", "kind": "subagent", "status": "ACTIVE", "reports_to": "ceo", "created": "2026-01-01"},
        "hr-director": {"title": "HR", "department": "HR", "model": "sonnet", "kind": "subagent", "status": "ACTIVE", "reports_to": "ceo", "created": "2026-01-01"},
    },
}


class CompanyCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.root = self.repo / "AI_Company_DayZMods"
        (self.root / "Company" / "HR").mkdir(parents=True)
        (self.root / "Company" / "HR" / "roster.json").write_text(json.dumps(ROSTER), encoding="utf-8")
        agents = self.repo / ".claude" / "agents"
        agents.mkdir(parents=True)
        for name, ag in ROSTER["agents"].items():
            if ag["kind"] == "subagent":
                (agents / f"{name}.md").write_text(
                    f"---\nname: {name}\ndescription: тестовый агент\nmodel: {ag['model']}\n---\nТест.\n", encoding="utf-8")
        self.env = dict(os.environ, DZM_ROOT=str(self.root), DZM_REPO=str(self.repo))
        self.ok("init")

    def tearDown(self):
        self.tmp.cleanup()

    # --- помощники
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], env=self.env, capture_output=True, text=True)

    def ok(self, *args):
        res = self.run_cli(*args)
        self.assertEqual(res.returncode, 0, f"ожидался успех: {args}\n{res.stdout}\n{res.stderr}")
        return res.stdout

    def fail(self, expected, *args):
        res = self.run_cli(*args)
        self.assertNotEqual(res.returncode, 0, f"ожидалась ошибка: {args}\n{res.stdout}")
        self.assertIn(expected, res.stdout + res.stderr)

    def add_task(self, title, assignee="dev-agent", type_="dev", deps=None):
        args = ["task", "add", "--title", title, "--assignee", assignee, "--type", type_]
        if deps:
            args += ["--deps", deps]
        out = self.ok(*args)
        return out.split()[0]

    def finish(self, tid, assignee="dev-agent", reviewer="qa-lead"):
        self.ok("task", "status", tid, "IN_PROGRESS", "--by", assignee)
        self.ok("task", "update", tid, "--result", "готово", "--by", assignee)
        self.ok("task", "status", tid, "REVIEW", "--by", assignee)
        self.ok("task", "review", tid, "--by", reviewer, "--verdict", "PASS", "--report", "проверено тестом", "--complete")

    def task(self, tid):
        data = json.loads((self.root / "Company" / "Tasks" / "tasks.json").read_text(encoding="utf-8"))
        return next(t for t in data["tasks"] if t["id"] == tid)

    # --- тесты
    def test_init_creates_tree(self):
        for sub in ("Company/CEO", "Knowledge_Base/Vehicles", "Projects/Archived", "Development/Builds",
                    "QA/Bugs", "Media/Finished", "Reports/Project_Reports"):
            self.assertTrue((self.root / sub).is_dir(), sub)
        self.assertTrue((self.root / "Company" / "Tasks" / "BOARD.md").exists())

    def test_dependency_gate(self):
        t1 = self.add_task("фундамент")
        t2 = self.add_task("надстройка", deps=t1)
        self.fail("не завершены зависимости", "task", "status", t2, "IN_PROGRESS", "--by", "dev-agent")
        self.finish(t1)
        self.ok("task", "status", t2, "IN_PROGRESS", "--by", "dev-agent")

    def test_review_requires_result(self):
        t = self.add_task("без результата")
        self.ok("task", "status", t, "IN_PROGRESS", "--by", "dev-agent")
        self.fail("заполните результат", "task", "status", t, "REVIEW", "--by", "dev-agent")

    def test_completion_requires_pass_review_by_other(self):
        t = self.add_task("код")
        self.ok("task", "status", t, "IN_PROGRESS", "--by", "dev-agent")
        self.ok("task", "update", t, "--result", "написан", "--by", "dev-agent")
        self.ok("task", "status", t, "REVIEW", "--by", "dev-agent")
        self.fail("нет отчёта о проверке", "task", "status", t, "COMPLETED", "--by", "ceo")
        self.fail("не может проверять собственную", "task", "review", t, "--by", "dev-agent", "--verdict", "PASS", "--report", "сам")
        self.ok("task", "review", t, "--by", "qa-lead", "--verdict", "FAIL", "--report", "ошибка в строке 10")
        self.assertEqual(self.task(t)["status"], "FIXING")
        self.ok("task", "status", t, "REVIEW", "--by", "dev-agent")
        self.ok("task", "review", t, "--by", "qa-lead", "--verdict", "PASS", "--report", "исправлено", "--complete")
        self.assertEqual(self.task(t)["status"], "COMPLETED")

    def test_qa_only_for_dev_tasks(self):
        t = self.add_task("конфиг", type_="config")
        self.ok("task", "status", t, "IN_PROGRESS", "--by", "dev-agent")
        self.ok("task", "update", t, "--result", "готов", "--by", "dev-agent")
        self.ok("task", "status", t, "REVIEW", "--by", "dev-agent")
        self.fail("закрывает только отдел QA", "task", "review", t, "--by", "research-lead", "--verdict", "PASS", "--report", "ок", "--complete")
        self.ok("task", "review", t, "--by", "qa-lead", "--verdict", "PASS", "--report", "ок", "--complete")

    def test_invalid_transition_and_blocked_note(self):
        t = self.add_task("переходы")
        self.fail("запрещён", "task", "status", t, "COMPLETED", "--by", "ceo")
        self.fail("обязательна причина", "task", "status", t, "BLOCKED", "--by", "ceo")
        self.ok("task", "status", t, "BLOCKED", "--by", "ceo", "--note", "ждём доступ")
        self.assertIn("ждём доступ", self.ok("status"))

    def test_cycle_detection(self):
        t1 = self.add_task("A")
        t2 = self.add_task("B", deps=t1)
        self.fail("Циклическая", "task", "update", t1, "--add-deps", t2, "--by", "ceo")
        self.assertEqual(self.task(t1)["deps"], [])

    def test_bug_lifecycle(self):
        base = ["bug", "add", "--title", "XML не парсится", "--severity", "S1", "--repro", "открыть файл парсером",
                "--location", "file.xml:332", "--fix", "закрыть тег", "--by", "qa-lead"]
        self.fail("обязательно", *base, "--cause", " ")
        self.ok(*base, "--cause", "не закрыт тег event")
        self.fail("только повторным тестом", "bug", "update", "BUG-0001", "--status", "CLOSED", "--by", "qa-lead")
        self.fail("отдел QA", "bug", "retest", "BUG-0001", "--by", "dev-agent", "--result", "PASS", "--notes", "сам")
        self.ok("bug", "retest", "BUG-0001", "--by", "qa-lead", "--result", "PASS", "--notes", "парсер OK")
        md = (self.root / "QA" / "Bugs" / "BUGS.md").read_text(encoding="utf-8")
        for n in range(1, 8):
            self.assertIn(f"{n}. **", md)
        self.assertIn("CLOSED", md)

    def test_hr_hire_and_retire(self):
        self.ok("hr", "hire", "--name", "uv-specialist", "--title", "Специалист по UV", "--dept", "3D_Art",
                "--model", "haiku", "--description", "UV-развёртка", "--reason", "тест найма", "--reports-to", "ceo")
        agent = self.repo / ".claude" / "agents" / "uv-specialist.md"
        self.assertIn("name: uv-specialist", agent.read_text(encoding="utf-8"))
        self.assertTrue((self.repo / ".claude" / "agent-memory" / "uv-specialist" / "MEMORY.md").exists())
        self.ok("roster", "--check")
        self.ok("hr", "retire", "uv-specialist", "--reason", "проект закрыт")
        self.assertFalse(agent.exists())
        self.assertTrue((self.root / "Company" / "HR" / "retired" / "uv-specialist.md").exists())
        self.ok("roster", "--check")

    def test_roster_check_detects_orphan_agent_file(self):
        (self.repo / ".claude" / "agents" / "ghost.md").write_text("---\nname: ghost\ndescription: x\n---\n", encoding="utf-8")
        self.fail("нет записи", "roster", "--check")

    def test_kb_validation_and_search(self):
        entry = self.root / "Knowledge_Base" / "Vehicles" / "test_entry.md"
        entry.write_text("---\ntitle: Тестовая запись о люках\nstatus: VERIFIED\nupdated: 2026-01-01\nowner: research-lead\n"
                         "tags: [hatch, vehicles]\nsources:\n  - https://example.org/a\n---\nТекст про люк.\n", encoding="utf-8")
        self.fail("требует минимум 2", "validate")
        entry.write_text(entry.read_text(encoding="utf-8").replace("  - https://example.org/a\n",
                         "  - https://example.org/a\n  - experiment:тест\n"), encoding="utf-8")
        self.ok("validate")
        self.assertIn("test_entry.md", self.ok("kb", "search", "hatch"))
        self.ok("kb", "index")
        self.assertIn("Тестовая запись о люках", (self.root / "Knowledge_Base" / "INDEX.md").read_text(encoding="utf-8"))

    def test_ceo_report_has_10_sections_and_resources(self):
        t = self.add_task("учёт")
        self.ok("run", "log", "--agent", "qa-lead", "--tokens", "12345", "--task", t)
        self.fail("Неизвестный агент", "run", "log", "--agent", "nobody", "--tokens", "1")
        report = self.ok("report", "ceo")
        for n in range(1, 11):
            self.assertIn(f"## {n}. ", report)
        self.assertIn("12345", report)
        self.ok("report", "daily", "--save")

    def test_project_lifecycle(self):
        self.ok("project", "add", "--name", "Тестовый мод", "--owner", "ceo", "--desc", "проверка")
        folder = next((self.root / "Projects" / "Active").glob("PRJ-0001_*"))
        self.assertTrue((folder / "PROJECT.md").exists())
        out = self.ok("task", "add", "--title", "работа", "--assignee", "dev-agent", "--type", "dev", "--project", "PRJ-0001")
        tid = out.split()[0]
        self.fail("не завершены задачи", "project", "close", "PRJ-0001", "--by", "ceo")
        self.finish(tid)
        self.ok("project", "close", "PRJ-0001", "--by", "ceo")
        self.assertTrue(any((self.root / "Projects" / "Completed").glob("PRJ-0001_*")))
        self.ok("validate")


if __name__ == "__main__":
    unittest.main()
