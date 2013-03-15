from datetime import date, datetime
from decimal import Decimal
from unittest.case import TestCase

from antiapi.errors import ValidationError
from antiapi.validation import Param, validate


class TestParam(TestCase):
    """
    Test all possible data types for Param class.
    """
    def test_wrong_type(self):
        self.assertRaises(AssertionError, Param, type='KillaGorilla')

    def test_int_type(self):
        min_value = 0
        max_value = 10
        param = Param(type='int', min=min_value, max=max_value)
        # Test to_value
        self.assertEqual(param.to_value(3), 3)
        self.assertEqual(param.to_value('3'), 3)
        self.assertRaises(ValueError, lambda: param.to_value('aa'))
        self.assertRaises(TypeError, lambda: param.to_value(None))
        # Test validate
        self.assertEqual(param.validate(1), None)
        self.assertEqual(
            param.validate(-1),
            'must be greater than %s' % str(min_value)
        )
        self.assertEqual(param.validate(10), None)
        self.assertEqual(
            param.validate(11),
            'must be less than %s' % str(max_value)
        )

    def test_unicode_type(self):
        min_value = 1
        max_value = 4
        param = Param(type='unicode', min=min_value, max=max_value)
        # Test to_value
        self.assertEqual(param.to_value('a'), 'a')
        self.assertEqual(param.to_value(3), '3')
        self.assertRaises(TypeError, lambda: param.to_value(None))
        # Test validate
        self.assertEqual(param.validate('a'), None)
        self.assertEqual(
            param.validate(''),
            'must be longer than %s' % str(min_value)
        )
        self.assertEqual(param.validate('aaaa'), None)
        self.assertEqual(
            param.validate('aaaaa'),
            'must be shorter than %s' % str(max_value)
        )

    def test_float_type(self):
        min_value = 0.1
        max_value = 0.9
        param = Param(type='float', min=min_value, max=max_value)
        # Test to_value
        self.assertEqual(param.to_value('0.5'), 0.5)
        self.assertEqual(param.to_value(3), 3.0)
        self.assertEqual(param.to_value(2.0), 2.0)
        self.assertRaises(TypeError, lambda: param.to_value(None))
        # Test validate
        self.assertEqual(param.validate(0.1), None)
        self.assertEqual(
            param.validate(0.09),
            'must be greater than %s' % str(min_value)
        )
        self.assertEqual(param.validate(0.9), None)
        self.assertEqual(
            param.validate(0.91),
            'must be less than %s' % str(max_value)
        )

    def test_decimal_type(self):
        min_value = Decimal(1.25)
        max_value = Decimal(5.25)
        param = Param(type='decimal', min=min_value, max=max_value)
        # Test to_value
        self.assertEqual(param.to_value('0.5'), 0.5)
        self.assertEqual(param.to_value(3), Decimal(3.0))
        self.assertEqual(param.to_value(2.0), Decimal(2.0))
        self.assertRaises(TypeError, lambda: param.to_value(None))
        # Test validate
        self.assertEqual(param.validate(Decimal(1.25)), None)
        self.assertEqual(
            param.validate(Decimal(1.24)),
            'must be greater than %s' % str(min_value)
        )
        self.assertEqual(param.validate(Decimal(5.25)), None)
        self.assertEqual(
            param.validate(Decimal(5.26)),
            'must be less than %s' % str(max_value)
        )

    def test_date_type(self):
        min_value = date(2012, 1, 1)
        max_value = date(2012, 12, 31)
        param = Param(type='date', min=min_value, max=max_value)
        # Test to_value
        self.assertEqual(param.to_value('2012-07-07'), date(2012, 7, 7))
        self.assertRaises(TypeError, lambda: param.to_value(None))
        # Test validate
        self.assertEqual(param.validate(date(2012, 1, 1)), None)
        self.assertEqual(
            param.validate(date(2011, 12, 31)),
            'must be greater than %s' % str(min_value)
        )
        self.assertEqual(param.validate(date(2012, 12, 31)), None)
        self.assertEqual(
            param.validate(date(2013, 1, 1)),
            'must be less than %s' % str(max_value)
        )


class TestValidation(TestCase):
    def test(self):
        params = {
            'p1': {'type': 'int', 'required': True, 'min': 0, 'max': 10},
            'p2': {'type': 'unicode', 'required': True, 'min': 1, 'max': 4},
            'p3': {'type': 'float', 'required': True, 'min': 0.1, 'max': 0.9},
            'p4': {
                'type': 'decimal',
                'min': Decimal(1.25),
                'max': Decimal(5.25)
            },
            'p5': {
                'type': 'date',
                'min': date(2012, 1, 1),
                'max': date(2012, 12, 31)
            },
            'p6': {
                'type': 'datetime',
                'min': datetime(2012, 1, 1, 11, 0),
                'max': datetime(2012, 12, 31, 16, 59)
            },
        }
        data = validate(params, {
            'p1': '1',
            'p2': 2,
            'p3': 0.3,
            'p4': '1.3',
            'p5': '2012-01-01',
            'p6': '2012-06-30T12:42:38',
        })
        self.assertEqual(data, {
            'p1': 1,
            'p2': '2',
            'p3': 0.3,
            'p4': Decimal('1.3'),
            'p5': date(2012, 1, 1),
            'p6': datetime(2012, 6, 30, 12, 42, 38),
        })

    def test_default_value(self):
        # Check setting default value for empty input data.
        params = {
            'field': {'type': 'unicode', 'default': 'value'}
        }
        valid_data = validate(params, {})
        self.assertIn('field', valid_data)
        self.assertEqual(valid_data['field'], 'value')

        # Check setting default value for required parameter.
        params['field']['required'] = True
        valid_data = validate(params, {})
        self.assertIn('field', valid_data)
        self.assertEqual(valid_data['field'], 'value')

        # Check overriding default value by input's data.
        valid_data = validate(params, {'field': 1})
        self.assertIn('field', valid_data)
        self.assertEqual(valid_data['field'], '1')

    def test_custom_validator(self):
        custom_error = 'must be non zero'
        param_name = 'field'
        param = {
            'type': 'int',
            'validator': lambda value: None if value else custom_error
        }
        params = {param_name: param}
        self.assertRaises(ValidationError, validate, params, {param_name: '0'})
        try:
            validate(params, {param_name: '0'})
        except ValidationError as e:
            self.assertEqual(
                e.message,
                '"%s" parameter has a wrong value (%s)' % (
                    param_name, custom_error
                )
            )
            self.assertEqual(e.key, param_name)
            self.assertEqual(e.code, 'custom')
        self.assertEqual(validate(params, {param_name: '1'}), {param_name: 1})

    def test_messaging(self):
        # Passing error message by param's property "errors".
        param_name = 'field'
        param = {
            'type': 'int',
            'required': True,
            'errors': {'required': 'GOSHA'},
        }
        params = {param_name: param}
        self.assertRaises(ValidationError, validate, params, {})
        try:
            validate(params, {})
        except ValidationError as e:
            self.assertEqual(e.message, param['errors']['required'])
            self.assertEqual(e.key, param_name)
            self.assertEqual(e.code, 'required')