# Validates file writes stay within project root
if [[ "$CLAUDE_TOOL_NAME" == "Write" || "$CLAUDE_TOOL_NAME" == "Edit" ]]; then
  PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  if [[ "$CLAUDE_TOOL_OUTPUT" != "$PROJECT_ROOT"* ]]; then
    echo "WARNING: Write outside project root detected"
  fi
fi
