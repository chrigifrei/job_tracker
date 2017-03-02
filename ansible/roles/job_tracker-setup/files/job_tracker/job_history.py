'''Tracks jobs according to a given pattern (time & event based)
Module: 
    job_history
Takes:
    job (dict) as defined in cfg file
Description:
    creates/extends job_history (obj)

    .file       job event history file
'''

import os, sys
import time
from filer import filer


class job_history():

    def __init__(self, cfg, logger, job):

        self.starttime = time.time()
        self.cfg = cfg
        self.logger = logger
        self.job = job

        self.filename = '%s/%s__%s.job_history' % (cfg.run_dir, job['name'], job['env'])
        
        self.file = filer(cfg, logger, self.filename)


    def get_status(self, t=float(-1.0)):
        ''' Takes:
                (optional) time float(seconds)
            
            Desc:
                gets job status from: now - (minus) <t> seconds
            
            Returns:
                status_statement (dict)
                    status: 'UNKNOWN' | 'RUNNING' | 'NOT_RUNNING' (string)
                    since:  epoche (float)
                    result: message (string) '''

        event_history = self.file.read_content()

        if t < 0 or not event_history:
            last_exec = self.file.get_last_statement()
            return self.evaluate_status(last_exec)

        target_time = time.time() - t
        target_exec_statement = dict()

        for exec_statement in event_history:
                        
            if exec_statement['epoche_until'] < target_time:
                target_exec_statement = exec_statement
                break

        return self.evaluate_status(target_exec_statement)
        

    def evaluate_status(self, exec_statement):
        ''' Takes:
                exec_statement (dict)
            
            Desc:
                evaluates the job status according to the pattern
                    exec_statement: None        -   UNKNOWN
                    epoche_from  = epoche_until -   RUNNING
                    epoche_from != epoche_until -   NOT_RUNNING
            
            Returns:
                status_statement (dict)
                    status: 'UNKNOWN' | 'RUNNING' | 'NOT_RUNNING' (string)
                    since:  epoche (float)
                    result: message (string) '''

        # UNKNOWN
        if not exec_statement or \
           self.cfg.job_state_unknown in exec_statement['result']:

            return dict([ ('status', self.cfg.job_state_unknown ), 
                          ('since', self.starttime ),
                          ('result', '%s - job status unknown' % self.cfg.job_state_unknown ) ])

        # RUNNING
        if exec_statement['epoche_from'] == exec_statement['epoche_until']:
            
            return dict([ ('status', self.cfg.job_state_running ), 
                          ('since', exec_statement['epoche_from'] ),
                          ('result', exec_statement['result']) ])

        # NOT_RUNNING
        return dict([ ('status', self.cfg.job_state_not_running ), 
                      ('since', exec_statement['epoche_until'] ),
                      ('result', exec_statement['result']) ])


    def add_event_to_history(self, event, timestamp, message_text='', message_id=''):

        if message_id == '':
            message_id = self.file.get_new_id()

        last_exec = self.file.get_last_statement()

        if event == self.cfg.job_start_keyword:
            epoche_from = timestamp

        elif not last_exec:
            epoche_from = float(-1.0)

        else:
            epoche_from = last_exec['epoche_from']

        this_exec = dict([ ('execution_id', message_id ), 
                           ('epoche_from',  epoche_from ), 
                           ('epoche_until', timestamp ), 
                           ('result',       '%s - %s' % (event, message_text) ) ])

            
        self.logger.debug('job_history (event_history):')
        self.logger.debug('    add_event_to_history::epoche_from = %s, epoche_until = %s, result = %s' % (this_exec['epoche_from'], this_exec['epoche_until'], this_exec['result']))
        
        self.check_for_duplicate_entries(this_exec)
        
        self.file.write_statement(this_exec, 'epoche_until')


    def check_for_duplicate_entries(self, exec_statement):

        this_status = self.evaluate_status(exec_statement)
        last_status = self.evaluate_status(self.file.get_last_statement())

        if not last_status:
            return False

        if this_status['status'] != last_status['status']:
            return False

        if this_status['result'] != last_status['result']:
            return False

        self.logger.warning('duplicate entries in %s - it seems that we missed event messages from source hosts' % self.filename)

        return True


    def interpret_new_messages(self, new_messages):
        ''' Takes:
                new_messages (array)
            
            Desc:
                process <new_messages> to an execution statement
                
                message format: { id: (string), 
                                  epoche_timestamp: (float), 
                                  env: (string), 
                                  job: (string), 
                                  event: (string), 
                                  message_text: (string) } '''

        if not new_messages:
            return

        for message in new_messages:

            self.add_event_to_history(message['event'], message['epoche_timestamp'], message['message_text'], message['id'])

        return

