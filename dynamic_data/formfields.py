# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import copy
import json
import re
from importlib import import_module
from json import JSONDecodeError

from django import forms
from django.utils.decorators import classonlymethod
from django.utils.translation import gettext_lazy as _

from .field import CommentBooleanWidget
from .utils import parse_bool_value


def format_display_label(cls_name):
    if cls_name.endswith('Field'):
        cls_name = cls_name[:-5]  # Strip trailing 'Field'

    # Precedes each group of capital letters by a whitespace except first
    return re.sub(r'([A-Z]+)', r' \1', cls_name).lstrip()


def load_class_from_string(cls_string):
    mod, cls = cls_string.rsplit('.', 1)
    module = import_module(mod)
    return getattr(module, cls)


class DynamicFormFieldRegistry(object):

    def __init__(self):
        self._fields = {}

    def get(self, key):
        return self._fields.get(key)

    def get_all(self):
        for k, c in sorted(self._fields.items()):
            yield {"value": k, "name": c.get_display_label()}

    def get_as_choices(self):
        for k, c in sorted(self._fields.items()):
            yield k, c.get_display_label()

    def register(self, cls):
        if not issubclass(cls, BaseDynamicFormField):
            raise ValueError('%r must inherit from %r' % (
                cls, BaseDynamicFormField))
        key = '%s.%s' % (cls.__module__, cls.__name__)
        self._fields[key] = cls

    def unregister(self, key):
        if key in self._fields:
            del self._fields[key]


formfield_registry = DynamicFormFieldRegistry()
dynamic_form_field_registry = formfield_registry


def dynamic_form_field(cls):
    """
    A class decorator to register the class as a dynamic form field in the
    :class:`DynamicFormFieldRegistry`.
    """
    formfield_registry.register(cls)
    return cls


class BaseCheckMetaclass(type):

    def __new__(mcs, name, bases, attrs):
        meta = attrs.pop('Meta', None)

        new_class = super(BaseCheckMetaclass, mcs).__new__(mcs, name, bases, attrs)

        opts = {}
        super_opts = getattr(new_class, '_meta', {})
        if meta:
            excludes = getattr(meta, '_exclude', ())
            # Copy all attributes from super's options not excluded here. No
            # need to check for leading _ as this is already sorted out on the
            # super class
            for k, v in super_opts.items():
                if k in excludes:
                    continue
                opts[k] = v
            # Copy all attributes not starting with a '_' from this Meta class
            for k, v in meta.__dict__.items():
                if k.startswith('_') or k in excludes:
                    continue
                opts[k] = v
        else:
            opts = copy.deepcopy(super_opts)
        setattr(new_class, '_meta', opts)
        return new_class


class BaseDynamicFormField(metaclass=BaseCheckMetaclass):
    cls = None
    display_label = None
    widget = None

    class Meta:
        help_text = [str, '', (forms.CharField, forms.Textarea)]
        required = [bool, False, forms.BooleanField]

    def __new__(cls, *args, **kwargs):
        self = super(BaseDynamicFormField, cls).__new__(cls)
        self._meta = copy.deepcopy(self.__class__._meta)
        return self

    def __init__(self, name, label, value=None, widget_attrs=None, **kwargs):
        self.name = name
        self.label = label
        self.widget_attrs = widget_attrs or {}
        self.value = value
        self.set_options(**kwargs)

    def get_cls(self):
        return self.cls

    def get_kwargs(self):
        args = {}
        for key, val in self.options.items():
            args[key] = val[1]
        return args

    def __str__(self):
        if isinstance(self.get_cls(), str):
            clsname = self.get_cls()
        else:
            clsname = '%s.%s' % (self.get_cls().__module__, self.get_cls().__name__)
        return '<%(class)s, name=%(name)s, label=%(label)s>' % {
            'class': clsname,
            'name': self.name,
            'label': self.label,
        }

    def construct(self, **kwargs):
        if isinstance(self.get_cls(), str):
            cls_type = load_class_from_string(self.get_cls())
        else:
            cls_type = self.get_cls()

        f_kwargs = self.get_kwargs()

        f_kwargs['label'] = self.label

        if self.widget is not None:
            if isinstance(self.widget, str):
                widget_type = load_class_from_string(self.widget)
            else:
                widget_type = self.widget
            f_kwargs['widget'] = widget_type(**self.get_widget_attrs())

        f_kwargs["initial"] = self.get_initial_value()

        kwargs["required"] = False
        f_kwargs.update(kwargs)  # Update the field kwargs by those given

        return cls_type(**f_kwargs)

    def get_initial_value(self):
        return self.value

    def contribute_to_form(self, form):
        form.fields[self.name] = self.construct()

    @classonlymethod
    def get_display_label(cls):
        if cls.display_label:
            return cls.display_label
        return format_display_label(cls.__name__)

    @property
    def options(self):
        return self._meta

    def get_widget_attrs(self):
        return self.widget_attrs

    def set_options(self, **kwargs):
        for key, value in kwargs.items():
            if key not in self.options:
                raise KeyError('%s is not a valid option.' % key)

            expected_types = self.options[key][0]
            if type(expected_types) != list and type(expected_types) != tuple:
                expected_types = [expected_types, ]
            if type(value) not in expected_types and value is not None:
                # if not isinstance(value, expected_type) and value is not None:
                raise TypeError('Neither of type %r nor None' % str(expected_types))

            self.options[key][1] = value
        self.options_valid()

    def options_valid(self):
        return True

    @classonlymethod
    def do_display_data(cls):
        return True

    def get_display(self, objeto, value=None):
        return objeto.data.get(self.name)


@dynamic_form_field
class BooleanField(BaseDynamicFormField):
    cls = 'django.forms.BooleanField'
    display_label = _('Boolean')

    def get_cls(self):
        # tengo que retornar solo charfield, porque sino al limpiar el campo borra el valor porque no s eparece a lo que guarda
        return 'django.forms.CharField'
        # if self.options["has_comment"][1]:
        #
        # if self.options["not_avaliable"][1]:
        #     return "django.forms.NullBooleanField"
        # return self.cls

    def get_options(self):
        return (
            (1, _("N/A")),
            (3, _("Yes")),
            (2, _("No"))
        )

    def get_kwargs(self):
        args = {}
        options = self.options

        widget = forms.RadioSelect(choices=(
            (3, _("Yes")),
            (2, _("No"))
        ))

        if self.options["not_avaliable"][1]:
            widget = forms.RadioSelect(choices=self.get_options())

        args["widget"] = CommentBooleanWidget(widget=widget, has_comment=self.options["has_comment"][1])

        del (options["not_avaliable"])
        del (options["has_comment"])
        for key, val in options.items():
            args[key] = val[1]
        return args

    class Meta:
        _exclude = ('required',)
        has_comment = [bool, False, forms.BooleanField]
        not_avaliable = [bool, False, forms.BooleanField]

    def construct(self, **kwargs):
        return super(BooleanField, self).construct(required=False)

    def get_display_boolean(self, boolean):
        return dict(self.get_options()).get(boolean, "")

    def get_display(self, objeto, value=None):
        value = objeto.data.get(self.name)
        try:
            json_obj = json.loads(value)
            bool = self.get_display_boolean(parse_bool_value(json_obj['bool']))

            if self.options["has_comment"][1]:
                return f"{bool}. Comment: {json_obj['comment']}"
            else:
                return f"{bool}"
        except (JSONDecodeError, TypeError):
            return self.get_display_boolean(parse_bool_value(value))


@dynamic_form_field
class ChoiceField(BaseDynamicFormField):
    cls = 'django.forms.ChoiceField'
    display_label = _('Choices')

    class Meta:
        choices = [[list, str, ], '', (forms.CharField, forms.Textarea)]

    def get_choices(self, array=False):
        value = self.options.get('choices')[1]
        choices = []
        if type(value) == str:
            try:
                value = json.loads(value)
            except JSONDecodeError:
                return []
        if array:
            return value
        for row in value:
            choices.append((row, row))
        return choices

    def get_choice_display(self, value):
        for choice in self.get_choices():
            if choice[0] == value:
                return value
        return None

    def get_display(self, objeto, value=None):
        return self.get_choice_display(objeto.data.get(self.name))

    def get_initial_value(self):
        choices = self.get_choices(True)
        if self.value in choices:
            return self.value
        else:
            try:
                value = int(self.value)
                return choices[value]
            except (ValueError, TypeError):
                pass

    def construct(self, **kwargs):
        choices = self.get_choices()
        if self.options["required"][1] is False:
            choices = [("", "---------"), ] + choices
        return super(ChoiceField, self).construct(choices=choices)

    def options_valid(self):
        if not self.options['choices'] or not self.options['choices'][1]:
            return False
        return True


@dynamic_form_field
class MultipleChoiceField(ChoiceField):
    cls = 'django.forms.MultipleChoiceField'
    display_label = _('Multiple Choices')

    def get_choice_display(self, value):
        if value is None:
            return ""
        if type(value) != list:
            value = [value]
        values = []
        for choice in self.get_choices():
            if choice[0] in value:
                values.append(choice[1])
        return ", ".join(values)

    def get_initial_value(self):
        choices = self.get_choices(True)
        if type(self.value) is list:
            return self.value
        else:
            try:
                value = [choices[int(v)] for v in self.value.split(",")]
                return value
            except AttributeError:
                pass

    def construct(self, **kwargs):
        return super(ChoiceField, self).construct(choices=self.get_choices())


@dynamic_form_field
class DateField(BaseDynamicFormField):
    cls = 'django.forms.DateField'
    display_label = _('Date')

    class Meta:
        localize = [bool, True, forms.BooleanField]


@dynamic_form_field
class DateTimeField(BaseDynamicFormField):
    cls = 'django.forms.DateTimeField'
    display_label = _('Date and Time')

    class Meta:
        localize = [bool, True, forms.NullBooleanField]



@dynamic_form_field
class EmailField(BaseDynamicFormField):
    cls = 'django.forms.EmailField'
    display_label = _('Email')


@dynamic_form_field
class IntegerField(BaseDynamicFormField):
    cls = 'django.forms.IntegerField'
    display_label = _('Integer')
    widget = forms.NumberInput

    class Meta:
        localize = [bool, False, forms.NullBooleanField]
        max_value = [int, None, forms.IntegerField]
        min_value = [int, None, forms.IntegerField]
        slide = [bool, False, forms.BooleanField]

    def get_widget_attrs(self):
        widget_attrs = super().get_widget_attrs()
        if self.options["slide"][1]:
            widget_attrs["attrs"] = {'type': 'range'}
        return widget_attrs

    def get_kwargs(self):
        args = {}
        options = self.options

        for key, val in options.items():
            if key != "slide":
                args[key] = val[1]
        return args


@dynamic_form_field
class FloatField(BaseDynamicFormField):
    cls = 'django.forms.FloatField'
    display_label = _('Float')

    class Meta:
        localize = [bool, False, forms.NullBooleanField]
        max_value = [int, None, forms.IntegerField]
        min_value = [int, None, forms.IntegerField]


@dynamic_form_field
class MultiLineTextField(BaseDynamicFormField):
    cls = 'django.forms.CharField'
    display_label = _('Multi Line Text')
    widget = 'django.forms.widgets.Textarea'


@dynamic_form_field
class SingleLineTextField(BaseDynamicFormField):
    cls = 'django.forms.CharField'
    display_label = _('Single Line Text')

    class Meta:
        max_length = [int, None, forms.IntegerField]
        min_length = [int, None, forms.IntegerField]


@dynamic_form_field
class TimeField(BaseDynamicFormField):
    cls = 'django.forms.TimeField'
    display_label = _('Time')

    class Meta:
        localize = [bool, True, forms.NullBooleanField]


@dynamic_form_field
class SystemField(BaseDynamicFormField):
    cls = 'django.forms.BooleanField'
    display_label = _('System')
    is_system = True

    class Meta:
        _exclude = ('required',)

    @classonlymethod
    def do_display_data(cls):
        return False

    def get_display(self, objeto, value=None):

        if hasattr(objeto, self.name):
            return getattr(objeto, self.name)


@dynamic_form_field
class ComponentField(BaseDynamicFormField):
    cls = 'sitehub.dynamic.field.ComponentField'
    display_label = _('Component')
    is_system = True

    class Meta:
        _exclude = ('required',)

    def get_display(self, objeto, value=None):
        if hasattr(objeto, self.name):
            return getattr(objeto, self.name)


@dynamic_form_field
class SubtitleField(BaseDynamicFormField):
    cls = 'sitehub.dynamic.field.SubtitleField'
    display_label = _('Subtitle')

    class Meta:
        _exclude = ('required', "help_text")

    def get_display(self, objeto, value=None):
        if hasattr(objeto, self.name):
            return getattr(objeto, self.name)
