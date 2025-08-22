from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class AddProductReviewForm(forms.Form):
    """Form for adding product reviews."""
    rating = forms.ChoiceField(
        choices=[
            (5, '⭐⭐⭐⭐⭐ Excellent'),
            (4, '⭐⭐⭐⭐ Very Good'),
            (3, '⭐⭐⭐ Good'),
            (2, '⭐⭐ Fair'),
            (1, '⭐ Poor'),
        ],
        widget=forms.RadioSelect,
        help_text='Rate your experience with this product'
    )
    title = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Review title (optional)'
        })
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 6,
            'class': 'form-control',
            'placeholder': 'Share your experience with this product...'
        }),
        help_text='Tell others about your experience'
    )
    images = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'multiple': True,
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text='Upload images (optional, max 5 images)'
    )
    pros = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'form-control',
            'placeholder': 'What did you like about this product?'
        })
    )
    cons = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'form-control',
            'placeholder': 'What could be improved?'
        })
    )
    recommend = forms.ChoiceField(
        choices=[
            ('yes', 'Yes, I recommend this product'),
            ('no', 'No, I do not recommend this product'),
            ('maybe', 'Maybe, with some reservations'),
        ],
        widget=forms.RadioSelect,
        help_text='Would you recommend this product to others?'
    )
    verified_purchase = forms.BooleanField(
        required=False,
        initial=True,
        help_text='I purchased this product'
    )
    
    def clean_images(self):
        images = self.files.getlist('images')
        if len(images) > 5:
            raise ValidationError('You can upload a maximum of 5 images.')
        
        for image in images:
            if image.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError(f'Image {image.name} is too large. Maximum size is 5MB.')
        
        return images


class ReviewVoteForm(forms.Form):
    """Form for voting on reviews."""
    review_id = forms.IntegerField(
        widget=forms.HiddenInput()
    )
    vote = forms.ChoiceField(
        choices=[
            ('up', '👍 Helpful'),
            ('down', '👎 Not Helpful'),
        ],
        widget=forms.RadioSelect
    )
    reason = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Why is this review helpful/not helpful? (optional)'
        })
    )


class ReviewReportForm(forms.Form):
    """Form for reporting inappropriate reviews."""
    review_id = forms.IntegerField(
        widget=forms.HiddenInput()
    )
    reason = forms.ChoiceField(
        choices=[
            ('inappropriate', 'Inappropriate content'),
            ('spam', 'Spam or fake review'),
            ('offensive', 'Offensive language'),
            ('irrelevant', 'Not relevant to the product'),
            ('duplicate', 'Duplicate review'),
            ('other', 'Other'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Please provide additional details about why you are reporting this review...'
        }),
        help_text='Additional details help us take appropriate action'
    )
    contact_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your email (optional, for follow-up)'
        })
    )


class ReviewModerationForm(forms.Form):
    """Form for moderators to manage reviews."""
    action = forms.ChoiceField(
        choices=[
            ('approve', 'Approve Review'),
            ('reject', 'Reject Review'),
            ('edit', 'Edit Review'),
            ('delete', 'Delete Review'),
            ('flag', 'Flag for Review'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    moderation_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Internal notes about this moderation action...'
        }),
        required=False
    )
    notify_user = forms.BooleanField(
        initial=True,
        required=False,
        help_text='Send notification to the review author'
    )
    rejection_reason = forms.ChoiceField(
        choices=[
            ('', 'Select a reason'),
            ('inappropriate', 'Inappropriate content'),
            ('spam', 'Spam or fake review'),
            ('offensive', 'Offensive language'),
            ('irrelevant', 'Not relevant to the product'),
            ('duplicate', 'Duplicate review'),
            ('policy_violation', 'Violates review policy'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


