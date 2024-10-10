import gc
import os
import json
import zipfile
import asyncio
from typing import List
from pathlib import Path
from ...serializer.osm.osm_graph import OSMGraph
from ...serializer.counters import WayCounter, NodeCounter, PointCounter, LineCounter, ZoneCounter, PolygonCounter
from ...serializer.osw.osw_normalizer import OSWWayNormalizer, OSWNodeNormalizer, OSWPointNormalizer, OSWLineNormalizer, \
    OSWZoneNormalizer, OSWPolygonNormalizer


class OSWHelper:
    @staticmethod
    def osw_way_filter(tags):
        normalizer = OSWWayNormalizer(tags)
        return normalizer.filter()

    @staticmethod
    def osw_node_filter(tags):
        normalizer = OSWNodeNormalizer(tags)
        return normalizer.filter()

    @staticmethod
    def osw_point_filter(tags):
        normalizer = OSWPointNormalizer(tags)
        return normalizer.filter()

    @staticmethod
    def osw_line_filter(tags):
        normalizer = OSWLineNormalizer(tags)
        return normalizer.filter()

    @staticmethod
    def osw_zone_filter(tags):
        normalizer = OSWZoneNormalizer(tags)
        return normalizer.filter()

    @staticmethod
    def osw_polygon_filter(tags):
        normalizer = OSWPolygonNormalizer(tags)
        return normalizer.filter()

    @staticmethod
    async def count_ways(osm_file_path: str):
        loop = asyncio.get_event_loop()
        way_counter = WayCounter()
        await loop.run_in_executor(None, way_counter.apply_file, osm_file_path)
        return way_counter.count

    @staticmethod
    async def count_nodes(osm_file_path: str):
        loop = asyncio.get_event_loop()
        node_counter = NodeCounter()
        await loop.run_in_executor(None, node_counter.apply_file, osm_file_path)
        return node_counter.count

    @staticmethod
    async def count_points(osm_file_path: str):
        loop = asyncio.get_event_loop()
        point_counter = PointCounter()
        await loop.run_in_executor(None, point_counter.apply_file, osm_file_path)
        return point_counter.count

    @staticmethod
    async def count_lines(osm_file_path: str):
        loop = asyncio.get_event_loop()
        line_counter = LineCounter()
        await loop.run_in_executor(None, line_counter.apply_file, osm_file_path)
        return line_counter.count

    @staticmethod
    async def count_zones(osm_file_path: str):
        loop = asyncio.get_event_loop()
        zone_counter = ZoneCounter()
        await loop.run_in_executor(None, zone_counter.apply_file, osm_file_path)
        return zone_counter.count

    @staticmethod
    async def count_polygons(osm_file_path: str):
        loop = asyncio.get_event_loop()
        polygon_counter = PolygonCounter()
        await loop.run_in_executor(None, polygon_counter.apply_file, osm_file_path)
        return polygon_counter.count

    @staticmethod
    async def count_entities(osm_file_path: str, counter_class):
        loop = asyncio.get_event_loop()
        counter = counter_class()
        await loop.run_in_executor(None, counter.apply_file, osm_file_path)
        return counter.count

    @staticmethod
    async def get_osm_graph(osm_file_path: str):
        loop = asyncio.get_event_loop()
        OG = await loop.run_in_executor(
            None,
            OSMGraph.from_osm_file,
            osm_file_path,
            OSWHelper.osw_way_filter,
            OSWHelper.osw_node_filter,
            OSWHelper.osw_point_filter,
            OSWHelper.osw_line_filter,
            OSWHelper.osw_zone_filter,
            OSWHelper.osw_polygon_filter
        )

        gc.collect()

        return OG

    @staticmethod
    def unzip(zip_file: str, output: str):
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(output)
            extracted_files = zip_ref.namelist()
            optional_files = ['nodes', 'edges', 'points', 'lines', 'zones', 'polygons']
            file_locations = {}

            for optional_file in optional_files:
                for extracted_file in extracted_files:
                    if '__MACOSX' in extracted_file:
                        continue
                    if optional_file in extracted_file:
                        file_locations[optional_file] = f"{output}/{extracted_file}"

            gc.collect()
            return file_locations

    @staticmethod
    def merge(osm_files: object, output: str, prefix: str):
        fc = {'type': 'FeatureCollection', 'features': []}
        for file, location in osm_files.items():
            geojson_path = Path(location)
            if geojson_path.exists():
                with open(geojson_path) as f:
                    region_fc = json.load(f)
                    fc['features'] = fc['features'] + region_fc['features']
                os.remove(geojson_path)
        output_path = Path(output, f'{prefix}.graph.all.geojson')
        with open(output_path, 'w') as f:
            json.dump(fc, f)

        del f
        gc.collect()

        return str(output_path)

    @classmethod
    async def simplify_og(cls, og):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, og.simplify)

    @classmethod
    async def construct_geometries(cls, og):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, og.construct_geometries)

    @classmethod
    async def write_og(cls, workdir: str, filename: str, og) -> List[str]:
        loop = asyncio.get_event_loop()
        points_path = Path(workdir, f'{filename}.graph.points.geojson')
        nodes_path = Path(workdir, f'{filename}.graph.nodes.geojson')
        edges_path = Path(workdir, f'{filename}.graph.edges.geojson')
        lines_path = Path(workdir, f'{filename}.graph.lines.geojson')
        zones_path = Path(workdir, f'{filename}.graph.zones.geojson')
        polygons_path = Path(workdir, f'{filename}.graph.polygons.geojson')
        await loop.run_in_executor(None, og.to_geojson, nodes_path, edges_path, points_path, lines_path, zones_path,
                                   polygons_path)
        # for the fi
        pot_gen_files = [str(nodes_path), str(edges_path), str(points_path), str(lines_path), str(zones_path),
                         str(polygons_path)]
        generated_files = [file for file in pot_gen_files if os.path.exists(file)]
        del og
        gc.collect()
        return generated_files
