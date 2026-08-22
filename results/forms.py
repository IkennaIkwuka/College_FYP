from django import forms

from accounts.forms import BootstrapFormMixin


class ScoreEntryForm(BootstrapFormMixin, forms.Form):
    registration_id = forms.IntegerField(widget=forms.HiddenInput)
    score = forms.IntegerField(min_value=0, max_value=100, required=False)


ScoreEntryFormSet = forms.formset_factory(ScoreEntryForm, extra=0)
