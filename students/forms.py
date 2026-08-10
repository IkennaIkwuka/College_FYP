from accounts.forms import BootstrapFormMixin
from django import forms


class BulkImportForm(BootstrapFormMixin, forms.Form):
    csv_file = forms.FileField(label="CSV file")
