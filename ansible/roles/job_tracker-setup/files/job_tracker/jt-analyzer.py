#!/usr/bin/env python
DESC=''' job_tracker log analyzer
Prints job_tracker logs in a nice format.
'''
EPILOG='''
Examples:

  # Analyze logs for example_job
  %(prog)s -j example_job
'''

import argparse
import textwrap
import sys
import time
import logging
from config import Config
from filer import filer


def convert_epoche_to_timestamp(epoche):

	return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoche))

def setup_config(name="job_tracker"):

	return Config(name)


if __name__ == '__main__':

	parser = argparse.ArgumentParser(
		prog="jt-analyzer",
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description=DESC,
		epilog=textwrap.dedent(EPILOG)
	)
	parser.add_argument("-c", "--config", type=str, metavar="config", help="job_tracker config file", default="job_tracker.cfg")
	parser.add_argument("-j", "--job", type=str, metavar="job", help="Job to analyze", required=True)
	parser.add_argument("-e", "--env", type=str, metavar="env", choices=['P', 'I'], default='I', help="Environment")

	# parse the args and call the appropriate command function
	args = parser.parse_args()

	cfg = setup_config()
	cfg.load_config(args.config)
	logger = logging.getLogger("/tmp/jt-analyzer.log")
	file_name = '%s/%s__%s.job_history' % (cfg.run_dir, args.job, args.env)
	file_handler = filer(cfg, logger, file_name)

	print "\nGetting log entries from %s\n" % file_name
	print "FROM                - UNTIL    : RESULT\n--------------------------------------------------------------"

	job_history = file_handler.read_content()

	for item in job_history:

		# item = dict(eval(item.rstrip()))
		# print item
		# item = dict(eval(item))
		item['epoche_until'] = convert_epoche_to_timestamp(item['epoche_until'])
		item['epoche_from'] = convert_epoche_to_timestamp(item['epoche_from'])
		
		if item['epoche_from'] == item['epoche_until']:
			print "%s            : %s" % (item['epoche_from'], item['result'] )

		else:
			print "%s - %s : %s" % (item['epoche_from'], item['epoche_until'].split(' ')[1], item['result'] )

sys.exit(0)
