from datetime import date, datetime, timedelta
from decimal import Decimal

from .errors import ValidationError


class Param(dict):
    """
    Helper class for describing parameters of API method. Used in place of
    a simple dict with a certain structure generally because of specifying of
    constructor's keyword arguments allows to autocomplete them in the most
    of IDEs.
    """
    def __init__(self, type, default=None, required=False, validator=None,
                 max=None, min=None, process=None, **kwargs):
        """
        Note that in the body of __init__ a standard pythonic "type", "max"
        and "min" are overriden by keyword arguments.
        """
        assert type in _types_map, 'Type must be one of %s' % _types_map.keys()
        self['type'] = type
        self['required'] = required
        self['default'] = default
        self['validator'] = validator
        self['max'] = max
        self['min'] = min
        self['process'] = process
        for k in kwargs:
            self[k] = kwargs[k]

    def __getattr__(self, name):
        if name in self:
            return self[name]

#    def to_value(self, value):
#        _value = _convert_by_type(self['type'], value)
#        if self['process']:
#            return self['process'](_value)
#        return _value
#
#    def validate(self, value):
#        """
#        Provides default validation for all types.
#        Returns string with error message if value is invalid or None
#        otherwise.
#        """
#        return _validate_by_type(self, value)


def validate(params, data, error_messages=None):
    """
    Validates values of API method's parameters got from GET or POST.
    Sets a cleaned values to get_values and post_values properties
    and call a wrapped HTTP method's handler if success or returns
    400 HTTP error otherwise.
    """
    values = {}
    for name, param in params.iteritems():
        value = data.get(name, param.get('default'))
        if not value:
            if param.get('required'):
                _validation_error(param, 'required', name, error_messages)
            elif param.get('default'):
                # If GET parameter is in the request,
                # but has an empty value.
                value = param['default']
            else:
                continue

        try:
            assert param['type'] in _types_map, \
                'Type must be one of %s' % _types_map.keys()
            values[name] = _types_map[param['type']](value)
            if 'process' in param:
                values[name] = param['process'](values[name])
        except (TypeError, ValueError):
            _type = getattr(param['type'], '__name__', param['type'])
            _validation_error(param, 'value', name, error_messages, _type)
        if param.get('process'):
            values[name] = param['process'](values[name])

        error = _validate_by_type(param, values[name])
        if error:
            _validation_error(param, 'limits', name, error_messages, error)

        validator = param.get('validator', None)
        if validator:
            error = validator(values[name])
            if error:
                _validation_error(param, 'custom', name, error_messages, error)

    return values


def strip_wrapper(type_):
    def wrapper(value):
        if hasattr(value, 'strip'):
            return type_(value.strip())
        return type_(value)
    return wrapper


def _to_datetime(value):
        dt, tm = value.strip('Z').split('T')
        return datetime(*(
            map(int, dt.split('-')) +
            map(int, tm.split(':'))
        ))


_types_map = {
    'int': strip_wrapper(int),
    'unicode': unicode,
    'float': strip_wrapper(float),
    'decimal': strip_wrapper(Decimal),
    'date': strip_wrapper(lambda x: date(*map(int, x.split('-')))),
    'datetime': strip_wrapper(_to_datetime),
}

_types_limit_aliases = {
    'date': {
        'today': date.today,
        'tomorrow': lambda: date.today() + timedelta(days=1),
    }
}

_default_errors = {
    'required': '"%s" parameter is required',
    'value': '"%s" parameter must have a valid value of "%s" type',
    'limits': 'Value of "%s" %s',
    'custom': '"%s" parameter has a wrong value (%s)',
}


def _validation_error(param, code, key, messages, *args):
    if 'errors' in param and code in param['errors']:
        msg = param['errors'][code]
    elif messages and key in messages and code in messages[key]:
        msg = messages[key][code]
    else:
        _args = [key]
        _args.extend(args)
        msg = _default_errors[code] % tuple(_args)
    raise ValidationError(msg, key=key, code=code)


def _validate_by_type(param, value):
    """
    Helper provides value's validation by type.
    Used in Param and validate function.
    """
    if param['type'] == 'unicode':
        _value = len(value)
        messages = ('shorter', 'longer')
    else:
        _value = value
        messages = ('less', 'greater')
    if param.get('max') is not None:
        _max = _get_limit(param, param['max'])
        if _value > _max:
            return 'must be %s than %s' % (messages[0], str(param['max']))
    if param.get('min') is not None:
        _min = _get_limit(param, param['min'])
        if _value < _min:
            return 'must be %s than %s' % (messages[1], str(param['min']))


def _get_limit(param, value):
    if param['type'] in _types_limit_aliases and \
            value in _types_limit_aliases[param['type']]:
        return _types_limit_aliases[param['type']][value]()
    return value


class ValidationMixin(object):
    params = None
    error_messages = None

    def validate(self, data, params=None, error_messages=None):
        return validate(
            params or self.params,
            data,
            error_messages or self.error_messsages
        )