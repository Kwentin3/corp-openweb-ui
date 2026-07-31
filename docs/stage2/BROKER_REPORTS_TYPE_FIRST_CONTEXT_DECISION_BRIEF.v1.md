# Broker Reports Type-First: bounded semantic context decision brief v1

Дата: 2026-07-31
Статус: решение до реализации
Область: неактивный Gate 2 proof; provider и product route недоступны

## Решение простыми словами

LLM не должна придумывать факт, значение или финансовый тип. Её единственная
задача — вернуть все правдоподобные локальные ключи из показанных Type Cards для
одной исходной строки. Для обоснованного выбора ей нужны не только значения, но
и происхождение строки: документ, раздел, таблица, исходные заголовки, сама
строка, структурно связанные строки и признаки качества.

Этот контекст собирает детерминированный subordinate factory. Он не получает
Type Cards, не ищет финансовые слова, не строит shortlist и не выбирает тип.
Он следует только явным связям package: тот же document/table, row ordinal,
parent, adjacency, footnote и continuation. После simulated response отдельный
guard сверяет выбранный тип с Pack-backed требованиями. Singleton не достаточен
сам по себе: при нехватке доказательств результат —
`INSUFFICIENT_SEMANTIC_CONTEXT` и `unclassified_financial_input`.

## Ответы на десять вопросов

1. **Что решает LLM?** Какие из уже разрешённых Type Cards правдоподобны для
   source unit; plural и empty ответы допустимы.
2. **Что ей нужно?** Смысловая подпись, reporting scope/date или period,
   document/section/table context, raw headers вместе с normalized roles,
   целевая строка, структурные соседи и quality/restrictions.
3. **Где это находится?** Часть есть в Gate 2 package и его source unit:
   document readiness, table identity, row/cells, provenance, quality, issues,
   continuation. Часть может быть связана через parent package той же таблицы.
4. **Что сейчас теряется?** Request оставляет только значения и обеднённые
   роли; document/section/table layers, raw headers, локальное окружение,
   quality, truncation и issues не видны модели.
5. **Кто собирает?** Один versioned deterministic context factory,
   подчинённый существующему proof/orchestration owner.
6. **Как выбираются фрагменты?** Только по document/table identity и явным
   structural links; не более двух предыдущих и двух следующих строк в одной
   таблице, плюс ограниченные parent/group/footnote/continuation links.
7. **Почему это не предварительная классификация?** Builder не импортирует
   Semantic Pack, не принимает type key, не использует regex/synonyms и не
   возвращает canonical type либо shortlist.
8. **Как выявляется нехватка?** Guard проверяет полноту bounded envelope,
   package/context hashes, Pack-backed required facets, truncation и
   disqualifying unresolved issues.
9. **Что с singleton без доказательств?** Existing validator/materializer
   получает code-owned unclassified choice; typed fact запрещён.
10. **Как доказать безопасность удаления контекста?** Exact ablation replay
    сравнивает values-only, normalized-roles, headers, section/table, local и
    full variants. Удаление слоя не может превратить insufficient/ambiguous в
    sufficient typed.

## Аудит текущего context flow

Проверены три реальные row-window units одного private source family через их
privacy-safe structural copies. В таблице `Да*` означает: поле есть в большом
package, но не является полезной исходной семантикой (например, operational
readiness вместо типа/названия документа). Все три units имеют одинаковую
доступность facets.

| Информация | Исходный документ | Gate 2 package | Текущий source unit | Видит LLM | Потеряна |
| --- | ---: | ---: | ---: | ---: | ---: |
| Тип документа | Да | Нет | Нет | Нет | Да |
| Роль документа | Да | Нет | Нет | Нет | Да |
| Название документа | Да | Нет | Нет | Нет | Да |
| Организация/эмитент | Да | Нет | Нет | Нет | Да |
| Отчётный период | Да | Нет | Нет | Нет | Да |
| Тип счёта | Возможно | Нет | Нет | Нет | Да/неизвестно |
| Язык | Да | Нет | Нет | Нет | Да |
| Section path | Да | Нет | Нет | Нет | Да |
| Название таблицы | Да | Нет | Нет | Нет | Да |
| Групповой заголовок | Возможно | Нет | Нет | Нет | Да/неизвестно |
| Исходные заголовки колонок | Да | `unknown` | `unknown` | Техническая замена | Да |
| Нормализованные роли колонок | Нет/неизвестно | Нет | Нет | Слабый placeholder | Да |
| Целевая строка | Да | Да | Да | Да, но раньше смысловая label была заменена | Частично |
| Родительская строка | Возможно | Нет | Нет | Нет | Да/неизвестно |
| Предыдущая строка | Да | В parent table | Нет | Нет | Да |
| Следующая строка | Да | В parent table | Нет | Нет | Да |
| Сноски | Возможно | Нет | Нет | Нет | Да/неизвестно |
| Continuation | Возможно | Пустой object | Пустой object | Нет | Да/неизвестно |
| Extraction method | — | Да | Да | Нет | Да |
| Reconstruction quality | — | Да | Да | Нет | Да |
| Missing/truncated context | — | Частично | Частично | Нет | Да |
| Unresolved document issues | — | Да | Нет | Нет | Да |

`CURRENT_CONTEXT_SUFFICIENCY = INSUFFICIENT`

Точный вывод для старого typed-case: реальные units сохраняют смысловую подпись
как первую ячейку строки, но не сохраняют raw headers, section/table title или
reporting date/period. Публичная KT2 fixture дополнительно заменила смысловую
первую ячейку числом. Поэтому прежний singleton нельзя оставить typed.

## Bounded contract и бюджеты

`broker_reports_bounded_semantic_context_v1` содержит шесть слоёв:
document, section, table, target unit, local structural context, quality and
restrictions. Передаются только фактически доступные значения. Raw headers и
normalized roles сосуществуют; отсутствие не маскируется.

Бюджеты: section depth 6, group labels 4, parent rows 2, previous rows 2, next
rows 2, footnotes 4, 2 000 символов на строку/label, 24 000 символов на весь
context envelope. Любое ограничение отмечает `context_truncated=true`; если
оно затрагивает required facet, typed output запрещён.

## Authority и безопасный исход

Sole product owner остаётся `Gate2DomainSourceFactRuntimeFactory`. Новый builder
proof-only, provider-free, не импортируется product route или Function bundles.
Type-specific requirements происходят только из существующего Semantic Pack;
validator, materializer и replay owner остаются прежними.

Для реального корпуса ожидаемый честный результат — три unclassified units с
`INSUFFICIENT_SEMANTIC_CONTEXT`. Sufficient typed path доказывается отдельной
явно маркированной semantically equivalent synthetic redaction, а не выдаётся
за восстановленный customer text. Exact private bytes остаются только под
ignored `local/`.
