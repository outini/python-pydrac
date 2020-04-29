# -*- coding: utf-8 -*-
#
#
#  Dell iDRAC python interface (python-pydrac)
#
#  Copyright (C) 2018 Denis Pompilio (jawa) <denis.pompilio@gmail.com>
#
#  This file is part of python-pydrac
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the MIT License.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  MIT License for more details.
#
#  You should have received a copy of the MIT License along with this
#  program; if not, see <https://opensource.org/licenses/MIT>.

"""
Dell iDRAC python interface (python-pydrac)
"""

import time
import logging
import socket
import textwrap
import collections
from itertools import chain
# from logging.handlers import SysLogHandler

import pexpect
from pexpect import pxssh


LOG = logging.getLogger(__name__)

_RaiseKeyError = object()  # singleton for no-default behavior


class RacAdmRegistry(dict):
    """"""
    __slots__ = ('_reg', '_racadm', 'changes')

    @staticmethod  # because this doesn't make sense as a global function.
    def _process_args(mapping=(), **kwargs):
        if hasattr(mapping, 'items'):
            mapping = mapping.items()
        return ((k, v) for k, v in chain(mapping, kwargs.items()))

    @staticmethod
    def _output_to_dict(output):
        """"""
        data = {}
        for line in output.splitlines()[1:]:  # skip output key header
            key, value = line.strip().split('=', 1)
            data[key] = value
        return data

    def __init__(self, _reg, _racadm, **kwargs):
        self._reg = _reg
        self._racadm = _racadm
        self.changes = dict()

        LOG.info("loading registry: %s", _reg)
        self.__load()

        super().__init__(**kwargs)

    def __load(self):
        out = self._racadm.r_exec('get %s' % self._reg)
        super().clear()
        super().update(**self._output_to_dict(out))

    def __getitem__(self, k):
        try:
            return self.changes.__getitem__(k)
        except KeyError:
            return super().__getitem__(k)

    def __setitem__(self, k, v):
        if k not in super().keys():
            raise KeyError(k)
        if v == super().__getitem__(k):
            return None
        return self.changes.__setitem__(k, v)

    def __delitem__(self, k):
        return self.changes.__delitem__(k)

    def __iter__(self, *args, **kwargs):
        return chain(super().items(), self.changes.items()).__iter__()

    # def items(self):
    #     return {**super(), **self.changes}.items()

    def get(self, k, default=None):
        return super().get(k, default)

    def pop(self, k, v=_RaiseKeyError):
        if v is _RaiseKeyError:
            return self.changes.pop(k)
        return self.changes.pop(k, v)

    def setdefault(self, k, default=None):
        return self.changes.setdefault(k, default)

    def update(self, mapping=(), **kwargs):
        changed_values = {}
        for key, val in self._process_args(mapping, **kwargs):
            if key not in super().keys():
                raise KeyError(key)
            if val == super().__getitem__(key):
                continue
            changed_values[key] = val
        self.changes.update(changed_values)

    def __contains__(self, k):
        return chain(super().items(), self.changes.items()).__contains__(k)

    def copy(self):  # don't delegate w/ super - dict.copy() -> dict :(
        copy = type(self)(self, _reg=self._reg, _racadm=self._racadm)
        copy.changes = self.changes.copy()
        return copy

    def __repr__(self):
        return '{0}({1}, changes={2})'.format(
            type(self).__name__, super().__repr__(), self.changes.__repr__()
        )

    def write(self):
        """Write changes on remote IDRAC

        :return: Success boolean
        """
        if not self.changes:
            return False
        LOG.info('writing changes on %s: %s', self._reg, self.changes)
        for key, val in self.changes.items():
            self._racadm.r_exec("set {0}.{1} {2}".format(self._reg, key, val))
        self.changes = {}
        self.__load()
        return True


class RacAdmBios(object):
    """"""
    def __init__(self, racadm_client):
        """Initialization"""
        self._racadm = racadm_client
        self.r_exec = self._racadm.r_exec

        self._registries = [
            ('idrac_ipv4', 'idrac.ipv4'),
            ('bios_boot_settings', 'BIOS.BiosBootSettings'),
            ('sys_profile_settings', 'BIOS.SysProfileSettings')
        ]
        for attr, reg_name in self._registries:
            setattr(self, attr, RacAdmRegistry(_reg=reg_name, _racadm=self))

    @property
    def changes(self):
        changes = {}
        for attr, reg in self._registries:
            for key, val in getattr(self, attr).changes.items():
                changes["%s.%s" % (reg, key)] = val
        return changes

    def commit(self):
        result = (getattr(self, attr).write()
                  for attr, reg in self._registries)
        if True in result:
            self._racadm.run_jobs('bios.setup.1-1')
            return True
        return False


class RacAdmStorage(object):
    """"""
    def __init__(self, racadm_client):
        """Initialization"""
        self.racadm = racadm_client

        self._pdisks = None
        self._vdisks = None

        self.defaults = {
            'vdisks': {
                'readpolicy': 'nra',
                'writepolicy': 'wt',
                'stripesize': '1M'
            }
        }

    def r_exec(self, command, retry=3, ignoreerrors=False):
        """Execute storage related command on the remote iDRAC

        Commands are automatically prefixed with 'racadm raid'

        :param str command: Racadm raid command to execute
        :param int retry: Retry count on error
        :param bool ignoreerrors: Ignore returned errors
        :return: Command output
        :rtype: str
        """
        return self.racadm.r_exec('raid ' + command, retry, ignoreerrors)

    @property
    def pdisks(self):
        """List physical disks

        :return: Physical disks information
        :rtype: list
        """
        if self._pdisks is None:
            output = self.r_exec(
                'get pdisks -o -p Name,State,Status,MediaType,Size'
            )
            self._pdisks = self._disks_to_obj(output)
        return self._pdisks

    @property
    def pdisks_by_size(self):
        """List physical disks sorted by size

        :return: Physical disks information
        :rtype: dict
        """
        disks = collections.defaultdict(list)
        for pdisk in self.pdisks:
            # skip the unit and convert to float
            # then group disks together with 10GB span
            size = float(pdisk['size'].split()[0])
            for known_size in disks:
                if int(size - known_size) < 10:
                    size = known_size
            disks[int(size)].append(pdisk)
        return disks

    @property
    def has_foreign_disks(self):
        """"""
        return 'Foreign' in [disk['state'] for disk in self.pdisks]

    @property
    def vdisks(self):
        """List virtual disks

        :return: Virtual disks information
        :rtype: list
        """
        if self._vdisks is None:
            try:
                output = self.r_exec(
                    'get vdisks -o '
                    '-p Name,State,Status,MediaType,Size,Layout'
                )
                self._vdisks = self._disks_to_obj(output)
            except RuntimeError:
                self._vdisks = []

        return self._vdisks

    def get_vdisk(self, name):
        """Get specific virtual disk by name

        :param str name: Virtual disk name
        :return: virtual disk information
        :rtype: dict
        """
        for virtual_disk in self.vdisks:
            if virtual_disk['name'] == name:
                return virtual_disk
        return None

    def select_pdisks(self, selection_method):
        """Select disks according to selection method

        :param str selection_method: Selection method
        """
        if selection_method == "smallest":
            return self.pdisks_by_size[sorted(self.pdisks_by_size)[0]]
        if selection_method == "largest":
            return self.pdisks_by_size[sorted(self.pdisks_by_size)[-1]]

    @staticmethod
    def _disks_to_obj(output):
        """Convert iDRAC disk listing output to object

        :param str output: iDRAC disk listing output
        :return: Disks list object
        :rtype: dict
        """
        try:
            lines = output.splitlines()
            objects = []
            for line in lines:
                if not line.strip():
                    continue
                if '=' not in line:
                    dkey = line.strip()
                    dkey_data = dkey.split(':', 3)
                    objects.append({
                        'dkey': dkey,
                        'disk': dkey_data[0]
                    })
                    if len(dkey_data) == 3:
                        # physical disks have enclosure information
                        objects[-1]['enclosure'] = dkey_data[1]
                        objects[-1]['controller'] = dkey_data[2]
                    else:
                        objects[-1]['controller'] = dkey_data[1]
                else:
                    fields = line.strip().split(None, 2)
                    objects[-1][fields[0].lower()] = fields[2]
            return objects
        except IndexError:
            LOG.error("error parsing disks output")
            LOG.error("content was:\n%s", output)
            raise

    def converttoraid(self, pdkey):
        """Convert physical disk to raid mode

        :param str pdkey: Physical disk key
        :return: iDRAC command output
        :rtype: str
        """
        LOG.info("converting Non-Raid disk: %s", pdkey)
        return self.r_exec('converttoraid:%s' % pdkey)

    def createvd(self, name, raid_type, disks):
        """Create RAID virtual disk

        :param str name: Virtual disk name
        :param str raid_type: Virtual disk RAID type
        :param list disks: List of physical disks to use
        :return: iDRAC command output
        :rtype: str
        """
        LOG.info("registering '%s' virtual disk creation job" % name)
        LOG.info("member disks:")
        for disk in disks:
            LOG.info("  %s (%s) - %s",
                     disk['dkey'], disk['mediatype'], disk['size'])

        # Check if all disk are in state ready, convert those if needed
        for disk in disks:
            if disk['state'] == 'Non-Raid':
                LOG.info("converting Non-Raid disk: %s" % disk['dkey'])
                self.converttoraid(disk['dkey'])

        self._vdisks = None
        return self.r_exec(
            'createvd:%s -name %s -rl %s -rp %s -wp %s -ss %s -pdkey:%s' % (
                disks[0]['controller'],
                name,
                raid_type,
                self.defaults['vdisks']['readpolicy'],
                self.defaults['vdisks']['writepolicy'],
                self.defaults['vdisks']['stripesize'],
                ','.join([disk['dkey'] for disk in disks])
            ))

    def deletevd(self, vdkey):
        """Delete virtual disk

        :param str vdkey: Virtual disk key
        :return: iDRAC command output
        :rtype: str
        """
        self._vdisks = None
        LOG.warning("deleting vdisk %s", vdkey)
        return self.r_exec('deletevd:%s' % vdkey)

    def assign_hotspare(self, vdkey, pdkey):
        """Assign dedicated hotspare to virtual disk

        :param str vdkey: Virtual disk key
        :param str pdkey: Physical disk to use as hotspare
        :return: iDRAC command output
        :rtype: str
        """
        LOG.info("assigning hotspare %s to %s", pdkey, vdkey)
        return self.r_exec(('hotspare:%s -assign yes -type dhs '
                            '-vdkey:%s' % (pdkey, vdkey)))

    def destroy_storage_configuration(self, controller):
        """Destroy the entire storage controller configuration
        """
        LOG.warning("destroying entire controller configuration")
        if self.has_foreign_disks:
            self.r_exec("clearconfig:%s" % controller,
                        retry=1, ignoreerrors=True)
        self.r_exec("resetconfig:%s" % controller)
        self.racadm.run_jobs(controller, wait=True)
        LOG.info("virtual disks cleaning is done")

    def set_profile_default(self):
        """Configure storage with default profile

        Default profile is:
            system - RAID1 - 2 smallest disks
            data - RAID5 - all largest disks, 1 dedicated hotspare
        """
        system_disks = self.select_pdisks("smallest")[:2]
        data_disks = self.select_pdisks("largest")[:-1]
        hspare = self.select_pdisks("largest")[-1]
        controller = system_disks[0]['controller']

        self.createvd('system', 'r1', system_disks)
        self.createvd('data', 'r5', data_disks)
        self.racadm.run_jobs(controller, wait=True)

        self._vdisks = None
        data_vd = self.get_vdisk('data')
        self.assign_hotspare(data_vd['dkey'], hspare['dkey'])
        self.racadm.run_jobs(controller)

    def set_profile_nodata(self):
        """Configure storage with nodata profile

        Nodata profile is:
            system - RAID1 - 2 smallest disks
        """
        system_disks = self.select_pdisks("smallest")[:2]
        controller = system_disks[0]['controller']

        self.createvd('system', 'r1', system_disks)
        self.racadm.run_jobs(controller, wait=True)
        self._vdisks = None

    def set_profile_database(self):
        """Configure storage with database profile

        Database profile is:
            system - RAID1 - 2 smallest disks
            logtemp - RAID1 - 2 largest disks
            data - RAID5 - all largest disks, 1 dedicated hotspare
        """
        system_disks = self.select_pdisks("smallest")[:2]
        controller = system_disks[0]['controller']

        data_disks_a = self.select_pdisks("largest")[:2]
        data_disks_b = self.select_pdisks("largest")[2:-1]
        hspare = self.select_pdisks("largest")[-1]

        self.createvd('system', 'r1', system_disks)
        self.createvd('logtemp', 'r1', data_disks_a)
        self.createvd('data', 'r5', data_disks_b)

        self.racadm.run_jobs(controller, wait=True)

        self._vdisks = None
        data_vd = self.get_vdisk('data')
        self.assign_hotspare(data_vd['dkey'], hspare['dkey'])
        self.racadm.run_jobs(controller)

    def set_profile_passthrough(self):
        """Configure storage with passthrough profile

        In passthrough profile, all disks are exposed as raid0.
        It bypass missing JBOD mode on controller.
        """
        controller = self.pdisks[0]['controller']

        self.createvd('system', 'r1', self.pdisks[:2])
        for pdisk in self.pdisks[2:]:
            self.createvd(pdisk['disk'], 'r0', [pdisk])
        self.racadm.run_jobs(controller, wait=True)
        self._vdisks = None


class RacAdmInventory(object):
    """"""
    def __init__(self, racadm_client):
        """Initialization"""
        self.racadm = racadm_client

        self.data = None

    def load(self, retry=3, ignoreerrors=False):
        """Execute inventory related command on the remote iDRAC

        :param int retry: Retry count on error
        :param bool ignoreerrors: Ignore returned errors
        :return: Command output
        :rtype: str
        """
        if not self.data:
            self.data = dict()
            instance = None
            data = None
            output = self.racadm.r_exec('hwinventory', retry, ignoreerrors)
            for line in output.splitlines():
                if not len(line.strip()) or line.startswith('-------'):
                    LOG.debug("instance data: " + str(data))
                    if data:
                        self.data[instance] = data
                    instance, data = None, None
                    continue

                if line.startswith('[InstanceID: '):
                    LOG.debug("instance line: " + line)
                    instance = line[13:-1]
                    LOG.debug("instance name: " + str(instance))
                    data = dict()
                else:
                    LOG.debug("data line: " + line)
                    fields = line.split('=', 1)
                    LOG.debug("data fields: " + str(fields))
                    data[fields[0].strip()] = fields[1].strip()

        return self.data

    def get_device_type(self, device_type):
        """"""
        self.load()
        return [data for instance, data in self.data.items()
                if data['Device Type'] == device_type]

    @property
    def system(self):
        """"""
        return self.get_device_type('System')[0]

    @property
    def psus(self):
        """"""
        return self.get_device_type('PowerSupply')

    @property
    def cpus(self):
        """"""
        return self.get_device_type('CPU')

    @property
    def memory(self):
        """"""
        return self.get_device_type('Memory')

    @property
    def nics(self):
        """"""
        return self.get_device_type('NIC')

    @property
    def raid_controllers(self):
        """"""
        return [device for device in self.get_device_type('PCIDevice')
                if device['InstanceID'].startswith('RAID.')]

    @property
    def enclosures(self):
        """"""
        return self.get_device_type('Enclosure')

    @property
    def disks(self):
        """"""
        return self.get_device_type('PhysicalDisk')

    def get_enclosure_disks(self, enclosure_id):
        """"""
        return [disk for disk in self.disks
                if disk['InstanceID'].endswith(enclosure_id)]

    def show(self, details=True):
        """"""
        data = self.system
        print(textwrap.dedent("""\
        Model: %s (%s)
        Serial: %s
        Hostname: %s
        CPU slots: %s / %s
        Memory slots: %s / %s
        Installed memory: %s / %s
        Power supply: %d psu(s)""" % (
            data['Model'], data['ChassisSystemHeight'],
            data['ServiceTag'],
            data.get('HostName', 'n/a'),
            data['PopulatedCPUSockets'], data['MaxCPUSockets'],
            data['PopulatedDIMMSlots'], data['MaxDIMMSlots'],
            data['SysMemTotalSize'], data['SysMemMaxCapacitySize'],
            len(self.psus)
        )))

        if details:
            output = "CPUs specs:"
            for cpu in self.cpus:
                output += "\n   %s Model: %s (%sc/%st)" % (
                    cpu['DeviceDescription'], cpu['Model'],
                    cpu['NumberOfEnabledCores'], cpu['NumberOfEnabledThreads']
                )
            output += "\nMemory specs:"
            for mem in self.memory:
                output += "\n    %s: %s %s @%s %s" % (
                    mem['DeviceDescription'],
                    mem['Size'],
                    mem['Model'],
                    mem['Speed'],
                    mem['Rank']
                )
            output += "\nNICs specs:"
            for nic in self.nics:
                output += "\n    %s" % nic['ProductName']
            output += "\nRAID ctls:"
            for device in self.raid_controllers:
                output += "\n    %s %s" % (device['Description'],
                                           device['DeviceDescription'])
            output += "\nEnclosures:"
            for encl in self.enclosures:
                output += "\n    %s - %s %s" % (
                    encl.get('ServiceTag', 'n/a'),
                    encl['ProductName'], encl['DeviceDescription']
                )
                output += "\n    Disks:"
                for disk in self.get_enclosure_disks(encl['InstanceID']):
                    output += "\n        %s %s %s (%s %s) - %d GB" % (
                        disk['DriveFormFactor'],
                        disk['MediaType'],
                        disk.get('SerialNumber', 'n/a'),
                        disk['Manufacturer'],
                        disk['Model'],
                        int(disk['SizeInBytes'].split()[0]) / 1073741824
                    )
            print(output)


class RacAdm(object):
    """"""
    capabilities = {
        'raid': RacAdmStorage,
        'bios': RacAdmBios,
        'inventory': RacAdmInventory
    }

    def __init__(self, idrac_conn, force_password=False):
        """Initialization"""
        self.conn = idrac_conn
        self._force_password = force_password
        self.ssh = None

    def __getattr__(self, item):
        if item in self.capabilities:
            setattr(self, item, self.capabilities[item](self))
            return getattr(self, item)
        else:
            raise AttributeError

    @property
    def ssh_is_open(self):
        """"""
        LOG.debug("testing %s:22" % self.conn['endpoint'])
        result = 1
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            result = sock.connect_ex((self.conn['endpoint'], 22))
        except socket.gaierror as exc:
            LOG.error(exc)
        if result == 0:
            LOG.debug("%s:22 is open" % self.conn['endpoint'])
            return True
        return False

    def login(self):
        """Log into the remote iDRAC
        """
        error_msg = "unable to connect idrac: %s"
        LOG.info("connecting to %s" % self.conn['endpoint'])
        if not self.ssh_is_open:
            LOG.error("%s:22 is unreachable" % self.conn['endpoint'])
            raise RuntimeError(error_msg)

        retry = 3
        while retry > 0:
            try:
                self.ssh = pxssh.pxssh(timeout=10, maxread=10000,
                                       options={'PubkeyAuthentication': 'no',
                                                'NumberOfPasswordPrompts': 2})
                LOG.debug("connection to " + self.conn['endpoint'])
                self.ssh.login(self.conn['endpoint'],
                               self.conn['user'],
                               self.conn['password'],
                               auto_prompt_reset=False)
            except pxssh.ExceptionPxssh as exc:
                self.ssh = None
                if exc.value == "password refused" or retry <= 0:
                    LOG.error(error_msg % exc)
                    raise RuntimeError(error_msg % exc)
                retry -= 1
                time.sleep(1)
            else:
                break

        self.ssh.setwinsize(10000, 10000)  # big window for big operations
        self.ssh.PROMPT = r'(/admin1-> |racadm>>).*'
        self.ssh.prompt()
        LOG.info("connected to %s" % self.conn['endpoint'])

    def logout(self):
        """Log out from the remote iDRAC
        """
        if self.ssh:
            self.ssh.logout()

    def r_exec(self, command, retry=3, ignoreerrors=False):
        """Execute command on the remote iDRAC

        Commands are automatically prefixed with 'racadm'

        :param str command: Racadm command to execute
        :param int retry: Retry count on error
        :param bool ignoreerrors: Ignore returned errors
        :return: Command output
        :rtype: str
        :raise RuntimeError: Command returned an error.
        """
        if not self.ssh:
            self.login()

        output = ""
        while retry > 0:
            LOG.debug('running command: %s', command)
            self.ssh.sendline('racadm ' + command)
            self.ssh.prompt(timeout=60)
            output = self.ssh.before.decode()
            LOG.debug('received:\n%s' % output)

            # command is echoed back, skip the first line
            output = "\n".join(output.splitlines()[1:]).strip()
            if output.startswith('ERROR: LC062 '):
                LOG.debug('profile export job is running... waiting')
                time.sleep(10)
            elif output.startswith('ERROR: '):
                retry -= 1
                if retry:
                    LOG.debug("retrying command...")
            else:
                break

        if output.startswith('ERROR: ') and not ignoreerrors:
            LOG.error("error running command: %s", command)
            LOG.error("error was:\n%s", output)
            raise RuntimeError(output)

        return output

    def serveraction(self, action):
        """"""
        return self.r_exec("serveraction %s" % action)

    def run_jobs(self, unit, now=True, wait=False):
        """Run iDRAC pending jobs

        :param str unit: Unit to select to run jobs
        :param bool now: Run the job immediately
        :param bool wait: Wait for the job to finish
        :return: Job ID
        :rtype: str
        """
        LOG.info("running unit %s pending jobs", unit)
        command = 'jobqueue create %s' % unit
        if now:
            command += " --realtime"
        output = self.r_exec(command)
        jid = output.split('Commit JID = ')[1]

        if wait:
            LOG.info("waiting job %s completion", jid)
            while self.get_job(jid)['status'] not in ['Completed', 'Failed']:
                time.sleep(2)

        return jid

    def get_job(self, jid):
        """Get job information

        :param str jid: Job ID
        :return: Job information
        :rtype: dict
        """
        output = self.r_exec('jobqueue view -i %s' % jid)
        # ---------------------------- JOB -------------------------
        # [Job ID=JID_378288740486]
        # Job Name=Configure: RAID.Integrated.1-1
        # Status=Completed
        # Start Time=[Now]
        # Expiration Time=[Not Applicable]
        # Message=[PR19: Job completed successfully.]
        # Percent Complete=[100]
        # ----------------------------------------------------------
        job_status = {}
        for line in output.splitlines()[2:-1]:
            key, value = line.split('=', 1)
            key = key.lower().replace(' ', '_')
            job_status[key] = value
        # LOG.info(job_status)
        return job_status

    def get_sel(self, severity=None):
        """"""
        for event in self.r_exec('getsel -o').splitlines():
            e_date, e_time, e_src, e_sev, e_msg = event.split(None, 4)
            if not severity or e_sev in severity:
                yield " ".join([e_date, e_time, e_src, e_sev, e_msg])


if __name__ == "__main__":
    print("racadm is designed to be imported")
