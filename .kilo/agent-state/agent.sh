#!/bin/sh
# Реестр занятых файлов для нескольких агентов в одном репозитории.
#
#   agent.sh claim   <агент> <путь> [путь...]   занять файлы до первой правки
#   agent.sh release <агент> [путь...]          освободить после коммита
#   agent.sh list                                показать занятое
#
# Хук .githooks/pre-commit проверяет этот реестр и не даст закоммитить чужой файл.

set -e

root=$(git rev-parse --show-toplevel)
claims="$root/.kilo/agent-state/claims"

if [ $# -lt 1 ]; then
	printf 'usage: agent.sh claim|release|list ...\n' >&2
	exit 2
fi

command=$1
shift

case "$command" in
	claim|release)
		if [ $# -lt 1 ]; then
			printf 'нужно имя агента\n' >&2
			exit 2
		fi
		;;
esac

mkdir -p "$claims"
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

case "$command" in
	claim)
		agent=$1
		shift
		if [ $# -eq 0 ]; then
			printf 'нужен хотя бы один путь\n' >&2
			exit 2
		fi
		for path in "$@"; do
			claim_file="$claims/$(printf '%s' "$path" | tr '/' '_')"
			if [ -f "$claim_file" ]; then
				owner=$(sed -n 's/^agent=//p' "$claim_file" | head -n 1)
				if [ -n "$owner" ] && [ "$owner" != "$agent" ]; then
					printf 'отказ: %s уже занят агентом %s\n' "$path" "$owner" >&2
					exit 1
				fi
			fi
			printf 'agent=%s\npath=%s\nsince=%s\n' "$agent" "$path" "$now" > "$claim_file"
			printf 'занято: %s -> %s\n' "$path" "$agent"
		done
		;;
	release)
		agent=$1
		shift
		if [ $# -eq 0 ]; then
			released=0
			for claim_file in "$claims"/* "$claims"/.[!.]*; do
				[ -f "$claim_file" ] || continue
				if grep -q "^agent=$agent\$" "$claim_file"; then
					path=$(sed -n 's/^path=//p' "$claim_file" | head -n 1)
					rm -f "$claim_file"
					printf 'освобождено: %s\n' "$path"
					released=1
				fi
			done
			[ "$released" -eq 1 ] || printf 'у агента %s нет занятых файлов\n' "$agent"
		else
			for path in "$@"; do
				claim_file="$claims/$(printf '%s' "$path" | tr '/' '_')"
				if [ ! -f "$claim_file" ]; then
					continue
				fi
				owner=$(sed -n 's/^agent=//p' "$claim_file" | head -n 1)
				if [ -n "$owner" ] && [ "$owner" != "$agent" ]; then
					printf 'отказ: %s занят агентом %s, не вами\n' "$path" "$owner" >&2
					exit 1
				fi
				rm -f "$claim_file"
				printf 'освобождено: %s\n' "$path"
			done
		fi
		;;
	list)
		found=0
		for claim_file in "$claims"/* "$claims"/.[!.]*; do
			[ -f "$claim_file" ] || continue
			found=1
			agent=$(sed -n 's/^agent=//p' "$claim_file" | head -n 1)
			path=$(sed -n 's/^path=//p' "$claim_file" | head -n 1)
			since=$(sed -n 's/^since=//p' "$claim_file" | head -n 1)
			printf '%-14s %-52s %s\n' "$agent" "$path" "$since"
		done
		[ "$found" -eq 1 ] || printf 'ничего не занято\n'
		;;
	*)
		printf 'неизвестная команда: %s\n' "$command" >&2
		exit 2
		;;
esac