# Подключение к серверу

Инструкция по SSH-доступу для работы с сервером и деплоем сайта **meters-nsk.ru**.

> **Важно:** реальные IP, имена серверов, пользователи и ключи **не храните в git**.
> Заполните значения локально или в Secrets Cursor.

## Параметры (локально, не в репозитории)

| Параметр | Значение |
|---|---|
| Хост | `<SERVER_IP>` |
| Пользователь SSH | `<SSH_USER>` |
| Провайдер / регион | `<описание>` |
| ОС | Ubuntu 24.04 (пример) |

Root-пароль панели хостинга — только в менеджере паролей, **не коммитьте**.

## Подключение с вашей машины

```bash
ssh <SSH_USER>@<SERVER_IP>
```

Вход по SSH-ключу.

---

## Доступ для Cloud Agent (Cursor)

Агент работает в облачном окружении и не видит ключи на вашем Mac.
Используйте **отдельный временный ключ** `cursor_meters_nsk` — не основной ключ от Mac.

### Шаг 1 — создать временный ключ

На Mac:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/cursor_meters_nsk -C "cursor_meters_nsk" -N ""
```

### Шаг 2 — добавить публичный ключ на сервер

```bash
ssh-copy-id -i ~/.ssh/cursor_meters_nsk.pub <SSH_USER>@<SERVER_IP>
```

Или вручную:

```bash
cat ~/.ssh/cursor_meters_nsk.pub | ssh <SSH_USER>@<SERVER_IP> \
  'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

### Шаг 3 — передать приватный ключ агенту

1. Скопируйте содержимое `~/.ssh/cursor_meters_nsk` (весь файл, включая `BEGIN` / `END`).
2. Cursor → **Settings → Secrets** → создайте секрет `SSH_PRIVATE_KEY`.
3. Напишите агенту **«готово»**.

Это **временный** ключ только для работы агента — не ваш личный `id_ed25519`.

---

## Проверка подключения

После настройки агент выполнит:

```bash
ssh -i ~/.ssh/cursor_meters_nsk <SSH_USER>@<SERVER_IP> "whoami && hostname && uptime"
```

---

## Текущее состояние проекта

| Что | Статус |
|---|---|
| Репозиторий | Статический сайт (`index.html`, `privacy.html`, `thanks.html`) |
| Домен `meters-nsk.ru` | Проверьте DNS и хостинг отдельно |

---

## Безопасность

- Не коммитьте IP, пароли, приватные и публичные ключи.
- Не передавайте агенту **личный** SSH-ключ с Mac — только `cursor_meters_nsk`.
- После работы:
  - удалите секрет `SSH_PRIVATE_KEY` из Cursor;
  - удалите ключ с сервера (команда ниже);
  - при необходимости удалите файлы `~/.ssh/cursor_meters_nsk*` на Mac.

### Удалить временный ключ с сервера

```bash
ssh <SSH_USER>@<SERVER_IP> "sed -i '/cursor_meters_nsk/d' ~/.ssh/authorized_keys"
```
