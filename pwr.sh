#! /bin/bash
for i in {1..6}
do
/home/hypermaq/scripts/gpio05.py --output$i=$1
done