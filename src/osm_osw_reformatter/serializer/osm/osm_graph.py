from typing import List, Optional
import json
import pyproj
import osmium
import networkx as nx
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from ..osw.osw_normalizer import OSW_SCHEMA_ID, OSWPointNormalizer, OSWWayNormalizer, OSWNodeNormalizer, OSWLineNormalizer, OSWZoneNormalizer, OSWPolygonNormalizer


class OSMWayParser(osmium.SimpleHandler):
    def __init__(self, way_filter: Optional[callable], progressbar: Optional[callable] = None) -> None:
        osmium.SimpleHandler.__init__(self)
        self.G = nx.MultiDiGraph()
        if way_filter is None:
            self.way_filter = lambda w: True
        else:
            self.way_filter = way_filter
        self.progressbar = progressbar

    def way(self, w) -> None:
        if self.progressbar:
            self.progressbar.update(1)

        if not self.way_filter(w.tags):
            return

        d = {'osm_id': int(w.id)}

        tags = dict(w.tags)
        tags['osm_id'] = str(int(w.id))

        if "area" in tags and tags["area"] == "yes":
            return

        d2 = {**d, **OSWWayNormalizer(tags).normalize()}

        for i in range(len(w.nodes) - 1):
            u = w.nodes[i]
            v = w.nodes[i + 1]

            if not u.location.valid() or not v.location.valid():
                continue
            # NOTE: why are the coordinates floats? Wouldn't fix
            # precision be better?
            u_ref = int(u.ref)
            u_lon = float(u.lon)
            u_lat = float(u.lat)
            v_ref = int(v.ref)
            v_lon = float(v.lon)
            v_lat = float(v.lat)

            d3 = {**d2}
            d3['segment'] = i
            d3['ndref'] = [u_ref, v_ref]
            self.G.add_edges_from([(u_ref, v_ref, d3)])
            self.G.add_node(u_ref, lon=u_lon, lat=u_lat)
            self.G.add_node(v_ref, lon=v_lon, lat=v_lat)
            del u
            del v

        del w


class OSMNodeParser(osmium.SimpleHandler):
    def __init__(self, G: nx.MultiDiGraph, node_filter: Optional[callable] = None,
                 progressbar: Optional[callable] = None) -> None:
        """

        :param G: MultiDiGraph that already has ways inserted as edges.
        :type G: nx.MultiDiGraph

        """
        osmium.SimpleHandler.__init__(self)
        self.G = G
        if node_filter is None:
            self.node_filter = lambda w: True
        else:
            self.node_filter = node_filter
        self.progressbar = progressbar

    def node(self, n) -> None:
        if self.progressbar:
            self.progressbar.update(1)

        if not self.node_filter(n.tags):
            return

        if n.id not in self.G.nodes:
            return

        d = {}

        tags = dict(n.tags)

        d2 = {**d, **OSWNodeNormalizer(tags).normalize()}

        self.G.add_node(n.id, **d2)


class OSMPointParser(osmium.SimpleHandler):
    def __init__(self, G: nx.MultiDiGraph, point_filter: Optional[callable] = None,
                 progressbar: Optional[callable] = None) -> None:
        """

        :param G: MultiDiGraph that already has ways inserted as edges.
        :type G: nx.MultiDiGraph

        """
        osmium.SimpleHandler.__init__(self)
        self.G = G
        if point_filter is None:
            self.point_filter = lambda w: True
        else:
            self.point_filter = point_filter
        self.progressbar = progressbar

    def node(self, n) -> None:
        if self.progressbar:
            self.progressbar.update(1)

        if not self.point_filter(n.tags):
            return

        d = {}

        tags = dict(n.tags)

        d2 = {**d, **OSWPointNormalizer(tags).normalize()}

        self.G.add_node("p" + str(n.id), lon=n.location.lon, lat=n.location.lat, **d2)


class OSMLineParser(osmium.SimpleHandler):
    def __init__(self, G, line_filter=None, progressbar=None):
        """

        :param G: MultiDiGraph that already has ways inserted as edges.
        :type G: nx.MultiDiGraph

        """
        osmium.SimpleHandler.__init__(self)
        self.G = G
        if line_filter is None:
            self.line_filter = lambda w: True
        else:
            self.line_filter = line_filter
        self.progressbar = progressbar

    def way(self, w):
        if self.progressbar:
            self.progressbar.update(1)

        if not self.line_filter(w.tags):
            return

        d = {}
        tags = dict(w.tags)

        d2 = {**d, **OSWLineNormalizer(tags).normalize()}

        ndref = []
        for i in range(len(w.nodes)):
            u = w.nodes[i]

            if not u.location.valid():
                continue

            u_lon = float(u.lon)
            u_lat = float(u.lat)

            ndref.append([u_lon, u_lat])
            del u
        
        d3 = {**d2}
        d3["ndref"] = ndref
        self.G.add_node("l" + str(w.id), **d3)

        del w


class OSMZoneParser(osmium.SimpleHandler):
    def __init__(self, G, zone_filter=None, progressbar=None):
        """

        :param G: MultiDiGraph that already has ways inserted as edges.
        :type G: nx.MultiDiGraph

        """
        osmium.SimpleHandler.__init__(self)
        self.G = G
        if zone_filter is None:
            self.zone_filter = lambda w: True
        else:
            self.zone_filter = zone_filter
        self.progressbar = progressbar

    def area(self, a):
        if self.progressbar:
            self.progressbar.update(1)

        if not self.zone_filter(a.tags):
            return
        
        d = {}
        tags = dict(a.tags)

        d2 = {**d, **OSWZoneNormalizer(tags).normalize()}

        exteriors_count = 0
        for exterior in a.outer_rings():
            ndref = []
            for i in range(len(exterior)):
                u = exterior[i]

                u_ref = int(u.ref)
                u_lon = float(u.lon)
                u_lat = float(u.lat)

                ndref.append(str(u_ref))
                self.G.add_node(u_ref, lon=u_lon, lat=u_lat)
                del u
            
            d3 = {**d2}
            d3["ndref"] = ndref

            # Add interior holes without nodes
            indref = []
            for inner in a.inner_rings(exterior):
                ndref = []
                for i in range(len(inner)):
                    u = inner[i]

                    u_lon = float(u.lon)
                    u_lat = float(u.lat)

                    ndref.append([u_lon, u_lat])
                indref.append(ndref)
            
            d3["indref"] = indref
            if exteriors_count > 0:
                self.G.add_node("z" + str(a.id) + str(exteriors_count), **d3)
            else:
                self.G.add_node("z" + str(a.id), **d3)
            exteriors_count = exteriors_count + 1


class OSMPolygonParser(osmium.SimpleHandler):
    def __init__(self, G, polygon_filter=None, progressbar=None):
        """

        :param G: MultiDiGraph that already has ways inserted as edges.
        :type G: nx.MultiDiGraph

        """
        osmium.SimpleHandler.__init__(self)
        self.G = G
        if polygon_filter is None:
            self.polygon_filter = lambda w: True
        else:
            self.polygon_filter = polygon_filter
        self.progressbar = progressbar

    def area(self, a):
        if self.progressbar:
            self.progressbar.update(1)

        if not self.polygon_filter(a.tags):
            return

        d = {}
        tags = dict(a.tags)

        d2 = {**d, **OSWPolygonNormalizer(tags).normalize()}

        exteriors_count = 0
        for exterior in a.outer_rings():
            ndref = []
            for i in range(len(exterior)):
                u = exterior[i]

                u_lon = float(u.lon)
                u_lat = float(u.lat)

                ndref.append([u_lon, u_lat])
                del u
            
            d3 = {**d2}
            d3["ndref"] = ndref

            # Add interior holes without nodes
            indref = []
            for inner in a.inner_rings(exterior):
                ndref = []
                for i in range(len(inner)):
                    u = inner[i]

                    u_lon = float(u.lon)
                    u_lat = float(u.lat)

                    ndref.append([u_lon, u_lat])
                indref.append(ndref)
            
            d3["indref"] = indref
            if exteriors_count > 0:
                self.G.add_node("g" + str(a.id) + str(exteriors_count), **d3)
            else:
                self.G.add_node("g" + str(a.id), **d3)
            exteriors_count = exteriors_count + 1

class OSMTaggedNodeParser(osmium.SimpleHandler):
    def __init__(self, G: nx.MultiDiGraph):
        osmium.SimpleHandler.__init__(self)
        self.G = G

    def node(self, n):
        # Only add nodes with tags
        if n.tags and len(n.tags) > 0:
            d = dict(n.tags)
            # Store OSM node id as string (to match the pattern in your output)
            self.G.add_node(n.id, lon=n.location.lon, lat=n.location.lat, **d)

class OSMGraph:
    def __init__(self, G: nx.MultiDiGraph = None) -> None:
        if G is not None:
            self.G = G

        # Geodesic distance calculator. Assumes WGS84-like geometries.
        self.geod = pyproj.Geod(ellps='WGS84')

    def node(self, n):
        if len(n.tags) > 0 and n.id not in self.G.nodes:
            d = dict(n.tags)
            self.G.add_node(n.id, lon=n.location.lon, lat=n.location.lat, **d)

    @classmethod
    def from_osm_file(
      self, osm_file, way_filter: Optional[callable] = None, node_filter: Optional[callable] = None,
      point_filter: Optional[callable] = None, line_filter: Optional[callable] = None, zone_filter: Optional[callable] = None, 
      polygon_filter: Optional[callable] = None, progressbar: Optional[callable] = None
    ):
        way_parser = OSMWayParser(way_filter, progressbar=progressbar)
        way_parser.apply_file(osm_file, locations=True)
        G = way_parser.G
        del way_parser

        node_parser = OSMNodeParser(G, node_filter, progressbar=progressbar)
        node_parser.apply_file(osm_file)
        G = node_parser.G
        del node_parser

        point_parser = OSMPointParser(G, point_filter, progressbar=progressbar)
        point_parser.apply_file(osm_file)
        G = point_parser.G
        del point_parser

        line_parser = OSMLineParser(G, line_filter, progressbar=progressbar)
        line_parser.apply_file(osm_file, locations=True)
        G = line_parser.G
        del line_parser

        # --- PATCH START: Add all loose/tagged nodes ---
        tagged_node_parser = OSMTaggedNodeParser(G)
        tagged_node_parser.apply_file(osm_file)
        G = tagged_node_parser.G
        del tagged_node_parser
        # --- PATCH END ---

        # zone_parser = OSMZoneParser(G, zone_filter, progressbar=progressbar)
        # zone_parser.apply_file(osm_file)
        # G = zone_parser.G
        # del zone_parser

        # polygon_parser = OSMPolygonParser(G, polygon_filter, progressbar=progressbar)
        # polygon_parser.apply_file(osm_file)
        # G = polygon_parser.G
        # del polygon_parser

        return OSMGraph(G)

    def simplify(self) -> None:
        '''Simplifies graph by merging way segments of degree 2 - i.e.
        continuations.

        '''
        # Do not simplify edges that share a node with a zone
        zone_nodes = set()
        for node, d in self.G.nodes(data=True):
            if OSWZoneNormalizer.osw_zone_filter(d):
                zone_nodes.update(d["ndref"])

        # Structure is way_id: (node, segment_number). This makes it easy to
        # sort on-the-fly.
        remove_nodes = {}

        for node, d in self.G.nodes(data=True):
            if OSWNodeNormalizer.osw_node_filter(d):
                # Skip if this is a node feature of interest, e.g. kerb ramp
                continue

            if str(node) in zone_nodes:
                # Do not simplify edges that share a node with a zone
                continue

            predecessors = list(self.G.predecessors(node))
            successors = list(self.G.successors(node))

            if (len(predecessors) == 1) and (len(successors) == 1):
                # Only one predecessor and one successor - ideal internal node
                # to remove from the graph, merging its location data into other
                # edges.
                node_in = predecessors[0]
                node_out = successors[0]
                edge_in = self.G[node_in][node][0]
                edge_out = self.G[node][node_out][0]

                # Only one exception: we shouldn't remove a node that's shared
                # between two different ways: this is an important decision
                # point for some paths.
                if edge_in['osm_id'] != edge_out['osm_id']:
                    continue

                node_data = (node_in, node, node_out, edge_in['segment'])

                # Group by way
                edge_id = edge_in['osm_id']
                if edge_id in remove_nodes:
                    remove_nodes[edge_id].append(node_data)
                else:
                    remove_nodes[edge_id] = [node_data]

        # NOTE: an otherwise unconnected circular path would be removed, as all
        # nodes are degree 2 and on the same way. This path is pointless for a
        # network, but is something to keep in mind for any downstream
        # analysis.
        for way_id, node_data in remove_nodes.items():
            # Sort by segment number
            sorted_node_data = list(sorted(node_data, key=lambda x: x[3]))

            # First node matches last node_out?
            is_circular = sorted_node_data[0][1] == sorted_node_data[-1][2]

            # Split into lists of neighboring nodes
            neighbors_list = []

            neighbors = [sorted_node_data.pop(0)]
            for node_in, node, node_out, segment_n in sorted_node_data:
                if (segment_n - neighbors[-1][3]) != 1:
                    # Not neighbors!
                    neighbors_list.append(neighbors)
                    neighbors = [(node_in, node, node_out, segment_n)]
                else:
                    # Neighbors!
                    neighbors.append((node_in, node, node_out, segment_n))
            neighbors_list.append(neighbors)

            # Detect neighbors in circular ways which are not completely disjoint from other ways
            if is_circular and len(neighbors_list) > 1:
                # Combine first and last neighbor lists
                neighbors_list[-1].extend(neighbors_list.pop(0))
            
            # Remove internal nodes by group
            for neighbors in neighbors_list:
                u, v, w, segment_n = neighbors[0]
                # FIXME: this try/except is a hack to avert an uncommon and
                # unexplored edge case. Come back and fix!
                try:
                    edge_data = self.G[u][v][0]
                except KeyError:
                    continue
                ndref = edge_data['ndref']
                self.G.remove_edge(u, v)
                for node_in, node, node_out, segment_n in neighbors:
                    ndref.append(node_out)
                    # Remove intervening edge
                    try:
                        self.G.remove_edge(node, node_out)
                    except nx.exception.NetworkXError:
                        pass
                self.G.add_edges_from([(u, node_out, edge_data)])

    def construct_geometries(self, progressbar: Optional[callable] = None) -> None:
        '''Given the current list of node references per edge, construct
        geometry.

        '''
        internal_nodes = []
        for u, v, d in self.G.edges(data=True):
            coords = []
            for ref in d['ndref']:
                # FIXME: is this the best way to retrieve node attributes?
                node_d = self.G._node[ref]
                coords.append((node_d['lon'], node_d['lat']))

            geometry = LineString(coords)
            d['geometry'] = geometry
            d['length'] = round(self.geod.geometry_length(geometry), 1)
            internal_nodes = internal_nodes + d["ndref"][1:len(d["ndref"])-1]
            del d['ndref']
            if progressbar:
                progressbar.update(1)

        for n, d in self.G.nodes(data=True):
            if OSWZoneNormalizer.osw_zone_filter(d):
                coords = []
                for ref in d["ndref"]:
                    node_d = self.G._node[int(ref)]
                    coords.append((node_d["lon"], node_d["lat"]))

                geometry = Polygon(coords, d["indref"])
                d["geometry"] = geometry

                d["_w_id"] = d.pop("ndref")
                del d["indref"]

                if progressbar:
                    progressbar.update(1)
            elif OSWPolygonNormalizer.osw_polygon_filter(d):
                geometry = Polygon(d["ndref"], d["indref"])
                d["geometry"] = geometry

                del d["ndref"]
                del d["indref"]

                if progressbar:
                    progressbar.update(1)
            elif OSWLineNormalizer.osw_line_filter(d):
                geometry = LineString(d["ndref"])
                d["geometry"] = geometry
                d["length"] = round(self.geod.geometry_length(geometry), 1)
                del d["ndref"]
                if progressbar:
                    progressbar.update(1)
            else:
                geometry = Point(d["lon"], d["lat"])
                d["geometry"] = geometry
                if progressbar:
                    progressbar.update(1)
                
        self.G.remove_nodes_from(internal_nodes)

    def to_undirected(self):
        if self.G.is_multigraph():
            G = nx.MultiGraph(self.G)
        else:
            G = nx.Graph(self.G)
        return OSMGraph(G)

    def get_graph(self) -> nx.MultiDiGraph:
        return self.G

    def filter_edges(self, func: callable):
        # TODO: put this in a 'copy-like' function
        if self.G.is_multigraph():
            if self.G.is_directed():
                G = nx.MultiDiGraph()
            else:
                G = nx.MultiGraph()
        else:
            if self.G.is_directed():
                G = nx.DiGraph()
            else:
                G = nx.Graph()

        for u, v, d in self.G.edges(data=True):
            if func(u, v, d):
                G.add_edge(u, v, **d)

        # Copy in node data
        for node in G.nodes:
            d = self.G._node[node]
            G.add_node(node, **d)

        return OSMGraph(G)

    def is_multigraph(self) -> bool:
        return self.G.is_multigraph()

    def is_directed(self) -> bool:
        return self.G.is_directed()

    def to_geojson(self, *args) -> None:
        OSW_JSON_HEADER = {"$schema": OSW_SCHEMA_ID, "type": "FeatureCollection"}
        nodes_path = args[0]
        edges_path = args[1]
        points_path = args[2]
        lines_path = args[3]
        zones_path = args[4]
        polygons_path = args[5]

        _id = 1
        edge_features = []
        for u, v, d in self.G.edges(data=True):
            d_copy = {**d}
            d_copy['_id'] = str(_id)
            _id += 1
            d_copy['_u_id'] = str(u)
            d_copy['_v_id'] = str(v)

            d_copy['ext:osm_id'] = str(d['osm_id'])

            if 'osm_id' in d_copy:
                d_copy.pop('osm_id')

            if 'segment' in d_copy:
                d_copy.pop('segment')

            geometry = mapping(d_copy.pop('geometry'))

            edge_features.append(
                {'type': 'Feature', 'geometry': geometry, 'properties': d_copy}
            )
        edges_fc = {**OSW_JSON_HEADER, **{"features": edge_features}}

        node_features = []
        point_features = []
        line_features = []
        zone_features = []
        polygon_features = []
        for n, d in self.G.nodes(data=True):
            d_copy = {**d}
            d_copy["_id"] = str(n)[1:]
            d_copy['ext:osm_id'] = str(d_copy.get('osm_id', d_copy["_id"]))

            if OSWPointNormalizer.osw_point_filter(d):
                geometry = mapping(d_copy.pop("geometry"))

                if "lon" in d_copy:
                    d_copy.pop("lon")

                if "lat" in d_copy:
                    d_copy.pop("lat")

                point_features.append(
                    {"type": "Feature", "geometry": geometry, "properties": d_copy}
                )
            elif OSWLineNormalizer.osw_line_filter(d):
                geometry = mapping(d_copy.pop("geometry"))

                line_features.append(
                    {"type": "Feature", "geometry": geometry, "properties": d_copy}
                )
            elif OSWZoneNormalizer.osw_zone_filter(d):
                geometry = mapping(d_copy.pop("geometry"))

                zone_features.append(
                    {"type": "Feature", "geometry": geometry, "properties": d_copy}
                )
            elif OSWPolygonNormalizer.osw_polygon_filter(d):
                geometry = mapping(d_copy.pop("geometry"))

                polygon_features.append(
                    {"type": "Feature", "geometry": geometry, "properties": d_copy}
                )
            else:
                d_copy['_id'] = str(n)

                geometry = mapping(d_copy.pop('geometry'))

                if 'lon' in d_copy:
                    d_copy.pop('lon')

                if 'lat' in d_copy:
                    d_copy.pop('lat')

                node_features.append(
                    {'type': 'Feature', 'geometry': geometry, 'properties': d_copy}
                )
        nodes_fc = {**OSW_JSON_HEADER, **{"features": node_features}}
        points_fc = {**OSW_JSON_HEADER, **{"features": point_features}}
        lines_fc = {**OSW_JSON_HEADER, **{"features": line_features}}
        zones_fc = {**OSW_JSON_HEADER, **{"features": zone_features}}
        polygons_fc = {**OSW_JSON_HEADER, **{"features": polygon_features}}

        if len(edge_features) > 0:
            with open(edges_path, 'w') as f:
                json.dump(edges_fc, f)

        if len(node_features) > 0:
            with open(nodes_path, 'w') as f:
                json.dump(nodes_fc, f)

        if len(point_features) > 0:
            with open(points_path, "w") as f:
                json.dump(points_fc, f)

        if len(line_features) > 0:
            with open(lines_path, "w") as f:
                json.dump(lines_fc, f)

        if len(zone_features) > 0:
            with open(zones_path, "w") as f:
                json.dump(zones_fc, f)

        if len(polygon_features) > 0:
            with open(polygons_path, "w") as f:
                json.dump(polygons_fc, f)

    @classmethod
    def from_geojson(cls, nodes_path, edges_path):
        with open(nodes_path) as f:
            nodes_fc = json.load(f)

        with open(edges_path) as f:
            edges_fc = json.load(f)

        G = nx.MultiDiGraph()
        osm_graph = cls(G=G)

        for node_feature in nodes_fc['features']:
            props = node_feature['properties']
            n = props.pop('_id')
            props['geometry'] = shape(node_feature['geometry'])
            G.add_node(n, **props)

        for edge_feature in edges_fc['features']:
            props = edge_feature['properties']
