#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    exec "$@"
fi

user_id=${USER_ID:-1000}
group_id=${GROUP_ID:-1000}

group_name=$(awk -F: -v gid="$group_id" '$3 == gid {print $1}' /etc/group)
if [ -z "$group_name" ]; then
    addgroup -g "$group_id" -S app
    group_name=app
fi

user_name=$(awk -F: -v uid="$user_id" '$3 == uid {print $1}' /etc/passwd)
if [ -z "$user_name" ]; then
    adduser -u "$user_id" -G "$group_name" -S -H -D app
    user_name=app
fi

exec su-exec "$user_name" "$@"
