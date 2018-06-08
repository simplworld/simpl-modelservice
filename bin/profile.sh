#!/bin/sh

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
EOF
}

while getopts "h?m:w:g:u:" opt; do
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
    esac
done

shift $((OPTIND-1))

[ "$1" = "--" ] && shift

echo "module=$module"
echo "groups=$groups"
echo "usersfile=$usersfile"

if [[ -z "$usersfile" ]]; then
    echo "workers=$workers"
    seq ${workers} | xargs -ot -n 1 -P ${workers} ./manage.py profile -m ${module} -g ${groups} -w ${workers} --log-level error -n
else
    workers="$(awk 'NF' ${usersfile} | wc -l | sed 's/^ *//')"
    echo "workers=$workers"
    awk 'NF' ${usersfile} | xargs -ot -n 1 -P ${workers} -L1 ./manage.py profile -m ${module} -g ${groups} -w ${workers} --log-level error --user-email ${1}
fi
# End of file
