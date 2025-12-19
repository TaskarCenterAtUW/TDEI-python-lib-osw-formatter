import types
import math

OSW_SCHEMA_ID = "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json"

LEAF_CYCLE_VALUES = (
    "deciduous",
    "evergreen",
    "mixed",
    "semi_deciduous",
    "semi_evergreen",
)

LEAF_TYPE_VALUES = (
    "broadleaved",
    "leafless",
    "mixed",
    "needleleaved",
)


def _tag_value(tags, key):
    if key in tags:
        return tags.get(key, "")
    return tags.get(f"ext:{key}", "")


def _tags_to_dict(tags):
    # Accept dict-like and osmium TagList-like objects
    if hasattr(tags, "items"):
        try:
            return dict(tags)
        except Exception:
            pass

    try:
        return {
            (item.k if hasattr(item, "k") else item[0]): (item.v if hasattr(item, "v") else item[1])
            for item in tags
            if (hasattr(item, "k") and hasattr(item, "v")) or (isinstance(item, tuple) and len(item) == 2)
        }
    except Exception:
        return {}


def _has_only_ext_tags(tags):
    if not tags:
        return False
    return all(str(k).startswith("ext:") for k in tags.keys())


class OSWWayNormalizer:

    ROAD_HIGHWAY_VALUES = (
        "primary",
        "secondary",
        "tertiary",
        "residential",
        "service",
        "unclassified",
        "trunk", # Not traversible, just for conflation
        "primary_link",
        "secondary_link",
        "tertiary_link",
        "trunk_link"
    )

    CLIMB_VALUES = (
        "up",
        "down",
    )

    def __init__(self, tags):
        self.tags = tags

    def filter(self):
        return (
            self.is_sidewalk()
            or self.is_crossing()
            or self.is_traffic_island()
            or self.is_footway()
            or self.is_stairs()
            or self.is_pedestrian()
            or self.is_living_street()
            or self.is_driveway()
            or self.is_alley()
            or self.is_parking_aisle()
            or self.is_road()
        )

    @staticmethod
    def osw_way_filter(tags):
        return OSWWayNormalizer(tags).filter()

    def normalize(self):
        if self.is_sidewalk():
            return self._normalize_sidewalk()
        elif self.is_crossing():
            return self._normalize_crossing()
        elif self.is_traffic_island():
            return self._normalize_traffic_island()
        elif self.is_footway():
            return self._normalize_footway()
        elif self.is_stairs():
            return self._normalize_stairs()
        elif self.is_pedestrian():
            return self._normalize_pedestrian()
        elif self.is_living_street():
            return self._normalize_living_street()
        elif self.is_driveway():
            return self._normalize_service_road()
        elif self.is_alley():
            return self._normalize_service_road()
        elif self.is_parking_aisle():
            return self._normalize_service_road()
        elif self.is_road():
            return self._normalize_road()
        else:
            raise ValueError("This is an invalid way")
    
    def _normalize_way(self, keep_keys={}, defaults = {}):
        generic_keep_keys = {
            "highway": str,
            "width": float,
            "surface": surface,
            "name": str,
            "description": str,
            "foot": foot,
            "incline": incline,
            "length": float,
        }
        generic_defaults = {}
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def _normalize_pedestrian(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {}
        generic_defaults = {"foot": "yes"}
        
        new_tags = self._normalize_way({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def _normalize_stairs(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"step_count": int, "climb": climb}
        generic_defaults = {"foot": "yes"}
        
        new_tags = self._normalize_way({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def _normalize_footway(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"highway": "footway"}
        generic_defaults = {"foot": "yes"}
        
        new_tags = self._normalize_way({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags

    def _normalize_sidewalk(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"footway": str}
        generic_defaults = {}
        
        new_tags = self._normalize_footway({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags

    def _normalize_crossing(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"footway": str, "crossing": ["crossing:markings", crossing_markings], "crossing:markings": crossing_markings}
        generic_defaults = {}
        
        new_tags = self._normalize_footway({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags

    def _normalize_traffic_island(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"footway": str}
        generic_defaults = {}
        
        new_tags = self._normalize_footway({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags

    def _normalize_living_street(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {}
        generic_defaults = {"foot": "yes"}
        
        new_tags = self._normalize_way({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def _normalize_service_road(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"service": str}
        generic_defaults = {}
        
        new_tags = self._normalize_road({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def _normalize_road(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"highway": (lambda tag_value, tags: tag_value.partition("_")[0]), "maxspeed": ["ext:maxspeed", str]}
        generic_defaults = {}
        
        new_tags = self._normalize_way({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags

    def is_sidewalk(self):
        return (_tag_value(self.tags, "highway") == "footway") and (
            _tag_value(self.tags, "footway") == "sidewalk"
        )

    def is_crossing(self):
        return (_tag_value(self.tags, "highway") == "footway") and (
            _tag_value(self.tags, "footway") == "crossing"
        )
    
    def is_traffic_island(self):
        return (_tag_value(self.tags, "highway") == "footway") and (
            _tag_value(self.tags, "footway") == "traffic_island"
        )

    def is_footway(self):
        return (_tag_value(self.tags, "highway") == "footway")
    
    def is_stairs(self):
        return _tag_value(self.tags, "highway") == "steps"
    
    def is_pedestrian(self):
        return _tag_value(self.tags, "highway") == "pedestrian"
    
    def is_living_street(self):
        return _tag_value(self.tags, "highway") == "living_street"
    
    def is_driveway(self):
        return (_tag_value(self.tags, "highway") == "service") and (
            _tag_value(self.tags, "service") == "driveway"
        )

    def is_alley(self):
        return (_tag_value(self.tags, "highway") == "service") and (
            _tag_value(self.tags, "service") == "alley"
        )
    
    def is_parking_aisle(self):
        return (_tag_value(self.tags, "highway") == "service") and (
            _tag_value(self.tags, "service") == "parking_aisle"
        )
    
    def is_road(self):
        return _tag_value(self.tags, "highway") in self.ROAD_HIGHWAY_VALUES

class OSWNodeNormalizer:
    KERB_VALUES = ("flush", "lowered", "rolled", "raised")

    def __init__(self, tags):
        self.tags = tags

    def filter(self):
        return self.is_kerb()

    @staticmethod
    def osw_node_filter(tags):
        return OSWNodeNormalizer(tags).filter()

    def normalize(self):
        if self.is_kerb():
            return self._normalize_kerb()
        else:
            raise ValueError("This is an invalid node")

    def _normalize_node(self, keep_keys={}, defaults = {}):
        generic_keep_keys = {}
        generic_defaults = {}
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def _normalize_kerb(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"barrier": "kerb", "kerb": kerb, "tactile_paving": tactile_paving}
        generic_defaults = {}
        
        new_tags = self._normalize_node({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags

    def is_kerb(self):
        kerb_value = _tag_value(self.tags, "kerb")
        barrier_value = _tag_value(self.tags, "barrier")
        has_kerb_key = "kerb" in self.tags or "ext:kerb" in self.tags
        return (kerb_value in self.KERB_VALUES) or (
            barrier_value == "kerb" and (not has_kerb_key or kerb_value == "yes")
        )
    
class OSWPointNormalizer:
    def __init__(self, tags):
        self.tags = tags

    def filter(self):
        return (self.is_powerpole()) or (
            self.is_firehydrant()) or (
            self.is_bench()) or (
            self.is_waste_basket()) or (
            self.is_manhole()) or (
            self.is_bollard()) or (
            self.is_street_lamp()) or (
            self.is_tree()) or (
            self.is_custom())
    
    @staticmethod
    def osw_point_filter(tags):
        return OSWPointNormalizer(tags).filter()

    def normalize(self):
        if self.is_powerpole():
            return self._normalize_point({"power": str})
        elif self.is_firehydrant():
            return self._normalize_point({"emergency": str})
        elif self.is_bench() or self.is_waste_basket():
            return self._normalize_point({"amenity": str})
        elif self.is_manhole():
            return self._normalize_point({"man_made": str})
        elif self.is_bollard():
            return self._normalize_point({"barrier": str})
        elif self.is_street_lamp():
            return self._normalize_point({"highway": str})
        elif self.is_tree():
            return self._normalize_point(
                {
                    "natural": natural_point,
                    "leaf_cycle": leaf_cycle,
                    "leaf_type": leaf_type
                }
            )
        elif self.is_custom():
            return self._normalize_point()
        else:
            print(f"Invalid point skipped. Tags: {self.tags}")
            return {}
    
    def _normalize_point(self, keep_keys={}, defaults = {}):
        generic_keep_keys = {}
        generic_defaults = {}
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def is_powerpole(self):
        return _tag_value(self.tags, "power") == "pole"
    
    def is_firehydrant(self):
        return _tag_value(self.tags, "emergency") == "fire_hydrant"
    
    def is_bench(self):
        return _tag_value(self.tags, "amenity") == "bench"
    
    def is_waste_basket(self):
        return _tag_value(self.tags, "amenity") == "waste_basket"

    def is_manhole(self):
        return _tag_value(self.tags, "man_made") == "manhole"
    
    def is_bollard(self):
        return _tag_value(self.tags, "barrier") == "bollard"
    
    def is_street_lamp(self):
        return _tag_value(self.tags, "highway") == "street_lamp"
    
    def is_tree(self):
        return _tag_value(self.tags, "natural") == "tree"

    def is_custom(self):
        tag_dict = _tags_to_dict(self.tags)
        return _has_only_ext_tags(tag_dict)
    
class OSWLineNormalizer:
    def __init__(self, tags):
        self.tags = tags

    def filter(self):
        return (self.is_fence()) or (self.is_tree_row()) or (self.is_custom())
    
    @staticmethod
    def osw_line_filter(tags):
        return OSWLineNormalizer(tags).filter()

    def normalize(self):
        if self.is_fence():
            return self._normalize_line({"barrier": str})
        elif self.is_tree_row():
            return self._normalize_line(
                {
                    "natural": natural_line,
                    "leaf_cycle": leaf_cycle,
                    "leaf_type": leaf_type
                }
            )
        elif self.is_custom():
            return self._normalize_line()
        else:
            raise ValueError("This is an invalid line")
    
    def _normalize_line(self, keep_keys={}, defaults = {}):
        generic_keep_keys = {}
        generic_defaults = {}
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def is_fence(self):
        return _tag_value(self.tags, "barrier") == "fence"
    
    def is_tree_row(self):
        return _tag_value(self.tags, "natural") == "tree_row"

    def is_custom(self):
        tag_dict = _tags_to_dict(self.tags)
        return _has_only_ext_tags(tag_dict)
    
class OSWPolygonNormalizer:
    # Will be fetched from schema soon
    BUILDING_VALUES = (
        "allotment_house",
        "apartments",
        "bakehouse",
        "barn",
        "barracks",
        "beach_hut",
        "boathouse",
        "bridge",
        "bungalow",
        "bunker",
        "cabin",
        "carport",
        "castle",
        "cathedral",
        "chapel",
        "church",
        "civic",
        "college",
        "commercial",
        "conservatory",
        "construction",
        "container",
        "cowshed",
        "detached",
        "digester",
        "dormitory",
        "farm",
        "farm_auxiliary",
        "fire_station",
        "garage",
        "garages",
        "gatehouse",
        "ger",
        "government",
        "grandstand",
        "greenhouse",
        "guardhouse",
        "hangar",
        "hospital",
        "hotel",
        "house",
        "houseboat",
        "hut",
        "industrial",
        "kindergarten",
        "kingdom_hall",
        "kiosk",
        "livestock",
        "military",
        "monastery",
        "mosque",
        "museum",
        "office",
        "outbuilding",
        "pagoda",
        "parking",
        "pavilion",
        "presbytery",
        "public",
        "quonset_hut",
        "religious",
        "residential",
        "retail",
        "riding_hall",
        "roof",
        "ruins",
        "school",
        "semidetached_house",
        "service",
        "shed",
        "shrine",
        "silo",
        "slurry_tank",
        "sports_centre",
        "sports_hall",
        "stable",
        "stadium",
        "static_caravan",
        "stilt_house",
        "storage_tank",
        "sty",
        "supermarket",
        "synagogue",
        "tech_cab",
        "temple",
        "tent",
        "terrace",
        "toilets",
        "tower",
        "train_station",
        "transformer_tower",
        "transportation",
        "tree_house",
        "trullo",
        "university",
        "warehouse",
        "water_tower",
        "windmill",
        "yes"
    )

    def __init__(self, tags):
        self.tags = tags

    def filter(self):
        return self.is_building() or self.is_wood() or self.is_custom()
    
    @staticmethod
    def osw_polygon_filter(tags):
        return OSWPolygonNormalizer(tags).filter()

    def normalize(self):
        if self.is_building():
            return self._normalize_polygon(
                {
                    "building": str,
                    "name": str,
                    "opening_hours": str,
                    "leaf_cycle": leaf_cycle,
                    "leaf_type": leaf_type
                }
            )
        elif self.is_wood():
            return self._normalize_polygon(
                {
                    "natural": natural_polygon,
                    "name": str,
                    "opening_hours": str,
                    "leaf_cycle": leaf_cycle,
                    "leaf_type": leaf_type
                }
            )
        elif self.is_custom():
            return self._normalize_polygon()
        else:
            raise ValueError("This is an invalid polygon")
    
    def _normalize_polygon(self, keep_keys={}, defaults = {}):
        generic_keep_keys = {}
        generic_defaults = {}
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def is_building(self):
        return _tag_value(self.tags, "building") in self.BUILDING_VALUES
    
    def is_wood(self):
        return _tag_value(self.tags, "natural") == "wood"

    def is_custom(self):
        tag_dict = _tags_to_dict(self.tags)
        return _has_only_ext_tags(tag_dict)

class OSWZoneNormalizer:
    def __init__(self, tags):
        self.tags = tags

    def filter(self):
        return self.is_pedestrian()
    
    @staticmethod
    def osw_zone_filter(tags):
        return OSWZoneNormalizer(tags).filter()

    def normalize(self):
        if self.is_pedestrian():
            return self._normalize_zone({"highway": str, "surface": surface, "name": str, "description": str})
        else:
            raise ValueError("This is an invalid zone")
    
    def _normalize_zone(self, keep_keys={}, defaults = {}):
        generic_keep_keys = {}
        generic_defaults = {"foot": "yes"}
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags
    
    def is_pedestrian(self):
        return _tag_value(self.tags, "highway") == "pedestrian"


def check_nan_and_raise(tag_type, temp):
    if (tag_type == float or tag_type == int) and math.isnan(temp):
        raise ValueError("Value cannot be NaN")
    return temp

    
def _normalize(tags, keep_keys, defaults):
    new_tags = {}
    for tag, tag_type in keep_keys.items():
        try:
            if isinstance(tag_type, list):
                if isinstance(tag_type[1], (str, bool, int, float)):
                    new_tags[tag_type[0]] = tag_type[1]
                elif isinstance(tag_type[1], types.FunctionType):
                    temp = tag_type[1](tags[tag], tags)
                    if temp is not None:
                        check_nan_and_raise(tag_type[0], temp)
                        new_tags[tag_type[0]] = temp
                    else:
                        raise ValueError
                else:
                    temp = tag_type[1](tags[tag])
                    if temp is not None:
                        check_nan_and_raise(tag_type[0], temp)
                        new_tags[tag_type[0]] = temp
                    else:
                        raise ValueError
            else:
                if isinstance(tag_type, (str, bool, int, float)):
                    new_tags[tag] = tag_type
                elif isinstance(tag_type, types.FunctionType):
                    temp = tag_type(tags[tag], tags)
                    if temp is not None:
                        check_nan_and_raise(tag_type, temp)
                        new_tags[tag] = temp
                    else:
                        raise ValueError
                else:
                    temp = tag_type(tags[tag])
                    if temp is not None:
                        check_nan_and_raise(tag_type, temp)
                        new_tags[tag] = temp
                    else:
                        raise ValueError
        except ValueError:
            pass
        except KeyError:
            pass
    
    # Preserve order of keep_keys first followed by defaults
    new_tags.update(defaults)

    # Keep all tags that start with "ext:"
    ext_tags = {k: v for k, v in tags.items() if k.startswith("ext:")}

    return {**{**new_tags, **defaults}, **{**new_tags, **ext_tags}}

    
def leaf_cycle(tag_value, tags):
    if tag_value.lower() not in LEAF_CYCLE_VALUES:
        return None
    return tag_value.lower()


def leaf_type(tag_value, tags):
    if tag_value.lower() not in LEAF_TYPE_VALUES:
        return None
    return tag_value.lower()


def natural_point(tag_value, tags):
    if tag_value.lower() != "tree":
        return None
    return "tree"


def natural_line(tag_value, tags):
    if tag_value.lower() != "tree_row":
        return None
    return "tree_row"


def natural_polygon(tag_value, tags):
    if tag_value.lower() != "wood":
        return None
    return "wood"


def tactile_paving(tag_value, tags):
    if tag_value.lower() not in (
                                "yes", 
                                "contrasted", 
                                "no",
                                "primitive",
                                ):
        return None
    else:
        return tag_value.lower()

def surface(tag_value, tags):
    if tag_value.lower() not in (
                                "asphalt", 
                                "concrete", 
                                "gravel", 
                                "grass", 
                                "paved", 
                                "paving_stones", 
                                "unpaved", 
                                "dirt", 
                                "grass_paver"
                                ):
        return None
    else:
        return tag_value.lower()
    
def crossing_markings(tag_value, tags):
    if tags.get("crossing:markings", "").lower() in (                        
                                "dashes",
                                "dots",
                                "ladder",
                                "ladder:paired",
                                "lines",
                                "lines:paired",
                                "no",
                                "skewed",
                                "surface",
                                "yes",
                                "zebra",
                                "zebra:bicolour",
                                "zebra:double",
                                "zebra:paired",
                                "rainbow",
                                "lines:rainbow",
                                "zebra:rainbow",
                                "ladder:skewed",
                                "pictograms"
                                ):
        return tags["crossing:markings"].lower()
    elif tags.get("crossing", "").lower() == "marked":
        return "yes"
    elif tags.get("crossing", "").lower() == "zebra":
        return "zebra"
    elif tags.get("crossing", "").lower() == "unmarked":
        return "no"
    else:
        return None
    
def climb(tag_value, tags):
    if tag_value.lower() not in OSWWayNormalizer.CLIMB_VALUES:
        return None
    else:
        return tag_value.lower()

def incline(tag_value, tags):
    try:
        return float(str(tag_value))
    except (ValueError, TypeError):
        return None
    
def foot(tag_value, tags):
    if tag_value.lower() not in (
                                "yes", 
                                "no", 
                                "designated", 
                                "permissive", 
                                "use_sidepath", 
                                "private", 
                                "destination"
                                ):
        return None
    else:
        return tag_value.lower()
    
def kerb(tag_value, tags):
    if tag_value.lower() not in OSWNodeNormalizer.KERB_VALUES:
        return None
    else:
        return tag_value.lower()
