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
