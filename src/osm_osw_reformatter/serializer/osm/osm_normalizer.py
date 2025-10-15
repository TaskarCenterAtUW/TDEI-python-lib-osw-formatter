import ogr2osm

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

    def _check_datatypes(self, tags):
        for key, expected_type in self.OSM_TAG_DATATYPES.items():
            value = tags.get(key)
            if value is not None:
                try:
                    cast_value = expected_type(value)
                    if isinstance(cast_value, float) and (cast_value != cast_value):  # NaN check
                        tags.pop(key)
                    else:
                        tags[key] = str(cast_value)
                except (ValueError, TypeError):
                    tags.pop(key)

    def filter_tags(self, tags):
        '''
        Override this method if you want to modify or add tags to the xml output
        '''

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
                tags.pop('climb', '')

        if 'incline' in tags:
            try:
                incline_val = float(str(tags['incline']))
            except (ValueError, TypeError):
                # Drop the incline tag if it cannot be interpreted as a float
                tags.pop('incline', '')
            else:
                # Normalise numeric incline values by casting to string
                tags['incline'] = str(incline_val)

        self._check_datatypes(tags)

        return tags

    def process_feature_post(self, osmgeometry, ogrfeature, ogrgeometry):
        '''
        This method is called after the creation of an OsmGeometry object. The
        ogr feature and ogr geometry used to create the object are passed as
        well. Note that any return values will be discarded by ogr2osm.
        '''
        osm_id = None
        # ext:osm_id is probably in the tags dictionary as 'ext:osm_id' or similar
        if 'ext:osm_id' in osmgeometry.tags and osmgeometry.tags['ext:osm_id'][0]:
            osm_id = int(osmgeometry.tags['ext:osm_id'][0])
        elif '_id' in osmgeometry.tags and osmgeometry.tags['_id'][0]:
            osm_id = int(osmgeometry.tags['_id'][0])

        if osm_id is not None:
            osmgeometry.id = osm_id

    def process_output(self, osmnodes, osmways, osmrelations):
        """
        Convert negative IDs into deterministic 63-bit positive IDs
        for all nodes, ways, and relations (and their references),
        and add a '_id' tag with the new derived positive ID.
        """
        mask_63bit = (1 << 63) - 1

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

        def _normalise_id(osm_obj):
            if osm_obj.id < 0:
                new_id = osm_obj.id & mask_63bit
                osm_obj.id = new_id
                _set_id_tag(osm_obj, new_id)
                return new_id
            return osm_obj.id

        # Fix node IDs
        for node in osmnodes:
            _normalise_id(node)

        # Fix ways and their node references
        for way in osmways:
            _normalise_id(way)

            # Detect how node references are stored
            node_refs = getattr(way, "nds", None) or getattr(way, "refs", None) or getattr(way, "nodeRefs", None) or getattr(way, "nodes", None)

            if node_refs is not None:
                new_refs = []
                for ref in node_refs:
                    # Handle both int and OsmNode-like objects
                    if isinstance(ref, int):
                        new_refs.append(ref & mask_63bit if ref < 0 else ref)
                    elif hasattr(ref, "id"):
                        if ref.id < 0:
                            ref.id = ref.id & mask_63bit
                            _set_id_tag(ref, ref.id)
                        new_refs.append(ref)
                    else:
                        new_refs.append(ref)

                # Write back using whichever attribute exists
                if hasattr(way, "nds"):
                    way.nds = new_refs
                elif hasattr(way, "refs"):
                    way.refs = new_refs
                elif hasattr(way, "nodeRefs"):
                    way.nodeRefs = new_refs
                elif hasattr(way, "nodes"):
                    way.nodes = new_refs

        # Fix relation IDs and their member refs
        for rel in osmrelations:
            if rel.id < 0:
                rel.id = rel.id & mask_63bit
            _normalise_id(rel)

            if hasattr(rel, "members"):
                for member in rel.members:
                    if hasattr(member, "ref"):
                        ref = member.ref
                        if isinstance(ref, int) and ref < 0:
                            member.ref = ref & mask_63bit
                        elif hasattr(ref, "id") and ref.id < 0:
                            ref.id = ref.id & mask_63bit
                            _set_id_tag(ref, ref.id)

        # Ensure deterministic ordering now that IDs have been normalised
        if hasattr(osmnodes, "sort"):
            osmnodes.sort(key=lambda n: n.id)
        if hasattr(osmways, "sort"):
            osmways.sort(key=lambda w: w.id)
        if hasattr(osmrelations, "sort"):
            osmrelations.sort(key=lambda r: r.id)


