#!/bin/bash

# Script pour afficher les logs de cnamsign
# Usage :
#   ./showlogs.sh            -> affiche les 50 dernieres lignes
#   ./showlogs.sh 100        -> affiche les 100 dernieres lignes
#   ./showlogs.sh 50 -f      -> affiche et suit en direct

LINES=50
FOLLOW=""

for arg in "$@"; do
    case "$arg" in
        -f|--follow)
            FOLLOW="-f"
            ;;
        *)
            if [[ "$arg" =~ ^[0-9]+$ ]]; then
                LINES="$arg"
            fi
            ;;
    esac
done

LOG_FILE="logs.txt"

if [ -f "$LOG_FILE" ]; then
    if [ -n "$FOLLOW" ]; then
        tail -n "$LINES" -f "$LOG_FILE"
    else
        tail -n "$LINES" "$LOG_FILE"
    fi
else
    if [ -n "$FOLLOW" ]; then
        docker compose logs -f --tail "$LINES" cnamsign
    else
        docker compose logs --tail "$LINES" cnamsign
    fi
fi
