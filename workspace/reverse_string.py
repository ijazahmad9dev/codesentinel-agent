def reverse_string(s):
    """Reverse a given string."""
    return s[::-1]

# Test the function
if __name__ == "__main__":
    test_cases = [
        "hello",
        "world",
        "",
        "a",
        "Python"
    ]

    print("Testing reverse_string function:")
    for test in test_cases:
        result = reverse_string(test)
        print(f"Input: '{test}' -> Output: '{result}'")
