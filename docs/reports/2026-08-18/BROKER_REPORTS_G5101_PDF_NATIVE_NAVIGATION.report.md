# G5.101 — нативная навигационная сетка PDF

## Итог

**STOP: `NATIVE_PDF_POINT_NAVIGATION_INSUFFICIENT`.**

Гипотеза проверена узко и дала однозначный отрицательный результат. Поверх уже проверенного full-page render добавлена видимая сетка с линейками в нативных координатах `pdfplumber`: `x` вправо, `top` вниз, без изменения пикселей самой страницы. Модель увидела правильную систему координат, но на всех четырёх положительных страницах продолжила возвращать несовместимую геометрию. Полностью корректно извлечено **0 из 9** ожидаемых таблиц.

Вторичный вывод: `VISIBLE_NATIVE_GRID_DID_NOT_ANCHOR_MODEL_COORDINATES`. Статическая линейка рядом со страницей сама по себе не превращает визуальное указание модели в надёжный native extraction plan.

G5.100 не изменялся. Повторных попыток, prompt repair, best-of-N и нового unseen holdout не было.

## Что именно изменилось

Изменена одна переменная: к исходному page render добавлен навигационный overlay.

```text
existing PdfTableRasterFactory
→ research-only NativePdfPointNavigationOverlayFactory
→ unchanged provider path and model
→ frozen G5.100 VisualPdfPlumberTableAdapterFactory
→ existing Gate 2 Canonical owners
```

Overlay:

- рисует major/minor grid и внешние линейки в PDF points;
- явно обозначает направление `x` и `top`;
- сохраняет исходный raster без resize, crop и rotation;
- не читает PDF text, не ищет таблицы и не знает broker semantics;
- не попадает в package exports или product routing.

Модель видела только три поля plan: `bbox`, `explicit_vertical_lines`, `horizontal_strategy`. `vertical_strategy="explicit"` добавлялся механически после strict validation. Преобразование model plan → `pdfplumber` было identity; tolerance knobs — 0.

## Проверка coordinate seam до inference

Входные страницы G5.99 повторно прошли через существующий `PdfTableRasterFactory`; PNG совпали с замороженными baseline побайтно. Для всех страниц подтверждены одинаковые исходные свойства: top-left page space, отсутствие rotation и согласованность PDF bounds с render transform.

Отдельные overlay-страницы проверены визуально. Оси направлены правильно, подписи соответствуют границам страницы, содержимое не растянуто и не повёрнуто. Следовательно, наблюдаемый провал нельзя объяснить ошибкой рендера или переворотом координат.

До provider execution также прошли 14 focused tests G5.100/G5.101: deterministic overlay, fail-closed render verification, grid bounds, private ownership, exact three-field contract, identity native-point handoff и отсутствие старых repair/tolerance paths.

## Development на тех же страницах G5.99

Режим исполнения:

- те же 9 уже открытых development-страниц;
- та же модель `models/gemini-3.5-flash` и minimal thinking;
- ровно один provider call на страницу;
- retry = false;
- best-of-N = false;
- post-result correction = false.

| Метрика | G5.100 без сетки | G5.101 с сеткой |
|---|---:|---:|
| Expected visual tables | 9 | 9 |
| VLM table proposals | 9 | 8 |
| Pages с точным presence/count | 9 / 9 | 8 / 9 |
| False plans на 5 negatives | 0 | 0 |
| Strictly invalid positive pages | 1 | 4 |
| Native objects, дошедшие до Canonical | 2 | 0 |
| Полностью корректные таблицы | **0 / 9** | **0 / 9** |

Пять отрицательных страниц остались корректными: пустой plan, без ложных таблиц. На положительных страницах стало хуже:

1. В трёх случаях `bbox` и column boundaries выходили за нативные границы страницы. Ответ сохранял признаки внутренней image/normalized coordinate convention, несмотря на видимые PDF-point rulers.
2. В одном случае вертикальные границы пришли не в возрастающем порядке, что согласуется с сохранявшейся путаницей осей/полей.
3. На одной странице две визуальные таблицы были слиты в один proposal.
4. Из семи таблиц с выразимыми frozen truth regions точное совпадение региона получено в 0 случаях. Ещё две embedded-таблицы имеют не contiguous truth и оценивались отдельно.

Strict validator остановил все четыре положительные страницы до вызова `pdfplumber`. Поэтому ни одна ошибочная геометрия не стала Canonical authority.

## Source truth и completeness

Модель по-прежнему не возвращала cell values. Значения разрешено получать только из PDF words через native `pdfplumber` cells и существующие Gate 2 builders.

```text
VLM BODY VALUES USED = 0
INVENTED SOURCE LITERALS = 0
INVALID POSITIVE PLANS REACHING CANONICAL = 0
```

Пять отрицательных страниц собраны существующим ordinary-text path; все пять Canonical artifacts valid и имеют exact source accounting. Это подтверждает fail-closed поведение, но не является успехом table extraction.

## Почему это не повод ещё крутить contract

Провал не связан с отсутствующим полем `pdfplumber` или tolerance knob. Модель не выполнила уже явную, визуально нанесённую привязку к координатной системе. Дополнительные названия полей, примеры чисел или послепросмотровая коррекция были бы новым prompt-tuning экспериментом и нарушили бы one-shot comparison.

Тем более не обоснованы `snap_*`, `join_*` и другие extraction tolerances: они не исправляют координаты за границами страницы, перестановку осей и слияние разных таблиц.

## KISS verdict и scope stop

Здравое зерно гипотезы сохранено: overlay очень прост, детерминирован и хорошо подходит человеку для проверки координат. Но для текущей VLM он не стал надёжным механизмом навигации и ухудшил native-plan acceptance относительно G5.100.

Следовательно:

```text
NATIVE_PDF_POINT_NAVIGATION_INSUFFICIENT
```

Не выполнены и не разрешены:

- freeze G5.101;
- unseen cross-document holdout;
- повторные provider calls или prompt repair;
- production activation;
- Gate 3+ изменения;
- возврат к G5.96–G5.98 resolver/materializer как repair.

Если открывать отдельную следующую гипотезу, то уже не про ещё одну подпись на картинке. Осмысленный развилочный тест — либо настоящий интерактивный coordinate-selection/click tool с машинно возвращаемой точкой, либо полностью детерминированный geometric detector перед `pdfplumber`. Это новый GOAL; в G5.101 он не реализовывался.
