import random
import numpy as np

# Define the prime number for the finite field
# Using 257 as it's the smallest prime greater than 255 (max pixel value)
PRIME = 257

def mod_inverse(num, mod):
    """
    Calculate the modular multiplicative inverse using Extended Euclidean Algorithm
    """
    # Extended Euclidean Algorithm to find modular multiplicative inverse
    def extended_gcd(a, b):
        if a == 0:
            return (b, 0, 1)
        else:
            g, x, y = extended_gcd(b % a, a)
            return (g, y - (b // a) * x, x)
    
    gcd, x, y = extended_gcd(num, mod)
    if gcd != 1:
        raise ValueError(f"Modular inverse does not exist for {num} mod {mod}")
    else:
        return (x % mod + mod) % mod

def evaluate_polynomial(coefficients, x, prime):
    """
    Evaluate a polynomial with given coefficients at point x in a finite field with given prime.
    """
    result = 0
    for coefficient in reversed(coefficients):
        result = (result * x + coefficient) % prime
    return result

def split_secret(secret, threshold, num_shares, prime=PRIME):
    """
    Split a secret into n shares using Shamir's Secret Sharing.
    
    Args:
        secret: The secret to share (0-255 for pixel values)
        threshold: Minimum number of shares required to reconstruct the secret
        num_shares: Total number of shares to generate
        prime: Prime number for the finite field
        
    Returns:
        List of tuples (x_i, y_i) where each tuple is a share
    """
    if threshold > num_shares:
        raise ValueError("Threshold cannot be greater than the number of shares")
    
    if not 0 <= secret < prime:
        raise ValueError(f"Secret must be in range [0, {prime-1}]")
    
    # Generate random coefficients for the polynomial
    coefficients = [secret]  # First coefficient is the secret
    for _ in range(threshold - 1):
        coefficients.append(random.randint(1, prime - 1))
    
    # Generate shares
    shares = []
    for i in range(1, num_shares + 1):  # Starting from 1, not 0
        x = i
        y = evaluate_polynomial(coefficients, x, prime)
        shares.append((x, y))
    
    return shares

def lagrange_interpolation(shares, prime=PRIME):
    """
    Reconstruct the secret (y-intercept) using Lagrange interpolation.
    
    Args:
        shares: List of tuples (x_i, y_i) representing the shares
        prime: Prime number for the finite field
        
    Returns:
        The reconstructed secret
    """
    if not shares:
        raise ValueError("No shares provided")
    
    # Evaluate at x=0 (the secret is the y-intercept)
    x_values = [x for x, _ in shares]
    y_values = [y for _, y in shares]
    
    secret = 0
    for i, (x_i, y_i) in enumerate(shares):
        numerator = 1
        denominator = 1
        
        for j, x_j in enumerate([x for x, _ in shares]):
            if i != j:
                numerator = (numerator * (0 - x_j)) % prime
                denominator = (denominator * (x_i - x_j)) % prime
        
        # Calculate the Lagrange basis polynomial evaluated at x=0
        lagrange_basis = (numerator * mod_inverse(denominator, prime)) % prime
        
        # Add this term's contribution to the result
        secret = (secret + y_i * lagrange_basis) % prime
    
    return secret

def recover_secret(shares, prime=PRIME):
    """
    Recover the secret from at least threshold shares.
    
    Args:
        shares: List of tuples (x_i, y_i) representing the shares
        prime: Prime number for the finite field
        
    Returns:
        The recovered secret
    """
    return lagrange_interpolation(shares, prime)

# Testing the implementation
if __name__ == "__main__":
    # Example usage
    secret = 123  # Example secret (a pixel value)
    threshold = 3
    num_shares = 5
    
    # Split the secret
    shares = split_secret(secret, threshold, num_shares)
    print(f"Secret: {secret}")
    print(f"Generated {len(shares)} shares: {shares}")
    
    # Recover from exactly threshold shares
    recovered_secret = recover_secret(shares[:threshold])
    print(f"Recovered from {threshold} shares: {recovered_secret}")
    
    # Recover from all shares
    recovered_secret = recover_secret(shares)
    print(f"Recovered from all {len(shares)} shares: {recovered_secret}")
    
    # Verify that recovery works with any subset of shares >= threshold
    import random
    subset = random.sample(shares, threshold)
    recovered_secret = recover_secret(subset)
    print(f"Recovered from random subset of {threshold} shares: {recovered_secret}")