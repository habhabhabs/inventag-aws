# bash completion for inventag. Made by 'inventag completion bash'.
_inventag_words() {
    COMPREPLY=( $(compgen -W "$1" -- "$cur") )
}

_inventag_files() {
    compopt -o filenames 2>/dev/null
    local IFS=$'\n'
    COMPREPLY=( $(compgen -f -- "$cur") )
}

_inventag_dirs() {
    compopt -o filenames 2>/dev/null
    local IFS=$'\n'
    COMPREPLY=( $(compgen -d -- "$cur") )
}

_inventag() {
    local cur prev path word i
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev=""
    if (( COMP_CWORD > 0 )); then prev="${COMP_WORDS[COMP_CWORD-1]}"; fi
    # bash splits '--option=value' at the '=': look one word further back.
    if [[ "$cur" == "=" ]]; then
        cur=""
    elif [[ "$prev" == "=" && $COMP_CWORD -ge 2 ]]; then
        prev="${COMP_WORDS[COMP_CWORD-2]}"
    fi
    path=""
    # The word after the command name picks a command, as in the program.
    if (( COMP_CWORD > 1 )); then
        case "${COMP_WORDS[1]}" in
            tool|shell) path="${COMP_WORDS[1]}" ;;
        esac
    fi
    if [[ -n "$path" ]]; then
        for (( i = 2; i < COMP_CWORD; i++ )); do
            word="${COMP_WORDS[i]}"
            case "$path $word" in
                "tool run"|"tool show") path="$path $word" ;;
            esac
        done
    fi
    case "$path|$prev" in
        "|--output-directory") _inventag_dirs; return 0 ;;
        "|--accounts-file") _inventag_files; return 0 ;;
        "|--mode") _inventag_words 'fast slow aws:kms'; return 0 ;;
        "|--name") COMPREPLY=(); return 0 ;;
        "tool run|--out"|"tool run|-o") COMPREPLY=(); return 0 ;;
    esac
    if [[ "$cur" == -* ]]; then
        case "$path" in
            "") _inventag_words '-h --help -v --verbose --output-directory --accounts-file --mode --name --color --no-color --version' ;;
            "tool") _inventag_words '-h --help --dry' ;;
            "tool run") _inventag_words '-h --help --force -f --out -o' ;;
            "tool show") _inventag_words '-h --help' ;;
            "shell") _inventag_words '-h --help' ;;
        esac
        return 0
    fi
    case "$path" in
        "") (( COMP_CWORD == 1 )) && _inventag_words 'tool shell' ;;
        "tool") _inventag_words 'run show' ;;
        "tool run") _inventag_files ;;
        "tool show") _inventag_words 'one two' ;;
        "shell") _inventag_words 'bash zsh' ;;
    esac
    return 0
}

complete -F _inventag inventag
