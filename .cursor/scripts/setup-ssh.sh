#!/usr/bin/env bash
# Writes SSH_PRIVATE_KEY (Cursor Runtime Secret) into ~/.ssh for Cloud Agent sessions.
# Idempotent: safe to run on every agent boot.
set -euo pipefail

KEY_PATH="${HOME}/.ssh/cursor_meters_nsk"
MARKER="# cursor_meters_nsk cloud-agent"

if [[ -z "${SSH_PRIVATE_KEY:-}" ]]; then
  echo "setup-ssh: SSH_PRIVATE_KEY secret not set — skipping SSH key install"
  exit 0
fi

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

# Normalize newlines / strip accidental CR from mobile paste
printf '%s\n' "${SSH_PRIVATE_KEY}" | tr -d '\r' > "${KEY_PATH}"
chmod 600 "${KEY_PATH}"

# Prefer dedicated key name; also expose as default identity for plain `ssh user@host`
ln -sfn "${KEY_PATH}" "${HOME}/.ssh/id_ed25519"
chmod 600 "${HOME}/.ssh/id_ed25519" 2>/dev/null || true

# Minimal SSH client defaults (no host secrets in repo)
if [[ ! -f "${HOME}/.ssh/config" ]] || ! grep -q "IdentityFile ${KEY_PATH}" "${HOME}/.ssh/config" 2>/dev/null; then
  cat >> "${HOME}/.ssh/config" <<EOF
${MARKER}
Host *
  IdentityFile ${KEY_PATH}
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
EOF
  chmod 600 "${HOME}/.ssh/config"
fi

# Optional: load into agent if available
if command -v ssh-add >/dev/null 2>&1; then
  if [[ -z "${SSH_AUTH_SOCK:-}" ]] || [[ ! -S "${SSH_AUTH_SOCK}" ]]; then
    eval "$(ssh-agent -s)" >/dev/null
  fi
  ssh-add "${KEY_PATH}" 2>/dev/null || true
fi

echo "setup-ssh: installed ${KEY_PATH}"
