from pathlib import Path
from ..helpers.response import Response
from ..helpers.osw import OSWHelper
import geopandas as gpd
from tqdm import tqdm
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
import xml.etree.cElementTree as ElementTree
import numpy as np
from lxml.etree import xmlfile, Element

class OSW2OSMNew:
    def __init__(self, zip_file_path: str, workdir: str, prefix: str):
        tqdm.pandas(desc='Geo Pandas')
        self.zip_path = str(Path(zip_file_path))
        self.workdir = workdir
        self.prefix = prefix
        self.node_hash_dictionary = {}
    
    def get_line_hashes(self, line_geometry):
        points = [Point(p) for p in line_geometry.coords]
        hashes = [hash(str(point)) for point in points]
        return hashes

    def map_hashes_to_ids(self,hash_list):
        return [self.node_hash_dictionary.get(h) for h in hash_list if h in self.node_hash_dictionary]
    
    def make_node_element(self,row):
        node = Element("node", id=str(int(row['_id'])), lat=str(row['geometry'].y), lon=str(row['geometry'].x))
        for key, value in row.items():
            if key in ['geometry', '_id','hash'] or value is None  or value is np.nan:
                continue
            tag = Element("tag", k=key, v=str(value))
            node.append(tag)
        return node
    
    def make_way_element(self,row):
        way = Element("way", id=str(int(row['_id'])))
        for node_ref in row['ndref']:
            nd = Element("nd", ref=str(int(node_ref)))
            way.append(nd)
        for key, value in row.items():
            if key in ['geometry', '_id', 'ndref','hash'] or value is None or value is np.nan:
                continue
            tag = Element("tag", k=key, v=str(value))
            way.append(tag)
        return way

    def convert(self) -> Response:
        try:
            unzipped_files = OSWHelper.unzip(self.zip_path, self.workdir)
            print(f'Unzipped files: {unzipped_files}')
            nodes_file = unzipped_files.get('nodes')
            edges_file = unzipped_files.get('edges')
            nodes_gdf = gpd.read_file(nodes_file)
            # Get a hash for each point
            nodes_gdf['hash'] = nodes_gdf['geometry'].progress_apply(lambda x: hash(str(x)))
            edges_gdf = gpd.read_file(edges_file)
            # Get a hash for each line
            edges_gdf['hash'] = edges_gdf['geometry'].progress_apply(self.get_line_hashes)
            self.node_hash_dictionary = pd.Series(nodes_gdf['_id'].values, index=nodes_gdf['hash']).to_dict()
            edges_gdf['ndref'] = edges_gdf['hash'].progress_apply(self.map_hashes_to_ids)
            # print(edges_gdf.head())
            print(f'Writing file in xml')
            # Write to ET file
            self.write_to_et(edges_gdf, nodes_gdf)
            resp = Response(status=True, generated_files=str(''))
            return resp
        except Exception as error:
            print(f'Something went wrong: {error}')
            return Response(status=False, error=str(error))
        
    def write_to_et(self,edges_gdf,nodes_gdf):
        output_file = Path(self.workdir, f'{self.prefix}-new.graph.osm.xml')
        with xmlfile(output_file, encoding="utf-8") as xf:
            xf.write_declaration()
            #<osm version="0.6" generator="ogr2osm 1.2.0" upload="false">
            with xf.element("osm", version="0.6", generator="GeoPandas2OSM", upload="false"):
                for _, row in tqdm(nodes_gdf.iterrows(), total=nodes_gdf.shape[0], desc='Writing Nodes'):
                    node_element = self.make_node_element(row)
                    xf.write(node_element)
                for _, row in tqdm(edges_gdf.iterrows(), total=edges_gdf.shape[0], desc='Writing Ways'):
                    way_element = self.make_way_element(row)
                    xf.write(way_element)

        