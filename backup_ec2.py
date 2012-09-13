#!/usr/bin/env python
"""Creates snapshots of selected instances on daily,weekly,monthly basis. Also
manages the purge of expired snapshots"""

from settings import *



def boto_connection(fn):
    """Decorator for handling EC2 Errors from the API"""
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except EC2ResponseError as error:
            logger.error(error)
    return wrapped

class Backup:

    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'


    def __init__(self, backup_type):
        self.instances_to_backup= []
        self.backup_type = backup_type



    def monthdelta(self,initial_date, delta):
        """Calculates the date from current date and delta in months"""
        m, y = (initial_date.month+delta) % 12, initial_date.year + (initial_date.month+delta-1) // 12
        if not m:
            m = 12
        feb_leap = 29 if y%4==0 and not y%400==0 else 28
        d = min(initial_date.day, [31,feb_leap,31,30,31,30,31,31,30,31,30,31][m-1])
        new_date = date(y,m,d)
        return new_date

    def oldest_date(self):
        """Returns the earliest date (as a string) to be purged"""
        if self.backup_type == self.DAILY:
            dt = date.today()-timedelta(days=BACKUP_RETAIN[self.DAILY])
            return dt
        if self.backup_type == self.WEEKLY:
            dt = date.today()-timedelta(days=(BACKUP_RETAIN[self.WEEKLY]*7))
            return dt
        if self.backup_type == self.MONTHLY:
            dt = self.monthdelta(date.today(),BACKUP_RETAIN[self.MONTHLY])
            return dt
        raise Exception("backup frequency is not correct!!")

    @boto_connection
    def instance_id_by_name(self,name_tag):
        """returns instance id, searching for the name tag"""
        name_filter = {'tag-key': 'Name','tag-value':name_tag}
        reservations = conn.get_all_instances(filters=name_filter)
        if not reservations:
            raise NameError("Unrecognized instance %s" % name_tag)
        instances = [i for r in reservations for i in r.instances]
        if len(reservations) > 1:
            raise Exception("Instance name tag is not unique!")
        return instances[0]

    @boto_connection
    def instances_for_backup(self):
        """Creates a list of only the instances configured for backup"""
        instance = None
        excluded_instances= []
        for excluded in EXCLUDED_INSTANCES:
            try:
                instance = self.instance_id_by_name(excluded)
            except NameError as error:
                logger.error(error)
                exit(2)
            excluded_instances.append(instance)

        reservations = conn.get_all_instances()
        all_instances = [i for r in reservations for i in r.instances]

        for exc in excluded_instances:
            for instance in all_instances:
                if instance.id == exc.id:
                    all_instances.remove(instance)
        return all_instances

    @boto_connection
    def volumes_for_instances(self,instance_list):
        """Return a list of all volumes attached to each instance in instance_list"""
        backup_volumes = []
        for instance in instance_list:
            instance_id = unicodedata.normalize('NFKD', instance.id).encode('ascii','ignore')
            filter = {'attachment.instance-id': instance_id}
            volumes = conn.get_all_volumes(filters=filter)
            backup_volumes = backup_volumes + volumes
        return backup_volumes

    @boto_connection
    def purge_old_snapshots(self,volume_id):
        """purges snapshots older than that specified on the settings file"""
        filter = {'volume-id': volume_id}
        filter.update({'tag-key': 'backup','tag-value':self.backup_type})
        snapshots = conn.get_all_snapshots(filters=filter)
        for snapshot in snapshots:
            start_date = iso8601.parse_date(snapshot.start_time).date()
            if start_date < self.oldest_date():
                logger.info("Deleting snapshot %s" % snapshot.id)

    @boto_connection
    def create_snapshots(self,volume_id,volume_name):
        """Creates the snapshots for each volume with the appropriate tags"""
        logger.info("Creating %s snapshot for %s" % (self.backup_type,volume_name))
        #snap = conn.create_snapshot(volume_id,description=volume_name)
        #snap.add_tag("backup",backup_type)

    @boto_connection
    def start(self):
        """Starts the backup process"""
        logger.info("Starting backup run for %s backups", self.backup_type)
        instance_list = self.instances_for_backup()
        for volume in self.volumes_for_instances(instance_list):
            volume_id = unicodedata.normalize('NFKD', volume.id).encode('ascii','ignore')
            self.purge_old_snapshots(volume_id)
            if 'Name' in volume.tags:
                self.create_snapshots(volume_id, volume.tags['Name'])
            else:
                name_tag = ("No name instance: %s" % volume_id)
                self.create_snapshots(volume_id, name_tag)




if __name__ == "__main__":
    backup_type = False
    parser = optparse.OptionParser()
    options = [
    parser.add_option('-d', '--daily', action="store_true",
        dest="daily", help="Daily backup"),
    parser.add_option('-w', '--weekly', action="store_true",
        dest="weekly", help="Critical backup"),
    parser.add_option('-m', '--monthly', action="store_true",
        dest="monthly", help="Monthly backup")
    ]
    (options, args) = parser.parse_args()
    if not ((options.daily != options.weekly) != options.monthly):
        logger.error("You must select a single backup type")
        exit(2)

    if options.daily:
        backup_type = 'daily'
    if options.weekly:
        backup_type = 'weekly'
    if options.monthly:
        backup_type = 'monthly'

    backup = Backup(backup_type)
    backup.start()




