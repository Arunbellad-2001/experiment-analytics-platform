---

### File 2: `CHANGELOG.md`

Run `notepad CHANGELOG.md` (or open `D:\experiment-analytics-platform\CHANGELOG.md` in VS Code), paste the following, and save (`Ctrl + S`):

```markdown
# Changelog

All notable changes to the **Experiment Analytics Platform** are documented in this file.

## [0.1.0] - 2026-11-12 (Milestone 1: Project Scaffolding & Database Architecture)

### Features Added
- Initialized modular project structure (`config/`, `database/`, `generator/`, `services/`, `exports/`, `documentation/`, `ai_prompts/`, `tests/`, `data/`, `logs/`).
- Implemented cross-platform path configuration, fixed seed (`20261022`), scale presets (`STARTER_CONFIG` and `FULL_CONFIG`), and controlled vocabularies in `config/settings.py`.
- Implemented SQLite connection factory (`database/connection.py`) with startup runtime version verification (`SQLite >= 3.25.0`), automatic `PRAGMA foreign_keys = ON` enforcement, and transactional session scopes.
- Authored canonical DDL (`database/schema.sql`) and matching SQLAlchemy 2.0 ORM models (`database/models.py`) covering 11 operational tables, composite foreign keys, partial unique index for single Control variant enforcement, append-only immutability triggers on `metric_definitions` and `experiment_results`, exact lifecycle transition triggers, and MDE/statistical-significance consistency triggers.
- Added automated database integrity test suite (`tests/conftest.py`, `tests/test_database.py`).

### Files Created
- `.gitignore`
- `requirements.txt`
- `README.md`
- `CHANGELOG.md`
- `config/__init__.py`
- `config/settings.py`
- `database/__init__.py`
- `database/connection.py`
- `database/models.py`
- `database/schema.sql`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_database.py`
- `documentation/architecture.md`
- `documentation/database_design.md`
- `documentation/data_dictionary.md`
- `ai_prompts/prompt_history.md`

### Related Git Commits
- `chore: initialize project structure`
- `docs: add project development plan`
- `feat: implement database schema`