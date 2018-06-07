#!/bin/bash

if [ ! -d "Logs" ]; then
	mkdir "Logs" 
	chmod 777 "Logs"
fi

date=`date +%Y-%m-%d`
logdir="Logs/Logs_${date}"

lastweekdate=`date -d "-7 day" +%Y-%m-%d`
oldlogdir="Logs/Logs_${lastweekdate}"

if [ ! -d $logdir ]; then
	mkdir $logdir 
	chmod 777 $logdir
fi

if [ -d $oldlogdir ]; then
	sudo rm -rf $oldlogdir
fi

python main.py
exitcode=$?
if [ ! $exitcode ]; then
	#gets most recent modified log file
	recent_log=$(ls $logdir -t | head -n1)
	python Email_Error.py $recent_log
fi
