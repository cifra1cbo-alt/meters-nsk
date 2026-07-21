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

## Постоянный доступ для Cloud Agent (Cursor)

Cloud Agent каждый раз стартует в **новой** VM. Файл ключа на диске VM **не сохраняется**.
Постоянный доступ = **Secrets + install-скрипт + публичный ключ на сервере**.

В этом репозитории уже есть:

- `.cursor/environment.json` — при старте вызывает setup
- `.cursor/scripts/setup-ssh.sh` — кладёт ключ из секрета в `~/.ssh/cursor_meters_nsk`

### Шаг 1 — создать отдельный ключ (один раз на Mac)

Не используйте основной ключ Mac (`id_ed25519`). Только отдельный:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/cursor_meters_nsk -C "cursor_meters_nsk" -N ""
```

### Шаг 2 — добавить публичный ключ на сервер (один раз)

```bash
ssh-copy-id -i ~/.ssh/cursor_meters_nsk.pub <SSH_USER>@<SERVER_IP>
```

Или вручную:

```bash
cat ~/.ssh/cursor_meters_nsk.pub | ssh <SSH_USER>@<SERVER_IP> \
  'mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

Проверка:

```bash
ssh <SSH_USER>@<SERVER_IP> "grep cursor_meters_nsk ~/.ssh/authorized_keys"
```

### Шаг 3 — секрет в Cursor (постоянно)

1. Скопируйте приватный ключ:
   ```bash
   cat ~/.ssh/cursor_meters_nsk | pbcopy
   ```
2. Откройте [Cloud Agents → Secrets](https://cursor.com/dashboard/cloud-agents)  
   (или Cursor → **Settings → Secrets**).
3. Создайте секрет:
   - **Имя:** `SSH_PRIVATE_KEY`
   - **Тип:** Runtime Secret
   - **Значение:** весь файл (`-----BEGIN` … `-----END`)
4. **Не** вставляйте ключ в чат с агентом.

### Шаг 4 — обновить окружение агента (обязательно)

После добавления/смены секрета:

1. [cursor.com/dashboard/cloud-agents](https://cursor.com/dashboard/cloud-agents)
2. Ваше окружение / агент → **Start Setup Agent** → **Update Existing Env**  
   (или **Start Fresh**, если окружения ещё нет)
3. Дождитесь успешного install (`setup-ssh.sh`)
4. Напишите агенту **«готово»**

Без Update Env новая сессия может стартовать без секрета.

### Шаг 5 — проверка

Агент должен успешно выполнить:

```bash
ssh -i ~/.ssh/cursor_meters_nsk <SSH_USER>@<SERVER_IP> "whoami && hostname && uptime"
```

или просто:

```bash
ssh <SSH_USER>@<SERVER_IP> "whoami"
```

---

## Почему доступ «выпадал»

| Причина | Что происходит |
|---|---|
| Ключ только на диске старой VM | Новая сессия = пустой `~/.ssh/` |
| Ключ вставлен в чат | Работает один раз, не постоянно |
| Нет секрета `SSH_PRIVATE_KEY` | Скрипт setup-ssh пропускает установку |
| Секрет добавлен, но Env не обновлён | Старая сборка без секрета |

---

## Текущее состояние проекта

| Что | Статус |
|---|---|
| Репозиторий | Статический сайт + Cloud Agent SSH setup |
| `.cursor/environment.json` | install → `setup-ssh.sh` |
| Домен `meters-nsk.ru` | Проверьте DNS и хостинг отдельно |

---

## Безопасность

- Не коммитьте IP, пароли, приватные и публичные ключи.
- Не передавайте агенту **личный** SSH-ключ с Mac — только `cursor_meters_nsk`.
- Runtime Secret не должен светиться в чате; всё равно не вставляйте ключ в сообщения.
- Если ключ скомпрометирован — удалите строку с сервера и перевыпустите ключ.

### Удалить ключ с сервера

```bash
ssh <SSH_USER>@<SERVER_IP> "sed -i '/cursor_meters_nsk/d' ~/.ssh/authorized_keys"
```

### Удалить ключ с Mac

```bash
rm -f ~/.ssh/cursor_meters_nsk ~/.ssh/cursor_meters_nsk.pub
```

### Удалить секрет в Cursor

Settings / Cloud Agents → Secrets → удалить `SSH_PRIVATE_KEY` → Update Env.
