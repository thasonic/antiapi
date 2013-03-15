# coding: utf-8

from base64 import b64encode
from hashlib import sha256
from random import getrandbits, choice

from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist


def keygen():
    """
    Generates a random string of 43 symbols by very impressive algorithm.
    """
    return b64encode(
        sha256(str(getrandbits(256))).digest(),
        choice(['rA', 'aZ', 'gQ', 'hH', 'hG', 'aR', 'DD'])
    ).rstrip('=')


class SerializableMixin(object):
    def serialize(self):
        """
        Returns only valuable fields of Django model's __dict__.
        """
        return {
            k: v
            for k, v in self.__dict__.viewitems()
            if not k.startswith('_')
        }

    @classmethod
    def deserialize(cls, dict_):
        return cls(**dict_)


class AuthKeyMixin(SerializableMixin):
    CACHE_TTL = 3600

    def save(self, *args, **kwargs):
        """
        Generates a new auth key.
        """
        if not self.key and not kwargs.pop('force_empty_key', False):
            for _ in xrange(50):
                key = keygen()
                if not self.__class__.objects.filter(key=key).exists():
                    self.key = key
                    break
            # Prevent endless cycle
            if not self.key:
                raise AssertionError(
                    'keygen() returned not unique value 50 times'
                )
        return super(AuthKeyMixin, self).save(*args, **kwargs)

    @classmethod
    def get_key(cls, key_id):
        cache_key = cls._cache_key(cls.__name__, key_id)
        data = cache.get(cache_key)
        if data:
            return cls.deserialize(data)

        if hasattr(cls, 'key_queryset'):
            qs = cls.key_queryset()
        else:
            qs = cls.objects
        try:
            auth_key = qs.get(pk=key_id)
        except (ObjectDoesNotExist, ValueError):
            # ValueError are thrown by non integer key_id.
            raise ValueError('Non existent key with id=%s' % str(key_id))
        cache.set(
            cache_key,
            auth_key.serialize(),
            cls.CACHE_TTL
        )
        return auth_key

    def drop_cache(self):
        cache_key = self._cache_key(self.__class__.__name__, self.id)
        cache.delete(cache_key)

    @classmethod
    def drop_all_cache(cls):
        for key_id in cls.objects.values_list('id', flat=True).all():
            cache_key = cls._cache_key(cls.__name__, key_id)
            cache.delete(cache_key)

    @staticmethod
    def _cache_key(class_name, key_id):
        return 'API_KEY_%s_%s' % (class_name, key_id)
