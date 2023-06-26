#!/bin/bash

cd src/Celery
if [ -f worker_number.txt ]; then
    worker_number=$(cat worker_number.txt)
else
    worker_number=1
fi

next_worker_number=$((worker_number + 1))
echo $next_worker_number > worker_number.txt

celery -A Worker worker --concurrency=1 -E --loglevel=INFO --hostname=worker$worker_number



#cd src/Celery
#celery -A Worker worker --concurrency=1 -E --loglevel=INFO 
