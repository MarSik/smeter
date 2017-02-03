#!/bin/bash
./capture.py | stdbuf -i0 -o0 -e0 ./baseband | stdbuf -i0 -o0 -e0 tee -a baseband.txt | stdbuf -i0 -o0 -e0 ./water.py

