import json
from json import JSONDecodeError

from django import forms

from .utils import parse_bool_value


class DivWidget(forms.Widget):
    template_name = 'form/widgets/div.html'

    def __init__(self, attrs=None):
        # Use slightly better defaults than HTML's 20x2 box
        default_attrs = {'cols': '40', 'rows': '10'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class ComponentField(forms.Field):
    widget = DivWidget


class SubtitleWidget(forms.Widget):
    template_name = 'form/widgets/subtitle.html'


class SubtitleField(forms.Field):
    widget = SubtitleWidget


class CommentBooleanWidget(forms.MultiWidget):
    def __init__(self, attrs=None, widget=forms.CheckboxInput(), has_comment=False):
        if attrs is None:
            attrs = {}
        _widgets = [widget, ]
        if has_comment:
            _widgets.append(forms.TextInput())
        super().__init__(_widgets, attrs)

    def decompress(self, value):
        try:
            value = json.loads(value)
            value["bool"] = parse_bool_value(value["bool"])
            if value:
                return [value["bool"], value["comment"]]
        except (TypeError, JSONDecodeError):
            pass
        return [parse_bool_value(value), ""]

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['wrap_label'] = True
        return context

    def value_from_datadict(self, data, files, name):

        values = [
            widget.value_from_datadict(data, files, name + '_%s' % i)
            for i, widget in enumerate(self.widgets)]
        values[0] = parse_bool_value(values[0])
        return json.dumps({"bool": values[0], "comment": values[1] if len(values) == 2 else ""})
