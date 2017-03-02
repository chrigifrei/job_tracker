# Job Tracker
Tracks jobs according to a given pattern (time & event based)

Date: June 2016

This ansible playbook was written for a specific customer environment consisting of
- Nagios based CheckMK monitoring 
- Oracle DWH (Oracle Data Integrator ODI) monitored by Oracles Enterprise Manager (EM)

Since Oracle does not provide a tooling for supervising their loadjobs into the DWH, job_tracker was developed.


## QUICK START
- Adjust the ansible inventory `env-local.ini` (the given inventory is based on a local vagrant environment consisting of 5 VMs)
- Adjust the `roles/job_tracker-setup/templates/<env>-job_tracker.cfg` according to your needs
- Make sure the host running job_tracker (most commonly: EM) is able to connect to source hosts using certain SSH creds
- Deploy job_tracker `ansible-playbook -i env-local.ini setup.yml`
- Start the job_tracker `service job_tracker start`
- Check the log `/var/log/job_tracker.log`



## JOB_TRACKER - CONFIGFILE
- global config: application wide settings
- source hosts: hosts providing job relevant status data
- jobs: cyclic or daily (timed) jobs to track

### Global Config
| Param | Value | Description |
| jobs_start_keyword | string | The given keyword will advice the tracker to mark the job as started. |
| jobs_error_keyword | string | The given keyword will indicate the occurance of an error. |
| jobs_end_keyword | string | The given keyword will advice the tracker to mark the job as completed with success |
| no_timeout_for_cyclic_jobs_from_in_hh:mm | time as "hh:00" | during this timeframe no alarms will be triggered for job timeouts |
| no_timeout_for_cyclic_jobs_until_in_hh:mm | time as "hh:00" | during this timeframe no alarms will be triggered for job timeouts |
| controller_message_grace_period_in_sec | seconds as float | covers the time drift between the occurance of a status message and the processing of the message |

### Source Hosts
NOTE: The timedrift between the host running job_tracker and its source hosts cannot be greater than <controller_message_grace_period_in_sec>  

### Jobs
| Param | Value | Description |
| cyclic_or_daily | "cyclic" or "daily" | See params below for diferences between the two. |
| cyclic_interval_in_hh:mm:ss | time in "hh:mm:ss" | Job will run every <time> (like a cronjob). |
| daily_start_time_in_hh:mm | time in "hh:mm" | Job will start at <time>  (scheduled). |
| start_max_delay_in_hh:mm:ss | time in "hh:mm:ss" | Only for daily jobs. Tracker will wait <time> for the <start_keyword> before alarming. |
| timeout_in_hh:mm:ss | time in "hh:mm:ss" | Tracker will wait <time> for the <end_keyword> before alarming. |
| max_errors_before_alerting | number | Tracker will count <number> of errorous events before alarming. |


## JOB_TRACKER - SETUP
job_tracker installation instructions.

### Ansible Deployment
```
ansible-playbook -C -i <env>.ini -t checkmk-agent-check-oracle setup-clients-monitored.yml
```

### System V Service Operation
```
chkconfig --add job_tracker
service job_tracker start|stop|restart|status
```

### Source Hosts

_ATTENTION_: make sure that ssh connectivity is set up properly between host running job_tracker and source hosts.

By default status messages on source hosts are sent to: `/home/oracle/oem-status-check/status/msg-queue.sqlite`

message queue handling
```
cd /home/oracle/oem-status-check/tasks
python message-queue.py --help
```


## MONITORING BACKENDS
- CheckMK Service: "status"
- CheckMK Event Console: "event"

### CheckMK Service Integration

Status file for each job:
```
/var/run/<prog>.<jobname>.state
where by default:
  <prog>: job_tracker
  <jobname>: name__env 
```

Content:  
CheckMK status message: 
```
<status_as_int> <service_name> - <desc>
```

Local Checks in:
```
default: /usr/lib/check_mk_agent/local
```

Register new Services (on CheckMK monitoring server, using OMD):
```
su - <omd_admin>
check_mk -v -I <hostname_of_host_running_job_tracker>
```

### CheckMK Event Console Integration

Event handler:
* send-notification.py needed in the path of job_tracker


## TROUBLESHOOTING

Get messages from queue on source hosts:
```
cd /home/oracle/oem-status-check/status/
while true; do python ../tasks/message-queue.py -f `pwd`/odi-jobs-status-queue.sqlite list | egrep -v '\[\]' >> queue.txt; sleep 2; done &
tail -f queue.txt
```
