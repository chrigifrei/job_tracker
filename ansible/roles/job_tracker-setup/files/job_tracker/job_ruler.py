'''Tracks jobs according to a given pattern (time & event based)
Module: 
    job_ruler
Takes:
    config (obj)
    logger (obj)
    job (dict)
Description:
    creates job status output according to a ruleset

'''

import time
import datetime
import socket


class checkmk():

    def __init__(self, cfg, logger, job):

        self.cfg = cfg
        self.logger = logger
        self.job = job

        self.job_status_file = '%s/%s__%s.state' % (self.cfg.run_dir, self.job['name'], self.job['env'])

        self.checkmk_ok = 0
        self.checkmk_warning = 1
        self.checkmk_critical = 2
        self.checkmk_unknown = 3


    def convert_epoche_to_timestamp(self, epoche):

        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(epoche))


    def sec_to_str(self, sec):
        ''' Takes:
                sec (float)
            Returns:
                time in hh:mm:ss (string) '''

        m, s = divmod(sec, 60)
        h, m = divmod(m, 60)

        if h == 24:
            h = 0

        return '%02d:%02d:%02d' % (h, m, s)


    def get_epoche(self, daytime):
        ''' Takes:
                daytime (float) in sec
            Desc:
                calculates epoche timestamp for <daytime> of today
            Returns:
                epoche (float) '''

        target_time =  time.strftime('%Y-%m-%d')
        target_time += ' %s' % self.sec_to_str(daytime)
                
        # self.logger.debug('    expected execution time (target_time) = %s' % target_time)

        return time.mktime(time.strptime(target_time, '%Y-%m-%d %H:%M:%S'))


    def timeout(self, status_statement):
        ''' Desc:
                calculates runtime accurancy for cyclic and daily jobs
            Returns:
                True:  if job is below timeout
                False: if job reached the timeout '''

        now = time.time()

        # CYCLIC JOBS
        if 'cyclic' in self.job['cyclic_or_daily']:
            
            if status_statement['since']  <  now - ((self.job['max_errors_before_alerting'] * self.job['timeout_sec']) + self.cfg.controller_run_duration ):
                return True

            else:
                return False

        # DAILY (SCHEDULED) JOBS
        else:
            if status_statement['since']  <  now - self.job['timeout_sec']:
                return True

            else:
                return False


    def on_time(self, status_statement):
        ''' Desc:
                calculates starttime accurancy for cyclic and daily jobs
            Returns:
                True:  if job is on time 
                False: if job is delayed '''

        now = time.time()

        # CYCLIC JOBS
        if 'cyclic' in self.job['cyclic_or_daily']:
            
            t = ( self.job['max_errors_before_alerting'] * self.job['cyclic_interval_sec'] ) + self.cfg.controller_run_duration

            # do not check for ontime issues in predefined (cfg) snooze-timerange
            if self.time_in_range(datetime.datetime.today().time()):
                return True

            if status_statement['since']  <  now - t:
                return False

            else:
                status_statement['since'] = status_statement['since'] + t
                return True

        # DAILY (SCHEDULED) JOBS
        else:
            
            t = self.job['daily_start_time_sec'] + self.job['daily_start_max_delay_sec']

            if now < self.get_epoche( t ):
                # job seems to be on time but was already delayed at last status calculation (last job_history entry)
                if self.cfg.job_state_delayed in status_statement['result']:
                    return False
                else:
                    return True

            # job seems to be delayed but last event in the last 24h was a successful end
            elif self.cfg.job_end_keyword in status_statement['result'] and \
                 status_statement['since'] > now - (24 * 3600) :
                return True
            
            else:
                status_statement['since'] = t
                return False


    def compute_status(self, status_statement):
        ''' Takes:
                status_statement (dict):
                    status: 'UNKNOWN' | 'RUNNING' | 'NOT_RUNNING' (string)
                    since:  epoche (float)
                    result: message (string)
            
            Desc:
                calculates checkmk related job status

                Possible states:
                    ERROR (RUNNING)
                        RUNNING and
                        <error_keyword> in <result>

                    TIMEOUT
                        RUNNING since t and
                        t < now - <timeout>

                    RUNNING
                        RUNNING since t 

                    ERROR (NOT_RUNNING)
                        NOT_RUNNING and 
                        <error_keyword> in <result>

                    DELAYED 
                        UNKNOWN or NOT_RUNNING since t and
                        for cyclic jobs: t < now - ((<max_errors_before_alerting> * <interval>) + controller_run_duration)
                        for daily jobs:  t < (<daily_start_time_sec> + <daily_start_max_delay_sec>)

                    NOT_RUNNING
                        NOT_RUNNING since t 

                    UNKNOWN
            '''

        self.logger.debug('job_ruler (checkmk status):')

        # job state: ERROR
        if   self.cfg.job_error_keyword in status_statement['result']:

            status_statement['status'] = self.cfg.job_state_error
            status_statement['result'] = 'job failed (%s since %s) %s' % (
                self.cfg.job_state_error, 
                self.convert_epoche_to_timestamp(status_statement['since']), 
                status_statement['result'] )


        # job state: TIMEOUT
        elif status_statement['status'] == self.cfg.job_state_running and \
             self.timeout(status_statement):
            
            status_statement['status'] = self.cfg.job_state_timeout
            status_statement['result'] = 'job timeout (%s sec) reached (%s since %s)' % (
                int(self.job['timeout_sec']), 
                self.cfg.job_state_timeout,
                self.convert_epoche_to_timestamp(status_statement['since'] + self.job['timeout_sec']) )


        # job state: RUNNING
        elif status_statement['status'] == self.cfg.job_state_running:
            
            status_statement['result'] = 'job ok (%s since %s)' % (
                status_statement['status'], 
                self.convert_epoche_to_timestamp(status_statement['since']) )


        # job state: DELAYED
        elif (status_statement['status'] == self.cfg.job_state_unknown or \
              status_statement['status'] == self.cfg.job_state_not_running ) and \
             not self.on_time(status_statement):
            
            status_statement['status'] = self.cfg.job_state_delayed
            if 'cyclic' in self.job['cyclic_or_daily']:
                status_statement['result'] = 'job not started (%s, expected interval: %s)' % (
                    self.cfg.job_state_delayed, 
                    self.sec_to_str(self.job['cyclic_interval_sec']) )
            else:
                delayed_since = time.time() - (self.get_epoche(0.0) + self.job['daily_start_time_sec'])
                status_statement['result'] = 'job not started (%s since %s, expected starttime: %s)' % (
                    self.cfg.job_state_delayed, 
                    self.sec_to_str(delayed_since),
                    self.convert_epoche_to_timestamp(self.get_epoche(0.0) + self.job['daily_start_time_sec']) )


        # job state: NOT_RUNNING
        elif status_statement['status'] == self.cfg.job_state_not_running:
            
            status_statement['result'] = 'job ok (%s since %s)' % (
                status_statement['status'], 
                self.convert_epoche_to_timestamp(status_statement['since']) )


        # job state: UNKNOWN
        else:
            pass


        self.monitoring_handler(status_statement)



    def monitoring_handler(self, status_statement):
        ''' Desc:
                uses the configured monitoring backend '''
        
        if self.cfg.monitoring == 'event':
            self.trigger_checkmk_event(status_statement['status'], status_statement['result'])
        else:
            self.trigger_checkmk_status(status_statement['status'], status_statement['result'])


    def time_in_range(self, x, start='', end=''):
        ''' Desc:
                evaluates if x is between <start> and <end>
            Returns:
                True if x is in the range [start, end] '''

        start = datetime.time(int(self.cfg.snooze_frame_start.split(':')[0]), int(self.cfg.snooze_frame_start.split(':')[1]), 0)
        end = datetime.time(int(self.cfg.snooze_frame_end.split(':')[0]), int(self.cfg.snooze_frame_end.split(':')[1]), 0)
        
        if start <= end:
            return start <= x <= end
        else:
            return start <= x or x <= end


    def write_status_file(self, message):
        ''' Desc:
                writes <message> of a job to its status file '''
        
        self.logger.debug('    %s' % message)

        try:
            with open(self.job_status_file, 'w') as f_stream:
                f_stream.write(str(message))

        except:
            self.logger.warning('unable to write to statusfile: %s' % status_file)


    def trigger_checkmk_status(self, status='', message=''):
        ''' Desc:
                checkmk message format (containing 4 space seperated fields):
                <status_as_int> <service_name> <count=102|-> <any message> 
                
                Possible States:
                    RUNNING     - ok
                    NOT_RUNNING - ok
                    ERROR       - critical
                    TIMEOUT     - warning/critical
                    DELAYED     - warning/critical
                    UNKNOWN     - unknown '''

        if   status == self.cfg.job_state_running or \
             status == self.cfg.job_state_not_running:
            status = self.checkmk_ok
        
        # elif status == self.cfg.job_state_timeout or \
        #      status == self.cfg.job_state_delayed:
        #     status = self.checkmk_warning

        elif status == self.cfg.job_state_error or \
             status == self.cfg.job_state_timeout or \
             status == self.cfg.job_state_delayed:
            status = self.checkmk_critical
        
        else:
            status = self.checkmk_unknown
        
        self.write_status_file('%s %s%s - %s %s\n' % (
            status, 
            self.cfg.monitoring_servicename_prefix, 
            self.job['name'].lower(), 
            self.job['name'], 
            message) )



    def trigger_checkmk_event(self, status, msg=''):
        ''' Desc:
                triggers a checkmk event console message 
                
                message format: 
                    <date> <hostname> <service/facility>: <status> <message> '''
        
        # [TODO] extcfr, 30.06.2016: not yet tested

        if status == self.cfg.job_state_running or status == self.cfg.job_state_not_running:
            return

        event_msg = '%s %s %s%s: %s - %s %s' % (
                                datetime.datetime.now().strftime('%b %d %H:%M:%S'),
                                socket.getfqdn(),
                                self.cfg.monitoring_servicename_prefix,
                                self.name,
                                status,
                                self.name,
                                msg)

        # we assume send-notification is linked into shell PATH
        cmd = 'send-notification event -m  \"%s\"' % event_msg

        try:
            p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
            out = p.communicate()
        except Exception as err:
            self.logger.error('trigger_checkmk_event - failed command: %s - error: %s' % (cmd, err))
        
        if p.returncode != 0: 
            self.logger.error('trigger_checkmk_event - failed command: %s - error stack (RC: %d) %s' % (cmd, p.returncode, out[1]))

