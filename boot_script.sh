#!/bin/bash
sudo /usr/bin/python -u /home/hypermaq/scripts/gpio05.py --setup >> /home/hypermaq/data/cronlog.log 2>&1
sleep 10
/usr/bin/python -u /home/hypermaq/scripts/queue.py -a set_station_params,1 >> /home/hypermaq/data/cronlog.log 2>&1  # add task with priority 1
sleep 20
_date=$(date +"%Y%m%d_%H%M%S")
tar -czPf /home/hypermaq/data/backups/backup_$_date.tar.gz /home/hypermaq/data/cronlog.log /home/hypermaq/data/hypermaq.db
