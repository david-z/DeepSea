import pytest
from mock import patch, call, Mock, PropertyMock
from srv.modules.runners import disks


class TestBase(object):
    """ Test for the Base helper class from disks.py
    """

    @patch("salt.client.LocalClient", autospec=True)
    def test_base_init(self, mock_client):
        kwargs = {'target': 'a_valid_target'}
        base = disks.Base(**kwargs)
        assert base.base_target == 'a_valid_target'

    @patch("salt.client.LocalClient", autospec=True)
    def test_base_init_default(self, mock_client):
        base = disks.Base()
        assert base.base_target == '*'


class TestInventory(object):
    """ Test Inventory container class
    """

    @patch("salt.client.LocalClient", autospec=True)
    def test_inventory_init(self, mock_client):
        """ inv.base_target defaults to '*'
        """
        inv = disks.Inventory()
        assert inv.target == '*'

    @patch("salt.client.LocalClient", autospec=True)
    def test_inventory_init_target_overwrite(self, mock_client):
        """ Overwrite the target
        """
        inv = disks.Inventory('a_different_target')
        assert inv.target == 'a_different_target'

    @patch("salt.client.LocalClient", autospec=True)
    def test_inventory_raw(self, mock_client):
        """ Overwrite the target
        """
        local_client = mock_client.return_value
        disks.Inventory().raw()
        call1 = call('*', "cmd.run", ["ceph-volume inventory --format json"])
        assert call1 in local_client.cmd.mock_calls


class TestMatcher(object):
    """ Test Matcher base class
    """

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    def test_get_disk_key_1(self, virtual_mock):
        """
        virtual is True
        key is found
        return value of key is expected
        """
        virtual_mock.return_value = True
        disk_map = dict(path='/dev/vdb', foo='bar')
        ret = disks.Matcher('foo', 'bar')._get_disk_key(disk_map)
        assert ret == disk_map.get('foo')

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    def test_get_disk_key_2(self, virtual_mock):
        """
        virtual is True
        key is not found
        retrun False is expected
        """
        virtual_mock.return_value = True
        disk_map = dict(path='/dev/vdb')
        ret = disks.Matcher('bar', 'foo')._get_disk_key(disk_map)
        assert ret is ''

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    def test_get_disk_key_3(self, virtual_mock):
        """
        virtual is False
        key is found
        retrun value of key is expected
        """
        virtual_mock.return_value = False
        disk_map = dict(path='/dev/vdb', foo='bar')
        ret = disks.Matcher('foo', 'bar')._get_disk_key(disk_map)
        assert ret is disk_map.get('foo')

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    def test_get_disk_key_4(self, virtual_mock):
        """
        virtual is False
        key is not found
        expect raise Exception
        """
        virtual_mock.return_value = False
        disk_map = dict(path='/dev/vdb')
        with pytest.raises(
                Exception, message="No disk_key found for foo or None"):
            disks.Matcher('bar', 'foo')._get_disk_key(disk_map)

    @patch("salt.client.LocalClient", autospec=True)
    def test_virtual(self, mock_client):
        """ physical is in one of the hosts
        """
        grains = {
            'minion1': {
                'physical': True
            },
            'minion2': {
                'physical': False
            }
        }
        local_client = mock_client.return_value
        local_client.return_value = grains
        obj = disks.Matcher(None, None)
        obj.virtual is True

    @patch("salt.client.LocalClient", autospec=True)
    def test_virtual_1(self, mock_client):
        """ all hosts are physical
        """
        grains = {'minion1': {'physical': True}}
        local_client = mock_client.return_value
        local_client.return_value = grains
        obj = disks.Matcher(None, None)
        obj.virtual is False


class TestSubstringMatcher(object):
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare(self, mock_client, virtual_mock):
        virtual_mock.return_value = False
        disk_dict = dict(path='/dev/vdb', model='samsung')
        matcher = disks.SubstringMatcher('model', 'samsung')
        ret = matcher.compare(disk_dict)
        assert ret is True

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare_false(self, mock_client, virtual_mock):
        virtual_mock.return_value = False
        disk_dict = dict(path='/dev/vdb', model='nothing_matching')
        matcher = disks.SubstringMatcher('model', 'samsung')
        ret = matcher.compare(disk_dict)
        assert ret is False


class TestEqualityMatcher(object):
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare(self, mock_client, virtual_mock):
        virtual_mock.return_value = False
        disk_dict = dict(path='/dev/vdb', rotates='1')
        matcher = disks.SubstringMatcher('rotates', '1')
        ret = matcher.compare(disk_dict)
        assert ret is True

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare_false(self, mock_client, virtual_mock):
        virtual_mock.return_value = False
        disk_dict = dict(path='/dev/vdb', rotates='1')
        matcher = disks.SubstringMatcher('rotates', '0')
        ret = matcher.compare(disk_dict)
        assert ret is False


class TestSizeMatcher(object):
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_parse_filter_exact(self, mock_client, virtual_mock):
        """ Testing exact notation with 20G """
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', '20G')
        assert isinstance(matcher.exact, tuple)
        assert matcher.exact[0] == '20'
        assert matcher.exact[1] == 'GB'

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_parse_filter_exact_GB_G(self, mock_client, virtual_mock):
        """ Testing exact notation with 20G """
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', '20GB')
        assert isinstance(matcher.exact, tuple)
        assert matcher.exact[0] == '20'
        assert matcher.exact[1] == 'GB'

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_parse_filter_high_low(self, mock_client, virtual_mock):
        """ Testing high-low notation with 20G:50G """
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', '20G:50G')
        assert isinstance(matcher.exact, tuple)
        assert matcher.low[0] == '20'
        assert matcher.high[0] == '50'
        assert matcher.low[1] == 'GB'
        assert matcher.high[1] == 'GB'

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_parse_filter_max_high(self, mock_client, virtual_mock):
        """ Testing high notation with :50G """
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', ':50G')
        assert isinstance(matcher.exact, tuple)
        assert matcher.high[0] == '50'
        assert matcher.high[1] == 'GB'

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_parse_filter_min_low(self, mock_client, virtual_mock):
        """ Testing low notation with 20G: """
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', '50G:')
        assert isinstance(matcher.exact, tuple)
        assert matcher.low[0] == '50'
        assert matcher.low[1] == 'GB'

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_to_byte_GB(self, mock_client, virtual_mock):
        """ Pretty nonesense test.."""
        virtual_mock.return_value = False
        ret = disks.SizeMatcher('size', '10G').to_byte(('10', 'GB'))
        assert ret == 10 * 1e+9

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_to_byte_MB(self, mock_client, virtual_mock):
        """ Pretty nonesense test.."""
        virtual_mock.return_value = False
        ret = disks.SizeMatcher('size', '10M').to_byte(('10', 'MB'))
        assert ret == 10 * 1e+6

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_to_byte_TB(self, mock_client, virtual_mock):
        """ Pretty nonesense test.."""
        virtual_mock.return_value = False
        ret = disks.SizeMatcher('size', '10T').to_byte(('10', 'TB'))
        assert ret == 10 * 1e+12

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_to_byte_PB(self, mock_client, virtual_mock):
        """ Expect to raise """
        virtual_mock.return_value = False
        with pytest.raises(disks.UnitNotSupported):
            disks.SizeMatcher('size', '10P').to_byte(('10', 'PB'))
        assert 'Unit \'P\' is not supported'

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare_exact(self, mock_client, virtual_mock):
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', '20GB')
        disk_dict = dict(path='/dev/vdb', size='20.00 GB')
        ret = matcher.compare(disk_dict)
        assert ret is True

    @pytest.mark.parametrize("test_input,expected", [
        ("1.00 GB", None),
        ("20.00 GB", True),
        ("50.00 GB", True),
        ("100.00 GB", True),
        ("101.00 GB", None),
        ("1101.00 GB", None),
    ])
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare_high_low(self, mock_client, virtual_mock, test_input,
                              expected):
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', '20GB:100GB')
        disk_dict = dict(path='/dev/vdb', size=test_input)
        ret = matcher.compare(disk_dict)
        assert ret is expected

    @pytest.mark.parametrize("test_input,expected", [
        ("1.00 GB", True),
        ("20.00 GB", True),
        ("50.00 GB", True),
        ("100.00 GB", None),
        ("101.00 GB", None),
        ("1101.00 GB", None),
    ])
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare_high(self, mock_client, virtual_mock, test_input,
                          expected):
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', ':50GB')
        disk_dict = dict(path='/dev/vdb', size=test_input)
        ret = matcher.compare(disk_dict)
        assert ret is expected

    @pytest.mark.parametrize("test_input,expected", [
        ("1.00 GB", None),
        ("20.00 GB", None),
        ("50.00 GB", True),
        ("100.00 GB", True),
        ("101.00 GB", True),
        ("1101.00 GB", True),
    ])
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare_low(self, mock_client, virtual_mock, test_input,
                         expected):
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', '50GB:')
        disk_dict = dict(path='/dev/vdb', size=test_input)
        ret = matcher.compare(disk_dict)
        assert ret is expected

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_compare_raise(self, mock_client, virtual_mock):
        virtual_mock.return_value = False
        matcher = disks.SizeMatcher('size', 'None')
        disk_dict = dict(path='/dev/vdb', size='20.00 GB')
        with pytest.raises(Exception, message="Couldn't parse size"):
            matcher.compare(disk_dict)

    @pytest.mark.parametrize("test_input,expected", [
        ("10G", ('10', 'GB')),
        ("20GB", ('20', 'GB')),
    ])
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_get_k_v(self, mock_client, virtual_mock, test_input, expected):
        virtual_mock.return_value = False
        assert disks.SizeMatcher('size', '10G')._get_k_v(test_input) == expected

    @pytest.mark.parametrize("test_input,expected", [
        ("10G", ('GB')),
        ("20GB", ('GB')),
        ("20TB", ('TB')),
        ("20T", ('TB')),
        ("20MB", ('MB')),
        ("20M", ('MB')),
    ])
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_parse_suffix(self, mock_client, virtual_mock, test_input,
                          expected):
        virtual_mock.return_value = False
        assert disks.SizeMatcher('size', '10G')._parse_suffix(test_input) == expected

    @pytest.mark.parametrize("test_input,expected", [
        ("G", 'GB'),
        ("GB", 'GB'),
        ("TB", 'TB'),
        ("T", 'TB'),
        ("MB", 'MB'),
        ("M", 'MB'),
    ])
    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_normalize_suffix(self, mock_client, virtual_mock, test_input,
                              expected):
        virtual_mock.return_value = False
        assert disks.SizeMatcher(
            '10G', 'size')._normalize_suffix(test_input) == expected

    @patch("srv.modules.runners.disks.Matcher._virtual", autospec=True)
    @patch("salt.client.LocalClient", autospec=True)
    def test_normalize_suffix_raises(self, mock_client, virtual_mock):
        virtual_mock.return_value = False
        with pytest.raises(
                disks.UnitNotSupported, message="Unit 'P' not supported"):
            disks.SizeMatcher('10P', 'size')._normalize_suffix("P")


class TestDriveGroup(object):
    @patch("salt.client.LocalClient", autospec=True)
    def test_raw(self, mock_client):
        raw_sample = {
            'foo': {
                'target': 'data*',
                'data_devices': {
                    'size': '10G:29G',
                    'model': 'foo',
                    'vendor': '1x'
                },
                'wal_devices': {
                    'size': '20G'
                },
                'db_devices': {
                    'size': ':20G'
                },
                'db_slots': {5}
            }
        }

        local = mock_client.return_value
        local.cmd.return_value = raw_sample
        ret = disks.DriveGroup('*').raw
        assert isinstance(ret, dict)

    @pytest.fixture(scope='class')
    def test_fix(self, empty=None):
        def make_sample_data(empty=empty, limit=0):
            raw_sample = {
                'target': 'data*',
                'data_devices': {
                    'size': '10G:29G',
                    'model': 'foo',
                    'vendor': '1x',
                    'limit': limit
                },
                'wal_devices': {
                    'model': 'fast'
                },
                'db_devices': {
                    'size': ':10G'
                },
                'db_slots': 5,
                'wal_slots': 5,
                'objectstore': 'bluestore',
                'encryption': True,
            }
            if empty:
                raw_sample = {}

            self.check_filter_support = patch(
                'srv.modules.runners.disks.DriveGroup._check_filter_support',
                new_callable=Mock,
                return_value=True)
            self.local_client = patch('salt.client.LocalClient')
            self.raw_property = patch(
                'srv.modules.runners.disks.DriveGroup.raw',
                new_callable=PropertyMock,
                return_value=raw_sample)

            self.check_filter_support.start()
            self.local_client.start()
            self.raw_property.start()

            drive_disks = disks.DriveGroup
            return drive_disks

            self.check_filter_support.stop()
            self.local_client.stop()
            self.raw_property.stop()

        return make_sample_data

    def test_encryption_prop(self, test_fix):
        test_fix = test_fix()
        assert test_fix('target').encryption is True

    def test_encryption_prop_empty(self, test_fix):
        test_fix = test_fix(empty=True)
        assert test_fix('target').encryption is False

    def test_db_slots_prop(self, test_fix):
        test_fix = test_fix()
        assert test_fix('target').db_slots is 5

    def test_db_slots_prop_empty(self, test_fix):
        test_fix = test_fix(empty=True)
        assert test_fix('target').db_slots is False

    def test_wal_slots_prop(self, test_fix):
        test_fix = test_fix()
        assert test_fix('target').wal_slots is 5

    def test_wal_slots_prop_empty(self, test_fix):
        test_fix = test_fix(empty=True)
        assert test_fix('target').wal_slots is False

    def test_data_devices_prop(self, test_fix):
        test_fix = test_fix()
        assert test_fix('target').data_device_attrs == {
            'model': 'foo',
            'size': '10G:29G',
            'vendor': '1x',
            'limit': 0
        }

    def test_data_devices_prop_empty(self, test_fix):
        test_fix = test_fix(empty=True)
        assert test_fix('target').data_device_attrs == {}

    def test_db_devices_prop(self, test_fix):
        test_fix = test_fix()
        assert test_fix('target').db_device_attrs == {
            'size': ':10G',
        }

    def test_db_devices_prop_empty(self, test_fix):
        test_fix = test_fix(empty=True)
        assert test_fix('target').db_device_attrs == {}

    def test_wal_device_prop(self, test_fix):
        test_fix = test_fix()
        assert test_fix('target').wal_device_attrs == {
            'model': 'fast',
        }

    def test_wal_device_prop_empty(self, test_fix):
        test_fix = test_fix(empty=True)
        assert test_fix('target').wal_device_attrs == {}

    @patch(
        'srv.modules.runners.disks.DriveGroup._filter_devices',
        new_callable=Mock)
    def test_db_devices(self, filter_mock, test_fix):
        test_fix = test_fix()
        test_fix('*').data_devices
        filter_mock.assert_called_once_with({
            'size': '10G:29G',
            'model': 'foo',
            'vendor': '1x'
        })

    @patch(
        'srv.modules.runners.disks.DriveGroup._filter_devices',
        new_callable=Mock)
    def test_wal_devices(self, filter_mock, test_fix):
        test_fix = test_fix()
        test_fix('*').wal_devices
        filter_mock.assert_called_once_with({'model': 'fast'})

    @patch(
        'srv.modules.runners.disks.DriveGroup._filter_devices',
        new_callable=Mock)
    def test_db_devices(self, filter_mock, test_fix):
        test_fix = test_fix()
        test_fix('*').db_devices
        filter_mock.assert_called_once_with({'size': ':10G'})

    @pytest.fixture
    def inventory(self):
        inventory_sample = [
            {
                'available': False,
                'lvs': [],
                'path': '/dev/vda',
                'rejected_reasons': ['locked'],
                'sys_api': {
                    'human_readable_size': '10.00 GB',
                    'locked': 1,
                    'model': 'modelA',
                    'nr_requests': '256',
                    'partitions': {
                        'vda1': {
                            'sectors': '41940992',
                            'sectorsize': 512,
                            'size': '10.00 GB',
                            'start': '2048'
                        }
                    },
                    'path': '/dev/vda',
                    'removable': '0',
                    'rev': '',
                    'ro': '0',
                    'rotational': '1',
                    'sas_address': '',
                    'sas_device_handle': '',
                    'scheduler_mode': 'mq-deadline',
                    'sectors': 0,
                    'sectorsize': '512',
                    'size': 10474836480.0,
                    'support_discard': '',
                    'vendor': 'samsung'
                }
            },
            {
                'available':
                False,
                'lvs': [{
                    'block_uuid':
                    'EbnVK1-chW6-NfEA-0RY4-dWjo-0AeL-b1V9hv',
                    'cluster_fsid':
                    'b9f1174e-fc02-4142-8816-172f20573c13',
                    'cluster_name':
                    'ceph',
                    'name':
                    'osd-block-d8a50e9b-2ea3-43a8-9617-2edccfee0c28',
                    'osd_fsid':
                    'd8a50e9b-2ea3-43a8-9617-2edccfee0c28',
                    'osd_id':
                    '0',
                    'type':
                    'block'
                }],
                'path':
                '/dev/vdb',
                'rejected_reasons': ['locked'],
                'sys_api': {
                    'human_readable_size': '20.00 GB',
                    'locked': 1,
                    'model': 'modelB',
                    'nr_requests': '256',
                    'partitions': {
                        'vdb1': {
                            'sectors': '41940959',
                            'sectorsize': 512,
                            'size': '20.00 GB',
                            'start': '2048'
                        }
                    },
                    'path': '/dev/vdb',
                    'removable': '0',
                    'rev': '',
                    'ro': '0',
                    'rotational': '0',
                    'sas_address': '',
                    'sas_device_handle': '',
                    'scheduler_mode': 'mq-deadline',
                    'sectors': 0,
                    'sectorsize': '512',
                    'size': 21474836480.0,
                    'support_discard': '',
                    'vendor': 'intel'
                }
            },
            {
                'available':
                False,
                'lvs': [{
                    'block_uuid':
                    'ArrVrZ-5wIc-sDbu-gTkW-OFcc-uMy1-WuRbUZ',
                    'cluster_fsid':
                    'b9f1174e-fc02-4142-8816-172f20573c13',
                    'cluster_name':
                    'ceph',
                    'name':
                    'osd-block-ec36354c-110d-4273-8e47-f1fe78195860',
                    'osd_fsid':
                    'ec36354c-110d-4273-8e47-f1fe78195860',
                    'osd_id':
                    '4',
                    'type':
                    'block'
                }],
                'path':
                '/dev/vdc',
                'rejected_reasons': ['locked'],
                'sys_api': {
                    'human_readable_size': '30.00 GB',
                    'locked': 1,
                    'model': 'modelC',
                    'nr_requests': '256',
                    'partitions': {
                        'vdc1': {
                            'sectors': '41940959',
                            'sectorsize': 512,
                            'size': '30.00 GB',
                            'start': '2048'
                        }
                    },
                    'path': '/dev/vdc',
                    'removable': '0',
                    'rev': '',
                    'ro': '0',
                    'rotational': '1',
                    'sas_address': '',
                    'sas_device_handle': '',
                    'scheduler_mode': 'mq-deadline',
                    'sectors': 0,
                    'sectorsize': '512',
                    'size': 32474836480.0,
                    'support_discard': '',
                    'vendor': 'micron'
                }
            }
        ]

        self.raw_property = patch(
            'srv.modules.runners.disks.Inventory.raw',
            new_callable=PropertyMock,
            return_value=[])
        self.local_client = patch('salt.client.LocalClient')
        self.disks_property = patch(
            'srv.modules.runners.disks.Inventory.disks',
            new_callable=PropertyMock,
            return_value=inventory_sample)
        self.raw_property.start()
        self.disks_property.start()
        self.local_client.start()

        inv = disks.Inventory
        return inv

        self.raw_property.stop()
        self.disks_property.stop()
        self.local_client.stop()

    def test_filter_devices_2_size_min_max(self, test_fix, inventory):
        """ Test_fix's data_device_attrs is configured to take any disk from
        10G - 29G.  This means that in this test two out of three disks should
        appear in the output
        (Disks are 10G/20G/30G)
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(test_fix('*').data_device_attrs)
        assert len(ret) == 2

    def test_filter_devices_1_size_exact(self, test_fix, inventory):
        """
        Configure to only take disks with 10G
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(size='10G'))
        assert len(ret) == 1

    def test_filter_devices_3_max(self, test_fix, inventory):
        """
        Configure to only take disks with a max of 30G
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(size=':30G'))
        assert len(ret) == 3

    def test_filter_devices_1_max(self, test_fix, inventory):
        """
        Configure to only take disks with a max of 10G
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(size=':10G'))
        assert len(ret) == 1

    def test_filter_devices_1_min(self, test_fix, inventory):
        """
        Configure to only take disks with a min of 10G
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(size='10G:'))
        assert len(ret) == 3

    def test_filter_devices_2_min(self, test_fix, inventory):
        """
        Configure to only take disks with a min of 20G
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(size='20G:'))
        assert len(ret) == 2

    def test_filter_devices_1_model(self, test_fix, inventory):
        """
        Configure to only take disks with a model of modelA
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(model='modelA'))
        assert len(ret) == 1

    def test_filter_devices_3_model(self, test_fix, inventory):
        """
        Configure to only take disks with a model of model*(wildcard)
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(model='model'))
        assert len(ret) == 3

    def test_filter_devices_1_vendor(self, test_fix, inventory):
        """
        Configure to only take disks with a vendor of samsung
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(vendor='samsung'))
        assert len(ret) == 1

    def test_filter_devices_1_rotational(self, test_fix, inventory):
        """
        Configure to only take disks with a rotational flag of 0
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(rotational='0'))
        assert len(ret) == 1

    def test_filter_devices_2_rotational(self, test_fix, inventory):
        """
        Configure to only take disks with a rotational flag of 1
        """
        test_fix = test_fix()
        ret = test_fix('*')._filter_devices(dict(rotational='1'))
        assert len(ret) == 2

    def test_filter_devices_limit(self, test_fix, inventory):
        """
        Configure to only take disks with a rotational flag of 1
        This should take two disks, but limit=1 is in place
        """
        test_fix = test_fix(limit=1)
        ret = test_fix('*')._filter_devices(dict(rotational='1'))
        assert len(ret) == 1

    @patch('srv.modules.runners.disks.DriveGroup._check_filter')
    def test_check_filter_support(self, check_filter_mock, test_fix):
        test_fix = test_fix()
        test_fix('*')._check_filter_support()
        check_filter_mock.assert_called

    def test_check_filter(self, test_fix):
        test_fix = test_fix()
        ret = test_fix('*')._check_filter(dict(model='foo'))
        assert ret is None

    def test_check_filter_raise(self, test_fix):
        test_fix = test_fix()
        with pytest.raises(
                disks.FilterNotSupported,
                message="Filter unknown is not supported"):
            test_fix('*')._check_filter(dict(unknown='foo'))


class TestDriveGroups(object):
    @patch("salt.client.LocalClient", autospec=True)
    @patch('srv.modules.runners.disks.DriveGroup')
    def test_generate(self, drive_group_mock, mock_client):
        local = mock_client.return_value
        local.cmd.return_value = {'foo': {'internals'}, 'bar': {'internals'}}
        disks.DriveGroups().generate()
        drive_group_mock.assert_called_with('bar')


class TestFilter(object):

    def test_is_matchable(self):
        ret = disks.Filter()
        assert ret.is_matchable is False

    def test_assign_matchers_size(self):
        ret = disks.Filter(name='size', value='10G')
        assert isinstance(ret.matcher, disks.SizeMatcher)
        assert ret.is_matchable is True

    def test_assign_matchers_model(self):
        ret = disks.Filter(name='model', value='abc123')
        assert isinstance(ret.matcher, disks.SubstringMatcher)
        assert ret.is_matchable is True

    def test_assign_matchers_vendor(self):
        ret = disks.Filter(name='vendor', value='samsung')
        assert isinstance(ret.matcher, disks.SubstringMatcher)
        assert ret.is_matchable is True

    def test_assign_matchers_rotational(self):
        ret = disks.Filter(name='rotational', value='0')
        assert isinstance(ret.matcher, disks.EqualityMatcher)
        assert ret.is_matchable is True
