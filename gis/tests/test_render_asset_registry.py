import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('paris_render_audit', ROOT / 'unreal/scripts/audit_paris_rendering.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class RenderAssetRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'project'
        self.textures = self.root / 'textures'
        shutil.copytree(ROOT / 'unreal/textures/paris', self.textures)
        self.registry = json.loads((ROOT / 'unreal/assets/paris-photoreal-assets.json').read_text(encoding='utf-8'))
        for item in self.registry['existing_sets']:
            packages = [item['material']] + [f"/Game/Textures/T_Paris{item['recipe']}{s.title()}" for s in ('basecolor', 'surface')]
            for package in packages:
                target = audit.asset_file(self.project, package)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'filesystem fixture, not a UE load assertion')

    def validate(self, registry=None):
        return audit.validate_registry(registry or self.registry, self.project, self.textures)[0]

    def test_generated_inventory_and_pending_requirements(self):
        self.assertEqual([], self.validate())

    def test_missing_material_cannot_pass_inventory(self):
        audit.asset_file(self.project, self.registry['existing_sets'][0]['material']).unlink()
        self.assertTrue(self.validate())

    def test_tampered_texture_and_wrong_surface_packing_fail(self):
        (self.textures / 'Limestone_basecolor.png').write_bytes(b'not a PNG')
        self.registry['existing_sets'][0]['surface_layout'] = 'ORM'
        errors = self.validate()
        self.assertTrue(any('hash mismatch' in e for e in errors))
        self.assertTrue(any('packing' in e for e in errors))

    def test_unverified_asset_cannot_be_bound_or_marked_available(self):
        for change in ({'ue_asset': '/Game/Models/ImaginaryCathedral'}, {'status': 'available'}):
            registry = copy.deepcopy(self.registry)
            registry['required_assets'][0].update(change)
            self.assertTrue(self.validate(registry))

    def test_unreal_package_cannot_escape_content_root(self):
        self.assertIsNone(audit.asset_file(self.project, '/Game/../outside'))
        self.assertIsNone(audit.asset_file(self.project, '/Engine/Unreviewed'))


if __name__ == '__main__':
    unittest.main()
