export function currency(value: number): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(value);
}

export function compactCurrency(value: number): string {
  const absoluteValue = Math.abs(value);

  if (absoluteValue >= 1_000_000) {
    return `£${trimTrailingZero(value / 1_000_000)}m`;
  }

  if (absoluteValue >= 1_000) {
    return `£${trimTrailingZero(value / 1_000)}k`;
  }

  return currency(value);
}

export function percentage(value: number): string {
  return new Intl.NumberFormat("en-GB", {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(value);
}

export function percentageValue(value: number): string {
  const normalised = Math.abs(value) > 1 ? value / 100 : value;
  return percentage(normalised);
}

export function shortDate(value: string | null): string {
  if (!value) {
    return "Not set";
  }

  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
  }).format(date);
}

export function monthLabel(value: string): string {
  const [year, month] = value.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
  }).format(date);
}

function trimTrailingZero(value: number): string {
  return value.toFixed(1).replace(/\.0$/, "");
}
