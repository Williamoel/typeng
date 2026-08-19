#!/bin/sh
set -eu

lexicon_path="${TYPENG_LEXICON_PATH:-}"
lexicon_url="${TYPENG_LEXICON_URL:-}"

if [ -n "$lexicon_path" ] && [ -n "$lexicon_url" ] && [ ! -s "$lexicon_path" ]; then
  mkdir -p "$(dirname "$lexicon_path")"
  TYPENG_DOWNLOAD_TARGET="$lexicon_path" TYPENG_DOWNLOAD_URL="$lexicon_url" python - <<'PY'
import os
import urllib.request
from pathlib import Path

target = Path(os.environ["TYPENG_DOWNLOAD_TARGET"])
temporary = target.with_suffix(target.suffix + ".download")
try:
    urllib.request.urlretrieve(os.environ["TYPENG_DOWNLOAD_URL"], temporary)
    temporary.replace(target)
    print(f"Downloaded runtime lexicon to {target}")
except Exception as exc:
    temporary.unlink(missing_ok=True)
    print(f"Runtime lexicon download skipped: {exc}")
PY
fi

exec gunicorn \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --threads 8 \
  --timeout 60 \
  wsgi:app
