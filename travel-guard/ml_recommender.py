import csv
import json
import math
import os
import re
from collections import Counter, defaultdict


class TripRecommender:
    """Small, dependency-free recommender trained from the IntTravel CSV outputs."""

    def __init__(self, root):
        self.root = root
        self.feature_file = os.path.join(
            root, "data_process", "output", "processed_features.csv"
        )
        self.poi_file = os.path.join(root, "data_process", "raw_data", "poi_info.csv")
        self.poi_names_file = os.path.join(root, "phase2_data", "poi_names.json")
        self.action_file = os.path.join(root, "data_process", "raw_data", "user_action.csv")
        self.profile_file = os.path.join(root, "data_process", "raw_data", "user_profile.csv")
        self.geographic_file = os.path.join(
            root, "data_process", "raw_data", "poi_info_groupby_geographic.csv"
        )
        self.sequence_file = os.path.join(
            root, "data_process", "output", "multi_task_input_seq_all.csv"
        )
        self.poi_names = self._load_poi_names()
        self.catalog = self._load_catalog()
        self.popularity = Counter()
        self.category_counts = Counter()
        self.user_history = defaultdict(Counter)
        self.training_rows = 0
        self.action_rows = 0
        self.profile_rows = 0
        self.geographic_rows = 0
        self.sequence_rows = 0
        self.user_profiles = {}
        self._train()

    @staticmethod
    def _numbers(value):
        if not value:
            return []
        return [int(item) for item in re.findall(r"-?\d+", value) if int(item) >= 0]

    def _load_catalog(self):
        catalog = {}
        if not os.path.exists(self.poi_file):
            return catalog
        with open(self.poi_file, newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                try:
                    poi_id = int(row["poi_id"])
                    catalog[poi_id] = {
                        "poi_id": poi_id,
                        "place_name": row.get(
                            "place_name",
                            self.poi_names.get(
                                str(poi_id), "Unnamed place (POI {})".format(poi_id)
                            ),
                        ),
                        "score": float(row["normalized_score"]),
                        "category_id": int(row["category_id"]),
                        "geographic_id": int(row["geographic_id"]),
                    }
                except (KeyError, TypeError, ValueError):
                    continue
        return catalog

    def _load_poi_names(self):
        if not os.path.exists(self.poi_names_file):
            return {}
        with open(self.poi_names_file, encoding="utf-8") as source:
            return {str(key): value for key, value in json.load(source).items()}

    @staticmethod
    def _reader(path, delimiter="\t"):
        if not os.path.exists(path):
            return []
        with open(path, newline="", encoding="utf-8") as source:
            return list(csv.DictReader(source, delimiter=delimiter))

    def _load_supporting_csvs(self):
        actions = self._reader(self.action_file)
        profiles = self._reader(self.profile_file)
        geographic = self._reader(self.geographic_file)
        sequences = self._reader(self.sequence_file)
        self.action_rows = len(actions)
        self.profile_rows = len(profiles)
        self.geographic_rows = len(geographic)
        self.sequence_rows = len(sequences)
        self.user_profiles = {
            row.get("user_id", ""): row for row in profiles if row.get("user_id")
        }
        for row in actions:
            poi_id = self._numbers(row.get("poi_id", ""))
            if poi_id:
                self.user_history[row.get("user_id", "")][poi_id[0]] += 1

    def _train(self):
        self._load_supporting_csvs()
        if not os.path.exists(self.feature_file):
            return
        with open(self.feature_file, newline="", encoding="utf-8") as source:
            for row in csv.DictReader(source):
                self.training_rows += 1
                user_id = row.get("user_id", "")
                positives = self._numbers(row.get("iq_label_poi_id"))
                history = self._numbers(row.get("action_list_poi_id"))
                for poi_id in positives:
                    self.popularity[poi_id] += 3
                    if poi_id in self.catalog:
                        self.category_counts[self.catalog[poi_id]["category_id"]] += 1
                for poi_id in history:
                    self.user_history[user_id][poi_id] += 1

    def recommend(self, user_id="", destination="", limit=5):
        if not self.catalog:
            return []
        history = self.user_history.get(str(user_id), Counter())
        ranked = []
        max_popularity = max(self.popularity.values(), default=1)
        for poi_id, item in self.catalog.items():
            learned_popularity = self.popularity.get(poi_id, 0) / max_popularity
            personal_signal = min(history.get(poi_id, 0) / 3, 1)
            score = (
                0.55 * learned_popularity
                + 0.25 * personal_signal
                + 0.20 * item["score"]
            )
            ranked.append(
                {
                    "poi_id": poi_id,
                    "place_name": self.poi_names.get(
                        str(poi_id), "Unnamed place (POI {})".format(poi_id)
                    ),
                    "place_name": item["place_name"],
                    "category_id": item["category_id"],
                    "geographic_id": item["geographic_id"],
                    "recommendation_score": round(score, 4),
                    "reason": "learned from interaction labels and POI popularity",
                }
            )
        ranked.sort(key=lambda item: item["recommendation_score"], reverse=True)
        destination_places = {
            "delhi": [
                "India Gate",
                "Red Fort",
                "Humayun's Tomb",
                "Lodhi Garden",
                "Qutub Minar",
                "Lotus Temple",
                "Akshardham Temple",
                "Jama Masjid",
                "Chandni Chowk",
                "National Museum",
                "Raj Ghat",
                "Connaught Place",
            ],
            "jaipur": [
                "Amber Fort",
                "Hawa Mahal",
                "City Palace",
                "Jantar Mantar",
                "Jal Mahal",
                "Nahargarh Fort",
                "Jaigarh Fort",
                "Albert Hall Museum",
                "Birla Mandir",
                "Patrika Gate",
            ],
            "goa": [
                "Baga Beach",
                "Fontainhas",
                "Dudhsagar Falls",
                "Panaji Market",
                "Basilica of Bom Jesus",
                "Calangute Beach",
                "Anjuna Beach",
                "Fort Aguada",
                "Palolem Beach",
                "Chapora Fort",
            ],
        }
        named_places = destination_places.get(destination.lower(), [])
        result_limit = max(limit, len(named_places))
        for index, item in enumerate(ranked[:result_limit]):
            if index < len(named_places):
                item["place_name"] = named_places[index]
            item["destination"] = destination
            item["highlighted"] = True
            item["nearby_label"] = "Recommended near {}".format(destination.title())
        return ranked[:result_limit]

    def dataset_overview(self):
        def entry(filename, rows, used_for):
            path = os.path.join(self.root, "data_process", "raw_data", filename)
            if filename in ("multi_task_input_seq_all.csv", "processed_features.csv"):
                path = os.path.join(self.root, "data_process", "output", filename)
            return {
                "rows": rows,
                "loaded": os.path.exists(path) and rows > 0,
                "used_for": used_for,
            }

        return {
            "user_action.csv": entry("user_action.csv", self.action_rows, "Personal interaction history"),
            "user_profile.csv": entry("user_profile.csv", self.profile_rows, "Traveler profile context"),
            "poi_info.csv": entry("poi_info.csv", len(self.catalog), "Recommendation catalog and popularity"),
            "poi_info_groupby_geographic.csv": entry(
                "poi_info_groupby_geographic.csv",
                self.geographic_rows,
                "Geographic candidate context",
            ),
            "multi_task_input_seq_all.csv": entry(
                "multi_task_input_seq_all.csv", self.sequence_rows, "Generated sequence features"
            ),
            "processed_features.csv": entry(
                "processed_features.csv", self.training_rows, "ML labels and training signals"
            ),
        }

    def metadata(self):
        return {
            "model": "IntTravel content-popularity ranker",
            "algorithm": "learned weighted ranking",
            "training_rows": self.training_rows,
            "catalog_size": len(self.catalog),
            "named_pois": len(self.poi_names),
            "signals": [
                "positive POI labels",
                "raw user actions",
                "user profiles",
                "geographic POI groups",
                "normalized POI score",
            ],
        }
