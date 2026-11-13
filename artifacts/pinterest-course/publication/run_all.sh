#!/bin/bash
cd /home/evgen/bk3.0
for n in $(seq 1 40); do python3 scripts/pub_build.py build $n || echo "ОШИБКА урок $n"; done
python3 scripts/pub_build.py report
echo ГОТОВО
