from django import forms


class SubscriptionActionForm(forms.Form):
    subscription_id = forms.IntegerField()
    action = forms.ChoiceField(choices=[('pause', 'Pause'), ('cancel', 'Cancel'), ('resume', 'Resume')])
    reason = forms.CharField(max_length=255, required=False)


