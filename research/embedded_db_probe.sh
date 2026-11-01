#!/usr/bin/env bash
# Reproduz as medisoes de research/embedded-db-options.md:
#   1. quais pacotes tem wheel cp39 para linux (python:3.9-slim) e quanto ocupam instalados
#   2. o que acontece com um arquivo de banco em restart x recriacao x volume x bind mount
#
# Uso:
#   bash research/embedded_db_probe.sh            # tudo
#   bash research/embedded_db_probe.sh wheels     # so disponibilidade de wheel
#   bash research/embedded_db_probe.sh sizes      # so tamanho instalado
#   bash research/embedded_db_probe.sh lifecycle  # so o ciclo de vida do container
set -euo pipefail

IMAGE="${IMAGE:-python:3.9-slim}"
MODE="${1:-all}"
TMP="$(mktemp -d)"
CTR=probe-c
VOL=probe-vol
IMG=probe-img

cleanup() {
  docker rm -f "$CTR" >/dev/null 2>&1 || true
  docker volume rm "$VOL" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

wheels() {
  echo "== wheels/import em $IMAGE =="
  docker run --rm "$IMAGE" bash -c '
    python -c "import sys, sqlite3, dbm.gnu; print(\"python\", sys.version.split()[0], \"| sqlite3\", sqlite3.sqlite_version, \"| dbm.gnu ok\")"
    for p in duckdb lmdb rocksdict tinydb zodb h5py tables pyarrow bsddb3; do
      if python -m pip download --no-deps -q -d /tmp/$p "$p" >/tmp/$p.log 2>&1; then
        echo "OK   $p -> $(basename $(ls /tmp/$p/*) )"
      else
        echo "FAIL $p -> $(grep -iE "error|no matching" /tmp/$p.log | tail -1 | cut -c1-110)"
      fi
    done'
}

sizes() {
  echo
  echo "== tamanho instalado (pip install --target) =="
  docker run --rm "$IMAGE" bash -c '
    for p in duckdb lmdb rocksdict tinydb zodb h5py pyarrow; do
      rm -rf /tmp/t
      python -m pip install -q --no-cache-dir --target /tmp/t "$p" >/dev/null 2>&1
      echo "$p $(du -sm /tmp/t | cut -f1)MB"
    done'
}

lifecycle() {
  echo
  echo "== ciclo de vida: writable layer x volume x bind mount =="
  mkdir -p "$TMP/ctx" "$TMP/hostdata"
  cat > "$TMP/ctx/store.py" <<'PY'
import os, sqlite3
path = os.environ.get('DB_PATH', '/app/data/store.sqlite')
os.makedirs(os.path.dirname(path), exist_ok=True)
con = sqlite3.connect(path)
con.execute('create table if not exists t (x)')
con.execute('insert into t values (1)')
con.commit()
print('  rows:', con.execute('select count(*) from t').fetchone()[0])
PY
  cat > "$TMP/ctx/Dockerfile" <<'DOCKER'
FROM python:3.9-slim
WORKDIR /app
COPY . .
CMD ["python", "store.py"]
DOCKER
  docker build -q -t "$IMG" "$TMP/ctx" >/dev/null
  docker rm -f "$CTR" >/dev/null 2>&1 || true

  echo "run (camada do container):"; docker run --name "$CTR" "$IMG"
  echo "stop + start (mesmo container):"
  docker stop "$CTR" >/dev/null; docker start "$CTR" >/dev/null; sleep 1; docker logs "$CTR" | tail -1
  echo "rm + run (recriado, sem volume):"
  docker rm -f "$CTR" >/dev/null; docker run --name "$CTR" "$IMG"
  docker rm -f "$CTR" >/dev/null

  echo "volume nomeado, run:"; docker volume rm -f "$VOL" >/dev/null 2>&1 || true
  docker run --name "$CTR" -e DB_PATH=/data/store.sqlite -v "$VOL":/data "$IMG"
  echo "volume, rm + run:"; docker rm -f "$CTR" >/dev/null
  docker run --name "$CTR" -e DB_PATH=/data/store.sqlite -v "$VOL":/data "$IMG"
  docker rm -f "$CTR" >/dev/null; docker volume rm "$VOL" >/dev/null

  echo "bind mount, run:"; rm -f "$TMP/hostdata"/*
  docker run --name "$CTR" -e DB_PATH=/data/store.sqlite -v "$TMP/hostdata":/data "$IMG"
  echo "  arquivo no host: $(ls "$TMP/hostdata")"
  docker rm -f "$CTR" >/dev/null

  echo "arquivo de banco no contexto de build (COPY . .):"
  mkdir -p "$TMP/ctx/data"
  python3 - "$TMP/ctx/data/store.sqlite" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
con.execute('create table if not exists t (x)')
con.executemany('insert into t values (1)', [() for _ in range(5)])
con.commit()
print('  linhas assadas no build:', con.execute('select count(*) from t').fetchone()[0])
PY
  docker build -q -t "$IMG" "$TMP/ctx" >/dev/null
  docker run --name "$CTR" "$IMG"; docker rm -f "$CTR" >/dev/null

  docker rmi -f "$IMG" >/dev/null 2>&1 || true
}

case "$MODE" in
  all)       wheels; sizes; lifecycle ;;
  wheels)    wheels ;;
  sizes)     sizes ;;
  lifecycle) lifecycle ;;
  *)         echo "uso: $0 [all|wheels|sizes|lifecycle]" >&2; exit 2 ;;
esac
