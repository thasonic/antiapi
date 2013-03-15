from contextlib import nested
from logging import getLogger
from time import time

from .serializers import to_json, to_xml, inflector
from csv import excel
free_up_memory = __import__(
    'utils.cli', fromlist=('free_up_memory',)
).free_up_memory


_logger = getLogger('api.export')


class Exporter(object):
    files = None
    xml_root_node = 'entities'
    _counters = None
    FLUSH_AT = 1000

    def add_file(self, filename, file_format, mapper=None, lang=None):
        assert file_format in ('xml', 'json', 'jsono', 'csv')
        if self.files is None:
            self.files = []
        self.files.append({
            'name': filename,
            'format': file_format,
            'lang': lang,
            'mapper': mapper,
        })

    def __enter__(self):
        self._counters = {}
        for f in self.files:
            f['serialize'] = getattr(self, 'serialize_' + f['format'])
            if not f['mapper']:
                f['mapper'] = lambda entity: entity
            f['file'] = open(f['name'], 'w')
            if hasattr(self, f['format'] + '_prefix'):
                f['file'].write(
                    getattr(self, f['format'] + '_prefix')(f['lang'])
                )
            self._counters[f['name']] = 0

    def __exit__(self, *excinfo):
        for f in self.files:
            if hasattr(self, f['format'] + '_suffix'):
                f['file'].write(
                    getattr(self, f['format'] + '_suffix')(f['lang'])
                )
            if hasattr(f['file'], '__exit__'):
                f['file'].__exit__(*excinfo)

    def export_entity(self, *args, **kwargs):
        for f in self.files:
            self.file = f  # Current file available in serializer
            mapped = f['mapper'](f['lang'], *args, **kwargs)
            if mapped is not None:
                self._counter = self._counters[f['name']]  # Used in serializers
                f['file'].write(f['serialize'](mapped))
                self._counters[f['name']] += 1
                if not self._counters[f['name']] % self.FLUSH_AT:
                    f['file'].flush()

    def xml_prefix(self, lang):
        return '<?xml version="1.0" encoding="utf-8"?><%s>' % \
            self.xml_root_node

    def xml_suffix(self, lang):
        return '</%s>' % self.xml_root_node

    def json_prefix(self, lang):
        return '['

    def json_suffix(self, lang):
        return ']'

    def serialize_xml(self, obj):
        return to_xml(
            obj,
            inflector.singular_noun(self.xml_root_node) or 'entity',
            inc_header=False
        )

    def serialize_json(self, obj):
        return (',' if self._counter else '') + to_json(obj)

    def jsono_prefix(self, lang):
        return '[\n'

    def jsono_suffix(self, lang):
        return ']'

    def serialize_jsono(self, obj):
        return (',' if self._counter else '') + to_json(obj) + '\n'

    def serialize_csv(self, obj):
        return (excel.lineterminator if self._counter else '') + \
            excel.delimiter.join([
                excel.quotechar +
                unicode(obj[field]).encode('utf-8').replace(
                    excel.quotechar,
                    excel.quotechar + excel.quotechar
                ) + excel.quotechar
                for field in self.csv_fields_order
            ])


class DjangoModelExport(object):
    def __init__(self, model, batch_size=1000):
        pass


def export_django_model(outputs, model, batch_size=1000, fields=None,
                        logger=None, limit=None, **filters):
    """
    Export Django model's data iteratively by "batch_size" pieces.
    "Outputs" is array of Exporter-based objects provide "export_entity"
    method. "Fields" are list of model's fields to export. By default
    all fields will be exported.
    """
    if logger is None:
        logger = _logger
    if not hasattr(outputs, '__iter__'):
        outputs = (outputs, )
    qs = model.objects.order_by('pk')
    if filters:
        qs = qs.filter(**filters)
    if fields is None:
        qs = qs.values()
    else:
        qs = qs.values(*fields)
    cnt_all = 0

    logger.info('Started exporting of %s' % model.__name__)
    _start = time()
    with nested(*outputs):
        batch_num = 0
        last_id = None
        while True:
            start = time()
            if limit and cnt_all >= limit:
                break
            batch_num += 1
            if limit and batch_num * batch_size > limit:
                batch_size = limit - (batch_num - 1) * batch_size
            cnt_batch = 0
            if last_id is not None:
                chunk = tuple(qs.filter(pk__gt=last_id)[:batch_size])
            else:
                chunk = tuple(qs[:batch_size])
            if not len(chunk):
                break
            for entity in chunk:
                for output in outputs:
                    output.export_entity(entity)
                    cnt_all += 1
            last_id = chunk[-1]['id']
            cnt_batch += 1
            logger.info(
                'Batch %d has been processed (%d entities) in %0.3f sec' % (
                    batch_num, len(chunk), time() - start
                )
            )
            free_up_memory()
    logger.info('Done in %0.3f sec' % (time() - _start))


class AsIsExporter(Exporter):
    def __init__(self, file_name, format_):
        self.add_file(file_name, format_)
