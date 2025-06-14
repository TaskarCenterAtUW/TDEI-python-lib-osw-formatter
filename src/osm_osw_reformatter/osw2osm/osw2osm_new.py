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
            edge_node_hash_gdf = gpd.GeoDataFrame()
            all_points = []
            all_hashes = []
            for index, row in tqdm(edges_gdf.iterrows(), total=edges_gdf.shape[0], desc='Processing Edges'):
                geometry = row['geometry']
                if geometry is None:
                    print(f'Edge {row["_id"]} has no geometry')
                    continue

                coords = list(geometry.coords)
    
                for coord in coords:
                    pt = Point(coord)
                    all_points.append(pt)
                    all_hashes.append(hash(coord))  # hash the tuple, faster and simpler
                # geometry = row['geometry']
                # # points = list(geometry.coords)
                # if geometry is None:
                #     print(f'Edge {row["_id"]} has no geometry')
                #     continue
                # points = [Point(p) for p in geometry.coords]
                # hashes = [hash(str(point)) for point in points]
                # points_gdf = gpd.GeoDataFrame({'geometry': points, 'hash': hashes}, geometry='geometry')
                # edge_node_hash_gdf = pd.concat([edge_node_hash_gdf, points_gdf])
            edge_node_hash_gdf = gpd.GeoDataFrame(
                   {'geometry': all_points, 'hash': all_hashes},
                geometry='geometry'
                )
            # Merge the edge_node_hash_gdf with nodes_gdf to get the node ids
            nodes_nodups_gdf = nodes_gdf.drop_duplicates(subset='hash')
            nodes_hash_gdf = pd.concat([nodes_gdf[['hash', 'geometry']], edge_node_hash_gdf])
            nodes_hash_gdf = nodes_hash_gdf.drop_duplicates(subset='hash')
            nodes_hash_gdf = nodes_hash_gdf.reset_index(drop=True)
            merged_nodes_gdf = nodes_hash_gdf.merge(nodes_nodups_gdf.drop(columns=['geometry']), on='hash', how='left')
            missing_mask = merged_nodes_gdf['_id'].isnull()
            num_missing = missing_mask.sum()
            negative_ids = [-i for i in range(1, num_missing + 1)]
            merged_nodes_gdf.loc[missing_mask, '_id'] = negative_ids
            print(f'Found {missing_mask.sum()} missing node ids')
            # Get a hash for each line
            edges_gdf['hash'] = edges_gdf['geometry'].progress_apply(self.get_line_hashes)
            self.node_hash_dictionary = pd.Series(merged_nodes_gdf['_id'].values, index=merged_nodes_gdf['hash']).to_dict()
            edges_gdf['ndref'] = edges_gdf['hash'].progress_apply(self.map_hashes_to_ids)
            # We dont need self.node_hash_dictionary anymore, so we can delete it
            del self.node_hash_dictionary
            del nodes_gdf
            del nodes_hash_gdf
            del edge_node_hash_gdf
            # print(edges_gdf.head())
            print(f'Writing file in xml')
            # Write to ET file
            self.write_to_et(edges_gdf, merged_nodes_gdf)
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
                    xf.write("\n")
                for _, row in tqdm(edges_gdf.iterrows(), total=edges_gdf.shape[0], desc='Writing Ways'):
                    way_element = self.make_way_element(row)
                    xf.write(way_element)
                    xf.write("\n")

        