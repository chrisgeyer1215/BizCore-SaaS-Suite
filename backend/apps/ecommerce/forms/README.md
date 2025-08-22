# Ecommerce Forms Package

This package contains comprehensive forms for the ecommerce module, organized by functionality and designed for multi-tenant SaaS applications.

## 📁 Package Structure

```
forms/
├── __init__.py          # Main package imports
├── products.py          # Product management forms
├── collections.py       # Collection management forms
├── cart.py             # Shopping cart forms
├── checkout.py         # Checkout process forms
├── orders.py           # Order management forms
├── reviews.py          # Product review forms
├── customers.py        # Customer management forms
├── discounts.py        # Discount and coupon forms
├── shipping.py         # Shipping and fulfillment forms
├── admin.py            # Admin and settings forms
├── utils.py            # Utility and helper forms
├── stubs.py            # Placeholder forms for future models
└── README.md           # This documentation
```

## 🚀 Available Forms

### **Products (`products.py`)**
- `EcommerceProductForm` - Main product creation/editing
- `ProductVariantForm` - Product variant management
- `ProductOptionForm` - Product option configuration
- `ProductOptionValueForm` - Product option values
- `ProductImageForm` - Product image management
- `ProductBundleForm` - Product bundle creation
- `BundleItemForm` - Bundle item management
- `ProductSEOForm` - SEO optimization
- `ProductTagForm` - Product tagging
- `ProductMetricForm` - Product metrics
- `ProductQuickAddForm` - Quick product addition

### **Collections (`collections.py`)**
- `CollectionForm` - Collection creation/editing
- `CollectionProductForm` - Collection-product relationships
- `CollectionRuleForm` - Collection automation rules
- `CollectionImageForm` - Collection image management
- `CollectionSEOForm` - Collection SEO
- `CollectionMetricsForm` - Collection performance metrics

### **Cart (`cart.py`)**
- `AddToCartForm` - Add products to cart
- `UpdateCartItemForm` - Modify cart items
- `RemoveCartItemForm` - Remove items from cart
- `ApplyCouponForm` - Apply discount coupons
- `CartShippingAddressForm` - Cart shipping setup
- `AddToWishlistForm` - Add to wishlist
- `UpdateWishlistItemForm` - Modify wishlist items
- `SavedForLaterForm` - Save items for later
- `CartAbandonmentEventForm` - Track cart abandonment
- `CartShareForm` - Share cart with others

### **Checkout (`checkout.py`)**
- `CheckoutCustomerForm` - Customer information
- `AddressForm` - Address management
- `CheckoutShippingForm` - Shipping options
- `CheckoutPaymentForm` - Payment processing
- `OrderReviewForm` - Final order confirmation

### **Orders (`orders.py`)**
- `GuestOrderLookupForm` - Guest order tracking
- `CancelOrderForm` - Order cancellation
- `OrderModificationForm` - Order modifications
- `OrderTrackingForm` - Order tracking
- `OrderFeedbackForm` - Order feedback

### **Reviews (`reviews.py`)**
- `AddProductReviewForm` - Product review submission
- `ReviewVoteForm` - Review helpfulness voting
- `ReviewReportForm` - Report inappropriate reviews
- `ReviewModerationForm` - Admin review moderation

### **Customers (`customers.py`)**
- `CustomerRegistrationForm` - Customer account creation
- `CustomerProfileForm` - Profile management
- `CustomerAddressForm` - Address management
- `CustomerPreferencesForm` - Customer preferences

### **Discounts (`discounts.py`)**
- `DiscountForm` - Discount creation
- `CouponForm` - Coupon code management
- `ApplyCouponForm` - Apply coupons
- `BulkDiscountForm` - Bulk discount application
- `SeasonalDiscountForm` - Seasonal promotions

### **Shipping (`shipping.py`)**
- `ShippingMethodForm` - Shipping method setup
- `ShippingRateForm` - Rate configuration
- `ShippingZoneForm` - Geographic zones
- `FulfillmentForm` - Order fulfillment
- `AddressValidationForm` - Address validation
- `ShippingCalculatorForm` - Cost calculation
- `InternationalShippingForm` - International shipping

### **Admin (`admin.py`)**
- `EcommerceSettingsForm` - Store settings
- `StoreAppearanceForm` - Visual customization
- `NotificationSettingsForm` - Notification preferences

### **Utils (`utils.py`)**
- `ProductSearchForm` - Product search
- `ProductFilterForm` - Advanced filtering
- `BulkActionForm` - Bulk operations
- `ImportExportForm` - Data import/export
- `AnalyticsFilterForm` - Analytics filtering

## ✨ Key Features

### **Multi-Tenant Support**
- All forms are tenant-aware
- Proper isolation between different stores
- Tenant-specific validation rules

### **Advanced Validation**
- Business logic validation
- Cross-field validation
- Custom error messages
- Data integrity checks

### **User Experience**
- Bootstrap-compatible CSS classes
- Helpful placeholder text
- Comprehensive help text
- Intuitive field organization

### **Flexibility**
- Dynamic field choices
- Conditional field display
- Custom widget attributes
- Extensible form classes

## 🔧 Usage Examples

### **Basic Product Form**
```python
from apps.ecommerce.forms import EcommerceProductForm

# Create a new product
form = EcommerceProductForm(data=request.POST, files=request.FILES)
if form.is_valid():
    product = form.save(commit=False)
    product.tenant = request.tenant
    product.save()
```

### **Cart Operations**
```python
from apps.ecommerce.forms import AddToCartForm

# Add item to cart
form = AddToCartForm(data=request.POST)
if form.is_valid():
    product_id = form.cleaned_data['product_id']
    quantity = form.cleaned_data['quantity']
    # Process cart addition
```

### **Search and Filtering**
```python
from apps.ecommerce.forms import ProductSearchForm

# Search products
form = ProductSearchForm(data=request.GET)
if form.is_valid():
    query = form.cleaned_data['query']
    price_min = form.cleaned_data['price_min']
    # Perform search
```

## 🚧 Future Enhancements

The following forms are currently stubs and will be implemented when their models are created:

- **Digital Products**: Digital download management
- **Subscriptions**: Recurring billing forms
- **Returns**: Return and refund processing

## 📋 Form Validation

All forms include comprehensive validation:

- **Required Fields**: Proper required field handling
- **Data Types**: Type validation and conversion
- **Business Rules**: Domain-specific validation logic
- **Cross-Validation**: Field relationship validation
- **Error Messages**: User-friendly error descriptions

## 🎨 Styling

Forms are designed to work with Bootstrap CSS framework:

- `form-control` class for inputs
- `form-select` for dropdowns
- Responsive design considerations
- Consistent spacing and layout

## 🔒 Security

- CSRF protection enabled
- Input sanitization
- SQL injection prevention
- XSS protection
- Proper permission checks

## 📱 Responsive Design

- Mobile-friendly form layouts
- Touch-optimized inputs
- Responsive grid systems
- Accessible form elements

## 🚀 Performance

- Efficient form rendering
- Minimal database queries
- Optimized validation
- Caching considerations

---

**Note**: This forms package is designed to work with the existing ecommerce models. When implementing new models, ensure to create corresponding forms and update the `__init__.py` file accordingly.
