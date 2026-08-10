def average_list(lst):
    """Calculate the average of a list."""
    if not lst:
        return 0.0
    return sum(lst) / len(lst)


# Test with an empty list
result = average_list([])
print(f"Average of empty list: {result}")

# Test with non-empty list for verification
result2 = average_list([1, 2, 3, 4, 5])
print(f"Average of [1, 2, 3, 4, 5]: {result2}")