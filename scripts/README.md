# scripts/

Developer utility scripts. All scripts assume they are executed from the repo root.

| Script | Purpose |
|---|---|
| `load_env.sh` | Source `.env` files for a given package into the current shell session. |

## Usage

```bash
# Load backend environment variables into your current shell
source scripts/load_env.sh backend

# Load agent environment variables
source scripts/load_env.sh agents
```

## Adding scripts

Place new scripts here with descriptive names (`verb_noun.sh` convention).
Ensure every script:
- Has a `#!/usr/bin/env bash` shebang.
- Uses `set -euo pipefail`.
- Is idempotent where possible.
- Never prints secret values.
- Has a brief comment at the top describing its purpose and usage.
