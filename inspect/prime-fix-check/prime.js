function isPrime(n) {
    if (n <= 1) return false;
    if (n <= 3) return true;
    if (n % 2 === 0 || n % 3 === 0) return false;
    
    for (let i = 5; i * i <= n; i += 6) {
        if (n % i === 0 || n % (i + 2) === 0) return false;
    }
    return true;
}

// Test with a few numbers
const testNumbers = [1, 2, 3, 4, 5, 16, 17, 19, 20, 23, 29, 30];
testNumbers.forEach(num => {
    console.log(`${num} is ${isPrime(num) ? 'prime' : 'not prime'}`);
});