from os import path

try:
    from django.conf import settings
    from django.http import HttpResponse as Response
    settings.DEBUG  # Try to get DEBUG to initialize lazy Django settings.
    IS_DJANGO = True
except ImportError:
    from werkzeug.wrappers import Response
    settings = object()
    IS_DJANGO = False

from .errors import ValidationError, NotFoundError, AuthError, \
    MultipleChoicesError
from .serializers import to_json, to_xml, to_jsonp


_serializers = {
    'xml': to_xml,
    'json': to_json,
    'jsonp': to_jsonp,
}

# Dict of MIME content types supported by API.
# Key of dict is a short name of MIME type, value is a full MIME type
# used as a value for HTTP header "Content-type".
MIME_TYPES = {
    'json': 'application/json',
    'jsonp': 'application/javascript',
    'xml': 'application/xml',
    'yaml': 'application/yaml',
    'csv': 'text/csv',
}

# List of HTTP methods.
# http://en.wikipedia.org/wiki/HTTP#Request_methods
# http://tools.ietf.org/html/rfc2616#page-51
HTTP_METHODS = {'get', 'post', 'put', 'delete', 'head', 'options', 'trace'}


def api_method(http_methods, content_types, is_secure=False,
               **serializer_params):
    if isinstance(content_types, basestring):
        content_types = [content_types]
    if isinstance(http_methods, basestring):
        http_methods = [http_methods]
    def wrapper(func):
        def _method(request, *args, **kwargs):
            http_method = request.method.lower()
            if http_method in http_methods and http_method in HTTP_METHODS:
                return process_api_method(
                    request, func, content_types, serializer_params,
                    *args, **kwargs
                )
            return _method_not_allowed(http_methods)
        return _method
    return wrapper


class ApiMethod(object):
    """
    Parent class for all API methods.
    Define "get" method to implement HTTP GET in your child class or "post"
    method to implemet HTTP POST and so on (like in Django class based views).
    Does all serialization job by default. To implement your own serialization
    for a particular MIME type, define to_<type> method
    (e.g. to_json or to_xml).

    Also ApiMethod's children are callable in Python directly. You can
    construct the object by passing current HttpRequest instance to __init__,
    and then call "get" or "post" of the object with necessary arguments.
    """

    # List of MIME content types supported by current API method.
    # Proposed to be overridden in methods implementation.
    # Values must exist in self.MIME_TYPES.
    content_types = {'json', 'xml'}

    # Content type of current instance of API method's class.
    # Detected automatically by current HttpRequest instance.
#    content_type = None

    # Name for root XML node. It will be used if serialized value isn't a dict.
    # E.g. {'killa': 'gorilla'} -> <killa>gorilla</killa>, but
    # 'gorilla' -> '<xml_root_node>gorilla</xml_root_node>'
    xml_root_node = None

    # Requires that client must be authenticated by standard Django
    # authentication: request.user.is_authenticated() == True.
    is_auth_required = False

    # Forces to use HTTPS for requesting API method.
    is_https_only = False

    # Dict to storing HTTP cookies. Use "set_cookie" method to set cookie
    # in your API method's code. Cookies will be set in response's rendering.
    _http_cookies = None

    # TODO: csrf option

    @classmethod
#    @csrf_exempt
    def view(cls, request, *args, **kwargs):
        """
        Shortcut method to use in urls.py.
        """
        api_obj = cls()
        api_obj.request = request
        return api_obj(*args, **kwargs)

    def __init__(self):
        self._http_cookies = []

    def __call__(self, *args, **kwargs):
        """
        Try to dispatch to the right HTTP method. If a method doesn't exist,
        defer to the error handler. Also defer to the error handler if the
        request method isn't on the approved list.
        """
#        if self.is_https_only and not self.request.is_secure() \
#                and getattr(settings, 'HTTPS_SUPPORT', False):
#            return self.error(403, 'This method is available by HTTPS only')

        http_method = self.request.method.lower()
        if 'HTTP_X_HTTP_METHOD_OVERRIDE' in self.request.META:
            http_method = \
                self.request.META['HTTP_X_HTTP_METHOD_OVERRIDE'].lower()
        else:
            http_method = self.request.method.lower()
        if http_method in self.HTTP_METHODS and hasattr(self, 'http_' + http_method):
            handler = getattr(self, http_method)
        else:
            handler = self._method_not_allowed

#        # Check authentication possibly provided by additional mixin classes.
#        if hasattr(self, 'authenticate'):
#            try:
#                self.authenticate()
#            except AuthError as e:
#                return self.error(403, str(e))

#        if self.is_auth_required and not self.request.user.is_authenticated():
#            return self.error(403, 'Forbidden')

        return process_api_method(
            self.request, handler, self.content_types,
            {'xml_root_node': self.xml_root_node}
        )

        if isinstance(data, HttpResponse):
            return data

        response = HttpResponse(self._serialize(data))
        if self.content_type == 'json' and \
                self.request.GET.get('_pretty'):
            _set_header(
                response, 'Content-Type', 'application/json; charset=utf-8'
            )
        else:
            response['Content-Type'] = self.MIME_TYPES[self.content_type]
        if getattr(self, 'http_status_code', None):
            response.status_code = self.http_status_code
        if self._http_cookies:
            for cookie in self._http_cookies:
                response.set_cookie(**cookie)
        return response


def process_api_method(request, handler, content_types, serializer_params,
                       *args, **kwargs):
    patch_request(request)
    content_type = _get_content_type(
        request, content_types,  *args, **kwargs
    )
    err_kwargs = {'content_type': content_type}

    try:
        data = handler(request, *args, **kwargs)
    except ValidationError as e:
        err_kwargs.update(e.__dict__)
        return _http_error(400, **err_kwargs)
    except NotFoundError as e:
        return _http_error(404, unicode(e), **err_kwargs)
    except AuthError as e:
        return _http_error(403, e.message, **err_kwargs)
    except MultipleChoicesError as e:
        err_kwargs.update(e.body)
        return _http_error(300, unicode(e), **err_kwargs)
    except Exception as e:
        if getattr(settings, 'API_DEBUG', False):
            raise
#        logger.exception(e)
        return _http_error(500, 'Unexpected API error', content_type=content_type)

    if content_type == 'jsonp' and 'jsonp_callback' not in serializer_params:
        serializer_params['jsonp_callback'] = request.args.get(
            'callback',
            request.form.get('callback', 'callback')
        )
    serializer_params['is_pretty'] = request.args.get(
        '_pretty',
        request.form.get('_pretty')
    )

    response = Response(
        _serializers[content_type](data, **serializer_params),
        content_type=MIME_TYPES[content_type]
    )
    if content_type.startswith('json') and serializer_params['is_pretty']:
        mime = 'application/json; charset=utf-8'
    else:
        mime = MIME_TYPES[content_type]
    _set_header(response, 'Content-Type', mime)
#    if getattr(self, 'http_status_code', None):
#        response.status_code = self.http_status_code
#    if self._http_cookies:
#        for cookie in self._http_cookies:
#            response.set_cookie(**cookie)

    return response


def patch_request(request):
    if IS_DJANGO:
        request.args = request.GET
        request.form = request.POST


def _set_header(response, header, value):
    if IS_DJANGO:
        response[header] = value
    else:
        response.headers[header] = value


def _serialize(request, data, content_type, **serializer_params):
    """
    Serializes API method's response by default or overriden in method's
    class serializer.
    Supported serializer_params:
        - is_pretty;
        - root_node (XML only);
        - callback (JSONP only).
    """
#    serializer = getattr(
#        self,
#        'to_' + self.content_type,
#        self._serializers.get(self.content_type, None)
#    )
    serializer = _serializers[content_type]
    if serializer:
        return serializer(data, **serializer_params)
    return data


def _get_content_type(request, content_types, *args, **kwargs):
    # Try to extract content_type from keyword arguments:
    # e.g. "/method/(?P<id>\d+)\.(?P<content_type>json|xml)" in Django's urls.py
    # or "/method/<int:id>/<string:content_type>" in Werkzeug's URL map.
    if 'content_type' in kwargs:
        content_type = kwargs.pop('content_type')
    # Try to extract content_type from arguments:
    # e.g. "/method/(\d+)\.(json|xml)" in Django's urls.py (Django only).
    # TODO: deprecate, because it can damage API method's a normal argument
    # if it accidentally contains value from "content_types".
    elif args and args[-1] in content_types:
        args = list(args)
        content_type = args.pop()
    else:
        try:
            # TODO: getting PATH_INFO in Django
            info = request.environ['PATH_INFO']
            content_type = path.splitext(info)[1].strip('.')
        except IndexError:
            raise AssertionError(
                'Content type of API method have to be specified'
                ' as an extension in the "path" part of URL'
            )
    assert content_type in content_types, \
        'Unsupported content type "%s"' % content_type
    assert content_type in MIME_TYPES, \
        'No MIME type for content type "%s"' % content_type
    assert content_type in _serializers, \
        'Non serializable content type "%s"' % content_type
    return content_type


def _http_error(status_code=400, message='', content_type=None, **kwargs):
    response = Response(status=status_code)
    if content_type:
        _set_header(response, 'Content-Type', MIME_TYPES[content_type])
        body = {}
        if message:
            body['message'] = message
        if kwargs:
            body.update(kwargs)
        if body:
            params = {}
            if content_type == 'xml':
                params['root_node'] = 'error'
            data = _serializers[content_type](body, **params)
    elif message:
        data = message
    if data:
        if IS_DJANGO:
            response.content = data
        else:
            response.data = data
    return response


def _method_not_allowed(allowed_methods):
    response = _http_error(405, 'Method Not Allowed')
    response['Allow'] = ', '.join(map(str.upper, allowed_methods))
    return response
