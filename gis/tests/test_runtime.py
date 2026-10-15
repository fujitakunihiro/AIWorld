import copy,struct,unittest,zlib
from paris_twin.runtime import pack,validate_runtime,VERTEX


class RuntimeTests(unittest.TestCase):
    def scene(self):
        mesh=dict(id='test',kind='ground',color='#112233',positions_cm=[[.001,2,3],[100,2,3],[0,100,3]],
            normals=[[0,0,1]]*3,indices=[0,1,2],properties={'source_id':'osm/way/1'})
        footprint={**copy.deepcopy(mesh),'id':'footprint','vertex_colors':['#aabbcc','#abcdef','#123456']}
        return dict(objects=[mesh],footprint_mesh=footprint,georeference={'units':'cm'},pick_features=[{'id':'osm/way/1'}])

    def test_binary_roundtrip_preserves_geometry_color_and_source_identity(self):
        scene=self.scene();a,blob=pack(scene);b,blob2=pack(scene)
        self.assertEqual(a,b);self.assertEqual(blob,blob2);self.assertNotIn('positions_cm',a['objects'][0])
        self.assertEqual(a['pick_features'],scene['pick_features'])
        self.assertLess(validate_runtime(a,blob,scene)['max_position_error_cm'],.00001)
        self.assertEqual(a['objects'][0]['properties'],scene['objects'][0]['properties'])
        self.assertIn('positions_cm',scene['objects'][0])

    def test_corrupt_truncated_overlapping_and_out_of_bounds_packets_fail(self):
        meta,blob=pack(self.scene())
        for bad in [blob[:-1],bytes([0])+blob[1:],blob[:-1]+bytes([blob[-1]^1])]:
            with self.assertRaises(ValueError):validate_runtime(meta,bad)
        for key,value in [('offset',0),('vertex_count',1000001),('byte_length',1),('index_count',4)]:
            m=copy.deepcopy(meta);m['objects'][0]['mesh_buffer'][key]=value
            with self.assertRaises(ValueError):validate_runtime(m,blob)
        m=copy.deepcopy(meta);m['footprint_mesh']['mesh_buffer']['offset']=16
        with self.assertRaises(ValueError):validate_runtime(m,blob)
        bad=bytearray(blob);struct.pack_into('<I',bad,16+3*VERTEX.size,3)
        m=copy.deepcopy(meta);m['geometry_blob']['crc32']=f'{zlib.crc32(bad):08x}'
        with self.assertRaises(ValueError):validate_runtime(m,bad)

    def test_nonfinite_geometry_and_malformed_colours_fail_before_export(self):
        for change in ['position','color','index']:
            scene=self.scene()
            if change=='position':scene['objects'][0]['positions_cm'][0][0]=float('nan')
            elif change=='color':scene['objects'][0]['color']='#123'
            else:scene['objects'][0]['indices'][0]=99
            with self.assertRaises(ValueError):pack(scene)


if __name__=='__main__':unittest.main()
