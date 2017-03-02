''' Tracks jobs according to a given pattern (time & event based)
Module: 
    filer

Takes:
    filename (string)

Description:
    creates/handles a file with given dict entries

    .file       filename (string)
'''

import os
import random
from operator import itemgetter
from collections import OrderedDict

class filer():

    def __init__(self, cfg, logger, filename):

        self.cfg = cfg
        self.logger = logger
        self.file = filename

        if not os.path.exists(self.file):
            self.init_file()


    def init_file(self):
        
        try:
            open(self.file, 'a').close()
        
        except Exception as err:
            self.logger.warning('unable to init %s. %s' % (self.file, err))


    def get_new_id(self):

        return ''.join(random.choice('0123456789abcdef') for n in xrange(16))


    def get_last_statement(self):

        content = self.read_content()

        if len(content) > 0:
            return content[0]
        else:
            return dict()


    def read_content(self):
        
        content = []

        try:
            with open(self.file, 'r') as f_stream:
                for line in f_stream.readlines():
                    line = dict(eval(line.rstrip()))
                    content.append(line)
        
        except Exception as err:
            self.logger.warning('unable to read %s. %s' % (self.file, err))

        return content


    def write_statement(self, statement, sort_key):
        
        line_counter = 1
        
        content_old = self.read_content()
        content_old.append(statement)

        content_new = sorted(content_old, key=itemgetter(sort_key), reverse=True)

        try:
            with open(self.file, 'w') as f_stream:
                
                for line in content_new:
                    
                    if line_counter <= self.cfg.item['global_config'][0]['job_history_entry_count']:
                        f_stream.write('%s\n' % line)
                        line_counter += 1
                    
                    else:
                        break
                    
        except Exception as err:
            self.logger.warning('unable to write %s. %s' % (self.file, err))

