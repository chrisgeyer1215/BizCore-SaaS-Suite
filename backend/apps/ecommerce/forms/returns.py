from django import forms


class CreateReturnRequestForm(forms.Form):
    order_number = forms.CharField(max_length=50)
    items = forms.JSONField(help_text='List of items to return with quantities')
    reason = forms.CharField(max_length=255)
    comments = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)


class UpdateReturnStatusForm(forms.Form):
    status = forms.ChoiceField(choices=[
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ])
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)


