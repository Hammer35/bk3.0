# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Продавцы маркетплейсов, владельцы малого бизнеса и контент-менеджеры, которым
нужно превращать товарный каталог в Pinterest-контент и органический трафик.

## Product Purpose

BOOSTKLIENT® помогает пройти путь от профиля бизнеса и исследования Pinterest
до стратегии, контент-плана, публикации и аналитики.

## Positioning

Продукт связывает каталог магазина, Pinterest-стратегию и ежедневную работу с
контентом в одной рабочей среде, а не работает как общий чат или планировщик.

## Operating Context

Пользователь создаёт рабочее пространство и профиль бизнеса, затем работает с
ИИ-стратегом в контексте выбранного бизнеса.

## Capabilities and Constraints

- Django Templates, HTMX, Alpine.js, Tailwind CSS и CSS design tokens;
- рабочие домены MVP: аккаунт, workspace, business и ИИ-стратег;
- русский и английский интерфейсы;
- светлая и тёмная темы;
- данные из разных workspace изолированы.

## Brand Commitments

BOOSTKLIENT® — Pinterest-экосистема для бизнеса. Для публичного продукта
зафиксирован визуальный язык black / white / signal-red, связанный с маршрутом
catalog → pin → organic traffic. Интерфейс не должен выглядеть как generic SaaS.

## Evidence on Hand

- `BOOSTKLIENT_3_PLAN.md` — продуктовый путь и MVP;
- `BOOSTKLIENT_3_DESIGN_SYSTEM.md` — архитектура приложения и UI-правила;
- `/home/evgen/projects/BoostKlient/Documentation/SITE_REDESIGN_REQUIREMENTS.md`
  — подтверждённые брендовые ограничения;
- `/home/evgen/projects/BoostKlient/static/fonts/landing/` — Manrope и Oswald
  с лицензиями и поддержкой кириллицы/латиницы.

## Product Principles

1. Пользователь быстро понимает контекст бизнеса и следующее действие.
2. ИИ-стратег работает с данными выбранного бизнеса, а не как общий чат.
3. Компоненты и темы едины, а состав и иерархия страниц следуют задаче.
4. Декор не заменяет данные, состояние или действие.

## Accessibility & Inclusion

Контраст, клавиатурный фокус, читаемые русские и английские тексты и адаптивная
компоновка обязательны для всех экранов.
