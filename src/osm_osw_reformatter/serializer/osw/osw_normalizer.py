import types
import math
import json
from functools import lru_cache

from python_osw_validation import DEFAULT_DATASET_SCHEMAS

OSW_SCHEMA_ID = "https://sidewalks.washington.edu/opensidewalks/0.3/schema.json"


@lru_cache(maxsize=None)
def _schema_enum_values(dataset, discriminator, feature_type, property_name):
    """Read an enum from the same bundled dataset schema used for validation.

    Feature-specific anyOf branches can restrict the top-level property enum
    (for example, mixed leaf types are allowed for woods but not single trees).
    Schema loading/structure failures must surface rather than falling back to
    an independently maintained list of allowed values.
    """
    schema = _dataset_property_schema(dataset)
    matches = [
        branch for branch in schema["anyOf"]
        if discriminator in branch.get("required", [])
        and feature_type in branch.get("properties", {}).get(
            discriminator, {}).get("enum", [])
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one OSW {dataset} schema branch for "
            f"{discriminator}={feature_type}; found {len(matches)}."
        )
    definition = matches[0]["properties"].get(property_name)
    if definition is None or "enum" not in definition:
        raise RuntimeError(
            f"Missing OSW enum for {dataset}/{feature_type}/{property_name}."
        )
    values = frozenset(definition["enum"])
    parent_enum = schema.get("properties", {}).get(property_name, {}).get("enum")
    if parent_enum is not None:
        values &= frozenset(parent_enum)
    return values


@lru_cache(maxsize=None)
def _dataset_property_schema(dataset):
    try:
        with open(DEFAULT_DATASET_SCHEMAS[dataset], encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
        properties = schema["properties"]["features"]["items"]["properties"]["properties"]
        if not isinstance(properties.get("anyOf"), list):
            raise ValueError("Missing feature-specific anyOf branches")
        return properties
    except (OSError, ValueError, KeyError, TypeError) as error:
        # _normalize treats ValueError/KeyError as bad input tags. A broken
        # schema is a conversion failure, so it must not take that path.
        raise RuntimeError(f"Cannot load OSW {dataset} property schema: {error}") from error


@lru_cache(maxsize=None)
def _property_enum_values(dataset, property_name):
    definition = _dataset_property_schema(dataset).get("properties", {}).get(property_name, {})
    if "enum" not in definition:
        raise RuntimeError(f"Missing OSW enum for {dataset}/{property_name}.")
    return frozenset(definition["enum"])


def _enum_value(dataset, property_name, value):
    value = value.lower()
    return value if value in _property_enum_values(dataset, property_name) else None


def _leaf_value(property_name, tag_value, tags):
    # Route by feature type, not by a shared union of incompatible enums.
    natural = _tag_value(tags, "natural")
    dataset = {"tree": "points", "tree_row": "lines", "wood": "polygons"}.get(natural)
    if dataset is None:
        return None
    value = tag_value.lower()
    allowed = _schema_enum_values(dataset, "natural", natural, property_name)
    return value if value in allowed else None


def _tag_value(tags, key):
    return tags.get(key, "")


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


def _feature_tags(tags):
    tag_dict = _tags_to_dict(tags)
    internal_keys = {
        "geometry",
        "indref",
        "lat",
        "length",
        "lon",
        "ndref",
        "osm_id",
        "segment",
    }
    return {
        k: v
        for k, v in tag_dict.items()
        if k not in internal_keys and not str(k).startswith("_")
    }


def _has_only_ext_tags(tags):
    if not tags:
        return False
    return all(str(k).startswith("ext:") for k in tags.keys())


class OSWWayNormalizer:

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
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults}, dataset="edges")
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
        generic_keep_keys = {"highway": (lambda tag_value, tags: tag_value.removesuffix("_link")), "maxspeed": ["ext:maxspeed", str]}
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
        # Link suffix removal is an OSM-to-OSW mapping, not an OSW enum.
        highway = _tag_value(self.tags, "highway").removesuffix("_link")
        pedestrian = OSWWayNormalizer({"highway": highway})
        return highway in _property_enum_values("edges", "highway") and not (
            pedestrian.is_footway() or pedestrian.is_stairs()
            or pedestrian.is_pedestrian() or pedestrian.is_living_street()
        )

class OSWNodeNormalizer:
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
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults}, dataset="nodes")
        return new_tags
    
    def _normalize_kerb(self, keep_keys = {}, defaults = {}):
        generic_keep_keys = {"barrier": "kerb", "kerb": kerb, "tactile_paving": tactile_paving}
        generic_defaults = {}
        
        new_tags = self._normalize_node({**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults})
        return new_tags

    def is_kerb(self):
        kerb_value = _tag_value(self.tags, "kerb")
        barrier_value = _tag_value(self.tags, "barrier")
        has_kerb_key = "kerb" in self.tags
        return (kerb_value in _property_enum_values("nodes", "kerb")) or (
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
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults}, dataset="points")
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
        tag_dict = _feature_tags(self.tags)
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
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults}, dataset="lines")
        return new_tags
    
    def is_fence(self):
        return _tag_value(self.tags, "barrier") == "fence"
    
    def is_tree_row(self):
        return _tag_value(self.tags, "natural") == "tree_row"

    def is_custom(self):
        tag_dict = _feature_tags(self.tags)
        return _has_only_ext_tags(tag_dict)
    
class OSWPolygonNormalizer:
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
                    "opening_hours": str
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
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults}, dataset="polygons")
        return new_tags
    
    def is_building(self):
        return self.tags.get("building", "") in _property_enum_values("polygons", "building")
    
    def is_wood(self):
        return _tag_value(self.tags, "natural") == "wood"

    def is_custom(self):
        tag_dict = _feature_tags(self.tags)
        # Polygon parsing only calls this normalizer for closed OSM areas. Let
        # unsupported source tags reach ``normalize()``, where they are safely
        # namespaced as ``ext:*``. Requiring them to already use that namespace
        # made the conversion order self-defeating: ordinary tags were rejected
        # before normalization had a chance to preserve them.
        return bool(tag_dict) and not self.is_building() and not self.is_wood()

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
            return self._normalize_zone({"highway": str, "surface": (lambda value, tags: _enum_value("zones", "surface", value)), "name": str, "description": str})
        else:
            raise ValueError("This is an invalid zone")
    
    def _normalize_zone(self, keep_keys={}, defaults = {}):
        generic_keep_keys = {}
        generic_defaults = {"foot": "yes"}
        
        new_tags = _normalize(self.tags, {**generic_keep_keys, **keep_keys}, {**generic_defaults, **defaults}, dataset="zones")
        return new_tags
    
    def is_pedestrian(self):
        return _tag_value(self.tags, "highway") == "pedestrian"


def check_nan_and_raise(tag_type, temp):
    if (tag_type == float or tag_type == int) and math.isnan(temp):
        raise ValueError("Value cannot be NaN")
    return temp

    
def _normalize(tags, keep_keys, defaults, dataset=None):
    new_tags = {}
    consumed_tags = set()
    invalid_tags = set()
    for tag, tag_type in keep_keys.items():
        try:
            if isinstance(tag_type, list):
                if isinstance(tag_type[1], (str, bool, int, float)):
                    new_tags[tag_type[0]] = tag_type[1]
                    consumed_tags.add(tag)
                elif isinstance(tag_type[1], types.FunctionType):
                    temp = tag_type[1](tags[tag], tags)
                    if temp is not None:
                        check_nan_and_raise(tag_type[0], temp)
                        new_tags[tag_type[0]] = temp
                        consumed_tags.add(tag)
                    else:
                        raise ValueError
                else:
                    temp = tag_type[1](tags[tag])
                    if temp is not None:
                        check_nan_and_raise(tag_type[0], temp)
                        new_tags[tag_type[0]] = temp
                        consumed_tags.add(tag)
                    else:
                        raise ValueError
            else:
                if isinstance(tag_type, (str, bool, int, float)):
                    new_tags[tag] = tag_type
                    consumed_tags.add(tag)
                elif isinstance(tag_type, types.FunctionType):
                    temp = tag_type(tags[tag], tags)
                    if temp is not None:
                        check_nan_and_raise(tag_type, temp)
                        new_tags[tag] = temp
                        consumed_tags.add(tag)
                    else:
                        raise ValueError
                else:
                    temp = tag_type(tags[tag])
                    if temp is not None:
                        check_nan_and_raise(tag_type, temp)
                        new_tags[tag] = temp
                        consumed_tags.add(tag)
                    else:
                        raise ValueError
        except ValueError:
            if tag in tags:
                invalid_tags.add(tag)
            pass
        except KeyError:
            pass
    
    # Preserve order of keep_keys first followed by defaults
    new_tags.update(defaults)

    # Also check enum fields copied as strings or supplied by a conversion
    # default. Invalid source values follow the existing extension-tag path.
    if dataset is not None:
        definitions = _dataset_property_schema(dataset).get("properties", {})
        for key, value in list(new_tags.items()):
            if "enum" in definitions.get(key, {}) and value not in _property_enum_values(dataset, key):
                if key in defaults:
                    raise RuntimeError(f"Invalid OSW {dataset} default: {key}={value!r}.")
                del new_tags[key]
                for source_key, rule in keep_keys.items():
                    destination = rule[0] if isinstance(rule, list) else source_key
                    if destination == key and source_key in tags:
                        invalid_tags.add(source_key)

    # Preserve non-compliant or unknown source tags under ext:*.
    ext_tags = {}
    for key, value in _feature_tags(tags).items():
        if str(key).startswith("ext:"):
            ext_tags[key] = value
        elif key in invalid_tags or key not in consumed_tags:
            ext_tags[f"ext:{key}"] = value

    return {**{**new_tags, **defaults}, **{**new_tags, **ext_tags}}

    
def leaf_cycle(tag_value, tags):
    return _leaf_value("leaf_cycle", tag_value, tags)


def leaf_type(tag_value, tags):
    return _leaf_value("leaf_type", tag_value, tags)


def natural_point(tag_value, tags):
    return _enum_value("points", "natural", tag_value)


def natural_line(tag_value, tags):
    return _enum_value("lines", "natural", tag_value)


def natural_polygon(tag_value, tags):
    return _enum_value("polygons", "natural", tag_value)


def tactile_paving(tag_value, tags):
    return _enum_value("nodes", "tactile_paving", tag_value)


def surface(tag_value, tags):
    return _enum_value("edges", "surface", tag_value)


def crossing_markings(tag_value, tags):
    value = _enum_value("edges", "crossing:markings", tags.get("crossing:markings", ""))
    if value is not None:
        return value
    # These are translations of legacy OSM tags, not schema enum definitions.
    value = {"marked": "yes", "zebra": "zebra", "unmarked": "no"}.get(
        tags.get("crossing", "").lower()
    )
    return _enum_value("edges", "crossing:markings", value) if value is not None else None


def climb(tag_value, tags):
    return _enum_value("edges", "climb", tag_value)


def incline(tag_value, tags):
    try:
        return float(str(tag_value))
    except (ValueError, TypeError):
        return None
    
def foot(tag_value, tags):
    return _enum_value("edges", "foot", tag_value)


def kerb(tag_value, tags):
    return _enum_value("nodes", "kerb", tag_value)
