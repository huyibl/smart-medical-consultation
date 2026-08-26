# 默认只拉 API。本机已有 Neo4j 时不要加 -Neo4j。
param(
    [switch]$Neo4j,
    [switch]$Redis,
    [switch]$Mysql,
    [switch]$Build
)
$profiles = @()
if ($Neo4j) { $profiles += "--profile"; $profiles += "neo4j" }
if ($Redis) { $profiles += "--profile"; $profiles += "redis" }
if ($Mysql) { $profiles += "--profile"; $profiles += "mysql" }
$args = @("-f", "deploy/docker-compose.yml") + $profiles + @("up", "-d")
if ($Build) { $args += "--build" }
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose @args
