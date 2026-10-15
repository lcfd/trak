"""
`trak dev fill`: years of made-up but believable data, relative to today.

A freelancer working most weekdays (rarely on weekends), with holidays in
summer and at Christmas, on a few projects at a time: projects start and
end over the years, some for a customer and some personal, and get
archived a while after they end. Sessions run in local time, a few late
ones past midnight; today has a couple of running sessions. Goals sit
around each project's work: past ones reached or missed, current ones with
days left, and some still to start. Sessions have a category and some tags;
most projects and customers have a category, many have tags.
"""

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlmodel import Session as DBSession
from sqlmodel import delete, func, select

from trak.customers.models import Customer
from trak.goals.models import Goal
from trak.labels.links import LINKS
from trak.projects.models import Project
from trak.sessions.models import Category, Session, Tag

CUSTOMERS = [
    "ACME",
    "Globex",
    "Initech",
    "Umbrella",
    "Hooli",
    "Stark Industries",
    "Wayne Enterprises",
    "Soylent",
    "Wonka",
    "Cyberdyne",
    "Tyrell",
    "Vandelay Industries",
    "Pied Piper",
    "Monsters Inc",
]
KINDS = [
    "website",
    "api",
    "mobile-app",
    "dashboard",
    "redesign",
    "migration",
    "shop",
    "crm",
    "analytics",
    "docs",
    "onboarding",
    "seo",
    "intranet",
    "newsletter",
]
PERSONAL = ["blog", "side-project", "open-source", "learning-rust", "portfolio"]
DESCRIPTIONS = [
    "",
    "",
    "Maintenance and small features.",
    "Full rewrite, new stack.",
    "Fixed price, tight deadline.",
    "Retainer: a few hours a week.",
]

# Category -> what its sessions are called ("" leaves a session unnamed).
CATEGORIES = {
    "Development": ["", "Feature work", "Bug fixing", "Refactoring", "Code review"],
    "Design": ["", "Wireframes", "Mockups", "Design review"],
    "Meetings": ["Standup", "Planning", "Call with the client", "Retrospective"],
    "Admin": ["Invoices", "Email", "Taxes", "Accounting"],
    "Research": ["", "Spike", "Reading docs", "Benchmarks"],
    "Support": ["Hotfix", "Support ticket", "Deploy"],
    "Writing": ["Proposal", "Documentation", "Report", "Blog post"],
}
# How often each category comes up in project work.
WORK_WEIGHTS = {
    "Development": 50,
    "Design": 12,
    "Meetings": 14,
    "Research": 8,
    "Support": 8,
    "Writing": 6,
    "Admin": 2,
}
# Kinds of customer, and their weights.
CUSTOMER_CATEGORIES = {"Agency": 3, "Startup": 4, "Enterprise": 3, "Non-profit": 1}
# What a project mostly is.
PROJECT_CATEGORIES = {"Development": 6, "Design": 2, "Writing": 1, "Research": 1}
# Session tags: any number of them on a session.
TAGS = ["billable", "internal", "urgent", "remote", "on-site", "overtime"]
# Project and customer tags (shared with sessions: tags are one list).
PROJECT_TAGS = ["retainer", "fixed-price", "maintenance", "billable", "internal"]
CUSTOMER_TAGS = ["priority", "remote", "on-site", "late-payer"]


@dataclass
class Plan:
    """A project with the days it's worked on, which its dates only hint at."""

    project: Project
    first: date
    last: date
    weight: float
    tracked: dict[date, int] = field(default_factory=lambda: defaultdict(int))


@dataclass
class Filled:
    first_day: date
    last_day: date
    customers: int
    projects: int
    sessions: int
    running: int
    goals: int
    categories: int
    tags: int


def has_data(db: DBSession) -> bool:
    return any(
        db.exec(select(func.count()).select_from(model)).one()
        for model in (Session, Project, Customer, Goal, Category, Tag)
    )


def clear(db: DBSession) -> None:
    """Delete every row, children first (foreign keys are enforced)."""

    links = [link for link, _ in LINKS.values()]
    for model in (*links, Goal, Session, Project, Customer, Category, Tag):
        db.exec(delete(model))  # type: ignore[call-overload]
    db.commit()


def at(day: date, minutes: int) -> datetime:
    """`minutes` after local midnight of `day` (past 24h is the next day), in UTC."""

    local = datetime.combine(day, time()) + timedelta(minutes=minutes)
    return local.astimezone().astimezone(UTC)


def is_holiday(day: date, holidays: set[date]) -> bool:
    christmas = (day.month == 12 and day.day >= 24) or (day.month == 1 and day.day <= 2)
    return christmas or day in holidays


def weighted(rng: random.Random, weights: dict[str, int]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def some(rng: random.Random, names: list[str], most: int) -> list[str]:
    """Up to `most` of `names`, fewer more likely (none too)."""

    count = rng.choices(range(most + 1), weights=[4, 4, 2, 1][: most + 1])[0]
    return rng.sample(names, count)


def plan_projects(
    rng: random.Random,
    customers: list[Customer],
    first_day: date,
    today: date,
    categories: dict[str, Category],
) -> list[Plan]:
    span = (today - first_day).days
    plans: list[Plan] = []
    names: set[str] = set()

    def add(
        name: str,
        customer: Customer | None,
        first: date,
        last: date,
        weight: float,
        dated: bool = True,
    ) -> None:
        if name in names:
            return
        names.add(name)
        roll = rng.random()
        start: date | None = first if dated else None
        end: date | None = last if dated else None
        if dated and roll < 0.25:
            end = None  # Open-ended.
        elif dated and roll < 0.35:
            start = None
        archived = end is not None and end < today - timedelta(days=90)
        archived = archived and rng.random() < 0.85
        project = Project(
            name=name,
            customer_fk=customer.id if customer else None,
            description=rng.choice(DESCRIPTIONS),
            rate=rng.randrange(35, 125, 5) if customer else 0,
            archived=archived,
            start=start,
            end=end,
            category_fk=(
                categories[weighted(rng, PROJECT_CATEGORIES)].id
                if rng.random() < 0.8
                else None
            ),
        )
        plans.append(Plan(project, first, last, weight))

    def customer_name(customer: Customer) -> str:
        return (customer.name or "").split()[0].lower()

    # Work spread over the years, then a few projects running now and a
    # couple still to start, so every screen has something to show.
    for _ in range(max(6, span // 60)):
        customer = rng.choice(customers)
        first = first_day + timedelta(days=rng.randrange(span))
        last = first + timedelta(days=rng.randint(20, 540))
        name = f"{customer_name(customer)}-{rng.choice(KINDS)}"
        add(name, customer, first, min(last, today), rng.uniform(0.5, 3))
    for customer in rng.sample(customers, 4):
        first = today - timedelta(days=rng.randint(30, 300))
        last = today + timedelta(days=rng.randint(20, 200))
        name = f"{customer_name(customer)}-{rng.choice(KINDS)}"
        add(name, customer, first, last, rng.uniform(2, 4))
    for customer in rng.sample(customers, 2):
        first = today + timedelta(days=rng.randint(7, 60))
        last = first + timedelta(days=rng.randint(30, 180))
        name = f"{customer_name(customer)}-{rng.choice(KINDS)}"
        add(name, customer, first, last, 2)
    for name in PERSONAL:
        first = first_day + timedelta(days=rng.randrange(span))
        last = min(today, first + timedelta(days=rng.randint(60, 900)))
        add(name, None, first, last, rng.uniform(0.2, 0.6), dated=rng.random() < 0.5)
    # The personal project that never ends.
    add("trak", None, first_day, today, 0.4, dated=False)

    return plans


def fill(
    db: DBSession,
    *,
    today: date,
    now: datetime,
    years: int = 6,
    seed: int | None = None,
) -> Filled:
    """Fill an empty database with `years` of data up to `now` (on `today`)."""

    rng = random.Random(seed)
    first_day = today - timedelta(days=round(365.25 * years))

    category_names = [*CATEGORIES, *CUSTOMER_CATEGORIES]
    categories = {name: Category(name=name) for name in category_names}
    tag_names = list(dict.fromkeys([*TAGS, *PROJECT_TAGS, *CUSTOMER_TAGS]))
    tags_by_name = {name: Tag(name=name) for name in tag_names}
    db.add_all([*categories.values(), *tags_by_name.values()])
    db.flush()

    customers = [
        Customer(
            name=name,
            category_fk=(
                categories[weighted(rng, CUSTOMER_CATEGORIES)].id
                if rng.random() < 0.85
                else None
            ),
        )
        for name in CUSTOMERS
    ]
    db.add_all(customers)
    db.flush()

    plans = plan_projects(rng, customers, first_day, today, categories)
    db.add_all(plan.project for plan in plans)
    db.flush()

    # Tags, through the link tables: (row, tag names).
    tagged: list[tuple[Session | Project | Customer, list[str]]] = []
    tagged += [(c, some(rng, CUSTOMER_TAGS, 2)) for c in customers]
    tagged += [(p.project, some(rng, PROJECT_TAGS, 2)) for p in plans]

    holidays: set[date] = set()
    for year in range(first_day.year, today.year + 1):
        # Two or three weeks off in summer, and a few days here and there.
        summer = date(year, 7, 20) + timedelta(days=rng.randrange(25))
        holidays |= {summer + timedelta(days=d) for d in range(rng.choice([14, 21]))}
        for _ in range(rng.randint(4, 8)):
            holidays.add(date(year, 1, 1) + timedelta(days=rng.randrange(365)))

    # Today's sessions end an hour ago at the latest; the running ones follow.
    local_now = now.astimezone().replace(tzinfo=None)
    now_minutes = int(
        (local_now - datetime.combine(today, time())).total_seconds() // 60
    )
    sessions: list[Session] = []

    def add_session(
        day: date, start: int, end: int, plan: Plan | None, category: str
    ) -> None:
        project = plan.project if plan else None
        # A direct customer only when the project doesn't give one.
        customer_fk = None
        no_customer = project is None or project.customer_fk is None
        if no_customer and rng.random() < 0.3:
            customer_fk = rng.choice(customers).id
        session_tags = some(rng, TAGS, 3)
        if project is not None and project.customer_fk and rng.random() < 0.5:
            session_tags = list(dict.fromkeys(["billable", *session_tags]))
        sessions.append(
            Session(
                name=rng.choice(CATEGORIES[category]),
                project_fk=project.id if project else None,
                customer_fk=customer_fk,
                category_fk=categories[category].id,
                start=at(day, start),
                end=at(day, end),
                active=False,
            )
        )
        tagged.append((sessions[-1], session_tags))
        if plan:
            plan.tracked[day] += (end - start) * 60

    day = first_day
    while day <= today:
        weekend = day.weekday() >= 5
        skip = is_holiday(day, holidays) or rng.random() < 0.03
        if weekend:
            skip = skip or rng.random() > 0.08
        active = [p for p in plans if p.first <= day <= p.last]
        if skip or not active:
            day += timedelta(days=1)
            continue

        picks = rng.choices(
            active, weights=[p.weight for p in active], k=min(len(active), 3)
        )
        target = rng.randint(120, 300) if weekend else rng.randint(240, 540)
        limit = now_minutes - 60 if day == today else 24 * 60
        minute = rng.randint(7 * 60 + 30, 10 * 60)
        lunch = False
        worked = 0
        while worked < target:
            if not lunch and minute >= 12 * 60 + 15:
                minute += rng.randint(30, 75)
                lunch = True
            length = rng.choice([25, 30, 45, 60, 60, 90, 90, 120, 150, 180])
            length = min(length, target - worked + 15)
            if minute + length > min(limit, 20 * 60):
                break
            if rng.random() < 0.12:
                add_session(day, minute, minute + length, None, "Admin")
            else:
                plan = rng.choice(picks)
                category = rng.choices(
                    list(WORK_WEIGHTS), weights=list(WORK_WEIGHTS.values())
                )[0]
                add_session(day, minute, minute + length, plan, category)
            worked += length
            minute += length + rng.choice([0, 5, 10, 15, 30])

        # Now and then a late session, sometimes past midnight.
        start = rng.randint(21 * 60, 23 * 60)
        end = start + rng.randint(45, 150)
        if rng.random() < 0.06 and at(day, end) < now - timedelta(hours=1):
            add_session(day, start, end, picks[0], "Development")
        day += timedelta(days=1)

    running_plans = [p for p in plans if p.first <= today <= p.last]
    running = []
    if running_plans:
        plan = max(running_plans, key=lambda p: p.weight)
        running.append(
            Session(
                name="Feature work",
                project_fk=plan.project.id,
                category_fk=categories["Development"].id,
                start=now - timedelta(minutes=rng.randint(20, 50)),
                active=True,
            )
        )
        tagged.append((running[-1], ["billable", "remote"]))
    running.append(
        Session(
            name="Email",
            category_fk=categories["Admin"].id,
            start=now - timedelta(minutes=rng.randint(3, 15)),
            active=True,
        )
    )
    tagged.append((running[-1], ["internal"]))
    sessions += running
    db.add_all(sessions)
    db.flush()

    for row, names in tagged:
        link, column = LINKS[type(row)]
        db.add_all(
            link(**{column: row.id, "tag_fk": tags_by_name[name].id}) for name in names
        )

    goals = plan_goals(rng, plans, today)
    db.add_all(goals)
    db.commit()

    return Filled(
        first_day=first_day,
        last_day=today,
        customers=len(customers),
        projects=len(plans),
        sessions=len(sessions),
        running=len(running),
        goals=len(goals),
        categories=len(categories),
        tags=len(tags_by_name),
    )


def plan_goals(rng: random.Random, plans: list[Plan], today: date) -> list[Goal]:
    """Goals around each project's work: some reached, some missed, some to come."""

    goals: list[Goal] = []

    def hours_between(plan: Plan, start: date, deadline: date) -> float:
        seconds = sum(s for d, s in plan.tracked.items() if start <= d <= deadline)
        return seconds / 3600

    for plan in plans:
        assert plan.project.id is not None
        if plan.project.customer_fk is None and rng.random() < 0.6:
            continue
        # Past ones: a stretch of the project's work, aimed a bit above or
        # below what was tracked.
        cursor = plan.first
        while cursor < min(plan.last, today) - timedelta(days=30):
            if rng.random() < 0.5:
                start = cursor
                deadline = min(
                    start + timedelta(days=rng.choice([14, 30, 60, 90])), today
                )
                tracked = hours_between(plan, start, deadline)
                if tracked >= 1:
                    goals.append(
                        Goal(
                            project_fk=plan.project.id,
                            name=rng.choice(["", "Milestone", "Sprint", "Phase"]),
                            hours=max(1, round(tracked * rng.uniform(0.75, 1.3))),
                            start=start,
                            deadline=deadline,
                        )
                    )
            cursor += timedelta(days=rng.randint(30, 120))

        # Running now: started a while ago, deadline to come.
        if plan.first <= today <= plan.last:
            start = max(plan.first, today - timedelta(days=rng.randint(7, 45)))
            deadline = today + timedelta(days=rng.randint(3, 60))
            pace = hours_between(plan, start, today) / max(1, (today - start).days)
            goals.append(
                Goal(
                    project_fk=plan.project.id,
                    name=rng.choice(["Release", "Milestone", "Beta", ""]),
                    hours=max(
                        5, round(pace * (deadline - start).days * rng.uniform(0.8, 1.3))
                    ),
                    start=start,
                    deadline=deadline,
                )
            )
        # To come: on projects running now or starting soon.
        if plan.last > today and rng.random() < 0.7:
            start = max(plan.first, today + timedelta(days=rng.randint(10, 60)))
            goals.append(
                Goal(
                    project_fk=plan.project.id,
                    name=rng.choice(["Launch", "Phase 2", "Handover"]),
                    hours=rng.randrange(20, 160, 10),
                    start=start,
                    deadline=start + timedelta(days=rng.choice([30, 60, 90])),
                )
            )

    return goals
