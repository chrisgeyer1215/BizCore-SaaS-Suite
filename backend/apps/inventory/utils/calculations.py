import math
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import List, Dict, Any, Tuple, Optional, Union
from .constants import DEFAULT_VALUES, BUSINESS_RULES

def calculate_eoq(annual_demand: Union[Decimal, float], 
                 ordering_cost: Union[Decimal, float],
                 holding_cost_per_unit: Union[Decimal, float]) -> Decimal:
    """
    Calculate Economic Order Quantity (EOQ)
    
    Formula: EOQ = sqrt((2 * D * S) / H)
    Where:
    - D = Annual demand
    - S = Ordering cost per order
    - H = Holding cost per unit per year
    """
    try:
        demand = float(annual_demand)
        order_cost = float(ordering_cost)
        holding_cost = float(holding_cost_per_unit)
        
        if demand <= 0 or order_cost <= 0 or holding_cost <= 0:
            return Decimal('0')
        
        eoq = math.sqrt((2 * demand * order_cost) / holding_cost)
        return Decimal(str(eoq)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

def calculate_safety_stock(average_daily_usage: Union[Decimal, float],
                          lead_time_days: int,
                          service_level: float = 0.95,
                          demand_variability: Union[Decimal, float] = None,
                          lead_time_variability: int = None) -> Decimal:
    """
    Calculate Safety Stock
    
    Basic formula: Safety Stock = Z * σ * sqrt(L)
    Where:
    - Z = Service level factor (Z-score)
    - σ = Standard deviation of demand
    - L = Lead time
    """
    try:
        avg_usage = float(average_daily_usage)
        
        if avg_usage <= 0 or lead_time_days <= 0:
            return Decimal('0')
        
        # Service level factors (Z-scores)
        service_level_factors = {
            0.50: 0.00, 0.80: 0.84, 0.85: 1.04, 0.90: 1.28,
            0.95: 1.65, 0.97: 1.88, 0.99: 2.33, 0.995: 2.58
        }
        
        z_factor = service_level_factors.get(service_level, 1.65)  # Default to 95%
        
        if demand_variability is not None:
            # Use provided demand variability
            std_dev = float(demand_variability)
        else:
            # Estimate standard deviation as 20% of average (rule of thumb)
            std_dev = avg_usage * 0.20
        
        # Account for lead time variability
        if lead_time_variability:
            # More complex calculation with lead time variability
            demand_variance = std_dev ** 2
            lead_time_variance = lead_time_variability ** 2
            
            safety_stock = z_factor * math.sqrt(
                (lead_time_days * demand_variance) + 
                (avg_usage ** 2 * lead_time_variance)
            )
        else:
            # Basic calculation
            safety_stock = z_factor * std_dev * math.sqrt(lead_time_days)
        
        return Decimal(str(safety_stock)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

def calculate_reorder_point(average_daily_usage: Union[Decimal, float],
                           lead_time_days: int,
                           safety_stock: Union[Decimal, float] = None,
                           service_level: float = 0.95) -> Decimal:
    """
    Calculate Reorder Point
    
    Formula: Reorder Point = (Average Daily Usage × Lead Time) + Safety Stock
    """
    try:
        avg_usage = Decimal(str(average_daily_usage))
        lead_time = Decimal(str(lead_time_days))
        
        if avg_usage <= 0 or lead_time <= 0:
            return Decimal('0')
        
        base_reorder_point = avg_usage * lead_time
        
        if safety_stock is not None:
            safety_stock_qty = Decimal(str(safety_stock))
        else:
            # Calculate safety stock if not provided
            safety_stock_qty = calculate_safety_stock(
                avg_usage, lead_time_days, service_level
            )
        
        reorder_point = base_reorder_point + safety_stock_qty
        
        return reorder_point.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError):
        return Decimal('0')

def calculate_maximum_stock_level(reorder_point: Union[Decimal, float],
                                 eoq: Union[Decimal, float],
                                 buffer_percentage: float = 0.10) -> Decimal:
    """
    Calculate Maximum Stock Level
    
    Formula: Maximum Level = Reorder Point + EOQ + Buffer
    """
    try:
        reorder_qty = Decimal(str(reorder_point))
        order_qty = Decimal(str(eoq))
        buffer = order_qty * Decimal(str(buffer_percentage))
        
        max_level = reorder_qty + order_qty + buffer
        
        return max_level.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError):
        return Decimal('0')

def calculate_abc_classification(annual_usage_values: List[Tuple[Any, Decimal]],
                               a_percentage: float = 80,
                               b_percentage: float = 95) -> Dict[Any, str]:
    """
    Calculate ABC classification based on annual usage values
    
    Args:
        annual_usage_values: List of (item_id, annual_value) tuples
        a_percentage: Percentage threshold for Class A (default 80%)
        b_percentage: Percentage threshold for Class B (default 95%)
    
    Returns:
        Dictionary mapping item_id to classification ('A', 'B', or 'C')
    """
    if not annual_usage_values:
        return {}
    
    # Sort by value in descending order
    sorted_items = sorted(annual_usage_values, key=lambda x: x[1], reverse=True)
    
    # Calculate total value
    total_value = sum(value for _, value in sorted_items)
    
    if total_value == 0:
        return {item_id: 'C' for item_id, _ in sorted_items}
    
    classifications = {}
    cumulative_value = Decimal('0')
    
    for item_id, value in sorted_items:
        cumulative_value += value
        cumulative_percentage = (cumulative_value / total_value) * 100
        
        if cumulative_percentage <= a_percentage:
            classifications[item_id] = 'A'
        elif cumulative_percentage <= b_percentage:
            classifications[item_id] = 'B'
        else:
            classifications[item_id] = 'C'
    
    return classifications

def calculate_inventory_turnover(cogs: Union[Decimal, float],
                               average_inventory_value: Union[Decimal, float]) -> Decimal:
    """
    Calculate Inventory Turnover Ratio
    
    Formula: Inventory Turnover = Cost of Goods Sold / Average Inventory Value
    """
    try:
        cogs_value = Decimal(str(cogs))
        avg_inventory = Decimal(str(average_inventory_value))
        
        if avg_inventory <= 0:
            return Decimal('0')
        
        turnover = cogs_value / avg_inventory
        return turnover.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

def calculate_days_in_inventory(inventory_turnover: Union[Decimal, float],
                              days_in_period: int = 365) -> Decimal:
    """
    Calculate Days in Inventory (Days Sales in Inventory)
    
    Formula: Days in Inventory = Days in Period / Inventory Turnover
    """
    try:
        turnover = Decimal(str(inventory_turnover))
        
        if turnover <= 0:
            return Decimal('0')
        
        days = Decimal(str(days_in_period)) / turnover
        return days.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

def calculate_gross_margin(selling_price: Union[Decimal, float],
                          cost_price: Union[Decimal, float]) -> Decimal:
    """
    Calculate Gross Margin Percentage
    
    Formula: Gross Margin % = ((Selling Price - Cost Price) / Selling Price) * 100
    """
    try:
        selling = Decimal(str(selling_price))
        cost = Decimal(str(cost_price))
        
        if selling <= 0:
            return Decimal('0')
        
        margin = ((selling - cost) / selling) * 100
        return margin.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

def calculate_markup_percentage(selling_price: Union[Decimal, float],
                              cost_price: Union[Decimal, float]) -> Decimal:
    """
    Calculate Markup Percentage
    
    Formula: Markup % = ((Selling Price - Cost Price) / Cost Price) * 100
    """
    try:
        selling = Decimal(str(selling_price))
        cost = Decimal(str(cost_price))
        
        if cost <= 0:
            return Decimal('0')
        
        markup = ((selling - cost) / cost) * 100
        return markup.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

def calculate_carrying_cost(average_inventory_value: Union[Decimal, float],
                          carrying_cost_rate: float = 0.25) -> Decimal:
    """
    Calculate Annual Carrying Cost
    
    Formula: Carrying Cost = Average Inventory Value × Carrying Cost Rate
    """
    try:
        inventory_value = Decimal(str(average_inventory_value))
        rate = Decimal(str(carrying_cost_rate))
        
        carrying_cost = inventory_value * rate
        return carrying_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError):
        return Decimal('0')

def calculate_stockout_cost(lost_sales: Union[Decimal, float],
                          profit_margin_rate: float = 0.25,
                          goodwill_cost_multiplier: float = 1.5) -> Decimal:
    """
    Calculate Stockout Cost
    
    Includes lost profit and goodwill cost
    """
    try:
        sales = Decimal(str(lost_sales))
        margin_rate = Decimal(str(profit_margin_rate))
        goodwill_multiplier = Decimal(str(goodwill_cost_multiplier))
        
        lost_profit = sales * margin_rate
        goodwill_cost = lost_profit * goodwill_multiplier
        
        total_stockout_cost = lost_profit + goodwill_cost
        return total_stockout_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError):
        return Decimal('0')

def calculate_demand_forecast_simple_moving_average(
    historical_demand: List[Union[Decimal, float]], 
    periods: int = 3) -> Decimal:
    """
    Calculate demand forecast using Simple Moving Average
    """
    if not historical_demand or len(historical_demand) < periods:
        return Decimal('0')
    
    try:
        recent_demand = [Decimal(str(d)) for d in historical_demand[-periods:]]
        forecast = sum(recent_demand) / len(recent_demand)
        return forecast.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError):
        return Decimal('0')

def calculate_demand_forecast_exponential_smoothing(
    historical_demand: List[Union[Decimal, float]], 
    alpha: float = 0.3) -> Decimal:
    """
    Calculate demand forecast using Exponential Smoothing
    """
    if not historical_demand:
        return Decimal('0')
    
    try:
        forecast = Decimal(str(historical_demand[0]))
        alpha_decimal = Decimal(str(alpha))
        
        for demand in historical_demand[1:]:
            demand_decimal = Decimal(str(demand))
            forecast = alpha_decimal * demand_decimal + (1 - alpha_decimal) * forecast
        
        return forecast.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError):
        return Decimal('0')

def calculate_seasonal_index(historical_data: List[Tuple[int, Decimal]], 
                           seasonal_periods: int = 12) -> Dict[int, Decimal]:
    """
    Calculate seasonal indices for demand forecasting
    d, demand) tuples
        seasonal_periods: Number of periods in a season (e.g., 12 for monthly)
    
    Returns:
        Dictionary mapping period to seasonal index
    """
    return {}
    
    try:
        # Group data by seasonal period
        seasonal_data = {}
        for period, demand in historical seasonal_periods
            if season not
            seasonal_data[season].append(Decimal(str(demand)))
        
        # Calculate average demand for each season
        seasonal_averages = {}
        for season, demands in seasonal_data.items():
            seasonal_averages[season] = sum(demands) / len(demands)
        
        # Calculate overall average
        all_demands = [demand for _, demands in seasonal_data.items() for demand in demands]
        overall_average = sum(all_demands) / len(all_demands)
        
        # Calculate seasonal indices
        seasonal_indices = {}
        for season, avg_demand in seasonal_averages.items():
            if overall_average > 0:
                index = avg_demand / overall_average
                seasonal_indices[season] = index.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                seasonal_indices[season] = Decimal('1.00')
        
        return seasonal_indices
    
    except (ValueError, TypeError, ZeroDivisionError):
        return {}

def calculate_service_level_from_fill_rate(orders_filled: int, 
                                          total_orders: int) -> Decimal:
    """
    Calculate service level as order fill rate
    """
    try:
        if total_orders <= 0:
            return Decimal('0')
        
        fill_rate = (Decimal(str(orders_filled)) / Decimal(str(total_orders))) * 100
        return fill_rate.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

def calculate_forecast_accuracy(actual_values: List[Union[Decimal, float]],
                              forecasted_values: List[Union[Decimal, float]],
                              method: str = 'MAPE') -> Decimal:
    """
    Calculate forecast accuracy using various methods
    
    Methods:
    - MAPE: Mean Absolute Percentage Error
    - MAD: Mean Absolute Deviation
    - MSE: Mean Squared Error
    """
    if not actual_values or not forecasted_values or len(actual_values) != len(forecasted_values):
        return Decimal('0')
    
    try:
        actual = [Decimal(str(a)) for a in actual_values]
        forecast = [Decimal(str(f)) for f in forecasted_values]
        
        if method == 'MAPE':
            # Mean Absolute Percentage Error
            percentage_errors = []
            for a, f in zip(actual, forecast):
                if a != 0:
                    error = abs((a - f) / a) * 100
                    percentage_errors.append(error)
            
            if percentage_errors:
                mape = sum(percentage_errors) / len(percentage_errors)
                accuracy = 100 - mape  # Convert error to accuracy
                return max(Decimal('0'), accuracy.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        
        elif method == 'MAD':
            # Mean Absolute Deviation
            absolute_errors = [abs(a - f) for a, f in zip(actual, forecast)]
            mad = sum(absolute_errors) / len(absolute_errors)
            return mad.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        elif method == 'MSE':
            # Mean Squared Error
            squared_errors = [(a - f) ** 2 for a, f in zip(actual, forecast)]
            mse = sum(squared_errors) / len(squared_errors)
            return mse.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return Decimal('0')
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

def calculate_lead_time_variability(lead_times: List[int]) -> Tuple[Decimal, int]:
    """
    Calculate lead time average and variability
    
    Returns:
        Tuple of (average_lead_time, standard_deviation)
    """
    if not lead_times:
        return Decimal('0'), 0
    
    try:
        # Calculate average
        avg_lead_time = sum(lead_times) / len(lead_times)
        
        # Calculate standard deviation
        variance = sum((lt - avg_lead_time) ** 2 for lt in lead_times) / len(lead_times)
        std_deviation = math.sqrt(variance)
        
        return (
            Decimal(str(avg_lead_time)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            int(std_deviation)
        )
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0'), 0

def calculate_order_frequency(orders_per_period: List[int], 
                            periods: int = 12) -> Decimal:
    """
    Calculate optimal order frequency
    """
    if not orders_per_period:
        return Decimal('0')
    
    try:
        total_orders = sum(orders_per_period)
        avg_orders_per_period = total_orders / len(orders_per_period)
        
        # Annualize if needed
        if len(orders_per_period) != periods:
            avg_orders_per_period = avg_orders_per_period * (periods / len(orders_per_period))
        
        return Decimal(str(avg_orders_per_period)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    except (ValueError, TypeError, ZeroDivisionError):
        return Decimal('0')

class InventoryCalculator:
    """Advanced inventory calculations class"""
    
    @staticmethod
    def calculate_optimal_lot_size(annual_demand: Decimal, setup_cost: Decimal,
                                 holding_cost_rate: Decimal, unit_cost: Decimal) -> Decimal:
        """Calculate optimal lot size considering quantity discounts"""
        holding_cost_per_unit = unit_cost * holding_cost_rate
        return calculate_eoq(annual_demand, setup_cost, holding_cost_per_unit)
    
    @staticmethod
    def calculate_total_annual_cost(annual_demand: Decimal, order_quantity: Decimal,
                                  ordering_cost: Decimal, holding_cost_per_unit: Decimal) -> Decimal:
        """Calculate total annual inventory cost"""
        try:
            # Ordering cost component
            annual_ordering_cost = (annual_demand / order_quantity) * ordering_cost
            
            # Holding cost component
            annual_holding_cost = (order_quantity / 2) * holding_cost_per_unit
            
            total_cost = annual_ordering_cost + annual_holding_cost
            return total_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        except (ValueError, TypeError, ZeroDivisionError):
            return Decimal('0')
    
    @staticmethod
    def calculate_quantity_discount_eoq(annual_demand: Decimal, ordering_cost: Decimal,
                                       holding_cost_rate: Decimal,
                                       price_breaks: List[Tuple[Decimal, Decimal]]) -> Tuple[Decimal, Decimal]:
        """
        Calculate EOQ with quantity discounts
        
        Args:
            price_breaks: List of (quantity_threshold, unit_price) tuples
        
        Returns:
            Tuple of (optimal_quantity, optimal_total_cost)
        """
        if not price_breaks:
            return Decimal('0'), Decimal('0')
        
        try:
            best_quantity = Decimal('0')
            best_total_cost = Decimal('999999999')
            
            # Sort price breaks by quantity
            sorted_breaks = sorted(price_breaks, key=lambda x: x[0])
            
            for quantity_threshold, unit_price in sorted_breaks:
                holding_cost_per_unit = unit_price * holding_cost_rate
                
                # Calculate EOQ for this price level
                eoq = calculate_eoq(annual_demand, ordering_cost, holding_cost_per_unit)
                
                # Adjust EOQ if it's below the quantity threshold
                if eoq < quantity_threshold:
                    eoq = quantity_threshold
                
                # Calculate total cost for this quantity
                purchase_cost = annual_demand * unit_price
                inventory_cost = InventoryCalculator.calculate_total_annual_cost(
                    annual_demand, eoq, ordering_cost, holding_cost_per_unit
                )
                total_cost = purchase_cost + inventory_cost
                
                # Track the best option
                if total_cost < best_total_cost:
                    best_total_cost = total_cost
                    best_quantity = eoq
            
            return best_quantity, best_total_cost
        
        except (ValueError, TypeError, ZeroDivisionError):
            return Decimal('0'), Decimal('0')