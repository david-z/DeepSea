#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" This module will match disks based on applied filter rules

Internally this will be called 'DriveGroups'
"""

from __future__ import absolute_import
import json
import re
import logging
from typing import Set, Tuple
import salt.client

log = logging.getLogger(__name__)


class NoMatcherFound(Exception):
    """
    """

    pass


class FilterNotSupported(Exception):
    """ A critical error when the user specified filter is unsupported
    """

    pass


class UnitNotSupported(Exception):
    """ A critical error which encouters when a unit is parsed which
    isn't supported.
    """
    pass


# pylint: disable=too-few-public-methods
class Base(object):
    """ The base class container for local_client and base_target assignment
    """

    def __init__(self, **kwargs):
        self.local_client = salt.client.LocalClient()
        self.base_target = kwargs.get("target", "*")


class Filter(object):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', None)
        self.matcher = kwargs.get('matcher', None)
        self.value = kwargs.get('value', None)
        self._assign_matchers()
        log.debug("Initializing filter for {} with value {}".format(
            self.name, self.value))

    @property
    def is_matchable(self):
        return self.matcher is not None

    def _assign_matchers(self):
        """ Assign a matcher based on filter_name

        This method assigns an individual Matcher based
        on `filter_name` and returns it.

        :param str filter_name: The filter (size, model, vendor..)
        :param str filter_value: The filter_value (0,1, 'Samsung', '10G')
        :return: Any of the assigned matcher
        :rtype: *Matcher
        """
        if self.name == "size":
            self.matcher = SizeMatcher(self.name, self.value)
        elif self.name == "model":
            self.matcher = SubstringMatcher(self.name, self.value)
        elif self.name == "vendor":
            self.matcher = SubstringMatcher(self.name, self.value)
        elif self.name == "rotational":
            self.matcher = EqualityMatcher(self.name, self.value)

    def __repr__(self):
        return 'Filter<{}>'.format(self.name)


# pylint: disable=too-few-public-methods
class Inventory(Base):
    """ The Inventory class

    A container for the inventory call
    This may be extended in the future, depending on our needs.
    """

    def __init__(self, target=None):
        Base.__init__(self)
        self.target = target if target is not None else self.base_target
        log.debug("Retrieving Inventory for target {}".format(self.target))

    @property
    def raw(self):
        """
        TODO docstring
        """
        return self.local_client.cmd(self.target, "cmd.run",
                                     ["ceph-volume inventory --format json"])

    @property
    def disks(self):
        """
        TODO harden this & docstring
        """
        return json.loads((list(self.raw.values()))[0])


class Matcher(Base):
    """ The base class to all Matchers

    It holds utility methods such as _virtual, _get_disk_key
    and handles the initialization.

    Inherits from Base
    """

    def __init__(self, key: str, value: str) -> None:
        """ Initialization of Base class

        :param str key: Attribute like 'model, size or vendor'
        :param str value: Value of attribute like 'X123, 5G or samsung'
        """
        Base.__init__(self)
        self.key: str = key
        self.value: str = value
        self.fallback_key: str = ''
        self.virtual: bool = self._virtual()

    def _virtual(self):
        """ Detect if any of the hosts is virtual

        In vagrant(libvirt) environments the 'model' flag is not set.
        I assume this is flag is set everywhere else. However:

        This can possibly lead to bugs since all our testing
        runs on virtual environments. This is subject to be
        moved/changed/removed
        """
        virtual: dict = self.local_client.cmd(self.base_target, "grains.get",
                                              ["virtual"])
        flag: bool = False
        for host, val in virtual.items():
            if val != "physical":
                log.debug("Host {} seems to be a VM".format(host))
                flag = True
        return flag

    # pylint: disable=inconsistent-return-statements
    def _get_disk_key(self, disk: dict) -> str:
        """ Helper method to safely extract values form the disk dict

        There is a 'key' and a _optional_ 'fallback' key that can be used.
        The reason for this is that the output of ceph-volume is not always
        consistent (due to a bug currently, but you never know).
        There is also a safety measure for a disk_key not existing on
        virtual environments. ceph-volume apparently sources its information
        from udev which seems to not populate certain fields on VMs.

        :param dict disk: A disk representation
        :raises: A generic Exception when no disk_key could be found.
        :return: A disk value
        :rtype: str
        """
        disk_value: str = disk.get(self.key)
        if not disk_value and self.fallback_key:
            disk_value = disk.get(self.fallback_key)
        if disk_value:
            return disk_value
        if self.virtual:
            log.info(
                "Virtual-env detected. Not raising Exception on missing keys."
                " {} and {} appear not to be present".format(
                    self.key, self.fallback_key))
            return False
        else:
            raise Exception("No value found for {} or {}".format(
                self.key, self.fallback_key))

    def compare(self, disk: dict):
        """ Implements a valid comparison method for a SubMatcher
        This will get overwritten by the individual classes

        :param dict disk: A disk representation
        {'model': 'model_a',
         'size': '12345'}
        """
        pass


class SubstringMatcher(Matcher):
    """ Substring matcher subclass
    """

    def __init__(self, key: str, value: str, fallback_key=None) -> None:
        Matcher.__init__(self, key, value)
        self.fallback_key = fallback_key

    def compare(self, disk: dict) -> bool:
        """ Overwritten method to match substrings

        This matcher does substring matching
        :param dict disk: A disk representation (see base for examples)
        :return: True/False if the match succeeded
        :rtype: bool
        """
        disk_value: str = self._get_disk_key(disk)
        if str(self.value) in str(disk_value):
            return True
        return False


class EqualityMatcher(Matcher):
    """ Equality matcher subclass
    """

    def __init__(self, key: str, value: str) -> None:
        Matcher.__init__(self, key, value)

    def compare(self, disk: dict) -> bool:
        """ Overwritten method to match equality

        This matcher does value comparison
        :param dict disk: A disk representation
        :return: True/False if the match succeeded
        :rtype: bool
        """
        disk_value: str = self._get_disk_key(disk)
        if int(disk_value) == int(self.value):
            return True
        return False


class SizeMatcher(Matcher):
    """ Size matcher subclass
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, key: str, value: str) -> None:
        # TODO: key will be ignored
        Matcher.__init__(self, key, value)
        self.key: str = "human_readable_size"
        self.fallback_key: str = "size"
        self._high = None
        self._high_suffix = None
        self._low = None
        self._low_suffix = None
        self._exact = None
        self._exact_suffix = None
        self._parse_filter()

    @property
    def low(self) -> Tuple:
        """ Getter for 'low' matchers
        """
        return self._low, self._low_suffix

    @low.setter
    def low(self, low: Tuple):
        """ Setter for 'low' matchers
        """
        self._low, self._low_suffix = low

    @property
    def high(self) -> Tuple:
        """ Getter for 'high' matchers
        """
        return self._high, self._high_suffix

    @high.setter
    def high(self, high: Tuple):
        """ Setter for 'high' matchers
        """
        self._high, self._high_suffix = high

    @property
    def exact(self) -> Tuple:
        """ Getter for 'exact' matchers
        """
        return self._exact, self._exact_suffix

    @exact.setter
    def exact(self, exact: Tuple):
        """ Setter for 'exact' matchers
        """
        self._exact, self._exact_suffix = exact

    @property
    def supported_suffixes(self):
        """ Only power of 10 notation is supported
        """
        return ["MB", "GB", "TB", "M", "G", "T"]

    def _normalize_suffix(self, suffix: str) -> str:
        """ Normalize any supported suffix

        Since the Drive Groups are user facing, we simply
        can't make sure that all users type in the requested
        form. That's why we have to internally agree on one format.
        It also checks if any of the supported suffixes was used
        and raises an Exception otherwise.

        :param str suffix: A suffix ('G') or ('M')
        :return: A normalized output
        :rtype: str
        """
        if suffix not in self.supported_suffixes:
            raise UnitNotSupported("Unit '{}' not supported".format(suffix))
        if suffix == "G":
            return "GB"
        if suffix == "T":
            return "TB"
        if suffix == "M":
            return "MB"
        return suffix

    def _parse_suffix(self, obj: str) -> str:
        """ Wrapper method to find and normalize a prefix

        :param str obj: A size filtering string ('10G')
        :return: A normalized unit ('GB')
        :rtype: str
        """
        return self._normalize_suffix(re.findall(r"[a-zA-Z]+", obj)[0])

    def _get_k_v(self, data: str) -> Tuple:
        """ Helper method to extract data from a string

        It uses regex to extract all digits and calls _parse_suffix
        which also uses a regex to extract all letters and normalizes
        the resulting suffix.

        :param str data: A size filtering string ('10G')
        :return: A Tuple with normalized output (10, 'GB')
        :rtype: tuple
        """
        return (re.findall(r"\d+", data)[0], self._parse_suffix(data))

    def _parse_filter(self):
        """ Identifies which type of 'size' filter is applied

        There are four different filtering modes:

        1) 10G:50G (high-low)
           At least 10G but at max 50G of size

        2) :60G
           At max 60G of size

        3) 50G:
           At least 50G of size

        4) 20G
           Exactly 20G in size

        This method uses regex to identify and extract this information
        and raises if none could be found.
        """
        low_high = re.match(r"\d+[A-Z]{1,2}:\d+[A-Z]{1,2}", self.value)
        if low_high:
            low, high = low_high.group().split(":")
            self.low = self._get_k_v(low)
            self.high = self._get_k_v(high)

        low = re.match(r"\d+[A-Z]{1,2}:$", self.value)
        if low:
            self.low = self._get_k_v(low.group())

        high = re.match(r"^:\d+[A-Z]{1,2}", self.value)
        if high:
            self.high = self._get_k_v(high.group())

        exact = re.match(r"^\d+[A-Z]{1,2}$", self.value)
        if exact:
            self.exact = self._get_k_v(exact.group())

        if not self.low and not self.high and not self.exact:
            raise Exception("Couldn't parse {}".format(self.value))

    @staticmethod
    # pylint: disable=inconsistent-return-statements
    def to_byte(tpl: Tuple) -> float:
        """ Convert any supported unit to bytes

        :param tuple tpl: A tuple with ('10', 'GB')
        :return: The converted byte value
        :rtype: float
        """
        value = float(tpl[0])
        suffix = tpl[1]
        if suffix == "MB":
            return value * 1e+6
        if suffix == "GB":
            return value * 1e+9
        if suffix == "TB":
            return value * 1e+12

    # pylint: disable=inconsistent-return-statements
    def compare(self, disk: dict) -> bool:
        """ Convert MB/GB/TB down to bytes and compare

        1) Extracts information from the to-be-inspected disk.
        2) Depending on the mode, apply checks and return

        #todo This doesn't seem very solid and _may_
        be re-factored


        """
        disk_value = self._get_disk_key(disk)
        # This doesn't neccessarily have to be a float.
        # The current output from ceph-volume gives a float..
        # This may change in the future..
        # TODO: harden this paragraph
        disk_size = float(re.findall(r"\d+\.\d+", disk_value)[0])
        disk_suffix = self._parse_suffix(disk_value)
        disk_size_in_byte = self.to_byte((disk_size, disk_suffix))

        if all(self.high) and all(self.low):
            if disk_size_in_byte <= self.to_byte(
                    self.high) and disk_size_in_byte >= self.to_byte(self.low):
                return True
            # is a else: return False neccessary here?
            # (and in all other branches)
            log.debug("Disk didn't match for 'high/low' filter")

        elif all(self.low) and not all(self.high):
            if disk_size_in_byte >= self.to_byte(self.low):
                return True
            log.debug("Disk didn't match for 'low' filter")

        elif all(self.high) and not all(self.low):
            if disk_size_in_byte <= self.to_byte(self.high):
                return True
            log.debug("Disk didn't match for 'high' filter")

        elif all(self.exact):
            if disk_size_in_byte == self.to_byte(self.exact):
                return True
            log.debug("Disk didn't match for 'exact' filter")
        else:
            log.debug("Neither high, low, nor exact was given")
            raise Exception("No filters applied")


class DriveGroup(Base):
    """ The Drive-Group class

    Targets on node and applies filters on the node's inventory
    It mainly exposes:

    `data_devices`
    `wal_devices`
    `db_devices`
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, target) -> None:
        Base.__init__(self)
        self.target: str = target
        self._check_filter_support()

    @property
    def raw(self) -> dict:
        """
        TODO docstring
        """
        return list(
            self.local_client.cmd(self.target, "pillar.get",
                                  ["drive_group"]).values())[0]

    @property
    def db_slots(self) -> dict:
        """
        TODO docstring
        """
        return self.raw.get("db_slots", False)

    @property
    def wal_slots(self) -> dict:
        """
        TODO docstring
        """
        return self.raw.get("wal_slots", False)

    @property
    def encryption(self) -> dict:
        """
        TODO docstring
        """
        return self.raw.get("encryption", False)

    @property
    def data_device_attrs(self) -> dict:
        """
        TODO docstring
        """
        return self.raw.get("data_devices", dict())

    @property
    def db_device_attrs(self) -> dict:
        """
        TODO docstring
        """
        return self.raw.get("db_devices", dict())

    @property
    def wal_device_attrs(self) -> dict:
        """
        TODO docstring
        """
        return self.raw.get("wal_devices", dict())

    @property
    def limit(self) -> int:
        """
        TODO docstring
        """
        return self.data_device_attrs.get("limit", 0)

    @property
    def inventory(self) -> dict:
        """
        TODO
        """
        return Inventory(self.target).disks

    @property
    def data_devices(self) -> list:
        """ Filter for (bluestore) DATA devices
        """
        log.warning("Scanning for data devices on host {}".format(self.target))
        return self._filter_devices(self.data_device_attrs)

    @property
    def wal_devices(self) -> list:
        """ Filter for bluestore WAL devices
        """
        log.warning("Scanning for WAL devices on host {}".format(self.target))
        return self._filter_devices(self.wal_device_attrs)

    @property
    def db_devices(self) -> list:
        """ Filter for bluestore DB devices
        """
        log.warning("Scanning for db devices on host {}".format(self.target))
        return self._filter_devices(self.db_device_attrs)

    def _limit_reached(self, len_devices: int, disk_path: str) -> bool:
        """ Check for the <limit> property and apply logic

        If a limit is set in 'device_attrs' we have to stop adding
        disks at some point.

        If limit is set (>0) and len(devices) >= limit

        :param int len_devices: Length of the already populated device set/list
        :param str disk_path: The disk identifier (for logging purposes)
        :return: True/False if the device should be added to the list of devices
        :rtype: bool
        """
        if self.limit > 0 and len_devices >= self.limit:
            log.info("Refuse to add {} due to limit policy <{}>".format(
                disk_path, self.limit))
            return True
        return False

    def _filter_devices(self, device_filter: dict) -> list:
        """ Filters devices with applied filters

        Iterates over all applied filter (there can be multiple):

        size: 10G:50G
        model: Fujitsu
        rotational: 1

        TODO:
        This currently acts as a OR gate. Should this be a AND gate?
        TODO:

        Iterates over all known disk (on one host(self.target)) and checks
        for matches by using the matcher subclasses.

        :param dict device_filter: Device filter as in description above
        :return: Set of devices that matched the filter
        :rtype set:
        """
        devices: Set = set()
        for name, val in device_filter.items():
            filter = Filter(name=name, value=val)
            for disk in self.inventory:
                # continue criterias
                if not filter.is_matchable:
                    continue

                if not filter.matcher.compare(
                        self._reduce_inventory(disk)):
                    continue

                if not self._has_mandatory_idents(disk):
                    continue

                if self._limit_reached(len(devices), disk.get('path')):
                    continue

                devices.add(disk.get("path"))

        # sorted() returns a sorted list by the cost of losing the <set>
        return sorted(devices)

    def _has_mandatory_idents(self, disk: dict) -> bool:
        if disk.get("path", None):
            log.debug("Found matching disk: {}".format(
                disk.get("path")))
            return True
        else:
            raise Exception(
                "Disk {} doesn't have a 'path' identifier".format(
                    disk))

    @property
    def _supported_filters(self) -> list:
        """ List of supported filters
        """
        return ["size", "vendor", "model", "rotational", "limit"]

    def _check_filter_support(self) -> None:
        """ Iterates over attrs to check support
        """
        for attr in [
                self.data_device_attrs,
                self.wal_device_attrs,
                self.db_device_attrs,
        ]:
            self._check_filter(attr)

    def _check_filter(self, attr: dict) -> None:
        """ Check if the used filters are supported

        :param dict attr: A dict of filters
        :raises: FilterNotSupported if not supported
        :return: None
        """
        for applied_filter in list(attr.keys()):
            if applied_filter not in self._supported_filters:
                raise FilterNotSupported(
                    "Filtering for {} is not supported".format(applied_filter))

    @staticmethod
    # pylint: disable=inconsistent-return-statements
    def _reduce_inventory(disk: dict) -> dict:
        """ Wrapper to validate 'ceph-volume inventory' output
        """
        # FIXME: Temp disable this check, only for testing purposes
        # maybe this check doesn't need to be here as ceph-volume
        # does this check aswell..
        # This also mostly exists due to:
        # https://github.com/ceph/ceph/pull/25390
        # maybe this can and should be dropped when the fix is public
        if disk["available"] is False:  # True
            try:
                reduced_disk = {"path": disk.get("path")}

                reduced_disk["size"] = disk.get("sys_api", {}).get(
                    "human_readable_size", "")
                reduced_disk["vendor"] = disk.get("sys_api", {}).get(
                    "vendor", "")
                reduced_disk["bare_size"] = disk.get("sys_api", {}).get(
                    "size", "")
                reduced_disk["model"] = disk.get("sys_api", {}).get(
                    "model", "")
                reduced_disk["rotational"] = disk.get("sys_api", {}).get(
                    "rotational", "")

                return reduced_disk
            except KeyError("Could not retrieve mandatory key from disk spec"):
                raise


class DriveGroups(Base):
    """ A DriveGroup container class

    It resolves the 'host_target' from the drive_group spec and
    feeds the 'target' on by one to the DriveGroup class
    This in turn filters all matching devices and returns
    """

    def __init__(self):
        Base.__init__(self)
        self.targets: list = list(
            self.local_client.cmd(self.base_target, "cmd.run",
                                  ["test.ping"]).keys())

    def generate(self):
        """ Generate DriveGroups for all targets
        """
        for target in self.targets:
            drive_group = DriveGroup(target)
            print(drive_group.data_devices)
            print(drive_group.wal_devices)
            print(drive_group.db_devices)
            print("\n")


def test():
    """ Generate DriveGroups for specification.
    """
    DriveGroups().generate()
