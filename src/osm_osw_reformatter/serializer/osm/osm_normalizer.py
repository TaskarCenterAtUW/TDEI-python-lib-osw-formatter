import json
import math
import ogr2osm

from ...config import FormatterConfig


class OSMNormalizer(ogr2osm.TranslationBase):

    OSM_IMPLIED_FOOTWAYS = (
        "footway",
        "pedestrian",
        "steps",
        "living_street"
    )

    OSM_TAG_DATATYPES = {
        'width': float,
        'step_count': int,
    }

    OSM_ALLOWED_TAGS = {
        '_id',
        '_u_id',
        '_v_id',
        '_w_id',
        'area',
        'amenity',
        'barrier',
        'building',
        'climb',
        'crossing:markings',
        'description',
        'emergency',
        'ext:maxspeed',
        'foot',
        'footway',
        'highway',
        'incline',
        'kerb',
        'leaf_cycle',
        'leaf_type',
        'length',
        'man_made',
        'name',
        'natural',
        'opening_hours',
        'power',
        'service',
        'step_count',
        'surface',
        'tactile_paving',
        'width',
    }

    WAY_NODE_ATTRIBUTES = ('nds', 'refs', 'nodeRefs', 'nodes')

    def __init__(self, config: FormatterConfig = None):
        super().__init__()
        self.config = config or FormatterConfig()
        # OSW `_id` -> the OsmNode created for that node feature, and each way
        # -> the `_u_id`/`_v_id` of the edge it came from. ogr2osm builds ways
        # from geometry alone, so co-located nodes are indistinguishable to it;
        # these let the endpoints be restored from the OSW references instead.
        self._nodes_by_osw_id = {}
        self._way_endpoints = {}

    def merge_tags(self, geometry_type, tags_existing_geometry, tags_new_geometry):
        """Decide whether two geometries at the same location become one.

        ogr2osm keys nodes by their coordinates and merges anything that lands
        on the same key. Returning ``None`` is its documented way to say the two
        cannot be merged, which keeps both in the output. When
        ``allow_zero_length_lines`` is set, two OSW features at the same location
        stay two OSM nodes even with identical tags; otherwise they are merged.

        Only feature-to-feature collisions are refused. ogr2osm routes way
        vertices through the same call with empty tags, and merging those is what
        attaches an edge to the node feature at its endpoint -- refuse them and
        every way gets private vertices, leaving the network disconnected and
        kerb nodes orphaned.
        """
        if (
            geometry_type == 'node'
            and self.config.allow_zero_length_lines
            and tags_existing_geometry
            and tags_new_geometry
        ):
            return None
        return super().merge_tags(geometry_type, tags_existing_geometry, tags_new_geometry)

    def _stash_ext(self, tags, key, value):
        """Preserve non-compliant values under an ext: namespace."""
        if value is None:
            return
        try:
            if isinstance(value, (dict, list)):
                safe_value = json.dumps(value, separators=(",", ": "))
            elif isinstance(value, str):
                # Normalize JSON-like strings to canonical compact form
                stripped = value.strip()
                if (stripped.startswith("{") and stripped.endswith("}")) or (
                    stripped.startswith("[") and stripped.endswith("]")
                ):
                    try:
                        safe_value = json.dumps(json.loads(stripped), separators=(",", ": "))
                    except Exception:
                        safe_value = value
                else:
                    safe_value = value
            else:
                safe_value = str(value)
        except Exception:
            safe_value = str(value)
        # Final canonicalization for any JSON-like string
        if isinstance(safe_value, str):
            s = safe_value.strip()
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                try:
                    safe_value = json.dumps(json.loads(s), separators=(",", ": "))
                except Exception:
                    pass
        tags[f"ext:{key}"] = safe_value

    def _check_datatypes(self, tags):
        for key, expected_type in self.OSM_TAG_DATATYPES.items():
            value = tags.get(key)
            if value is not None:
                try:
                    cast_value = expected_type(value)
                    if isinstance(cast_value, float) and (cast_value != cast_value):  # NaN check
                        self._stash_ext(tags, key, value)
                        tags.pop(key)
                    else:
                        tags[key] = str(cast_value)
                except (ValueError, TypeError):
                    self._stash_ext(tags, key, value)
                    tags.pop(key)

    def filter_tags(self, tags):
        '''
        Override this method if you want to modify or add tags to the xml output
        '''

        # Promote non-serializable values (e.g., dict/list) to ext: namespace
        for key in list(tags.keys()):
            value = tags[key]
            if isinstance(value, (dict, list)):
                self._stash_ext(tags, key, value)
                tags.pop(key, None)
            elif key not in self.OSM_ALLOWED_TAGS and not key.startswith('ext:'):
                # Preserve unknown/non-compliant fields as ext: tags
                self._stash_ext(tags, key, value)
                tags.pop(key, None)

        # Handle zones
        if 'highway' in tags and tags['highway'] == 'pedestrian' and '_w_id' in tags and tags['_w_id']:
            tags['area'] = 'yes'

        # OSW derived fields
        tags.pop('_u_id', '')
        tags.pop('_v_id', '')
        tags.pop('_w_id', '')
        tags.pop('length', '')
        if 'foot' in tags and tags['foot'] == 'yes' and 'highway' in tags and tags['highway'] in self.OSM_IMPLIED_FOOTWAYS:
            tags.pop('foot', '')

        # OSW fields with similar OSM field names
        if 'climb' in tags:
            if tags.get('highway') != 'steps' or tags['climb'] not in ('up', 'down'):
                self._stash_ext(tags, 'climb', tags.get('climb'))
                tags.pop('climb', '')

        if 'incline' in tags:
            try:
                incline_val = float(str(tags['incline']))
            except (ValueError, TypeError):
                # Preserve invalid incline as extension
                self._stash_ext(tags, 'incline', tags.get('incline'))
                tags.pop('incline', '')
            else:
                # Normalise numeric incline values by casting to string
                tags['incline'] = str(incline_val)

        self._check_datatypes(tags)

        return tags

    @staticmethod
    def _ogr_field(ogrfeature, name):
        """Read a field from the source feature, or None when it is absent."""
        try:
            index = ogrfeature.GetFieldIndex(name)
        except Exception:
            return None
        if index is None or index < 0:
            return None
        try:
            if not ogrfeature.IsFieldSet(index):
                return None
            value = ogrfeature.GetFieldAsString(index)
        except Exception:
            return None
        return value or None

    def _way_nodes_attribute(self, way):
        for attribute in self.WAY_NODE_ATTRIBUTES:
            if hasattr(way, attribute):
                return attribute
        return None

    def _record_osw_references(self, osmgeometry, ogrfeature):
        """Remember how OSW identified this geometry, before ogr2osm renumbers."""
        if ogrfeature is None or osmgeometry is None:
            return

        if self._way_nodes_attribute(osmgeometry) is not None:
            u_id = self._ogr_field(ogrfeature, '_u_id')
            v_id = self._ogr_field(ogrfeature, '_v_id')
            if u_id and v_id:
                self._way_endpoints[id(osmgeometry)] = (u_id, v_id)
            return

        osw_id = self._ogr_field(ogrfeature, '_id')
        if osw_id:
            self._nodes_by_osw_id.setdefault(osw_id, osmgeometry)

    def _repair_way_endpoints(self, osmways):
        """Point each way at the nodes its OSW edge actually referenced.

        Two OSW nodes may share a location, and ogr2osm resolves a way vertex by
        coordinate, so both endpoints of a zero-length edge land on whichever
        node it created first. The `_u_id`/`_v_id` references say which nodes
        were meant.
        """
        if not self._way_endpoints or not self._nodes_by_osw_id:
            return

        for way in osmways:
            endpoints = self._way_endpoints.get(id(way))
            if not endpoints:
                continue
            start = self._nodes_by_osw_id.get(endpoints[0])
            end = self._nodes_by_osw_id.get(endpoints[1])
            if start is None or end is None:
                continue

            attribute = self._way_nodes_attribute(way)
            if attribute is None:
                continue
            nodes = list(getattr(way, attribute) or [])
            if len(nodes) >= 2:
                nodes[0] = start
                nodes[-1] = end
            else:
                nodes = [start, end]
            setattr(way, attribute, nodes)

    def process_feature_post(self, osmgeometry, ogrfeature, ogrgeometry):
        '''
        This method is called after the creation of an OsmGeometry object. The
        ogr feature and ogr geometry used to create the object are passed as
        well. Note that any return values will be discarded by ogr2osm.
        '''
        self._record_osw_references(osmgeometry, ogrfeature)
        def _set_tag(osm_obj, key, value):
            tags = getattr(osm_obj, "tags", None)
            if tags is None:
                return
            if isinstance(tags.get(key), list):
                tags[key] = [value]
            elif key in tags:
                tags[key] = value
            else:
                tags[key] = [value] if any(isinstance(v, list) for v in tags.values()) else value

        osm_id = None
        # ext:osm_id is probably in the tags dictionary as 'ext:osm_id' or similar
        def _as_int(val):
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        if 'ext:osm_id' in osmgeometry.tags and osmgeometry.tags['ext:osm_id'][0]:
            osm_id = _as_int(osmgeometry.tags['ext:osm_id'][0])
        elif '_id' in osmgeometry.tags and osmgeometry.tags['_id'][0]:
            osm_id = _as_int(osmgeometry.tags['_id'][0])

        is_generated_node = (
            hasattr(osmgeometry, "x")
            and hasattr(osmgeometry, "y")
            and not hasattr(osmgeometry, "nodes")
            and not hasattr(osmgeometry, "members")
        )
        if osm_id is not None and not is_generated_node:
            osmgeometry.id = osm_id
        elevation = self._extract_elevation(ogrgeometry)
        if elevation is not None:
            _set_tag(osmgeometry, "ext:elevation", str(elevation))

    def _extract_elevation(self, ogrgeometry):
        """Return the Z value of the first coordinate, if present and valid."""
        if ogrgeometry is None:
            return None

        try:
            dim = ogrgeometry.GetCoordinateDimension()
            if dim < 3:
                return None
        except Exception:
            return None

        def _first_point(geom):
            try:
                if geom.GetPointCount() > 0:
                    return geom.GetPoint(0)
            except Exception:
                pass
            try:
                if geom.GetGeometryCount() > 0:
                    ref = geom.GetGeometryRef(0)
                    if ref and ref.GetPointCount() > 0:
                        return ref.GetPoint(0)
            except Exception:
                pass
            return None

        point = _first_point(ogrgeometry)
        if not point or len(point) < 3:
            return None

        try:
            z_val = float(point[2])
        except (ValueError, TypeError):
            return None

        if math.isnan(z_val):
            return None

        return z_val

    def process_output(self, osmnodes, osmways, osmrelations):
        """
        Remap all element IDs to sequential, collision-free values per type.
        Adds a '_id' tag with the new derived positive ID and rewrites
        references accordingly.
        """
        self._repair_way_endpoints(osmways)

        # Capture original IDs for mapping
        node_identity_map = {}
        node_id_map = {}
        way_identity_map = {}
        way_id_map = {}
        rel_identity_map = {}
        rel_id_map = {}
        next_node_id = 1
        next_way_id = 1
        next_rel_id = 1

        def _set_id_tag(osm_obj, new_id):
            tags = getattr(osm_obj, "tags", None)
            if tags is None or not hasattr(tags, "__setitem__"):
                return

            value = str(new_id)
            existing = tags.get("_id") if hasattr(tags, "get") else None

            if isinstance(existing, list):
                tags["_id"] = [value]
            elif existing is None:
                # Determine if the container generally stores values as lists
                sample_value = None
                if hasattr(tags, "values"):
                    for sample_value in tags.values():
                        if sample_value is not None:
                            break
                if isinstance(sample_value, list):
                    tags["_id"] = [value]
                else:
                    # Default to list storage to match ogr2osm's internal structures
                    tags["_id"] = [value]
            else:
                tags["_id"] = value

        def _member_type(member):
            for attr in ("type", "member_type", "objtype", "element_type"):
                value = getattr(member, attr, None)
                if isinstance(value, str):
                    normalized = value.lower()
                    if normalized in ("node", "way", "relation"):
                        return normalized
            return None

        # Remap node IDs sequentially starting at 1
        for node in osmnodes:
            old_id = getattr(node, "id", None)
            if old_id is None:
                continue
            new_id = next_node_id
            next_node_id += 1
            node_identity_map[id(node)] = new_id
            # Keep first mapping only as a fallback for raw integer refs.
            node_id_map.setdefault(old_id, new_id)
            node.id = new_id
            _set_id_tag(node, new_id)

        # Remap way IDs and rewrite node refs
        for way in osmways:
            old_id = getattr(way, "id", None)
            if old_id is not None:
                new_id = next_way_id
                next_way_id += 1
                way_identity_map[id(way)] = new_id
                way_id_map.setdefault(old_id, new_id)
                way.id = new_id
                _set_id_tag(way, new_id)

            node_refs = getattr(way, "nds", None) or getattr(way, "refs", None) or getattr(way, "nodeRefs", None) or getattr(way, "nodes", None)
            if node_refs is not None:
                new_refs = []
                for ref in node_refs:
                    if isinstance(ref, int):
                        if ref not in node_id_map:
                            new_id = next_node_id
                            next_node_id += 1
                            node_id_map[ref] = new_id
                        new_refs.append(node_id_map.get(ref, ref))
                    elif hasattr(ref, "id"):
                        ref_identity = id(ref)
                        if ref_identity in node_identity_map:
                            ref.id = node_identity_map[ref_identity]
                        elif ref.id not in node_id_map:
                            new_id = next_node_id
                            next_node_id += 1
                            node_id_map[ref.id] = new_id
                            ref.id = new_id
                        else:
                            ref.id = node_id_map.get(ref.id, ref.id)
                        new_refs.append(ref)
                    else:
                        new_refs.append(ref)

                if hasattr(way, "nds"):
                    way.nds = new_refs
                elif hasattr(way, "refs"):
                    way.refs = new_refs
                elif hasattr(way, "nodeRefs"):
                    way.nodeRefs = new_refs
                elif hasattr(way, "nodes"):
                    way.nodes = new_refs

        # Remap relation IDs and member refs
        for rel in osmrelations:
            old_id = getattr(rel, "id", None)
            if old_id is not None:
                new_id = next_rel_id
                next_rel_id += 1
                rel_identity_map[id(rel)] = new_id
                rel_id_map.setdefault(old_id, new_id)
                rel.id = new_id
                _set_id_tag(rel, new_id)

            if hasattr(rel, "members"):
                for member in rel.members:
                    if not hasattr(member, "ref"):
                        continue
                    ref = member.ref
                    m_type = _member_type(member)
                    if isinstance(ref, int):
                        if m_type == "node":
                            if ref not in node_id_map:
                                new_id = next_node_id
                                next_node_id += 1
                                node_id_map[ref] = new_id
                            member.ref = node_id_map.get(ref, ref)
                        elif m_type == "way":
                            if ref not in way_id_map:
                                new_id = next_way_id
                                next_way_id += 1
                                way_id_map[ref] = new_id
                            member.ref = way_id_map.get(ref, ref)
                        elif m_type == "relation":
                            if ref not in rel_id_map:
                                new_id = next_rel_id
                                next_rel_id += 1
                                rel_id_map[ref] = new_id
                            member.ref = rel_id_map.get(ref, ref)
                        else:
                            if ref not in node_id_map and ref not in way_id_map and ref not in rel_id_map:
                                new_id = next_rel_id
                                next_rel_id += 1
                                rel_id_map[ref] = new_id
                            member.ref = node_id_map.get(ref, way_id_map.get(ref, rel_id_map.get(ref, ref)))
                    elif hasattr(ref, "id"):
                        ref_identity = id(ref)
                        if m_type == "node":
                            if ref_identity in node_identity_map:
                                ref.id = node_identity_map[ref_identity]
                            elif ref.id not in node_id_map:
                                new_id = next_node_id
                                next_node_id += 1
                                node_id_map[ref.id] = new_id
                                ref.id = new_id
                            else:
                                ref.id = node_id_map.get(ref.id, ref.id)
                        elif m_type == "way":
                            ref_identity = id(ref)
                            if ref_identity in way_identity_map:
                                ref.id = way_identity_map[ref_identity]
                            elif ref.id not in way_id_map:
                                new_id = next_way_id
                                next_way_id += 1
                                way_id_map[ref.id] = new_id
                                ref.id = new_id
                            else:
                                ref.id = way_id_map.get(ref.id, ref.id)
                        elif m_type == "relation":
                            ref_identity = id(ref)
                            if ref_identity in rel_identity_map:
                                ref.id = rel_identity_map[ref_identity]
                            elif ref.id not in rel_id_map:
                                new_id = next_rel_id
                                next_rel_id += 1
                                rel_id_map[ref.id] = new_id
                                ref.id = new_id
                            else:
                                ref.id = rel_id_map.get(ref.id, ref.id)
                        else:
                            if ref.id not in node_id_map and ref.id not in way_id_map and ref.id not in rel_id_map:
                                new_id = next_rel_id
                                next_rel_id += 1
                                rel_id_map[ref.id] = new_id
                            ref.id = node_id_map.get(ref.id, way_id_map.get(ref.id, rel_id_map.get(ref.id, ref.id)))

        # Ensure deterministic ordering now that IDs have been remapped
        if hasattr(osmnodes, "sort"):
            osmnodes.sort(key=lambda n: n.id)
        if hasattr(osmways, "sort"):
            osmways.sort(key=lambda w: w.id)
        if hasattr(osmrelations, "sort"):
            osmrelations.sort(key=lambda r: r.id)
