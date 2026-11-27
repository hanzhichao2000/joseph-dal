"""Trading calendar contract."""

from collections.abc import Iterable
from datetime import date, timedelta


class TradingCalendar:
    """Trading calendar for Chinese futures markets.

    Provides methods to iterate over trading days and check if a date is a trading day.
    By default, excludes weekends (Saturday=5, Sunday=6).

    For MVP, holidays are optionally provided as a set. Future versions may load
    holidays from external sources (exchange calendars, APIs).

    Example:
        >>> cal = TradingCalendar()
        >>> cal.is_trading_day(date(2025, 1, 6))  # Monday
        True
        >>> cal.is_trading_day(date(2025, 1, 4))  # Saturday
        False

        >>> # Get trading days in range
        >>> days = cal.get_trading_days(date(2025, 1, 6), date(2025, 1, 10))
        >>> len(days)  # Mon-Fri
        5

        >>> # With holidays
        >>> holidays = {date(2025, 1, 1)}  # New Year
        >>> cal = TradingCalendar(holidays=holidays)
        >>> cal.is_trading_day(date(2025, 1, 1))
        False
    """

    def __init__(self, holidays: Iterable[date] | None = None):
        """Initialize trading calendar.

        Args:
            holidays: Optional set/list of holiday dates to exclude.
        """
        self._holidays: set[date] = set(holidays) if holidays else set()

    @property
    def holidays(self) -> set[date]:
        """Get the set of holidays."""
        return self._holidays.copy()

    def add_holiday(self, d: date) -> None:
        """Add a holiday date.

        Args:
            d: Date to add as holiday.
        """
        self._holidays.add(d)

    def add_holidays(self, dates: Iterable[date]) -> None:
        """Add multiple holiday dates.

        Args:
            dates: Dates to add as holidays.
        """
        self._holidays.update(dates)

    def is_weekend(self, d: date) -> bool:
        """Check if date is a weekend.

        Args:
            d: Date to check.

        Returns:
            True if Saturday (5) or Sunday (6).
        """
        return d.weekday() >= 5

    def is_holiday(self, d: date) -> bool:
        """Check if date is a holiday.

        Args:
            d: Date to check.

        Returns:
            True if date is in the holidays set.
        """
        return d in self._holidays

    def is_trading_day(self, d: date) -> bool:
        """Check if date is a trading day.

        A trading day is one that is:
        - Not a weekend (Saturday or Sunday)
        - Not a holiday

        Args:
            d: Date to check.

        Returns:
            True if the date is a trading day.

        Example:
            >>> cal = TradingCalendar()
            >>> cal.is_trading_day(date(2025, 1, 6))  # Monday
            True
        """
        return not self.is_weekend(d) and not self.is_holiday(d)

    def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """Get list of trading days in date range (inclusive).

        Args:
            start_date: First date (inclusive).
            end_date: Last date (inclusive).

        Returns:
            List of trading dates in chronological order.

        Raises:
            ValueError: If start_date > end_date.

        Example:
            >>> cal = TradingCalendar()
            >>> days = cal.get_trading_days(date(2025, 1, 6), date(2025, 1, 10))
            >>> len(days)
            5
        """
        if start_date > end_date:
            raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

        trading_days = []
        current = start_date
        while current <= end_date:
            if self.is_trading_day(current):
                trading_days.append(current)
            current += timedelta(days=1)

        return trading_days

    def get_previous_trading_day(self, d: date) -> date:
        """Get the previous trading day before the given date.

        Args:
            d: Reference date.

        Returns:
            The most recent trading day before d.

        Example:
            >>> cal = TradingCalendar()
            >>> cal.get_previous_trading_day(date(2025, 1, 6))  # Monday
            datetime.date(2025, 1, 3)
        """
        current = d - timedelta(days=1)
        while not self.is_trading_day(current):
            current -= timedelta(days=1)
        return current

    def get_next_trading_day(self, d: date) -> date:
        """Get the next trading day after the given date.

        Args:
            d: Reference date.

        Returns:
            The next trading day after d.

        Example:
            >>> cal = TradingCalendar()
            >>> cal.get_next_trading_day(date(2025, 1, 3))  # Friday
            datetime.date(2025, 1, 6)
        """
        current = d + timedelta(days=1)
        while not self.is_trading_day(current):
            current += timedelta(days=1)
        return current

    def count_trading_days(self, start_date: date, end_date: date) -> int:
        """Count trading days in date range (inclusive).

        Args:
            start_date: First date (inclusive).
            end_date: Last date (inclusive).

        Returns:
            Number of trading days.

        Example:
            >>> cal = TradingCalendar()
            >>> cal.count_trading_days(date(2025, 1, 6), date(2025, 1, 10))
            5
        """
        return len(self.get_trading_days(start_date, end_date))

    def get_trading_days_before(self, d: date, n: int) -> list[date]:
        """Get N trading days before (not including) the given date.

        Useful for factor warm-up periods.

        Args:
            d: Reference date (not included).
            n: Number of trading days to get.

        Returns:
            List of N trading days in chronological order.

        Example:
            >>> cal = TradingCalendar()
            >>> days = cal.get_trading_days_before(date(2025, 1, 10), 3)
            >>> len(days)
            3
        """
        if n <= 0:
            return []

        result: list[date] = []
        current = d - timedelta(days=1)

        while len(result) < n:
            if self.is_trading_day(current):
                result.append(current)
            current -= timedelta(days=1)

        # Return in chronological order
        return list(reversed(result))
