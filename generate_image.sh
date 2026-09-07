#!/bin/bash
git pull

set -euo pipefail

REGISTRY="ghcr.io"
REPO_NAME="${REPO_NAME:-schulnetz-to-ha-integration}"

# ── Check if already logged in to ghcr.io ────────────────────────────────────
DOCKER_CONFIG="${DOCKER_CONFIG:-${HOME}/.docker}"
ALREADY_LOGGED_IN=false
GITHUB_USER="The12Forest"

if [ -f "${DOCKER_CONFIG}/config.json" ]; then
  if grep -q '"ghcr.io"' "${DOCKER_CONFIG}/config.json" 2>/dev/null; then
    AUTH_B64=$(grep -A2 '"ghcr.io"' "${DOCKER_CONFIG}/config.json" | grep '"auth"' | sed 's/.*"auth"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' 2>/dev/null || true)
    if [ -n "${AUTH_B64}" ]; then
      GITHUB_USER=$(echo "${AUTH_B64}" | base64 -d 2>/dev/null | cut -d: -f1 || true)
    fi
    if [ -n "${GITHUB_USER}" ]; then
      ALREADY_LOGGED_IN=true
      echo "✓ Already logged in to ${REGISTRY} as ${GITHUB_USER}"
    fi
  fi
  
  if [ "${ALREADY_LOGGED_IN}" = false ]; then
    CREDS_STORE=$(grep '"credsStore"' "${DOCKER_CONFIG}/config.json" 2>/dev/null | sed 's/.*"credsStore"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || true)
    if [ -z "${CREDS_STORE}" ]; then
      CREDS_STORE=$(sed -n '/"credHelpers"/,/}/p' "${DOCKER_CONFIG}/config.json" 2>/dev/null | grep '"ghcr.io"' | sed 's/.*"ghcr.io"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || true)
    fi
    if [ -n "${CREDS_STORE}" ] && command -v "docker-credential-${CREDS_STORE}" &>/dev/null; then
      STORED_USER=$(echo "ghcr.io" | "docker-credential-${CREDS_STORE}" get 2>/dev/null | grep -o '"Username"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"Username"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || true)
      if [ -n "${STORED_USER}" ]; then
        GITHUB_USER="${STORED_USER}"
        ALREADY_LOGGED_IN=true
        echo "✓ Already logged in to ${REGISTRY} as ${GITHUB_USER}"
      fi
    fi
  fi
fi

# ── Prompt for inputs ─────────────────────────────────────────────────────────
if [ "${ALREADY_LOGGED_IN}" = false ]; then
  if [ -z "${GITHUB_USER}" ]; then
    read -rp "GitHub username: " GITHUB_USER
  fi
  read -rsp "GitHub Personal Access Token (write:packages scope): " CR_PAT
  echo ""
  if [ -z "${GITHUB_USER}" ] || [ -z "${CR_PAT}" ]; then
    echo "ERROR: username and token are required."
    exit 1
  fi
fi

GITHUB_USER_LOWER=$(echo "${GITHUB_USER}" | tr '[:upper:]' '[:lower:]')

# ── Fetch latest published version from GHCR ─────────────────────────────────
get_latest_version() {
  local image_path="$1"
  local token=""

  if [ -n "${CR_PAT:-}" ]; then
    token="${CR_PAT}"
  elif [ -n "${AUTH_B64:-}" ]; then
    token=$(echo "${AUTH_B64}" | base64 -d 2>/dev/null | cut -d: -f2 || true)
  elif [ -n "${CREDS_STORE:-}" ] && command -v "docker-credential-${CREDS_STORE}" &>/dev/null; then
    token=$(echo "ghcr.io" | "docker-credential-${CREDS_STORE}" get 2>/dev/null \
      | grep -o '"Secret"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || true)
  fi

  if [ -z "${token}" ]; then
    echo ""
    return 0
  fi

  local bearer
  bearer=$(curl -sf -u "${GITHUB_USER}:${token}" \
    "https://ghcr.io/token?scope=repository:${image_path}:pull" 2>/dev/null \
    | grep -o '"token":"[^"]*"' | sed 's/"token":"//;s/"//' || true)

  if [ -z "${bearer}" ]; then
    echo ""
    return 0
  fi

  local tags
  tags=$(curl -sf -H "Authorization: Bearer ${bearer}" \
    "https://ghcr.io/v2/${image_path}/tags/list" 2>/dev/null || true)

  local latest
  latest=$(echo "${tags}" \
    | grep -oE '"[0-9]+(\.[0-9]+)+"' \
    | tr -d '"' \
    | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n \
    | tail -1 || true)

  echo "${latest}"
  return 0
}

IMAGE_PATH="${GITHUB_USER_LOWER}/${REPO_NAME}"
LATEST_VERSION=$(get_latest_version "${IMAGE_PATH}" || true)

if [ -n "${LATEST_VERSION}" ]; then
  echo ""
  echo "  Latest published version: ${LATEST_VERSION}"
  read -rp "  New image version: " VERSION
else
  read -rp "Image version (e.g. 1.0.0): " VERSION
fi

if [ -z "${VERSION}" ]; then
  echo "ERROR: version is required."
  exit 1
fi

# ── Login to GitHub Container Registry (only if needed) ──────────────────────
if [ "${ALREADY_LOGGED_IN}" = false ]; then
  echo "→ Logging in to ${REGISTRY} as ${GITHUB_USER}..."
  if ! echo "${CR_PAT}" | docker login "${REGISTRY}" -u "${GITHUB_USER}" --password-stdin; then
    echo "ERROR: Login to ${REGISTRY} failed."
    exit 1
  fi
fi

# ── Define Image ──────────────────────────────────────────────────────────────
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_PATH}"

# ── Build Image ───────────────────────────────────────────────────────────────
echo "→ Building ${FULL_IMAGE_NAME}:${VERSION} (also tagging as latest)..."
docker build \
  --tag "${FULL_IMAGE_NAME}:${VERSION}" \
  --tag "${FULL_IMAGE_NAME}:latest" \
  .

# ── Push Image ────────────────────────────────────────────────────────────────
echo "→ Pushing ${FULL_IMAGE_NAME}:${VERSION}..."
docker push "${FULL_IMAGE_NAME}:${VERSION}"

echo "→ Pushing ${FULL_IMAGE_NAME}:latest..."
docker push "${FULL_IMAGE_NAME}:latest"

echo ""
echo "✓ Done! Published: ${FULL_IMAGE_NAME}:${VERSION}"