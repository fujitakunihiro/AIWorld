import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('paris_surfaces', Path(__file__).resolve().parents[2]/'unreal/scripts/paris_surfaces.py')
surfaces = importlib.util.module_from_spec(spec)
spec.loader.exec_module(surfaces)


class SurfaceTests(unittest.TestCase):
    def test_tiling_channels_and_physical_relief(self):
        for name, recipe in surfaces.RECIPES.items():
            base, packed = surfaces.pixels(name, 64)
            for image in (base, packed):
                for y in range(64):
                    self.assertEqual(image[y*64*3:y*64*3+3], image[(y*64+63)*3:(y*64+64)*3], name)
                self.assertEqual(image[:64*3], image[-64*3:], name)
            roughness = packed[1::3]
            self.assertGreater(min(roughness)/255, .35)
            self.assertLess(max(roughness)/255, .99)
            self.assertLessEqual(recipe['height_cm'], 1.2)
            self.assertGreater(max(packed[2::3])-min(packed[2::3]), 20)

    def test_regeneration_hashes_and_corrupt_cache_recovery(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first = surfaces.generate(a, 32)
            self.assertEqual(first, surfaces.generate(b, 32))
            target = Path(a)/'Zinc_surface.png'
            target.write_bytes(b'corrupt')
            self.assertEqual(first, surfaces.generate(a, 32))
            self.assertEqual(target.read_bytes(), (Path(b)/target.name).read_bytes())
            self.assertEqual(len(first['files']), 10)
