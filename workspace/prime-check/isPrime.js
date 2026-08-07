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
console.log('Testing isPrime function:');
console.log('isPrime(2):', isPrime(2));
console.log('isPrime(7):', isPrime(7));
console.log('isPrime(10):', isPrime(10));
console.log('isPrime(13):', isPrime(13));
console.log('isPrime(15):', isPrime(15));
