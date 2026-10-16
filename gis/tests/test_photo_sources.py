"""Offline rejection tests for bundled surface provenance and GPU channel data."""
import copy
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('photo_sources',ROOT/'unreal/scripts/paris_photo_sources.py')
photos=importlib.util.module_from_spec(spec);spec.loader.exec_module(photos)


class PhotoSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.manifest=copy.deepcopy(photos.load())
        for item in self.manifest['sets']:
            for role,info in item['maps'].items():
                data=('hash fixture '+role).encode();(self.folder/info['file']).write_bytes(data)
                info['sha256']=hashlib.sha256(data).hexdigest()
        env=self.manifest['environment'];data=b'HDR hash fixture'
        (self.folder/env['file']).write_bytes(data);env['sha256']=hashlib.sha256(data).hexdigest()

    def check(self):return photos.validate(self.manifest,self.folder)

    def test_offline_manifest_and_all_bundled_originals(self):
        self.assertEqual([],self.check())
        self.assertEqual([],photos.validate(photos.load()))

    def test_modified_source_and_missing_normal_are_rejected(self):
        item=self.manifest['sets'][0]
        (self.folder/item['maps']['albedo']['file']).write_bytes(b'changed')
        del item['maps']['normal']
        self.assertGreaterEqual(len(self.check()),2)

    def test_arh_and_srgb_normal_cannot_be_misread_as_orm(self):
        self.manifest['sets'][0]['surface_layout']='ARH'
        self.manifest['sets'][1]['maps']['normal']['srgb']=True
        self.assertEqual(2,len(self.check()))

    def test_license_and_path_confinement(self):
        self.manifest['environment']['license']='unknown'
        self.manifest['sets'][0]['maps']['orm']['file']='../outside.png'
        self.assertEqual(2,len(self.check()))

    def test_old_or_duplicate_material_cache_requires_refresh(self):
        self.manifest['sets'].pop()
        self.assertTrue(self.check(),'Old cache cannot silently omit grass')
        self.manifest['sets'].append(copy.deepcopy(self.manifest['sets'][0]))
        self.assertTrue(self.check(),'Duplicate keys cannot stand in for a missing set')

    def test_wrong_asset_identity_or_scale_is_not_a_valid_offline_cache(self):
        self.manifest['sets'][0]['id']='previous-coarse-stone'
        self.manifest['sets'][1]['tile_cm']*=10
        self.assertEqual(2,len(self.check()))
