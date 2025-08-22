from django import forms


class DigitalDownloadAccessForm(forms.Form):
    email = forms.EmailField()
    order_number = forms.CharField(max_length=50)
    download_code = forms.CharField(max_length=100)


