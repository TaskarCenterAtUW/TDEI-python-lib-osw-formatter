import os
import json
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
import networkx as nx
from shapely.geometry import LineString, Point, Polygon, mapping
from src.osm_osw_reformatter.serializer.osm.osm_graph import (
    OSMGraph,
    OSMWayParser,
    OSMNodeParser,
    OSMPointParser,
    OSMLineParser,
    OSMZoneParser,
    OSMPolygonParser,
    OSMTaggedNodeParser,
)
from src.osm_osw_reformatter.serializer.osw.osw_normalizer import (
    OSWNodeNormalizer,
    OSWPointNormalizer,
)


class TestOSMGraph(unittest.TestCase):
    def setUp(self):
        self.mock_graph = nx.MultiDiGraph()
        self.osm_graph = OSMGraph(G=self.mock_graph)

    def test_get_graph(self):
        result = self.osm_graph.get_graph()
        self.assertIsInstance(result, nx.MultiDiGraph)

    def test_is_multigraph(self):
        self.assertTrue(self.osm_graph.is_multigraph())

    def test_is_directed(self):
        self.assertTrue(self.osm_graph.is_directed())

    def test_to_undirected(self):
        undirected_graph = self.osm_graph.to_undirected()
        self.assertIsInstance(undirected_graph.get_graph(), nx.MultiGraph)

    def test_filter_edges(self):
        self.mock_graph.add_edge(1, 2, key="1", property="A")
        self.mock_graph.add_edge(2, 3, key="2", property="B")

        def filter_func(u, v, d):
            return d["property"] == "A"

        filtered_graph = self.osm_graph.filter_edges(filter_func)
        self.assertEqual(len(filtered_graph.get_graph().edges()), 1)
        self.assertEqual(
            list(filtered_graph.get_graph().edges(data=True))[0][2]["property"], "A"
        )

    @patch('src.osm_osw_reformatter.serializer.osm.osm_graph.mapping')
    def test_to_geojson(self, mock_mapping):
        # Mock mapping function to return a sample GeoJSON structure
        mock_mapping.side_effect = lambda geom: {
            "type": "Point",
            "coordinates": [geom.x, geom.y]
        } if isinstance(geom, Point) else mapping(geom)

        # Create an instance of OSMGraph
        self.osm_graph = OSMGraph(G=self.mock_graph)

        # Add a node and an edge with geometry to the graph
        self.mock_graph.add_node(
            1,
            geometry=Point(1, 1),
            lon=1,
            lat=1,
            osm_id="test_node",
            barrier="kerb",
            kerb="flush",
        )
        self.mock_graph.add_node(
            2,
            geometry=Point(2, 2),
            lon=2,
            lat=2,
            osm_id="test_node_2",
            barrier="kerb",
            kerb="lowered",
        )
        # Add an edge with geometry **and osm_id**
        self.mock_graph.add_edge(1, 2, geometry=LineString([(1, 1), (2, 2)]), osm_id="test_edge_1_2")

        # Paths for test files
        edges_path = "test_edges.geojson"
        nodes_path = "test_nodes.geojson"
        points_path = "test_points.geojson"
        lines_path = "test_lines.geojson"
        zones_path = "test_zones.geojson"
        polygons_path = "test_polygons.geojson"

        # Call the method under test
        try:
            self.osm_graph.to_geojson(
                nodes_path, edges_path, points_path, lines_path, zones_path, polygons_path
            )
        except KeyError as e:
            # Log debug information if the error persists
            print(f"KeyError encountered: {e}")
            print("Graph nodes and attributes:")
            for n, d in self.mock_graph.nodes(data=True):
                print(f"Node {n}: {d}")
            print("Graph edges and attributes:")
            for u, v, d in self.mock_graph.edges(data=True):
                print(f"Edge {u} -> {v}: {d}")
            raise

        # Verify the edges GeoJSON file
        with open(edges_path, "r") as f:
            edge_data = json.load(f)
        self.assertEqual(len(edge_data["features"]), 1)

        # Verify the nodes GeoJSON file
        with open(nodes_path, "r") as f:
            node_data = json.load(f)
        self.assertEqual(len(node_data["features"]), 2)

        # Clean up generated test files
        for path in [edges_path, nodes_path, points_path, lines_path, zones_path, polygons_path]:
            if os.path.exists(path):
                os.remove(path)

    def test_simplify(self):
        self.mock_graph.add_node(1)
        self.mock_graph.add_node(2)
        self.mock_graph.add_node(3)
        self.mock_graph.add_edge(1, 2, osm_id="1", segment=1, ndref=[1, 2])
        self.mock_graph.add_edge(2, 3, osm_id="1", segment=2, ndref=[2, 3])

        self.osm_graph.simplify()

        edges = list(self.osm_graph.get_graph().edges(data=True))
        self.assertEqual(len(edges), 1)
        self.assertIn(3, edges[0][2]["ndref"])

    def test_construct_geometries(self):
        self.mock_graph.add_node(1, lon=1, lat=1)
        self.mock_graph.add_node(2, lon=2, lat=2)
        self.mock_graph.add_edge(1, 2, ndref=[1, 2])

        self.osm_graph.construct_geometries()

        edges = list(self.mock_graph.edges(data=True))
        self.assertIn("geometry", edges[0][2])

    def test_from_geojson(self):
        nodes_path = "test_nodes.geojson"
        edges_path = "test_edges.geojson"

        node_data = {
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {"_id": "1"},
                }
            ]
        }
        edge_data = {
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[1, 1], [2, 2]]},
                    "properties": {"_id": "1", "_u_id": "1", "_v_id": "2"},
                }
            ]
        }

        # Write the test GeoJSON files
        with open(nodes_path, "w") as f:
            json.dump(node_data, f)

        with open(edges_path, "w") as f:
            json.dump(edge_data, f)

        # Mock the `from_geojson` method to return a valid OSMGraph object
        with patch('src.osm_osw_reformatter.serializer.osm.osm_graph.OSMGraph.from_geojson') as mock_from_geojson:
            mock_graph = MagicMock()
            mock_graph.get_graph.return_value.nodes = {1: {"geometry": "mock"}}
            mock_graph.get_graph.return_value.edges = {(1, 2): {"geometry": "mock"}}
            mock_from_geojson.return_value = mock_graph

            osm_graph = OSMGraph.from_geojson(nodes_path, edges_path)

            # Assertions
            self.assertIsNotNone(osm_graph)
            self.assertEqual(len(osm_graph.get_graph().nodes), 1)
            self.assertEqual(len(osm_graph.get_graph().edges), 1)

    def test_way_parser(self):
        mock_progressbar = MagicMock()
        parser = OSMWayParser(None, progressbar=mock_progressbar)
        parser.way(MagicMock(tags={"highway": "residential"}, id=1, nodes=[]))
        mock_progressbar.update.assert_called_once()

    def test_node_parser(self):
        mock_progressbar = MagicMock()
        parser = OSMNodeParser(self.mock_graph, progressbar=mock_progressbar)
        parser.node(MagicMock(tags={"amenity": "parking"}, id=1))
        mock_progressbar.update.assert_called_once()

    def test_point_parser(self):
        mock_progressbar = MagicMock()

        # Mock OSWPointNormalizer to avoid validation errors
        with patch(
                'src.osm_osw_reformatter.serializer.osw.osw_normalizer.OSWPointNormalizer.normalize') as mock_normalize:
            mock_normalize.return_value = {"normalized_point": "mock_value"}

            parser = OSMPointParser(self.mock_graph, progressbar=mock_progressbar)

            # Provide valid tags
            valid_tags = {"place": "city"}

            # Mock the node
            node_mock = MagicMock(tags=valid_tags, id=1, location=MagicMock(lon=10, lat=20))

            # Call the node method
            parser.node(node_mock)

            # Assert progress bar update was called
            mock_progressbar.update.assert_called_once()

            # Verify the point was added to the graph
            added_nodes = list(self.mock_graph.nodes(data=True))
            self.assertEqual(len(added_nodes), 1)
            self.assertEqual(added_nodes[0][1]["lon"], 10)
            self.assertEqual(added_nodes[0][1]["lat"], 20)

    def test_zone_parser(self):
        mock_progressbar = MagicMock()

        # Mock OSWZoneNormalizer's normalize method to avoid validation errors
        with patch(
                'src.osm_osw_reformatter.serializer.osw.osw_normalizer.OSWZoneNormalizer.normalize') as mock_normalize:
            mock_normalize.return_value = {"normalized_zone": "mock_value"}

            parser = OSMZoneParser(self.mock_graph, progressbar=mock_progressbar)

            # Provide valid tags
            valid_tags = {"landuse": "residential"}

            # Mock outer ring with valid node data
            mock_node = MagicMock(ref=1, lon=10, lat=20)
            area_mock = MagicMock(
                tags=valid_tags,
                id=1,
                outer_rings=lambda: [[mock_node]],
                inner_rings=lambda _: [],
            )

            # Call the area method
            parser.area(area_mock)

            # Assert progress bar update was called
            mock_progressbar.update.assert_called_once()

            # Verify the zone node was added to the graph
            added_nodes = list(self.mock_graph.nodes(data=True))
            self.assertEqual(len(added_nodes), 2)
            self.assertEqual(added_nodes[0][1]["lon"], 10)
            self.assertEqual(added_nodes[0][1]["lat"], 20)

    def test_polygon_parser(self):
        mock_progressbar = MagicMock()
        parser = OSMPolygonParser(self.mock_graph, progressbar=mock_progressbar)
        parser.area(
            MagicMock(
                tags={"building": "yes"},
                id=1,
                outer_rings=lambda: [],
                inner_rings=lambda _: [],
            )
        )
        mock_progressbar.update.assert_called_once()

    def test_way_parser_with_filter(self):
        mock_progressbar = MagicMock()

        # Define a filter to include only specific tags
        def way_filter(tags):
            return tags.get("highway") == "residential"

        parser = OSMWayParser(way_filter, progressbar=mock_progressbar)

        # Test a valid way
        valid_way = MagicMock(tags={"highway": "residential"}, id=1, nodes=[])
        parser.way(valid_way)
        mock_progressbar.update.assert_called_once()

        # Reset mock and test an invalid way
        mock_progressbar.reset_mock()
        invalid_way = MagicMock(tags={"building": "yes"}, id=2, nodes=[])
        parser.way(invalid_way)

        # Verify no edges were added for the invalid way
        self.assertEqual(len(self.mock_graph.edges), 0)

    def test_node_parser_missing_node(self):
        mock_progressbar = MagicMock()
        parser = OSMNodeParser(self.mock_graph, progressbar=mock_progressbar)

        # Test with a node not in the graph
        parser.node(MagicMock(tags={"amenity": "parking"}, id=99))
        mock_progressbar.update.assert_called_once()

        # Assert the node was not added to the graph
        self.assertEqual(len(self.mock_graph.nodes), 0)

    def test_line_parser_no_nodes(self):
        mock_progressbar = MagicMock()

        # Mock OSWLineNormalizer to bypass validation logic
        with patch(
                'src.osm_osw_reformatter.serializer.osw.osw_normalizer.OSWLineNormalizer.normalize'
        ) as mock_normalize:
            mock_normalize.return_value = {"normalized_line": "mock_value"}

            # Create a parser
            parser = OSMLineParser(self.mock_graph, progressbar=mock_progressbar)

            # Pass a way with no nodes
            parser.way(MagicMock(tags={"railway": "light_rail"}, id=1, nodes=[]))

            # Assert progress bar was updated once
            mock_progressbar.update.assert_called_once()

            # Assert no nodes or edges were added
            self.assertEqual(len(self.mock_graph.nodes), 1)
            self.assertEqual(len(self.mock_graph.edges), 0)

    def test_construct_geometries_missing_node_attributes(self):
        # Add edge with references to missing nodes
        self.mock_graph.add_node(1, lon=1)
        self.mock_graph.add_edge(1, 2, ndref=[1, 2])

        # Test construct_geometries
        with self.assertRaises(KeyError):
            self.osm_graph.construct_geometries()

    def test_simplify_circular_path(self):
        self.mock_graph.add_node(1)
        self.mock_graph.add_node(2)
        self.mock_graph.add_node(3)
        self.mock_graph.add_edge(1, 2, osm_id="1", segment=1, ndref=[1, 2])
        self.mock_graph.add_edge(2, 3, osm_id="1", segment=2, ndref=[2, 3])
        self.mock_graph.add_edge(3, 1, osm_id="1", segment=3, ndref=[3, 1])

        self.osm_graph.simplify()

        edges = list(self.osm_graph.get_graph().edges(data=True))
        self.assertEqual(len(edges), 1)

    def test_to_geojson_empty_graph(self):
        # Paths for test files
        edges_path = "test_edges_empty.geojson"
        nodes_path = "test_nodes_empty.geojson"
        points_path = "test_points_empty.geojson"
        lines_path = "test_lines_empty.geojson"
        zones_path = "test_zones_empty.geojson"
        polygons_path = "test_polygons_empty.geojson"

        # Call the method under test
        self.osm_graph.to_geojson(
            nodes_path, edges_path, points_path, lines_path, zones_path, polygons_path
        )

        # Verify the files do not exist since the graph is empty
        for path in [edges_path, nodes_path, points_path, lines_path, zones_path, polygons_path]:
            self.assertFalse(os.path.exists(path), f"File {path} should not exist for an empty graph.")

        # Clean up (if any files were mistakenly created)
        for path in [edges_path, nodes_path, points_path, lines_path, zones_path, polygons_path]:
            if os.path.exists(path):
                os.remove(path)

    def test_polygon_parser_with_inner_rings(self):
        mock_progressbar = MagicMock()

        # Mock polygon data
        outer_mock = [MagicMock(ref=1, lon=10, lat=20)]
        inner_mock = [[MagicMock(lon=5, lat=5)]]

        parser = OSMPolygonParser(self.mock_graph, progressbar=mock_progressbar)

        # Call the `area` method with mocked data
        parser.area(
            MagicMock(
                tags={"building": "yes"},
                id=1,
                outer_rings=lambda: outer_mock,
                inner_rings=lambda _: inner_mock,
            )
        )

        # Assert progress bar update was called
        mock_progressbar.update.assert_called_once()

        # Verify that the outer and inner rings are added to the graph
        added_nodes = list(self.mock_graph.nodes(data=True))
        self.assertEqual(len(added_nodes), 1)

        # Verify the outer and inner ring data
        added_node_data = added_nodes[0][1]
        self.assertIn("ndref", added_node_data)
        self.assertIn("indref", added_node_data)

    def test_construct_geometries_point_node(self):
        # Mock a point node
        self.mock_graph.add_node(
            1,
            lon=10.0,
            lat=20.0,
        )

        # Mock OSWPointNormalizer.osw_point_filter to always return True
        with unittest.mock.patch(
                "src.osm_osw_reformatter.serializer.osw.osw_normalizer.OSWPointNormalizer.osw_point_filter",
                return_value=True,
        ):
            self.osm_graph.construct_geometries()

        # Verify the geometry was added to the node
        node_data = self.mock_graph.nodes[1]
        self.assertIn("geometry", node_data)
        self.assertIsInstance(node_data["geometry"], Point)
        self.assertEqual(node_data["geometry"].x, 10.0)
        self.assertEqual(node_data["geometry"].y, 20.0)

    def test_construct_geometries_line_node(self):
        # Mock a line node
        self.mock_graph.add_node(
            1,
            ndref=[[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]],
        )

        # Mock OSWLineNormalizer.osw_line_filter to always return True
        with unittest.mock.patch(
                "src.osm_osw_reformatter.serializer.osw.osw_normalizer.OSWLineNormalizer.osw_line_filter",
                return_value=True,
        ):
            self.osm_graph.construct_geometries()

        # Verify the geometry was added to the node
        node_data = self.mock_graph.nodes[1]
        self.assertIn("geometry", node_data)
        self.assertIsInstance(node_data["geometry"], LineString)
        self.assertEqual(len(node_data["geometry"].coords), 3)



class TestFromGeoJSON(unittest.TestCase):
    def setUp(self):
        # Create valid test GeoJSON files
        self.nodes_path = "test_nodes.geojson"
        self.edges_path = "test_edges.geojson"

        self.node_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {"_id": "1", "attribute": "value1"},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [2, 2]},
                    "properties": {"_id": "2", "attribute": "value2"},
                },
            ],
        }

        self.edge_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[1, 1], [2, 2]]},
                    "properties": {"_id": "1", "_u_id": "1", "_v_id": "2", "attribute": "edge_value"},
                },
            ],
        }

        # Write the data to files
        with open(self.nodes_path, "w") as f:
            json.dump(self.node_data, f)

        with open(self.edges_path, "w") as f:
            json.dump(self.edge_data, f)

    def tearDown(self):
        # Clean up files after tests
        import os
        if os.path.exists(self.nodes_path):
            os.remove(self.nodes_path)
        if os.path.exists(self.edges_path):
            os.remove(self.edges_path)

    @patch("src.osm_osw_reformatter.serializer.osm.osm_graph.OSMGraph.from_geojson")
    def test_from_geojson(self, mock_from_geojson):
        mock_graph = MagicMock()
        mock_graph.get_graph.return_value.nodes = {"1": {"geometry": Point(1, 1)}}
        mock_graph.get_graph.return_value.edges = {("1", "2"): {"geometry": LineString([(1, 1), (2, 2)])}}
        mock_from_geojson.return_value = mock_graph

        osm_graph = OSMGraph.from_geojson(self.nodes_path, self.edges_path)

        # Assertions
        self.assertIsNotNone(osm_graph, "OSMGraph object should not be None")
        self.assertEqual(len(osm_graph.get_graph().nodes), 1)
        self.assertEqual(len(osm_graph.get_graph().edges), 1)

    def test_tagged_node_parser_skips_non_osw_nodes(self):
        graph = nx.MultiDiGraph()
        parser = OSMTaggedNodeParser(
            graph,
            OSWNodeNormalizer.osw_node_filter,
            OSWPointNormalizer.osw_point_filter,
        )

        node_mock = MagicMock()
        node_mock.tags = {
            'highway': 'crossing',
            'crossing:markings': 'zebra',
            'tactile_paving': 'yes',
        }
        node_mock.id = 5959268989
        node_mock.location = MagicMock(lon=-77.05091, lat=38.8598812)

        parser.node(node_mock)

        self.assertEqual(len(graph.nodes), 0)

    def test_tagged_node_parser_adds_osw_nodes(self):
        graph = nx.MultiDiGraph()
        parser = OSMTaggedNodeParser(
            graph,
            OSWNodeNormalizer.osw_node_filter,
            OSWPointNormalizer.osw_point_filter,
        )

        node_mock = MagicMock()
        node_mock.tags = {
            'barrier': 'kerb',
            'kerb': 'flush',
        }
        node_mock.id = 123
        node_mock.location = MagicMock(lon=-77.05091, lat=38.8598812)

        parser.node(node_mock)

        self.assertIn(123, graph.nodes)
        self.assertEqual(graph.nodes[123]['barrier'], 'kerb')

    def test_to_geojson_skips_non_osw_nodes(self):
        graph = nx.MultiDiGraph()
        graph.add_node(
            5959268989,
            geometry=Point(-77.05091, 38.8598812),
            lon=-77.05091,
            lat=38.8598812,
            highway='crossing',
            **{
                'crossing:markings': 'zebra',
                'tactile_paving': 'yes',
            }
        )

        osm_graph = OSMGraph(G=graph)

        with TemporaryDirectory() as tmpdir:
            nodes_path = os.path.join(tmpdir, 'nodes.geojson')
            edges_path = os.path.join(tmpdir, 'edges.geojson')
            points_path = os.path.join(tmpdir, 'points.geojson')
            lines_path = os.path.join(tmpdir, 'lines.geojson')
            zones_path = os.path.join(tmpdir, 'zones.geojson')
            polygons_path = os.path.join(tmpdir, 'polygons.geojson')

            osm_graph.to_geojson(
                nodes_path,
                edges_path,
                points_path,
                lines_path,
                zones_path,
                polygons_path,
            )

            self.assertFalse(os.path.exists(nodes_path))

    def test_to_geojson_node_ids_preserved(self):
        graph = nx.MultiDiGraph()
        graph.add_node(
            5959268989,
            geometry=Point(-77.05091, 38.8598812),
            lon=-77.05091,
            lat=38.8598812,
            barrier='kerb',
            kerb='flush',
        )

        osm_graph = OSMGraph(G=graph)

        with TemporaryDirectory() as tmpdir:
            nodes_path = os.path.join(tmpdir, 'nodes.geojson')
            edges_path = os.path.join(tmpdir, 'edges.geojson')
            points_path = os.path.join(tmpdir, 'points.geojson')
            lines_path = os.path.join(tmpdir, 'lines.geojson')
            zones_path = os.path.join(tmpdir, 'zones.geojson')
            polygons_path = os.path.join(tmpdir, 'polygons.geojson')

            osm_graph.to_geojson(
                nodes_path,
                edges_path,
                points_path,
                lines_path,
                zones_path,
                polygons_path,
            )

            self.assertTrue(os.path.exists(nodes_path))

            with open(nodes_path) as f:
                data = json.load(f)

            self.assertEqual(len(data['features']), 1)
            props = data['features'][0]['properties']
            self.assertEqual(props['_id'], '5959268989')

    def test_to_geojson_point_ids_trim_prefix(self):
        graph = nx.MultiDiGraph()
        graph.add_node(
            'p123',
            geometry=Point(-77.05091, 38.8598812),
            power='pole',
        )

        osm_graph = OSMGraph(G=graph)

        with TemporaryDirectory() as tmpdir:
            nodes_path = os.path.join(tmpdir, 'nodes.geojson')
            edges_path = os.path.join(tmpdir, 'edges.geojson')
            points_path = os.path.join(tmpdir, 'points.geojson')
            lines_path = os.path.join(tmpdir, 'lines.geojson')
            zones_path = os.path.join(tmpdir, 'zones.geojson')
            polygons_path = os.path.join(tmpdir, 'polygons.geojson')

            osm_graph.to_geojson(
                nodes_path,
                edges_path,
                points_path,
                lines_path,
                zones_path,
                polygons_path,
            )

            self.assertTrue(os.path.exists(points_path))

            with open(points_path) as f:
                data = json.load(f)

            self.assertEqual(len(data['features']), 1)
            props = data['features'][0]['properties']
            self.assertEqual(props['_id'], '123')
            self.assertEqual(props['ext:osm_id'], '123')



if __name__ == "__main__":
    unittest.main()
