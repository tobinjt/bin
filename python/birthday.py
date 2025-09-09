#!/usr/bin/env python3
"""Show the probability of a birthday paradox collision.

The probability of a birthday paradox collision happening is surprisingly high.
This program calculates the probability of a birthday collision between N
people, or the probability of a collision between N of M things.
"""

import decimal
import sys

__author__ = "johntobin@johntobin.ie (John Tobin)"


def birthday(num_people: int, num_days: int) -> decimal.Decimal:
    """Calculate the probability of a birthday collision.

    Args:
      num_days: int, the number of days in the year
      num_people: int, the number of people

    Returns:
      decimal.Decimal, a number between 0 and 1 giving the probability of a
      collision.
    """

    if num_people > num_days:
        return decimal.Decimal(1)

    # We want to calculate P(collision) = 1 - P(no collision)
    # P(no collision) = (num_days / num_days) *
    #   ((num_days - 1) / num_days) * ... *
    #   ((num_days - num_people + 1) / num_days)
    # P(no collision) = product_{i=0}^{num_people-1} (num_days - i) / num_days
    # To avoid floating point issues with very large numbers, we use logarithms.
    # log(P(no collision)) = sum_{i=0}^{num_people-1} log((num_days - i) / num_days)
    # log(P(no collision)) = sum_{i=0}^{num_people-1}
    #   (log(num_days - i) - log(num_days))
    # Then P(no collision) = 10^log(P(no collision))

    log_prob_no_collision = decimal.Decimal(0)
    for i in range(num_people):
        log_prob_no_collision += (
            decimal.Decimal(num_days - i).log10() - decimal.Decimal(num_days).log10()
        )

    prob_no_collision = decimal.Decimal(10) ** log_prob_no_collision
    return 1 - prob_no_collision


def main(argv: list[str]):
    """Parse arguments and call birthday.

    Args:
        argv: command line arguments.
    """
    if len(argv) not in (2, 3):
        sys.exit(f"Usage: {argv[0]} NUM_PEOPLE [NUM_DAYS]")

    try:
        for number in argv[1:]:
            _ = int(number)
    except ValueError:
        sys.exit(f"Argument is not a number: {str(number)}")

    (num_people, num_days) = (int(argv[1]), 365)
    if len(argv) == 3:
        num_days = int(argv[2])

    if num_people <= 0:
        sys.exit(f"Number of people must be greater than 0: {num_people}")
    if num_days <= 0:
        sys.exit(f"Number of days must be greater than 0: {num_days}")

    print(birthday(num_people, num_days))


if __name__ == "__main__":
    main(sys.argv)
