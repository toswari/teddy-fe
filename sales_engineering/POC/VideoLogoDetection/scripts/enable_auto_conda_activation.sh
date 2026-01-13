#!/usr/bin/env zsh
# Enable auto-activation of the VideoDetection-312 conda environment for new interactive shells
set -euo pipefail

ENV_NAME="VideoDetection-312"
BLOCK_START="# >>> video-detection auto-conda >>>"
BLOCK_END="# <<< video-detection auto-conda <<<"

append_block() {
  local rcfile="$1"
  if [[ ! -f "$rcfile" ]]; then
    touch "$rcfile"
  fi
  if grep -q "$BLOCK_START" "$rcfile"; then
    echo "Block already present in $rcfile"
    return 0
  fi
  cat >> "$rcfile" <<'EOF'
# >>> video-detection auto-conda >>>
# Auto-activate project conda env for interactive shells
if [[ "$-" == *i* ]]; then
  # Ensure conda is available in this shell
  if command -v conda >/dev/null 2>&1; then
    eval "$(conda shell.zsh hook)"
    conda activate VideoDetection-312 2>/dev/null || true
  else
    # Fallback: try sourcing common conda locations
    for cpath in "$HOME/miniconda3/etc/profile.d/conda.sh" \
                 "$HOME/anaconda3/etc/profile.d/conda.sh" \
                 "/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh" \
                 "/opt/homebrew/Caskroom/mambaforge/base/etc/profile.d/conda.sh"; do
      if [[ -r "$cpath" ]]; then
        source "$cpath"
        conda activate VideoDetection-312 2>/dev/null || true
        break
      fi
    done
  fi
fi
# <<< video-detection auto-conda <<<
EOF
  echo "Added auto-activation block to $rcfile"
}

# Update zsh and bash rc files when available
if [[ -n "${ZDOTDIR:-}" && -f "${ZDOTDIR}/.zshrc" ]]; then
  append_block "${ZDOTDIR}/.zshrc"
elif [[ -f "$HOME/.zshrc" ]]; then
  append_block "$HOME/.zshrc"
fi

if [[ -f "$HOME/.bashrc" ]]; then
  # Adapt block for bash by switching hook
  if ! grep -q "$BLOCK_START" "$HOME/.bashrc"; then
    cat >> "$HOME/.bashrc" <<'EOF'
# >>> video-detection auto-conda >>>
# Auto-activate project conda env for interactive shells
if [[ "$-" == *i* ]]; then
  if command -v conda >/dev/null 2>&1; then
    eval "$(conda shell.bash hook)"
    conda activate VideoDetection-312 2>/dev/null || true
  else
    for cpath in "$HOME/miniconda3/etc/profile.d/conda.sh" \
                 "$HOME/anaconda3/etc/profile.d/conda.sh" \
                 "/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh" \
                 "/opt/homebrew/Caskroom/mambaforge/base/etc/profile.d/conda.sh"; do
      if [[ -r "$cpath" ]]; then
        source "$cpath"
        conda activate VideoDetection-312 2>/dev/null || true
        break
      fi
    done
  fi
fi
# <<< video-detection auto-conda <<<
EOF
    echo "Added auto-activation block to $HOME/.bashrc"
  else
    echo "Block already present in $HOME/.bashrc"
  fi
fi

echo "Done. Open a new terminal to see the environment auto-activated (VideoDetection-312)."