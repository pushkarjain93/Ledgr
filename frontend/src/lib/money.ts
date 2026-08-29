/** Format paise as Indian rupees — never render raw paise. */
export function formatINR(paise: number): string {
  const rupees = paise / 100
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(rupees)
}

export function formatCompactINR(paise: number): string {
  if (paise >= 10000000) {
    return `₹${(paise / 10000000).toFixed(2)} Cr`
  }
  return formatINR(paise)
}
