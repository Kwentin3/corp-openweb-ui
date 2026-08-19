# Broker Reports Gate 5 G5.36 — Real OpenWebUI Product-path Proof

Date: `2026-08-11`

Status: `PROVEN`

Terminal:

```text
REAL_PRODUCT_PATH_XML_VALID
blockers = 0
```

Да. В реально запущенном controlled-staging OpenWebUI обычный
аутентифицированный User A загрузил synthetic broker CSV через native upload,
прошёл machine-driven human residual, получил полный XML 3-НДФЛ через обычный
chat product path и дважды скачал его через native Files boundary. Оба download
дали побайтово одинаковые `1109` bytes и прошли packaged official FNS XSD.

Безопасный hash-chain receipt:
[G5.36 receipt](./BROKER_REPORTS_GATE5_REAL_OPENWEBUI_PRODUCT_PATH_G5_36.receipt.safe.json).

Контракт:
[Real OpenWebUI Product Path v0](../../stage2/contracts/BROKER_REPORTS_GATE5_REAL_OPENWEBUI_PRODUCT_PATH.v0.md).

## 1. Environment proof

| Поле | Фактическое значение |
| --- | --- |
| Environment | controlled staging; реальный удалённый OpenWebUI |
| Application | OpenWebUI `0.9.6` |
| Container image | `corp-openwebui/openwebui:v0.9.6-native-web-stt-broker-intake-v2-8e6a71f` |
| Git HEAD | `02659a9b0bdfb2f19171d2a070a660af85119d59` |
| Branch | `feature/gate5-tax-period-category-aggregation` |
| Tree | dirty cumulative Gate 5 working tree; 22-file G5.36 implementation manifest SHA-256 `e7aa9788530a8b6807e2379c5b53ef31cb9f8388f887b6384047d8df90ea4636` |
| Final deployed bundle | `8c0187d211c0aad700c07d619f48d95e98bf3ee211501ce1b0a38d8423d79934` |
| Artifact persistence | SQLite metadata + external project artifact payloads |
| User file persistence | native OpenWebUI Files + local storage provider |
| Provider route | `google_gemini / models/gemini-3.5-flash` |
| Browser | local Playwright `1.59.1`, Chromium revision `1217`, headless |

Built-in Playwright MCP was unavailable in this session. Following the
Playwright triage boundary, the final proof used the installed compatible local
Playwright browser. Это не API-only proof: login выполнялся через `/auth`, а
финальный XML скачивался кликом по rendered chat link.

Proof activation была временной: точечный model read grant получил только
synthetic User A; существующая base Function была callable лишь в controlled
staging window. User B не видел stable product model.

## 2. User journey

```text
browser login
→ native OpenWebUI upload
→ native chat with broker-reports-ndfl
→ Gate 1 → Gate 2 → live Gate 3 → Gate 4
→ machine blocker for missing supplied-case sections
→ user submits explicit structured synthetic facts
→ machine blocker for declaration_date
→ user submits declaration_date only
→ existing Gate 5 owners → unchanged PROJECT
→ private XML publication
→ rendered chat link
→ browser download
→ same semantic reply with different JSON whitespace
→ second browser download
→ byte-identical XML
```

Начальный product flow не загружал G5.35 case resource. Единственный
G5.36 product Definition содержит section/provenance contract, но не case
values. Human facts вошли через native Chat и сохранились двумя private
case-fact submissions. Известный системе `signer_ref` для
`taxpayer_self` был связан с authenticated user context; filing date не
подставлялась и была получена отдельным коротким ответом.

## 3. Live provider proof

Fresh product case прошёл configured OpenWebUI provider transport через
`Gate2StructuredModelClientFactory.create`; до этого case не имел persisted
Gate 3 annotation. Успешный downstream terminal тем самым требует нового
validated Gate 3 sidecar.

Отдельный bounded provider-smoke сохранил exact synthetic response вне Git.
Repository-safe aggregate:

- documents: `1`;
- provider attempts with raw response: `1`;
- role attempts: `1`;
- Gate 3 validation and annotations persistence: passed;
- private audit manifest SHA-256:
  `959ab58156e88aa0a8ef0317b275d36e7e101491cbec96498b70aa1895e56beb`;
- secrets/raw provider payload in report or Git: `0`.

После smoke exact private audit был выключен до основного full replay.

## 4. Product blocker ledger

| Blocker | Закрытие | Clean replay |
| --- | --- | --- |
| Normal user не видел private stable model | temporary per-user model grant; no public grant | User A sees model; User B does not |
| Completion form не давал server-attested chat scope | owner-bound native `Chats.get_chat_by_id_and_user_id` recovery | authenticated case accepted |
| Sanitized form не содержал текущий human answer | latest marker-bearing user message recovered from owned native Chat | partial and final answers observed |
| Human turn не получил новый canonical ref | resolve one validated Gate 3 artifact for same owner/case/run; continue through existing owner | provider calls on continuation `0` |
| Synthetic subject ref не совпадал с trusted methodology | corrected explicit synthetic fixture binding; trusted methodology unchanged | Tax Model projected |
| `taxpayer_self` signer used guessed internal ID | bind signer ref from authenticated context | filing component valid |
| Global supplemental idempotency broke ambiguity/run contracts | restored common runtime; exact replay reuse localized in end-to-end owner | old tests and replay both pass |
| Exact text replay reused Workload idempotency key | same parsed JSON with whitespace-only transport difference | same semantic input re-executed |
| Repeated private artifacts had new retention timestamps | exact ID/type/scope/payload reuse in product adapter; overwrite still forbidden | two downloads, one XML artifact |
| Installed Playwright `1.62.1` expected absent browser revision | used installed compatible `1.59.1 / Chromium 1217` | real browser completed |

Каждый blocker считается закрытым только по последующему full product replay.

## 5. Access proof

User A успешно загрузил source и дважды скачал XML. В отдельном browser
context User B получил:

- source: HTTP `404`;
- XML: HTTP `404`;
- chat: HTTP `401`.

Native source и оба XML файла имели одного владельца. ArtifactStore private
records были `validated/private_ready`; отдельный resolver regression отверг
wrong-user context.

## 6. Negative workflow proof

- Source без обязательного `amount` вернул source-financial blocker;
  XML artifact count для negative case: `0`.
- Полный synthetic fact submission без `declaration_date` вернул точный
  `declaration_date` blocker; XML и default не создавались.
- User B denial не требовал отключения ACL.

## 7. Final artifact proof

| Boundary | SHA-256 |
| --- | --- |
| Uploaded source | `fbf9d6bd6562b334943a15c5a70ea4bca959a507cdee7671f84128a3249b877c` |
| Authenticated case binding | `97c8f7e2a25d7c505d3a60314297b21af27fad5f9d67f4bb14394b2e92ed431a` |
| Gate 4 Financial Case | `0842d0c04732e55892c99bc3762bf1690d3ced28c60f8b53831bb000d8cc7d52` |
| Resolved Declaration Package | `e5f47dd1cf1799d865c07041f53ae935a0fd25658a98a759671e16e5f9e3e388` |
| Semantic Input | `9e2d7f6bdefc4e9362296fc13a07683168938b4322277da3bab3619fb5acbc83` |
| Projection Definition | `48109cc6b3de6fd4d242346648660d99b40863310e622ab2cec44dc641ec7b26` |
| Downloaded XML | `69a2185184ec9c076c8557defd746f04a664caa6fcbc457f494eae1b0b0b16f6` |
| Official XSD | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |
| 16-stage chain terminal | `18cc7fd596739b032c9d7b9aba90d5d465b945499fe0115edc6c4e88f3aca54c` |

Downloaded bytes, ArtifactStore XML payload, native file record and native
stored bytes had exact XML hash parity. Два фактических download были
byte-identical; оба well-formed и official-XSD-valid, `xsd_errors_total=0`.

Persistence aggregate: `49` case artifacts, `2` fact submissions, `1`
FinancialAnnotationsV2, `1` XML artifact, `2` delivery receipts.

## 8. Anti-drift audit

```text
second pipeline: NO
hidden G5.35 case fixture in product runtime/bundle: NO
Gate 1–5 owner bypass: NO
tax logic in UI/Pipe adapter: NO
direct provider client in product adapter: NO
provider mock in live smoke: NO
manual XML: NO
direct SQL as runtime authority: NO
ACL bypass: NO
Knowledge/RAG: NO
```

Product adapter delegates to
`Gate5EndToEndFullTargetXmlRuntime.continue_from_validated_gate3`; native XML
publication delegates to OpenWebUI `Storage` and `Files`. SQL was used only
after the run for read-only aggregate accounting, never as runtime authority.

## Regression and KISS

Expanded local Gate 5 + bundle + architecture run:

```text
280 passed
0 failed
```

The previous ambiguity and cross-run supplemental contracts remain intact;
replay behavior is localized to the end-to-end/product owners. Bundle hashes
are pinned, architecture allowlist explicitly names the single new adapter,
and no new service, endpoint, DB, registry, workflow profile or tax primitive
was introduced.

## Cleanup and limits

Post-proof live verification passed:

```text
final bundle hash exact: yes
ndfl_full_product_enabled: false
ndfl_gate3_private_audit_enabled: false
Function global: false
stable model public grants: none
temporary users remaining: 0
```

Это synthetic supplied-case proof, а не доказательство полноты реального
налогоплательщика и не legal/tax-correctness admission. Не выполнены и не
разрешены: real taxpayer pilot, PDF, отправка в ФНС, production-wide
activation, push или PR.

## 9. Terminal verdict

```text
USER
→ OPENWEBUI
→ UPLOAD
→ GATE 1–5
→ HUMAN RESIDUAL
→ DECLARATION_COMPLETE_FOR_SUPPLIED_CASE
→ XML
→ DOWNLOAD × 2
→ OFFICIAL XSD

REAL_PRODUCT_PATH_XML_VALID
blockers = 0
```

G5.36 завершён. Автоматического перехода к следующему GOAL нет.
