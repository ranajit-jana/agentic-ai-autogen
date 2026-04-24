import pandas as pd
from config import REVIEWS_FILE, EMAILS_FILE


class CSVReaderAgent:
    def read_all(self) -> list[dict]:
        reviews = self._read_reviews()
        emails = self._read_emails()
        return sorted(reviews + emails, key=lambda x: (x["source_type"], x["id"]))

    def _read_reviews(self) -> list[dict]:
        df = pd.read_csv(REVIEWS_FILE)
        items = []
        for _, row in df.iterrows():
            text = str(row["review_text"]).strip()
            items.append({
                "id": str(row["review_id"]),
                "source_type": "review",
                "text": text,
                "metadata": {
                    "platform": row["platform"],
                    "rating": int(row["rating"]),
                    "user_name": row["user_name"],
                    "date": row["date"],
                    "app_version": str(row["app_version"]),
                },
            })
        return items

    def _read_emails(self) -> list[dict]:
        df = pd.read_csv(EMAILS_FILE)
        items = []
        for _, row in df.iterrows():
            subject = str(row["subject"]).strip()
            body = str(row["body"]).strip()
            text = f"{subject}\n\n{body}"
            items.append({
                "id": str(row["email_id"]),
                "source_type": "email",
                "text": text,
                "metadata": {
                    "subject": subject,
                    "sender_email": row["sender_email"],
                    "timestamp": row["timestamp"],
                    "priority": str(row["priority"]) if pd.notna(row["priority"]) else "",
                },
            })
        return items
