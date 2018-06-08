#!/bin/bash
# vim: sw=4:ts=4:expandtab

# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
module="modelservice.profiles"
workers=1
groups=4
usersfile=""

show_help() {
  cat << EOF
  Usage: ${0##*/} [-m modelservice.profiles] [-w 1] [-g 4] [-u usersfile.txt]
  Run profiling tasks across workers.
  -h                          Print this help.
  -m module.dotted.path       Module to run.
  -w workers                  Number of workers to spin.
  -g groups                   How many times every tasks should be run.
  -u usersfile.txt            Text file containing user emails -- one per line
  -U modelservice URL         websocket URL to connect to for profile runs
EOF
}

while getopts "h?m:w:g:u:U" opt; do
    case "$opt" in
    h|\?)
        show_help
        exit 0
        ;;
    m)  module=$OPTARG
        ;;
    w)  workers=$OPTARG
        ;;
    g)  groups=$OPTARG
        ;;
    u)  usersfile=$OPTARG
        ;;
    U)  wsurl=$OPTARG
    ;;
    esac
done

shift $((OPTIND-1))

[ "$1" = "--" ] && shift

if [[ -z ${wsurl} ]];
then
    if [[ ! -z ${MODEL_SERVICE_WS} ]];
    then
        wsurl="${MODEL_SERVICE_WS}"
    else
        wsurl=""
    fi
fi

declare -i WORKER_COUNT
declare -i ELEMENT_COUNT

if [[ -n "$usersfile" ]] && [[ -f "$usersfile" ]];
then
    USERFILE=1
    WORKER_COUNT=$( egrep '^[[:alnum:]]+@[[:alnum:].]+' "$usersfile" | wc -l )
else
    USERFILE=
    WORKER_COUNT=${workers}
fi

echo "module=$module"
echo "groups=$groups"
echo "usersfile=$usersfile"
echo "wsurl=$wsurl"
echo "workers=$workers"
echo "WORKER_COUNT=${WORKER_COUNT}"

if [[ -z ${USERFILE} ]];
then
    seq 0 $(( ${WORKER_COUNT} - 1 )) |
    xargs -t -n 1 -P ${WORKER_COUNT} \
        django-admin profile --url ${wsurl} -m ${module} -g ${groups} -w ${WORKER_COUNT} --log-level error --name ${1}
else
    egrep '^[[:alnum:]]+@[[:alnum:].]+$' ${usersfile} |
    xargs -t -n 1 -P ${WORKER_COUNT} \
        django-admin profile --url ${wsurl} -m ${module} -g ${groups} -w ${WORKER_COUNT} --log-level error --user-email ${1}
fi
# End of file
