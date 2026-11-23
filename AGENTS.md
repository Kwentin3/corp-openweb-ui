# AGENTS.md

Короткие рабочие правила для кодовых агентов в `corp-openweb-ui`.

## Архитектурные границы

- **Extension-first:** новые возможности добавляются через штатные механизмы OpenWebUI (Functions, Actions, Tools, Skills, Knowledge, конфиги) или изолированный Docker-сервис. Правки исходников ядра OpenWebUI и LiteLLM допускаются только при явном согласовании и фиксируются в [`docs/infra-ops/patch-registry.md`](docs/infra-ops/patch-registry.md).
- **CI:** обязательный PR-чек — `active-ci` (`.github/workflows/active-ci.yml`). Замороженный контур `services/broker-reports-gate1-proof/` имеет собственный локальный [`AGENTS.md`](services/broker-reports-gate1-proof/AGENTS.md) и не входит в обязательный PR-gate.
- **Секреты:** никогда не коммитить реальные API-ключи, токены, `.env`, дампы БД и приватные артефакты (`local/`).

## Контракт актуализации карты архитектуры

Актуальная карта проекта живёт в двух связанных файлах:
- [`docs/architecture-map.html`](docs/architecture-map.html) (интерактивная версия, публикуется на GitHub Pages автоматически при мёрдже в `main`);
- [`docs/ARCHITECTURE_MAP.md`](docs/ARCHITECTURE_MAP.md) (Mermaid-схема и сводка для GitHub).

**Обязательно обновляй оба файла в том же PR**, если изменения затрагивают архитектурную границу:
- добавлен, изменён или снят **патч ядра** (`deploy/openwebui-patches/`, `deploy/litellm-patches/`);
- добавлен, удалён или переименован **Docker-сервис / шлюз** (`compose/`, `services/`);
- добавлена, удалена или перенесена **точка расширения OpenWebUI** (`deploy/openwebui-functions/`, `deploy/openwebui-tools/`, `deploy/openwebui-budgets/`, `deploy/openwebui-skills/`, `deploy/openwebui-knowledge/`);
- изменился **поток данных (воркфлоу)**, прокси/egress или обход биллинга.

**Не трогай карту** при обычных багфиксах, тестах, рефакторингах без смены границ и правках коммерческих/операционных отчётов.

Подробный чек-лист обновления см. в [`docs/ARCHITECTURE_MAP.md#контракт-актуализации-карты`](docs/ARCHITECTURE_MAP.md#контракт-актуализации-карты).
