#!/usr/bin/env python
'''Tracks jobs according to a given pattern (time & event based)
Module:
	checkmk_localcheck
Description:
	Reads the status sockets
Usage:
	Put this script in CheckMKs local check folder'''

from sys import exit
import glob

for f in glob.glob('/var/run/job_tracker/*.state'):
    print open(f).read()

exit(0)