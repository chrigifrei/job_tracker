'''Tracks jobs according to a given pattern (time & event based)
Module:
    controller
Description:
    Controls jobs in loading one thread for each job.
'''

import time
import signal
import sys
import shutil
import random
import inspect  # debugging: allows the inspection of the calling func within a func
from subprocess import Popen, PIPE

# job_tracker
import job_ruler
from job_history import job_history


class Controller():
    ''' launches job trackers
        CYCLIC jobs:
            one job tracker per job
            no specific <start_time>

        DAILY (scheduled) jobs:
            one job tracker for each jobrun
            with scheduled <start_time>
        '''
    
    def __init__(self, cfg, logger):
        
        self.cfg = cfg
        self.logger = logger
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path =  self.cfg.pidfile_path
        self.pidfile_timeout = 5


    def get_timestamp_from_epoche(self, epoche, format='%Y-%m-%d %H:%M:%S'):
        ''' Takes:
                epoche as float
                (optional) format as string
            Returns:
                timestamp as string '''

        return time.strftime(format, time.localtime(epoche))


    def run_shell(self, cmd):
        ''' runs a shell command
            returns: 
                dict (stdout, stderr, rc) '''

        try:
            p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
            out = p.communicate()
            result = dict([('stdout', out[0].rstrip()), ('stderr', out[1].rstrip()), ('rc', p.returncode)])
        except Exception as err:
            print '%s running %s failed. %s. exiting.' % (inspect.stack()[1][3], cmd, err)
            sys.exit(1)

        if result['rc'] != 0: 
            self.logger.error('%s - failed command: %s' % (inspect.stack()[1][3], cmd))
            self.logger.error('%s - error stack (RC: %d) %s' % (inspect.stack()[1][3], p.returncode, out[1]))
        
        return result


    def get_ssh_command(self, src_user, src_key, src_host):

        ssh_cmd = 'ssh'
        
        if not src_key == '':
            ssh_cmd += ' -i %s' % src_key

        ssh_cmd += ' -x -o ConnectTimeout=%s -o BatchMode=yes -o StrictHostKeyChecking=no %s@%s' % (
            str(self.cfg.item['global_config'][0]['controller_data_load_timeout']), 
            src_user, src_host)

        return ssh_cmd


    def get_sql_data_over_ssh(self, user, key, host, q, q_handler):
        ''' return: 
                dict (stdout, stderr, rc) '''

        cmd = '%s -f %s remove -t EPOCHE -i %s' % (q_handler, q, self.cfg.item['global_config'][0]['job_history_entry_count'])

        ssh_cmd = self.get_ssh_command(user, key, host)

        ssh_cmd += ' \"%s\"' % cmd

        # if self.cfg.log_level == 'debug':
        #     print ssh_cmd

        return self.run_shell(ssh_cmd)


    # def get_sql_data_over_ssh(self, src_user, src_key, src_host, src_db, src_table=''):
    #     ''' get all records from sqlite DB <src_db>
    #         in <src_table> on <src_host> as <src_user> using <src_key>
    #         return: 
    #             dict (stdout, stderr, rc) '''

    #     if src_table == '':
    #         src_table = 'messages'

    #     sql_cmd = 'sqlite3 -list -separator \'|\' %s \'select * from %s;\'' % (src_db, src_table)

    #     ssh_cmd = self.get_ssh_command(src_user, src_key, src_host)

    #     ssh_cmd += ' \"%s\"' % sql_cmd

    #     # if self.cfg.log_level == 'debug':
    #     #     print ssh_cmd

    #     return self.run_shell(ssh_cmd)


    # def delete_sql_data_over_ssh(self, src_user, src_key, src_host, src_db, src_table=''):
        
    #     if src_table == '':
    #         src_table = 'messages'
        
    #     sql_cmd = 'sqlite3 %s \'delete from %s;\'' % (src_db, src_table)

    #     ssh_cmd = self.get_ssh_command(src_user, src_key, src_host)

    #     ssh_cmd += ' \"%s\"' % sql_cmd

    #     # if self.cfg.log_level == 'debug':
    #     #     print ssh_cmd

    #     return self.run_shell(ssh_cmd)


    def sig_handler(self, signum, frame):
        ''' handles SIGTERM '''

        self.cfg.exit_flag = True


    def cleanup(self):
        
        try:
            pass
            # shutil.rmtree(self.cfg.run_dir)
        except:
            self.logger.warning('run dir clean up failed. check %s for unneeded runtime files.' % self.cfg.run_dir)

        self.logger.info('========= %s terminated =========' % self.cfg.me)


    def get_message_as_dict(self, msg):
        ''' Takes:
                msg (dict)
            Desc:
                converts <message> string to dict according to the pattern:
                    json: { "timestamp": (int), "instance": (string) e.g. "P", "job": (string), "message": (string), "_id": (int), "event": (string) }
                    dict:   { id: (string), epoche_timestamp: (float), env: (string), job: (string), event: (string), message_text: (string) } 
            Returns:
                message (dict) '''


        return dict([ ('id', ''.join(random.choice('0123456789abcdef') for n in xrange(16)) ), 
                      ('epoche_timestamp', float(msg["timestamp"]) ), 
                      ('env', msg["instance"]), 
                      ('job', msg["job"]), 
                      ('event', msg["event"]), 
                      ('message_text', msg["message"]) ])


    def get_data_from_source_hosts(self):
        ''' Returns:
                messages (dicts) from all hosts as array
            Desc:
                messages (dict):
                    { id: (string), epoche_timestamp: (float), env: (string), job: (string), event: (string), message_text: (string) }
            '''

        source_data = []

        for host in self.cfg.item['source_hosts']:
            
            sql_data_str = self.get_sql_data_over_ssh(user=host['user'], 
                                                      key=host['key'], 
                                                      host=host['hostname'], 
                                                      q=host['message_queue'],
                                                      q_handler=host['message_queue_handler'])['stdout']
            
            if sql_data_str:
            
                sql_data = eval(sql_data_str)

                for msg in sql_data:
                                
                    source_data.append(self.get_message_as_dict(msg))

                # self.delete_sql_data_over_ssh(src_user=host['user'], 
                #                               src_key=host['key'], 
                #                               src_host=host['hostname'], 
                #                               src_db=host['file'])

        return source_data


    def fetch_new_messages(self, job, message_stack):
        ''' takes:
                job (dict) as defined in cfg file
                message_stack (array, containing messages as array)
            desc:
                sorts out messages relevant to <job>
                message format: [str(<id>), float(<epoche_timestamp>), str(<environment>), str(<job>), str(<event>), str(<message_text>)]
            returns:
                new messages (array) '''

        new_messages = []

        for message in message_stack:
            
            if job['env'] != message['env'] or job['name'] != message['job']:
                continue
            
            new_messages.append(message)

        return new_messages


    def run(self):
        ''' main controller logic 
            returning from this function will terminate the process '''

        self.logger.info('========= %s started =========' % self.cfg.me)
        
        # initialize the jobs
        jobs = []

        for job in self.cfg.item['jobs']:
            
            job['history'] = job_history(self.cfg, self.logger, job)

            job['ruler'] = job_ruler.checkmk(self.cfg, self.logger, job)

            jobs.append(job)


        while True:
            
            start_time = time.time()

            signal.signal(signal.SIGTERM, self.sig_handler)
            
            if self.cfg.exit_flag:

                self.cleanup()
                return
            
            try:
                message_stack = self.get_data_from_source_hosts()
            except Exception as err:
                # msg = 'corrupt message stack. clear message db on source hosts.'
                self.logger.error(err)
                print '[ERROR] %s exiting.' % err
                sys.exit(1)


            self.logger.debug('%s::run::controller_run_duration                = %s sec' % (__name__, self.cfg.controller_run_duration))

            for job in jobs:

                new_messages = self.fetch_new_messages(job, message_stack)                

                self.logger.debug('%s__%s (%s):' % (job['name'], job['env'], job['cyclic_or_daily']))
                self.logger.debug('-------------------------------' )

                if self.cfg.log_level == 'debug':
                    
                    import traceback
                    
                    try:
                        job['history'].interpret_new_messages(new_messages)
                        job['ruler'].compute_status(job['history'].get_status())
                    
                    except Exception:
                        traceback.print_exc()
                        sys.exit(1)

                else:
                    job['history'].interpret_new_messages(new_messages)
                    job['ruler'].compute_status(job['history'].get_status())

                

            self.cfg.controller_run_duration = time.time() - start_time

            time.sleep(self.cfg.controller_interval)
