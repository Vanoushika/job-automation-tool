import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure


class JobDatabase:
    """
    MongoDB-backed job storage.
    Falls back to in-memory list if MONGODB_URI is not set (local dev without Atlas).
    """

    def __init__(self):
        uri = os.getenv("MONGODB_URI", "")
        self._client = None
        self._collection = None

        if uri and uri != "mongodb+srv://user:pass@cluster.mongodb.net/":
            try:
                self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
                self._client.admin.command("ping")
                db = self._client["job_automation"]
                self._collection = db["jobs"]
                # Index for fast lookups
                self._collection.create_index("id", unique=True)
                self._collection.create_index([("best_score", DESCENDING)])
                print("[DB] Connected to MongoDB Atlas")
            except Exception as e:
                print(f"[DB] MongoDB connection failed: {e} — falling back to JSON")
                self._client = None
                self._collection = None

    @property
    def connected(self) -> bool:
        return self._collection is not None

    # ── Write ────────────────────────────────────────────────────────────── #

    def save_jobs(self, jobs: List[Dict]) -> int:
        """Upsert jobs by their id. Returns count saved."""
        if not self.connected:
            return 0

        saved = 0
        for job in jobs:
            try:
                # Never overwrite posted_date on re-runs — preserve the original posting time
                job_without_posted = {k: v for k, v in job.items() if k != "posted_date"}
                self._collection.update_one(
                    {"id": job["id"]},
                    {
                        "$set": {**job_without_posted, "updated_at": datetime.now(timezone.utc).isoformat()},
                        "$setOnInsert": {"posted_date": job.get("posted_date")},
                    },
                    upsert=True,
                )
                saved += 1
            except Exception as e:
                print(f"[DB] Save error for {job.get('company')}: {e}")
        return saved

    def mark_applied(self, job_id: str) -> bool:
        if not self.connected:
            return False
        result = self._collection.update_one(
            {"id": job_id},
            {"$set": {"applied": True, "applied_at": datetime.now(timezone.utc).isoformat()}}
        )
        return result.modified_count > 0

    # ── Read ─────────────────────────────────────────────────────────────── #

    def get_jobs(
        self,
        tier: Optional[str] = None,
        job_type: Optional[str] = None,
        applied: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        if not self.connected:
            return []

        query = {}
        if tier and tier != "all":
            query["tier"] = tier.upper()
        if job_type and job_type != "all":
            query["job_type"] = job_type
        if applied is not None:
            query["applied"] = applied
        if search:
            query["$or"] = [
                {"company": {"$regex": search, "$options": "i"}},
                {"role":    {"$regex": search, "$options": "i"}},
            ]

        cursor = self._collection.find(
            query,
            {"_id": 0}  # exclude MongoDB internal _id
        ).sort("best_score", DESCENDING).limit(limit)

        return list(cursor)

    def get_stats(self) -> Dict:
        if not self.connected:
            return {}

        pipeline = [
            {"$group": {
                "_id": None,
                "total":     {"$sum": 1},
                "tier_a":    {"$sum": {"$cond": [{"$eq": ["$tier", "A"]}, 1, 0]}},
                "tier_b":    {"$sum": {"$cond": [{"$eq": ["$tier", "B"]}, 1, 0]}},
                "tier_c":    {"$sum": {"$cond": [{"$eq": ["$tier", "C"]}, 1, 0]}},
                "tier_d":    {"$sum": {"$cond": [{"$eq": ["$tier", "D"]}, 1, 0]}},
                "applied":   {"$sum": {"$cond": ["$applied", 1, 0]}},
                "full_time": {"$sum": {"$cond": [{"$eq": ["$job_type", "full_time"]}, 1, 0]}},
                "contract":  {"$sum": {"$cond": [{"$eq": ["$job_type", "contract"]}, 1, 0]}},
            }}
        ]
        result = list(self._collection.aggregate(pipeline))
        if not result:
            return {"total": 0, "tier_a": 0, "tier_b": 0, "tier_c": 0,
                    "tier_d": 0, "applied": 0, "full_time": 0, "contract": 0}
        row = result[0]
        row.pop("_id", None)
        return row
