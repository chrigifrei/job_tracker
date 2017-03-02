#!/usr/bin/env python
'''Tracks jobs according to a given pattern (time & event based)
Config
    json encoded. Provide as arg: -c FILE

Monitoring Backends
    CheckMK Service: "status"
    CheckMK Event Console: "event"

CheckMK Service Integration
    Status file for each job:
        /var/run/<prog>.<jobname>.state
    Content:
        CheckMK status message: <status_as_int> <service_name> - <desc>
    Local Checks in:
        /usr/lib/check_mk_agent/local

CheckMK Event Console Integration
    Event handler:
        send-notification.py needed in the path of %(prog)s

Further docs
    ...
'''

import time
import os, sys
import logging
from optparse import OptionParser

# 3rd party libs
from daemon import runner

# job_tracker
from controller import Controller
from config import Config


LOG_LEVEL_DEFINITIONS = {
        'debug': logging.DEBUG,
         'info': logging.INFO,
      'warning': logging.WARNING,
        'error': logging.ERROR,
     'critical': logging.CRITICAL}


def options_parsing():
    ''' command usage: prog options arg
        parses all options and removes them 
        args will not be handled in here 
        return: options as object'''

    parser = OptionParser(usage='usage: %prog [options] start|stop|restart')
    
    parser.add_option('-l', '--level', type='string', action="store", dest='log_level',
                      help='debug, info, warning, error, critical', metavar='LEVEL')
    
    parser.add_option('-c', '--config', action="store", dest='config_file',
                      help='config as json encoded file', metavar='FILE')

    (options, args) = parser.parse_args()

    # strip off the options and keep only the args
    sys.argv = [str(sys.argv[0]), str(sys.argv[len(sys.argv)-1])]

    return options


def setup_config(name=os.path.dirname(__file__).split('/')[-1]):

    return Config(name)


def load_config(options, cfg):
    
    if options.config_file:
        cfg.load_config(options.config_file)
    else:
        cfg.load_config(cfg.file)


def check_dir_and_file_access(cfg):

    if not os.path.exists(cfg.run_dir):
        
        try:
            os.makedirs(cfg.run_dir)
        
        except Exception as err:
            print '[ERROR] init checks - failed to create run dir: %s. %s exiting.' % (cfg.run_dir, err)
            sys.exit(1)

    try:
        test_file = '%s/testfile' % cfg.run_dir
        with open(test_file, 'w'):
            pass
        os.remove(test_file)

    except Exception as err: 
        print '[ERROR] init checks - failed to open file: %s. %s exiting.' % (f, err)
        sys.exit(1)


def setup_log_handler(options, cfg):
    ''' creates a log_handler
        return: log_handler as object '''

    if options.log_level:
        cfg.log_level = options.log_level

    try:
        with open(cfg.log_file, 'a'):
            pass
    
    except Exception as err: 
        print '[ERROR] init checks - failed to open file: %s. %s exiting.' % (f, err)
        sys.exit(1)

    log_handler = logging.FileHandler(cfg.log_file)
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s: [%(levelname)-7s] %(message)s"))

    return log_handler    


def kickoff_controller(cfg, logger):

    return Controller(cfg, logger)


def check_timedrift(cfg, logger, cntr):

    for host in cfg.item['source_hosts']:
        # #
        # # checking data load connectivity
        # #
        # res = cntr.get_sql_data_over_ssh(user=host['user'], 
        #                                  key=host['key'], 
        #                                  host=host['hostname'], 
        #                                  q=host['message_queue'],
        #                                  q_handler=host['message_queue_handler'] )
        # if res['rc'] != 0:
        #     msg = 'init checks - load test from source host %s@%s:%s failed. %s' % (
        #         host['user'], host['hostname'], host['message_queue'], res['stderr'])
        #     logger.warning(msg)
        #     print '[WARNING] %s.' % msg

        # #
        # # check time drift between source and local host
        # #
        cmd = 'ssh'
        if host['key'].strip() != '':
            cmd += ' -i %s' % host['key']
        
        try:
            local_time = time.time()
            src_host_time = cntr.run_shell('%s %s@%s \"python -c \'import time; print time.time()\'\"' % (
                cmd, host['user'], host['hostname']))['stdout']
        
        except:
            print '[ERROR] could not get time from source host. check log %s. exiting.' % cfg.item['global_config'][0]['log_file']
            sys.exit(1)

        if src_host_time:
            time_difference = float(src_host_time) - local_time
            logger.debug('init checks - time drift of %s [sec] between local and source host: %s' % (
                str(time_difference), host['hostname']))

            if time_difference < float(-cfg.controller_interval) or time_difference > float(cfg.controller_interval):
                msg = 'init checks - time drift between local and source host greater than %s [sec].' % cfg.controller_interval
                logger.warning(msg)
                print '[WARNING] %s' % msg


#===========================================
# main application logic
#===========================================

options = options_parsing()
cfg = setup_config()
logger = logging.getLogger(cfg.me)


if 'stop' in sys.argv:
    
    cntr = kickoff_controller(cfg, logger)
    cntr_runner = runner.DaemonRunner(cntr)

else:

    load_config(options, cfg)
    check_dir_and_file_access(cfg)

    log_handler = setup_log_handler(options, cfg)
    logger.setLevel(LOG_LEVEL_DEFINITIONS.get(cfg.log_level, logging.NOTSET))

    logger.addHandler(log_handler)
    
    cntr = kickoff_controller(cfg, logger)
    cntr_runner = runner.DaemonRunner(cntr)
    cntr_runner.daemon_context.files_preserve = [log_handler.stream]

    check_timedrift(cfg, logger, cntr)

try:
    cntr_runner.do_action()

except Exception as err:
    print err
    sys.exit(1)
