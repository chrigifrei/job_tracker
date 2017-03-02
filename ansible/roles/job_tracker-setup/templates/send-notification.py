#!/usr/bin/env python
DESC = 'Sends/parses notifications from/to various destinations'
EPILOG = ''' 
Common usage examples for

    Oracle Enterprise Manager (EM)
    Oracle Data Integrator (ODI)

EM integration
    Example: File destination
        %(prog)s file
    Example: CheckMK Event Console destination using SSH
        %(prog)s event

ODI integration
    Example:
        %(prog)s odi --job JOB01 --instance Q --event SUCCESS --message "some additional infos"

Further docs
    https://blogs.oracle.com/oem/entry/notifications

'''

import os.path
import sys
import time
import textwrap
from datetime import datetime
from subprocess import Popen, PIPE

# requires python >=2.7
import argparse


# ========================================================================

STATUS_ROOT_DIR = '{{ job_tracker.status_dir }}'
TASKS_ROOT_DIR  = '{{ job_tracker.root }}'

CHECKMK_REMOTE_LOG = '%s/oem-dwh-status.log' % STATUS_ROOT_DIR   # log file residing on client side
ODI_LOCAL_DB = '%s/odi-jobs-status-queue.sqlite' % STATUS_ROOT_DIR

CHECKMK_USER = 'root'   # ssh login to monitoring server if used with event console
CHECKMK_NSCA_CFG = '/etc/nsca/send_nsca.cfg'
CHECKMK_NSCA_BIN = '/usr/local/bin/send_nsca'

CHECKMK_HOST = "{{ hostvars[groups['monitoringserver'][0]].inventory_hostname }}"
CHECKMK_EVENT_PIPE = '/omd/sites/checkmk_{{ env }}/tmp/run/mkeventd/events'


# ========================================================================


def die(msg, exit_code=1):
    ''' die cleanly '''
    
    sys.stderr.write('%s\n' % msg)
    sys.exit(exit_code)


def clean_message_string(msg):
    ''' checks the message string for chars breaking the functionality of this script 
        return: 
            clean message'''

    chars_to_remove = ['"', '\\', '\'', '*']

    if msg is not None:
        try:
            return msg.translate(None, ''.join(chars_to_remove))
        except:
            import string
            return msg.translate(string.maketrans('', ''), ''.join(chars_to_remove))    


def get_message_from_oracle(form='syslog'):
    ''' forms message out of Oracles environment variables
        form: 
            either "syslog" or "tab" [default: syslog]
        values for SEVERITY_CODE (status): 
            FATAL, CRITICAL, WARNING, MINOR_WARNING, INFORMATIONAL, and CLEAR
        message format: 
            <date> <hostname> <service/facility>: <status> <message>
        returns: 
            message '''

    try:
        msg_status = clean_message_string(os.environ['SEVERITY_CODE'])
        msg_text = clean_message_string('%s:%s' % (os.environ['TARGET_NAME'], os.environ['MESSAGE']))
        msg_hostname = clean_message_string(os.environ['HOST_NAME'])
        msg_service = clean_message_string('%s:%s' % (os.environ['TARGET_TYPE'], os.environ['METRIC_GROUP'])) # or maybe METRIC_COLUMN
    except:
        # [TODO] extcfr, 01.07.2016: implement a logger
        print '[WARN] unable to get Oracle environment variables'
        # [TODO] extcfr, 01.07.2016: return a valid message even if empty
        return '<empty_message:unable_to_get_oracle_env_vars>'

    if form == 'tab':
        return '%s\t%s\t%s\t%s' % (msg_hostname, msg_service.replace(' ', '_'), msg_status.upper(), msg_text.replace(' ', '_'))
    else:
        return '%s %s %s: %s %s' % (time.strftime('%b %d %R:%S'), msg_hostname, msg_service.replace(' ', '_'), msg_status.upper(), msg_text.replace(' ', '_'))


def set_test_env():
    ''' sets CheckMK constants to test env
        sets environment variables like oracle does in case of an event
        purpose: 
            testing '''

    os.environ['HOST_NAME'] = '*oda0.company.com*'
    os.environ['TARGET_TYPE'] = '*Cluster Database*'
    os.environ['TARGET_NAME'] = '*LOCAL01* <https://dbmgmt-local.company.com:7802/em/redirect?'
    os.environ['MESSAGE'] = '*Session LOCAL123-379 blocking 9 other sessions for all instances.*'
    os.environ['SEVERITY_CODE'] = '*Warning*'
    os.environ['METRIC_GROUP'] = '*Blocking Session Count'


def run_cmd(cmd):
    ''' running shell command '''

    if args.verbose:
        print '[INFO] command: %s' % cmd

    # note extcfr, 06.06.2016: shell=True is used due to the pipe (|) needed, security risk is expected to be low
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    out = p.communicate()
    if p.returncode != 0: 
        print '[ERROR] failed command: %s' % cmd
        die("[ERROR] error stack (RC: %d) %s" % (p.returncode, out[1]))


def write_to_file(filename, msg):
    ''' writing msg to filename '''

    try:
        f = open(filename, 'a')
        f.write('%s\n' % msg)
        f.close()
    except IOError:
        die('[ERROR] unable to write to %s' % filename)


def send_to_file(args):
    ''' sub-command function for file-mode '''

    if args.test:
        set_test_env()

    if args.filename:
        filename = args.filename
    else:
        filename = CHECKMK_REMOTE_LOG
    
    if args.message:
        msg = clean_message_string(args.message)
    else:
        msg = get_message_from_oracle()

    if args.verbose:
        print '[INFO] sending mode: FILE, destination: %s, message: %s' % (filename, msg)

    write_to_file(filename, msg)


# def send_to_eventconsole(args):
def send_to_eventconsole(args,
        checkmk_host=CHECKMK_HOST, 
        checkmk_user=CHECKMK_USER, 
        msg=''):
    ''' sub-command function for event-mode '''

    if args.test:
        print 'setting test env'
        set_test_env()

    msg = get_message_from_oracle()
    global CHECKMK_EVENT_PIPE

    if args.host:
        print 'host info in arg found'
        checkmk_host = args.host
    if args.user:
        checkmk_user = args.user
    if args.message:
        msg = clean_message_string(args.message)

    if args.verbose:
        print '[INFO] sending mode: EVENT console, CheckMK host: %s, message: %s' % (checkmk_host, msg)


    run_cmd('echo \"%s\" | ssh %s@%s "cat > %s"' % (msg, checkmk_user, checkmk_host, CHECKMK_EVENT_PIPE))


def send_with_nsca(args):
    ''' sub-command function for nsca-mode 
        Usage: 
            send_nsca -H <host_address> [-p port] [-to to_sec] [-d delim] [-c config_file]'''

    if args.test:
        set_test_env()

    if args.host:
        checkmk_host = args.host
    else:
        checkmk_host = CHECKMK_HOST
    if args.message:
        msg = clean_message_string(args.message)
    else:
        msg = get_message_from_oracle('tab')

    if args.verbose:
        print '[INFO] sending mode: NSCA, CheckMK host: %s, message: %s' % (checkmk_host, msg)

    if not os.path.isfile(CHECKMK_NSCA_CFG):
        die('[ERROR] missing nsca config at: %s' % CHECKMK_NSCA_CFG, 127)
    if not os.path.exists(CHECKMK_NSCA_BIN):
        die('[ERROR] missing send_nsca at: %s' % CHECKMK_NSCA_BIN, 127)

    run_cmd('echo -e \"%s\\n\" | %s -H %s -c %s' % (msg, CHECKMK_NSCA_BIN, checkmk_host, CHECKMK_NSCA_CFG))


def send_from_odi(args):
    ''' sub-command function for writing a Oracle ODI message to <ODI_LOCAL_DB>
        '''

    if args.message:
        message = args.message
    else:
        message = ''

    message = clean_message_string(message.split('\n')[0])

    cmd = '''%s/message-queue.py -f %s add -j '{"instance": "%s", "job": "%s", "event": "%s", "message": "%s"}' ''' % (
        TASKS_ROOT_DIR, ODI_LOCAL_DB,
        args.instance, args.job, args.event, message )
    
    # f = open('%s/debug.txt' % STATUS_ROOT_DIR, 'w')
    # f.write('%s\n' % cmd)
    # f.close()

    run_cmd(cmd)

    if args.verbose:
        print '[INFO] sending mode: oracle ODI, destination: %s, Command: %s' % (ODI_LOCAL_DB, cmd)


# ========================================================================
#  ARGS PARSING
# ========================================================================
parser = argparse.ArgumentParser(prog=os.path.basename(__file__), formatter_class=argparse.RawDescriptionHelpFormatter, description=DESC, epilog=textwrap.dedent(EPILOG))
parser.add_argument(
    '-v', '--verbose', action='store_true', help='verbose')
parser.add_argument(
    '-t', '--test', action='store_true', help='set oracle env vars for testing')

# add subcommands and apropriate args
subparsers = parser.add_subparsers(help='Modes available for parsing/sending messages')

parser_file = subparsers.add_parser(
    'file', help='File destination')
parser_file.set_defaults(func=send_to_file)
parser_file.add_argument(
    '-f', '--filename', type=str, help='path to destination file')
parser_file.add_argument(
    '-m', '--message', type=str, help='notification message to send')

parser_nsca = subparsers.add_parser(
    'nsca', help='CheckMK Host using send_nsca')
parser_nsca.set_defaults(func=send_with_nsca)
parser_nsca.add_argument(
    '-H', '--host', type=str, help='CheckMK hostname')
parser_nsca.add_argument(
    '-m', '--message', type=str, help='notification message to send')

parser_event = subparsers.add_parser(
    'event', help='CheckMK Event Console using SSH')
parser_event.set_defaults(func=send_to_eventconsole)
parser_event.add_argument(
    '-H', '--host', type=str, help='CheckMK hostname')
parser_event.add_argument(
    '-u', '--user', type=str, help='user on CheckMK host')
parser_event.add_argument(
    '-m', '--message', type=str, help='notification message to send')

parser_odi = subparsers.add_parser(
    'odi', help='Received from an Oracle ODI')
parser_odi.set_defaults(func=send_from_odi)
parser_odi.add_argument(
    '-j', '--job', type=str, help='PROCESS_NAME', required=True)
parser_odi.add_argument(
    '-i', '--instance', choices=['I', 'Q', 'P'], help='environment', required=True)
parser_odi.add_argument(
    '-e', '--event', choices=['STARTED', 'SUCCESS', 'ERROR'], help='event code', required=True)
parser_odi.add_argument(
    '-f', '--filename', type=str, help='where to send the message')
parser_odi.add_argument(
    '-m', '--message', type=str, help='any message content')


# parse the args and call the apropriate function
args = parser.parse_args()
args.func(args)
