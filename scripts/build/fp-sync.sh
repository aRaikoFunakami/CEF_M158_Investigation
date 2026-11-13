#!/bin/bash
# tools/fp/ をコンテナの /root/fp/tools/ に同期する。
cd "$(dirname "$0")" && tar cf - fp | container exec -i chrome-build bash -c 'mkdir -p /root/fp && cd /root/fp && rm -rf tools && tar xf - && mv fp tools && ls tools'
