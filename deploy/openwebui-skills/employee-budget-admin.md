# Employee budget administration

For a request to open, view, configure or refresh employee budgets or limits,
call open_budget_form in the current turn, even if an older form is in history.
The form's refresh message "Обнови управление бюджетами" also requires a fresh call.
Use view_json only for display filters. Present the returned native form as the
main interface; do not ask which operation before opening it or suggest that
the user write or paste JSON plans. The form creates its own exact JSON proposal.
When the current user turn is a JSON employee_budget_plan,
employee_budget_template, employee_budget_initialize or provider_balance_snapshot, call apply_budget_form
with no business arguments. The server reads the exact saved parent user turn;
do not copy, rewrite or interpret its changes as tool arguments. Applying requires
the native server confirmation. Treat the returned fresh form as the result;
never claim that limits changed merely because a plan was drafted or submitted.
