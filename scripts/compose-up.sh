#!/usr/bin/env sh
# 默认只拉 API。本机已有 Neo4j 时不要加 --neo4j。
set -eu
cd "$(dirname "$0")/.."
PROFILES=""
BUILD=""
for arg in "$@"; do
  case "$arg" in
    --neo4j) PROFILES="$PROFILES --profile neo4j" ;;
    --redis) PROFILES="$PROFILES --profile redis" ;;
    --mysql) PROFILES="$PROFILES --profile mysql" ;;
    --build) BUILD="--build" ;;
  esac
done
# shellcheck disable=SC2086
docker compose -f deploy/docker-compose.yml $PROFILES up -d $BUILD
