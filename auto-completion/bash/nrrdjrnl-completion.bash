#/usr/bin/env bash
# bash completion for nrrdjrnl

shopt -s progcomp
_nrrdjrnl() {
    local cur prev firstword complete_options
    
    cur=$2
    prev=$3
	firstword=$(__get_firstword)

	GLOBAL_OPTIONS="\
        config\
        delete\
        list\
        open\
        search\
        shell\
        version\
        --config\
        --help"

    CONFIG_OPTIONS="--help"
    DELETE_OPTIONS="--help --force"
    LIST_OPTIONS="--help --page"
    LIST_OPTIONS_WA="--start --end"
    OPEN_OPTIONS="--help"
    SEARCH_OPTIONS="--help --page"
    SHELL_OPTIONS="--help"
    VERSION_OPTIONS="--help"

	case "${firstword}" in
	config)
		complete_options="$CONFIG_OPTIONS"
		complete_options_wa=""
		;;
	delete)
		complete_options="$DELETE_OPTIONS"
		complete_options_wa=""
		;;
	list)
		complete_options="$LIST_OPTIONS"
		complete_options_wa="$LIST_OPTIONS_WA"
		;;
	open)
		complete_options="$OPEN_OPTIONS"
		complete_options_wa=""
		;;
	search)
		complete_options="$SEARCH_OPTIONS"
		complete_options_wa=""
		;;
 	shell)
		complete_options="$SHELL_OPTIONS"
		complete_options_wa=""
		;;
	version)
		complete_options="$VERSION_OPTIONS"
		complete_options_wa=""
		;;

	*)
        complete_options="$GLOBAL_OPTIONS"
        complete_options_wa=""
		;;
	esac


    for opt in "${complete_options_wa}"; do
        [[ $opt == $prev ]] && return 1 
    done

    all_options="$complete_options $complete_options_wa"
    COMPREPLY=( $( compgen -W "$all_options" -- $cur ))
	return 0
}

__get_firstword() {
	local firstword i
 
	firstword=
	for ((i = 1; i < ${#COMP_WORDS[@]}; ++i)); do
		if [[ ${COMP_WORDS[i]} != -* ]]; then
			firstword=${COMP_WORDS[i]}
			break
		fi
	done
 
	echo $firstword
}
 
complete -F _nrrdjrnl nrrdjrnl
