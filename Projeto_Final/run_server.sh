#!/bin/bash

if [ -d worker_storage ]; then
    rm -r worker_storage
fi
if [ -d server_storage ]; then
    rm -r server_storage
fi
if [ -d worker_storage_2 ]; then
    rm -r worker_storage_2
fi
mkdir -p worker_storage
mkdir -p server_storage
mkdir -p worker_storage_2
python3 src/Celery/SvAPI.py