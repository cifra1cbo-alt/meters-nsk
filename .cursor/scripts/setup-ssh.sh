#!/usr/bin/env bash
# SSH key bootstrap for Cloud Agent.
# Modes (in order):
#   1) SSH_PRIVATE_KEY env/secret present → write ~/.ssh/cursor_meters_nsk
#   2) Key already on disk (saved environment snapshot) → keep it
#   3) Otherwise → skip (use Remote Control / Mac host agent instead)
set -euo pipefail

KEY_PATH="${HOME}/.ssh/cursor_meters_nsk"
MARKER="# cursor_meters_nsk cloud-agent"

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

if [[ -n "${SSH_PRIVATE_KEY:-}" ]]; then
  printf '%s\n' "${SSH_PRIVATE_KEY}" | tr -d '\r' > "${KEY_PATH}"
  chmod 600 "${KEY_PATH}"
  echo "setup-ssh: installed key from SSH_PRIVATE_KEY"
elif [[ -f "${KEY_PATH}" ]]; then
  chmod 600 "${KEY_PATH}"
  echo "setup-ssh: reusing existing ${KEY_PATH} (snapshot/local)"
else
  echo "setup-ssh: no key — skip (Remote Control on Mac or add key before Update Env)"
  exit 0
fi

# Default identity for plain `ssh user@host`
ln -sfn "${KEY_PATH}" "${HOME}/.ssh/id_ed25519"
chmod 600 "${HOME}/.ssh/id_ed25519" 2>/dev/null || true

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

if command -v ssh-add >/dev/null 2>&1; then
  if [[ -z "${SSH_AUTH_SOCK:-}" ]] || [[ ! -S "${SSH_AUTH_SOCK}" ]]; then
    eval "$(ssh-agent -s)" >/dev/null
  fi
  ssh-add "${KEY_PATH}" 2>/dev/null || true
fi

echo "setup-ssh: ready ${KEY_PATH}"
