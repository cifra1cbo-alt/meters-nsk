# Подключение к серверу

Инструкция по SSH-доступу для **meters-nsk.ru** и сервера Max.

> IP, пароли и приватные ключи **не коммитьте** в git.

## Два режима работы агента

| Режим | Где крутится агент | Ключ SSH | Когда удобно |
|---|---|---|---|
| **A. Remote Control** | На вашем Mac | Уже в `~/.ssh/cursor_meters_nsk` | Телефон управляет Mac, Mac включён |
| **B. Cloud Agent** | Облачная VM Cursor | Нужен секрет или snapshot | Mac выключен, работа только из облака |

Можно пользоваться **обоими**: с телефона через Mac (A) или чистым облаком (B).

---

## Режим A — без Secrets (Remote Control)

1. На Mac есть ключ: `~/.ssh/cursor_meters_nsk`
2. Публичный ключ на сервере (один раз):
   ```bash
   ssh-copy-id -i ~/.ssh/cursor_meters_nsk.pub <SSH_USER>@<SERVER_IP>
   ```
3. Cursor → **Settings → Agents**:
   - **Remote Control** → **ON**
   - **Keep This Computer Awake** → **ON** (Mac от розетки)
4. С телефона/web открывайте агента — он идёт через Mac, SSH на сервер стабилен.

Минус: Mac должен быть включён.

---

## Режим B — Cloud Agent (Mac может быть выключен)

Облачная VM **каждый раз новая**. Ключ с диска прошлой сессии не переносится сам.

### Постоянный вариант для облака (рекомендуется)

1. Cursor Secrets → `SSH_PRIVATE_KEY` = содержимое `~/.ssh/cursor_meters_nsk`
2. В репо уже есть:
   - `.cursor/environment.json`
   - `.cursor/scripts/setup-ssh.sh` — при старте кладёт ключ в `~/.ssh/`
3. [Cloud Agents dashboard](https://cursor.com/dashboard/cloud-agents) → **Update Existing Env**
4. Написать агенту «готово» и проверить SSH

Без Secrets у Cloud Agent доступ снова «выпадет» после новой сессии.

### Если Secrets недоступны (браузер не грузит)

Временный обход: вставить ключ в чат → агент положит в `~/.ssh` **только на эту сессию**.  
Для постоянства потом всё равно нужны Secrets + Update Env.

---

## Проверка

```bash
ssh -i ~/.ssh/cursor_meters_nsk <SSH_USER>@<SERVER_IP> "whoami && hostname && uptime"
```

---

## Безопасность

- Отдельный ключ `cursor_meters_nsk`, не основной `id_ed25519`
- Не коммитьте приватный ключ
- Если ключ светился в чате — перевыпустите и обновите `authorized_keys` + Secrets

### Удалить ключ с сервера

```bash
ssh <SSH_USER>@<SERVER_IP> "sed -i '/cursor_meters_nsk/d' ~/.ssh/authorized_keys"
```

### Удалить ключ с Mac

```bash
rm -f ~/.ssh/cursor_meters_nsk ~/.ssh/cursor_meters_nsk.pub
```
