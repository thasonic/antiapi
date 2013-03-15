# coding: utf-8

from decimal import Decimal
from json import JSONEncoder
try:
    from inflect import engine
    inflector = engine()
except ImportError:
    # TODO: make right error for XML serializer or graceful degradation.
    inflector = lambda x: x


# JSON serialization part.

def _json_extra(obj, *arg, **kwargs):
    """
    Serialized extra data types to JSON.
    """
    if isinstance(obj, Decimal):
        return str(obj)
    # datetime stuff
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if isinstance(obj, set):
        return encoder.encode(list(obj))
    raise TypeError('Cannot encode to JSON: %s' % type(obj))


encoder = JSONEncoder(default=_json_extra)
pretty_encoder = JSONEncoder(
    default=_json_extra,
    indent=2,
    ensure_ascii=False,
    sort_keys=True,
)


def to_json(obj, is_pretty=False):
    """
    JSON serialization shortcut function.
    """
    if is_pretty:
        return pretty_encoder.encode(obj)
    return encoder.encode(obj)


def to_jsonp(obj, callback, is_pretty=False):
    """
    JSONP serialization shortcut function.
    """
    return '%s(%s);' % (callback, to_json(obj, is_pretty))


# XML serialization part.


def _escape(value):
    """
    Escapes a special XML entities.
    """
    return value.replace('&', '&amp;').replace('<', '&lt;')


def _dict_key(key_name):
    """
    Casts key of dict to string encoded in UTF-8.
    """
    if isinstance(key_name, unicode):
        return key_name.encode('utf-8')
    return str(key_name)


def _serialize(obj, parent_name):
    """
    Serializes a different data types to XML.
    """
    if isinstance(obj, unicode):
        return _escape(obj.encode('utf-8')), ''

    # Serialize dict stuff.
    if hasattr(obj, 'iteritems'):
        res = ''
        attrs = ''
        is_text = False
        for key in obj.keys():
            k = _dict_key(key)
            if k[0] == '@':
                attr_val, _ = _serialize(obj[key], None)
                attrs += ' %s="%s"' % (
                    _dict_key(key[1:]), attr_val.replace('"', '&quot;')
                )
            elif k == 'text()':
                is_text = True
                text = _serialize(obj[key], None)[0]
            elif k == '#children':
                value, _attrs = _serialize(obj[key], parent_name)
                res += value
            elif k[0] != '#' and not is_text:
                value, _attrs = _serialize(text if is_text else obj[key], k)
                res += '<%s%s>%s</%s>' % (k, _attrs, value, k)
        return text if is_text else res, attrs

    # Serialize iterable stuff.
    if hasattr(obj, '__iter__'):
        # List of tags is a structure like:
        # ({'#name': 'attr', '@name': 'attr1', 'text()': '1'},
        #  {'#name': 'attr', '@name': 'attr2', 'text()': '2'},)
        # it is serialized to:
        # <attr name="attr1">1</attr><attr name="attr2">2</attr>
        is_tags_list = obj and hasattr(obj[0], 'iteritems') and \
            '#name' in obj[0]
        if not is_tags_list:
            # A bit morphological magic to get tag name for list item.
            item_name = inflector.singular_noun(parent_name) or 'item'
        res = ''
        for value in obj:
            if is_tags_list:
                if '#name' in value:
                    item_name = value['#name']
                else:
                    # Allow to serialize usual dict in tags list.
                    _value, _ = _serialize(value, None)
                    res += _value
                    continue
            _value, attrs = _serialize(value, item_name)
            res += '<%s%s>%s</%s>' % (
                item_name, attrs, _value, item_name
            )
        return res, ''

    if isinstance(obj, Decimal):
        return str(obj), ''

    # Serialize datetime stuff.
    if hasattr(obj, 'isoformat'):
        return obj.isoformat(), ''

    if isinstance(obj, bool):
        return '1' if obj else '0', ''

    if obj is None:
        return '', ''

    return _escape(str(obj)), ''


def to_xml(obj, xml_root_node=None, serializer=None, inc_header=True,
           is_pretty=False):
    """
    XML serialization shortcut function.
    """
    node_name = xml_root_node or 'root'
    value, attrs = (serializer or _serialize)(obj, node_name)
    return (
        '%s<%s%s>%s</%s>' % (
            '<?xml version="1.0" encoding="utf-8"?>' if inc_header else '',
            node_name, attrs, value, node_name
        )
    )
