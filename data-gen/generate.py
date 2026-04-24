"""
Dummy data generator for the capstone feedback pipeline.

Generates three CSV files:
  - app_store_reviews.csv       : Simulated app store reviews
  - support_emails.csv          : Simulated customer support emails
  - expected_classifications.csv: Ground-truth labels for the above

Usage:
    uv run data-gen/generate.py
    uv run data-gen/generate.py --reviews 150 --emails 80 --output data/seed/
"""

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


# ──────────────────────────── seed data pools ────────────────────────────

APP_NAMES = ["CapStore", "CapStore Pro", "CapStore Lite"]
PLATFORMS = ["Google Play", "App Store"]
VERSIONS = ["2.0.1", "2.1.0", "2.1.3", "3.0.0", "3.0.1", "3.1.0", "3.2.0"]
DEVICES = [
    "Samsung Galaxy S24", "iPhone 15 Pro", "Pixel 8", "OnePlus 12",
    "iPhone 14", "Samsung Galaxy A54", "Pixel 7a", "Xiaomi 14",
]
OS_VERSIONS = [
    "Android 14", "Android 13", "iOS 17.4", "iOS 16.6",
    "iOS 17.2", "Android 12", "Android 15",
]

# ── bug reviews ──
BUG_REVIEW_TEMPLATES = [
    ("App crashes when I {action}. Tried reinstalling but it still happens.",
     "App Crash Report"),
    ("Can't {action} since the latest update. Worked fine before.",
     "Login Issue"),
    ("Data {data_issue} after upgrading to {version}. Very frustrating.",
     "Data Loss Problem"),
    ("The app freezes every time I try to {action}. Running {device} on {os}.",
     "App Freeze Bug"),
    ("Getting a blank screen when {action}. Please fix ASAP.",
     "Blank Screen Issue"),
    ("Notifications stopped working after version {version} update.",
     "Push Notification Bug"),
    ("Sync keeps failing in the background. Device: {device}, OS: {os}.",
     "Sync Failure"),
]

BUG_ACTIONS = [
    "open the app", "log in", "switch accounts", "load my dashboard",
    "upload a file", "search for items", "check my notifications",
]
DATA_ISSUES = ["disappeared", "got corrupted", "is out of sync", "won't load"]

# ── feature request reviews ──
FEATURE_REVIEW_TEMPLATES = [
    ("Would love a dark mode option. My eyes hurt using it at night.",
     "Feature Request: Dark Mode"),
    ("Please add {feature}. This would make the app so much better.",
     "Suggestion for Improvement"),
    ("It would be great if you could export data as PDF. Missing that feature.",
     "Feature Request: PDF Export"),
    ("Suggestion: add {feature}. Competing apps already have this.",
     "Feature Suggestion"),
    ("Any chance of adding {feature}? Would be a game changer.",
     "Feature Request"),
]
FEATURES = [
    "biometric login", "offline mode", "bulk selection", "custom themes",
    "two-factor authentication", "widgets for home screen", "tablet support",
    "a search filter", "calendar integration",
]

# ── praise reviews ──
PRAISE_REVIEW_TEMPLATES = [
    ("Amazing app! Works perfectly and the UI is super clean.",),
    ("Love the new {feature} feature added in {version}. Keep it up!",),
    ("Best app of its kind. Fast, reliable, and intuitive.",),
    ("5 stars! The team clearly listens to user feedback.",),
    ("Exactly what I needed. No crashes, no issues. Highly recommend.",),
    ("The recent update improved performance a lot. Great work!",),
]

# ── complaint reviews ──
COMPLAINT_REVIEW_TEMPLATES = [
    ("Too expensive for what it offers. Competitors are cheaper.",),
    ("Customer support is non-existent. Emailed three times, no reply.",),
    ("The app has become so slow lately. Used to be snappy.",),
    ("Ads are too intrusive in the free tier. Almost unusable.",),
    ("Poor UX design. Simple tasks take too many taps.",),
    ("Battery drain is insane. Kills 20% battery per hour.",),
]

# ── spam reviews ──
SPAM_REVIEW_TEMPLATES = [
    ("Click here to win an iPhone 15 Pro!! {url}",),
    ("EARN $$$ FROM HOME!!! This app revealed my secret income method.",),
    ("asdfjkl; lol this app xDDDD",),
    ("Buy followers now @discountfollowers use code SAVE50",),
    ("Not related to this app at all but check out my channel",),
]
SPAM_URLS = ["bit.ly/3fakeurl", "t.me/spamchannel", "www.earn-now.biz"]

# ── email subjects / bodies ──
BUG_EMAIL_SUBJECTS = [
    "App Crash Report", "Login Issue Since Last Update",
    "Data Loss Problem - Urgent", "App Keeps Freezing",
    "Cannot Access My Account", "Sync Not Working",
]

FEATURE_EMAIL_SUBJECTS = [
    "Feature Request: Dark Mode", "Suggestion for Improvement",
    "Idea for Next Version", "Enhancement Request",
    "Would Love to See This Feature",
]

BUG_EMAIL_BODIES = [
    (
        "Hello Support,\n\nI am writing to report a crash that occurs every time I {action}. "
        "I am using {device} running {os}, app version {version}.\n\n"
        "Steps to reproduce:\n1. Open the app\n2. Navigate to {section}\n3. Tap {action}\n"
        "4. App crashes immediately\n\nPlease advise. This is affecting my daily workflow.\n\n"
        "Regards,\n{name}"
    ),
    (
        "Hi,\n\nSince updating to version {version}, I can no longer {action}. "
        "I've tried uninstalling and reinstalling but the issue persists.\n"
        "Device: {device} | OS: {os}\n\nThis is urgent for me. Please help.\n\n{name}"
    ),
    (
        "To Whom It May Concern,\n\nI am experiencing {issue} with my account data after "
        "the recent update. This is causing significant disruption.\n\n"
        "App version: {version}\nPlatform: {os}\nDevice: {device}\n\n"
        "I would appreciate a swift resolution.\n\nBest,\n{name}"
    ),
]

FEATURE_EMAIL_BODIES = [
    (
        "Hi CapStore Team,\n\nI've been using the app for {months} months and love it! "
        "One thing that would make it even better is {feature}. "
        "Would you consider adding this in a future update?\n\nThanks,\n{name}"
    ),
    (
        "Hello,\n\nJust a quick suggestion: it would be great to have {feature}. "
        "Many of your competitors offer this and it would help retain users like me.\n\n{name}"
    ),
]

FIRST_NAMES = [
    "Alex", "Jordan", "Morgan", "Taylor", "Casey", "Riley", "Drew", "Avery",
    "Jamie", "Quinn", "Blake", "Reese", "Skylar", "Cameron", "Rowan",
    "Lena", "Marcus", "Priya", "Yusuf", "Elena", "Santiago", "Mei",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White",
    "Harris", "Martin", "Thompson", "Robinson", "Clark", "Rodriguez",
]
DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "hotmail.com", "icloud.com"]
SECTIONS = ["Dashboard", "Settings", "Profile", "Notifications", "Search", "Cart"]
MONTHS = list(range(1, 24))

# ──────────────────────────── helpers ────────────────────────────

def _rand_date(days_back: int = 180) -> str:
    dt = datetime.now() - timedelta(days=random.randint(0, days_back))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _rand_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _rand_email(name: str) -> str:
    parts = name.lower().split()
    pattern = random.choice([
        f"{parts[0]}.{parts[1]}",
        f"{parts[0]}{random.randint(1, 99)}",
        f"{parts[0][0]}{parts[1]}",
    ])
    return f"{pattern}@{random.choice(DOMAINS)}"


def _fill(template: str, **kw) -> str:
    try:
        return template.format(**kw)
    except KeyError:
        return template


# ──────────────────────────── review generators ────────────────────────────

def _make_bug_review(review_id: str) -> dict:
    action = random.choice(BUG_ACTIONS)
    device = random.choice(DEVICES)
    os_ver = random.choice(OS_VERSIONS)
    version = random.choice(VERSIONS)
    tmpl, subject = random.choice(BUG_REVIEW_TEMPLATES)
    text = _fill(tmpl, action=action, device=device, os=os_ver,
                 version=version, data_issue=random.choice(DATA_ISSUES))
    return {
        "review_id": review_id,
        "app_name": random.choice(APP_NAMES),
        "review_text": text,
        "rating": random.choice([1, 1, 2]),
        "platform": random.choice(PLATFORMS),
        "app_version": version,
        "date": _rand_date(),
        "user_name": _rand_name(),
        "_category": "Bug",
        "_subject": subject,
        "_device": device,
        "_os": os_ver,
        "_action": action,
    }


def _make_feature_review(review_id: str) -> dict:
    feature = random.choice(FEATURES)
    version = random.choice(VERSIONS)
    tmpl, subject = random.choice(FEATURE_REVIEW_TEMPLATES)
    text = _fill(tmpl, feature=feature, version=version)
    return {
        "review_id": review_id,
        "app_name": random.choice(APP_NAMES),
        "review_text": text,
        "rating": random.choice([3, 3, 4]),
        "platform": random.choice(PLATFORMS),
        "app_version": version,
        "date": _rand_date(),
        "user_name": _rand_name(),
        "_category": "Feature Request",
        "_subject": subject,
        "_device": None,
        "_os": None,
        "_action": None,
    }


def _make_praise_review(review_id: str) -> dict:
    feature = random.choice(FEATURES)
    version = random.choice(VERSIONS)
    tmpl = random.choice(PRAISE_REVIEW_TEMPLATES)[0]
    text = _fill(tmpl, feature=feature, version=version)
    return {
        "review_id": review_id,
        "app_name": random.choice(APP_NAMES),
        "review_text": text,
        "rating": random.choice([4, 5, 5]),
        "platform": random.choice(PLATFORMS),
        "app_version": version,
        "date": _rand_date(),
        "user_name": _rand_name(),
        "_category": "Praise",
        "_subject": "Positive Review",
        "_device": None,
        "_os": None,
        "_action": None,
    }


def _make_complaint_review(review_id: str) -> dict:
    version = random.choice(VERSIONS)
    tmpl = random.choice(COMPLAINT_REVIEW_TEMPLATES)[0]
    text = _fill(tmpl, version=version)
    return {
        "review_id": review_id,
        "app_name": random.choice(APP_NAMES),
        "review_text": text,
        "rating": random.choice([1, 2, 2, 3]),
        "platform": random.choice(PLATFORMS),
        "app_version": version,
        "date": _rand_date(),
        "user_name": _rand_name(),
        "_category": "Complaint",
        "_subject": "User Complaint",
        "_device": None,
        "_os": None,
        "_action": None,
    }


def _make_spam_review(review_id: str) -> dict:
    version = random.choice(VERSIONS)
    tmpl = random.choice(SPAM_REVIEW_TEMPLATES)[0]
    text = _fill(tmpl, url=random.choice(SPAM_URLS))
    return {
        "review_id": review_id,
        "app_name": random.choice(APP_NAMES),
        "review_text": text,
        "rating": random.choice([1, 3, 5]),
        "platform": random.choice(PLATFORMS),
        "app_version": version,
        "date": _rand_date(),
        "user_name": _rand_name(),
        "_category": "Spam",
        "_subject": "Spam Content",
        "_device": None,
        "_os": None,
        "_action": None,
    }


def generate_reviews(n: int) -> list[dict]:
    # Distribution: 30% bug, 25% feature, 20% praise, 15% complaint, 10% spam
    weights = [("bug", 0.30), ("feature", 0.25), ("praise", 0.20),
               ("complaint", 0.15), ("spam", 0.10)]
    makers = {
        "bug": _make_bug_review,
        "feature": _make_feature_review,
        "praise": _make_praise_review,
        "complaint": _make_complaint_review,
        "spam": _make_spam_review,
    }

    categories = [c for c, w in weights for _ in range(round(w * n))]
    while len(categories) < n:
        categories.append(random.choice([c for c, _ in weights]))
    random.shuffle(categories[:n])

    reviews = []
    for i, cat in enumerate(categories[:n], start=1):
        row = makers[cat](f"REV{i:05d}")
        reviews.append(row)
    return reviews


# ──────────────────────────── email generators ────────────────────────────

def _make_bug_email(email_id: str) -> dict:
    name = _rand_name()
    action = random.choice(BUG_ACTIONS)
    device = random.choice(DEVICES)
    os_ver = random.choice(OS_VERSIONS)
    version = random.choice(VERSIONS)
    section = random.choice(SECTIONS)
    issue = random.choice(DATA_ISSUES)
    tmpl = random.choice(BUG_EMAIL_BODIES)
    body = _fill(tmpl, action=action, device=device, os=os_ver,
                 version=version, section=section, name=name, issue=issue)
    priority_choices = ["High", "High", "Medium", "Critical", ""]
    return {
        "email_id": email_id,
        "subject": random.choice(BUG_EMAIL_SUBJECTS),
        "body": body,
        "sender_email": _rand_email(name),
        "timestamp": _rand_date(90),
        "priority": random.choice(priority_choices),
        "_category": "Bug",
        "_device": device,
        "_os": os_ver,
        "_action": action,
        "_version": version,
    }


def _make_feature_email(email_id: str) -> dict:
    name = _rand_name()
    feature = random.choice(FEATURES)
    months = random.choice(MONTHS)
    tmpl = random.choice(FEATURE_EMAIL_BODIES)
    body = _fill(tmpl, feature=feature, months=months, name=name)
    return {
        "email_id": email_id,
        "subject": random.choice(FEATURE_EMAIL_SUBJECTS),
        "body": body,
        "sender_email": _rand_email(name),
        "timestamp": _rand_date(90),
        "priority": random.choice(["Low", "Medium", ""]),
        "_category": "Feature Request",
        "_device": None,
        "_os": None,
        "_action": None,
        "_version": None,
    }


def generate_emails(n: int) -> list[dict]:
    # 60% bug, 40% feature
    makers = ["bug"] * round(n * 0.6) + ["feature"] * round(n * 0.4)
    while len(makers) < n:
        makers.append(random.choice(["bug", "feature"]))
    random.shuffle(makers[:n])

    fns = {"bug": _make_bug_email, "feature": _make_feature_email}
    emails = []
    for i, kind in enumerate(makers[:n], start=1):
        emails.append(fns[kind](f"EML{i:05d}"))
    return emails


# ──────────────────────────── classification builder ────────────────────────────

_PRIORITY_MAP = {
    "Bug": {"Critical": 0.15, "High": 0.45, "Medium": 0.30, "Low": 0.10},
    "Feature Request": {"Critical": 0.0, "High": 0.10, "Medium": 0.50, "Low": 0.40},
    "Praise": {"Critical": 0.0, "High": 0.0, "Medium": 0.20, "Low": 0.80},
    "Complaint": {"Critical": 0.05, "High": 0.30, "Medium": 0.45, "Low": 0.20},
    "Spam": {"Critical": 0.0, "High": 0.0, "Medium": 0.0, "Low": 1.0},
}


def _pick_priority(category: str) -> str:
    dist = _PRIORITY_MAP.get(category, {"Medium": 1.0})
    priorities = list(dist.keys())
    weights = list(dist.values())
    return random.choices(priorities, weights=weights, k=1)[0]


def _tech_details(row: dict, category: str) -> str:
    if category != "Bug":
        return ""
    parts = []
    if row.get("_device"):
        parts.append(f"Device: {row['_device']}")
    if row.get("_os"):
        parts.append(f"OS: {row['_os']}")
    if row.get("_action"):
        parts.append(f"Trigger: {row['_action']}")
    version = row.get("_version") or row.get("version")
    if version:
        parts.append(f"App version: {version}")
    return " | ".join(parts)


def _suggested_title(category: str, row: dict) -> str:
    if category == "Bug":
        action = row.get("_action", "perform action") or "perform action"
        return f"[Bug] App fails to {action}"
    if category == "Feature Request":
        subject = row.get("_subject", "Feature Request")
        return subject
    if category == "Praise":
        return "[Praise] Positive user feedback"
    if category == "Complaint":
        return "[Complaint] Negative user experience reported"
    return "[Spam] Flagged for removal"


def build_classifications(reviews: list[dict], emails: list[dict]) -> list[dict]:
    rows = []
    for r in reviews:
        cat = r["_category"]
        rows.append({
            "source_id": r["review_id"],
            "source_type": "review",
            "category": cat,
            "priority": _pick_priority(cat),
            "technical_details": _tech_details(r, cat),
            "suggested_title": _suggested_title(cat, r),
        })
    for e in emails:
        cat = e["_category"]
        rows.append({
            "source_id": e["email_id"],
            "source_type": "email",
            "category": cat,
            "priority": _pick_priority(cat),
            "technical_details": _tech_details(e, cat),
            "suggested_title": _suggested_title(cat, e),
        })
    return rows


# ──────────────────────────── CSV writers ────────────────────────────

_REVIEW_COLS = ["review_id", "app_name", "review_text", "rating",
                "platform", "app_version", "date", "user_name"]
_EMAIL_COLS = ["email_id", "subject", "body", "sender_email", "timestamp", "priority"]
_CLASS_COLS = ["source_id", "source_type", "category", "priority",
               "technical_details", "suggested_title"]


def _write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written {len(rows):>4} rows → {path}")


# ──────────────────────────── summary ────────────────────────────

def _print_summary(reviews: list[dict], emails: list[dict], clsf: list[dict]) -> None:
    from collections import Counter

    print("\n── Data Inventory ────────────────────────────────────")
    print(f"{'Entity':<30} {'Fields':<8} {'Records'}")
    print(f"{'app_store_reviews.csv':<30} {len(_REVIEW_COLS):<8} {len(reviews)}")
    print(f"{'support_emails.csv':<30} {len(_EMAIL_COLS):<8} {len(emails)}")
    print(f"{'expected_classifications.csv':<30} {len(_CLASS_COLS):<8} {len(clsf)}")

    print("\n── Review distribution ───────────────────────────────")
    for cat, cnt in sorted(Counter(r["_category"] for r in reviews).items()):
        print(f"  {cat:<20} {cnt}")

    print("\n── Email distribution ────────────────────────────────")
    for cat, cnt in sorted(Counter(e["_category"] for e in emails).items()):
        print(f"  {cat:<20} {cnt}")

    print("\n── Classification priority distribution ──────────────")
    for pri, cnt in sorted(Counter(c["priority"] for c in clsf).items()):
        print(f"  {pri:<12} {cnt}")
    print()


# ──────────────────────────── main ────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate dummy CSV data for the feedback pipeline."
    )
    parser.add_argument("--reviews", type=int, default=120,
                        help="Number of app reviews to generate (default: 120)")
    parser.add_argument("--emails", type=int, default=60,
                        help="Number of support emails to generate (default: 60)")
    parser.add_argument("--output", type=str, default="data/input",
                        help="Output directory (default: data/input)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.reviews} reviews and {args.emails} emails …")

    reviews = generate_reviews(args.reviews)
    emails = generate_emails(args.emails)
    classifications = build_classifications(reviews, emails)

    _write_csv(out_dir / "app_store_reviews.csv", reviews, _REVIEW_COLS)
    _write_csv(out_dir / "support_emails.csv", emails, _EMAIL_COLS)
    _write_csv(out_dir / "expected_classifications.csv", classifications, _CLASS_COLS)

    _print_summary(reviews, emails, classifications)
    print("Done. Load the CSVs from:", out_dir.resolve())


if __name__ == "__main__":
    main()
