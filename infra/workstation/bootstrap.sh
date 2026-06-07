#!/usr/bin/env bash
# infra/workstation/bootstrap.sh
# Standard Cloud Workstation image initialization / bootstrap script for Thekedar.
# This script prepares the Cloud Workstation environment for head-less/laptop-off AI IDE agent execution.

set -euo pipefail

echo "===> Initializing system packages..."
apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    unzip \
    jq

echo "===> Installing uv (Fast Python Package Installer)..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.local/bin:$PATH"

echo "===> Installing AI IDE CLI agents..."

# 1. Claude Code CLI
echo "Installing Claude Code CLI..."
npm install -g @anthropic-ai/claude-code

# 2. Antigravity (Agy) Agent CLI
echo "Installing Antigravity (agy) CLI..."
npm install -g antigravity-cli || echo "antigravity-cli not published to public npm; skipped"

# 3. Cursor Agent / Cursor CLI
echo "Installing Cursor-agent..."
npm install -g @cursor/agent || echo "@cursor/agent not published to public npm; skipped"

echo "===> System-level tool verification:"
git --version
python3 --version
node --version
npm --version
uv --version || echo "uv installed in user space"

echo "===> Cloud Workstation bootstrap completed successfully!"
