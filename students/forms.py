from django import forms


class BulkImportForm(forms.Form):
    csv_file = forms.FileField(label="CSV file")
