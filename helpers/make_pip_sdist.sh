#!/usr/bin/env bash

usage() {
    echo "Usage: $0 [-u]";
    exit 1
}

make_sdist() {
    python setup.py sdist
}

sign_sdist() {
    gpg --detach-sign -a dist/${1}-${2}.tar.gz
}

upload_sdist() {
    [ -z "${3}" ] || repo="--repository-url ${3}"
    twine upload ${repo} dist/${1}-${2}.tar.gz*
}

# --- Main ---

pkg=pydrac
version=`cat VERSION`
upload=false

while getopts :uh opt; do
    case "$opt" in
        h) usage ;;
        u) upload=true ;;
        \?) echo "Unknown option $OPTARG"; exit 2 ;;
        :) echo "Option -$OPTARG requires an argument."; exit 2 ;;
    esac
done

read -p "Build sdist for $pkg v$version ? (^C to abort)"

make_sdist
sign_sdist "$pkg" "$version"

$upload && {
    read -p "Upload sdist ${pkg}-${version} ? (^C to abort)"
    upload_sdist ${repo} "$pkg" "$version" "${2}"
}

echo "All done."
