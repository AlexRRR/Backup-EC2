'''EC2 snapshot settings'''
import logging
from boto.ec2.connection import EC2Connection
from boto import ec2
from boto.exception import EC2ResponseError
import unicodedata
from datetime import date,timedelta
import iso8601
import optparse




logger = logging.getLogger('backup')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
fh = logging.handlers.RotatingFileHandler('backup.log',maxBytes=104857600)
fh.setLevel(logging.DEBUG)
frmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(frmt)
ch.setFormatter(frmt)
logger.addHandler(fh)
logger.addHandler(ch)


ec2_region = 'eu-west-1'
try:
    conn = ec2.connect_to_region(ec2_region)
except EC2ResponseError as error:
    logger.error(error)
    exit(2)


BACKUP_RETAIN = { 'daily': 4, 'weekly': 16, 'monthly': 1 }

EXCLUDED_INSTANCES = ['excluded.server.name']
