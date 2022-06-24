import random

from django.contrib.gis.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.widgets import HiddenInput
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from ordered_model.models import OrderedModel

from .formfields import formfield_registry


class BaseDynamicModel(models.Model):
    data = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        abstract = True

    @classmethod
    def get_fields(cls, company_site):
        return FieldModel.objects.filter(model=cls.__name__, company_site=company_site)

    @classmethod
    def getConcreteClasses(cls):
        """
            New-style classes automatically keep a weak reference to all of their child classes
            which can be accessed with the __subclasses__ method:
        """
        return cls.__subclasses__()

    @classmethod
    def getOptions(cls):
        return [(subClass.__name__, subClass._meta.verbose_name.title()) for subClass in
                cls.getConcreteClasses()]

    def getattr(self, name):
        if hasattr(self, name):
            return getattr(self, name)
        else:
            return name

    def getattr_display(self, name):
        if hasattr(self, 'get_%s_display' % name):
            return getattr(self, 'get_%s_display' % name)()
        elif hasattr(self, name):
            return getattr(self, name)
        else:
            return name


class BaseFieldModel(OrderedModel):
    model = models.CharField(max_length=20, verbose_name=_("Model"))

    label = models.CharField(max_length=250, verbose_name=_("Label"))
    name = models.SlugField(blank=True, null=True, verbose_name=_("DB Name"), max_length=250)
    field_type = models.CharField(_('Type'), max_length=255,
                                  choices=formfield_registry.get_as_choices())
    default = models.CharField(blank=True, null=True, max_length=200, default="",
                               verbose_name=_("Default"))
    required = models.BooleanField(default=False,
                                   verbose_name=_("Make this field a required entry"))
    options = models.JSONField(blank=True, verbose_name=_("Options"))

    class Meta(OrderedModel.Meta):
        unique_together = ("model", "name")
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._meta.get_field('model').choices = self.get_base_model().getOptions()

    def __str__(self):
        return self.label

    @staticmethod
    def get_base_model():
        return type("BaseDynamicModelClass",
                    (BaseDynamicModel,),
                    {'__module__': "apps.dynamic.models",
                     "Meta": type("Meta", (), {"abstract": True})})

    def get_field_type_display(self):
        field_type_cls = formfield_registry.get(self.field_type)
        if field_type_cls:
            return field_type_cls.get_display_label()

    def generate_form_field(self, form, value=None):
        field_type_cls = formfield_registry.get(self.field_type)
        if field_type_cls and field_type_cls.do_display_data():
            field = field_type_cls(**dict(value=value, **self.get_form_field_kwargs()))
            field.contribute_to_form(form)
            return field
        elif not self.visible:
            if self.name in form.fields:
                form.fields[self.name].widget = HiddenInput()

    def get_choices(self):
        field_type_cls = formfield_registry.get(self.field_type)
        try:
            field = field_type_cls(**self.get_form_field_kwargs())
            return field.get_choices()
        except (AttributeError, TypeError) as e:
            return []

    def get_display(self, value):
        field_type_cls = formfield_registry.get(self.field_type)
        try:
            field = field_type_cls(**self.get_form_field_kwargs())
            return field.get_display(value)
        except (AttributeError, TypeError):
            return

    def get_form_field_kwargs(self):
        kwargs = self.options
        kwargs.update({
            'name': self.name,
            'label': self.label
        })
        return kwargs

    def is_system(self):
        field_type_cls = formfield_registry.get(self.field_type)
        if field_type_cls is None:
            return False
        field = field_type_cls(**self.get_form_field_kwargs())
        return getattr(field, "is_system", False) is True

    def save(self, *args, **kwargs):
        if self.name == "" or self.name is None:
            self.name = slugify(self.label).replace("-", "_")[:120]

        if self.options is None:
            self.options = {}
        if self.name == "code":
            self.visible = True

        name = self.name
        if not self.id:
            while FieldModel.objects.filter(company_site=self.template,
                                            model=self.model,
                                            name=self.name).exclude(id=self.id).exists():
                self.name = name + str(random.randint(1, 99))

        for subClass in self.get_base_model().getConcreteClasses():
            if subClass.__name__ == self.model:
                if hasattr(subClass, self.name):
                    self.field_type = "sitehub.dynamic.formfields.SystemField"
                    self.options = {}

        if self.is_system():
            self.system = True

        super().save(*args, **kwargs)
