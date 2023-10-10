from datetime import datetime


def same_week(dateString):
    """returns true if a dateString in %Y%m%d format is part of the current week"""

    d1 = datetime.strptime(dateString, "%Y%m%d")
    d2 = datetime.today()
    return d1.isocalendar()[1] == d2.isocalendar()[1] and d1.year == d2.year
