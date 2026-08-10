def get_average(numbers):
    """Calculate the average of a list of numbers.
    
    Args:
        numbers: A list of numeric values
        
    Returns:
        The average (mean) of the numbers, or None if the list is empty
    """
    if not numbers:
        return None
    
    return sum(numbers) / len(numbers)

# Test with an empty list
print("Testing with empty list:", get_average([]))

# Test with some numbers
print("Testing with [1, 2, 3, 4, 5]:", get_average([1, 2, 3, 4, 5]))

# Test with a single number
print("Testing with [10]:", get_average([10]))