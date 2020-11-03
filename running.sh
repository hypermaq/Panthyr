#! /bin/bash
if ps -ef |grep worker.py |grep -v grep > /dev/null
    then
        reply=$(ps -ef | grep worker.py | grep -v sudo| grep -v grep)
        PID=$(echo $reply | awk '{ print $2 }')
        STARTED=$(echo $reply | awk '{ print $5 }')
        echo "Worker script is running with PID $PID, started at $STARTED. Use option k to kill."
        if [ "$1" = "k" ]; then
            sudo kill $PID
            echo "Killed Process ID $PID"
        exit 1
        fi
    else
        echo "Worker script is NOT RUNNING."
        exit 0
fi
