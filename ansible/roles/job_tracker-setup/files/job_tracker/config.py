'''Tracks jobs according to a given pattern (time & event based)
Module: 
    config
Description:
    Loads the config given as arg or using the default (%(prog)s.cfg)
'''

import os, sys
import json


class Config():

    def __init__(self, name):
        self.name = name
        self.me = self.name
        self.file = '%s.cfg' % name
        self.pidfile_path =  '/var/run/%s.pid' % self.name


    def str_to_sec(self, s):
        ''' converts a string in the form hh:mm:ss to seconds
            returns: float '''
        
        try:
            s = s.strip().split(':')
            if s[0] != '':
                try:
                    return float(s[0])*3600 + float(s[1])*60 + float(s[2])
                except:
                    return float(s[0])*3600 + float(s[1])*60
        except:
            print '[ERROR] configfile syntax error. wrong time format. check config file. exiting.'
            sys.exit(1)


    def load_config(self, configfile):

        self.run_dir = '/var/run/%s' % self.name
        self.exit_flag = False

        try:
            with open(configfile, 'r') as f:
                self.item = json.load(f)
        except Exception as err: 
            print 'init checks - failed to load config file: %s. exiting.' % err
            sys.exit(1)


        # [TODO] extcfr, 01.07.2016: config param syntax check

        self.log_file                = self.item['global_config'][0]['log_file']
        self.log_level               = self.item['global_config'][0]['log_level']
        self.controller_interval     = self.item['global_config'][0]['controller_interval_in_sec']
        self.controller_run_duration = 5.0
        
        self.job_start_keyword = self.item['global_config'][0]['jobs_start_keyword']
        self.job_error_keyword = self.item['global_config'][0]['jobs_error_keyword']
        self.job_end_keyword   = self.item['global_config'][0]['jobs_end_keyword']

        self.job_state_running      = 'RUNNING'
        self.job_state_not_running  = 'NOT_RUNNING'
        self.job_state_error        = 'ERROR'
        self.job_state_timeout      = 'TIMEOUT'
        self.job_state_delayed      = 'DELAYED'
        self.job_state_unknown      = 'UNKNOWN'

        self.snooze_frame_start = self.item['global_config'][0]['snooze_for_cyclic_jobs_from_hh:mm']
        self.snooze_frame_end   = self.item['global_config'][0]['snooze_for_cyclic_jobs_until_hh:mm']

        self.monitoring_servicename_prefix = self.item['global_config'][0]['monitoring_servicename_prefix_without_spaces']
        
        if 'status' in self.item['global_config'][0]['monitoring_backend_based_on_event_or_status']:
            self.monitoring = 'status'
        elif 'event' in self.item['global_config'][0]['monitoring_backend_based_on_event_or_status']:
            self.monitoring = 'event'
        else:
            print 'wrong parameter for monitoring_backend_based_on_event_or_status in config file. exiting'
            sys.exit(1)

        for job in self.item['jobs']:
            job['timeout_sec']            = self.str_to_sec(job['timeout_hh:mm:ss'])
            job['cyclic_interval_sec']       = self.str_to_sec(job['cyclic_interval_hh:mm:ss'])
            job['daily_start_time_sec']      = self.str_to_sec(job['daily_start_time_hh:mm'])
            job['daily_start_max_delay_sec'] = self.str_to_sec(job['daily_start_max_delay_hh:mm:ss'])

