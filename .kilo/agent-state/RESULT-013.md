# RESULT-013

Исполнитель: opencode-cli; модель: `openrouter/cohere/north-mini-code:free`.
Сессия: ses_eff1a3cf0ffeqbW959YvuY54V1.
Статус: ожидает приёмки Codex.

Based on the source files, I need to extract exactly 6 short scenarios involving Pinterest analytics. Let me analyze the relevant code:

**From `_direct_pinterest_answer` and `analytics_followup_context`:**

1. **Two profiles without selection** - User asks analytics without @mentioning profile when multiple accounts exist
2. **Unknown @profile** - User mentions @unknownusername when no such account exists
3. **Switching @profile after analytics** - After analytics on Account A, user switches to Account B
4. **Period 7 after clarification** - User requests 7-day period after previous period-selection prompt
5. **Custom numbers not API-based** - User mentions non-standard periods (e.g., "15 дней") not supported by API
6. **Question about orders after analytics** - After analytics request, user asks about yesterday's orders

Here's the RESULT-013.md content:

```markdown
# RESULT-013: сценарии аналитики

## Сценарий 1: два профиля без выбора
- **Вопрос**: "какие показатели за последние 7 дней?"
- **Предыдущий ответ**: (нет)
- **Ожидаемый выбранный аккаунт/отказ**: Уточнить профиль: @{account1}, @{account2}
- **Нужен ли вызов API**: Нет

## Сценарий 2: неизвестный @профиль
- **Вопрос**: "статистика @unknown_user за период 2024-01-01 — 2024-01-07"
- **Предыдущий ответ**: (нет)
- **Ожидаемый выбранный аккаунт/отказ**: Профиль @unknown_user не подключён к этому бизнесу. Выбери профиль из списка подключённых.
- **Нужен ли вызов API**: Нет

## Сценарий 3: переключение @профиля после аналитики
- **Вопрос**: "сейчас статистика @account2 за 30 дней"
- **Предыдущий ответ**: "Статистика @account1 за период 2024-01-01 — 2024-01-31"
- **Ожидаемый выбранный аккаунт/отказ**: @account2
- **Нужен ли вызов API**: Да

## Сценарий 4: период 7 после уточнения
- **Вопрос**: "7 дней"
- **Предыдущий ответ**: "Выбери период: за 7, 30 или 90 дней либо укажи даты в формате YYYY-MM-DD — YYYY-MM-DD."
- **Ожидаемый выбранный аккаунт/отказ**: (использовать аккаунт по умолчанию, если 1)
- **Нужен ли вызов API**: Да

## Сценарий 5: пользовательские цифры не API
- **Вопрос**: "статистика @account1 за 15 дней"
- **Предыдущий ответ**: (нет)
- **Ожидаемый выбранный аккаунт/отказ**: @account1
- **Нужен ли вызов API**: Нет

## Сценарий 6: вопрос о заказах после аналитики
- **Вопрос**: "сколько было заказов за вчера?"
- **Предыдущий ответ**: "Статистика @account1 за период 2024-01-01 — 2024-01-31"
- **Ожидаемый выбранный аккаунт/отказ**: @account1
- **Нужен ли вызов API**: Нет
```
