import copy
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from asset_library import choose_pair, pair_reasons, review_errors, identity
from discover_assets import video_record, refresh_video
from upload_history import fingerprint

def reviewed(kind, identifier=1):
    labels = {"setting": "window", "intensity": "gentle", "surface": "glass", "perspective": "indoors"}
    labels.update(dict.fromkeys(("thunder", "traffic", "animals", "music", "voices"), False))
    labels["style"] = "illustrated"
    return {"id": identifier, "pexels_id": identifier, "freesound_id": identifier,
            "asset_id": f"pexels:{identifier}" if kind == "video" else f"freesound:{identifier}",
            "width": 1920, "height": 1080, "duration": 30,
            "source_url": "https://example.com/source", "license_url": "https://example.com/license",
            "review": {"approved": True, "reviewed_at": "2026-09-29", "notes": "Reviewed full source and loop",
                       "rights_checked": True, "labels": labels,
                       "quality": dict.fromkeys(("full_playback", "loop_checked", "sharp", "stable",
                                               "rain_visible", "clean_recording", "no_clipping"), True)}}

class LibraryTests(unittest.TestCase):
    def test_legacy_approval_is_insufficient(self):
        self.assertTrue(review_errors({"review": {"approved": True, "labels": {}}}, "audio"))

    def test_unknown_event_is_not_false(self):
        a = reviewed("audio")
        del a["review"]["labels"]["thunder"]
        self.assertIn("thunder must be true or false (unknown cannot publish)", review_errors(a, "audio"))

    def test_quality_and_rights_are_required(self):
        v = reviewed("video")
        self.assertEqual(review_errors(v, "video"), [])
        v["review"]["rights_checked"] = False
        self.assertTrue(review_errors(v, "video"))

    def test_surface_and_perspective_conflicts(self):
        a, v = reviewed("audio"), reviewed("video")
        a["review"]["labels"]["surface"] = "metal"
        self.assertTrue(pair_reasons(a, v))
        a["review"]["labels"]["surface"] = "glass"
        a["review"]["labels"]["perspective"] = "outdoors"
        self.assertTrue(pair_reasons(a, v))

    def test_rejected_not_selected_even_in_preview(self):
        a, v = reviewed("audio"), reviewed("video")
        v["review"]["status"] = "rejected"
        with self.assertRaises(RuntimeError):
            choose_pair([v], [a], {}, random.Random(1), strict=False)

    def test_reserved_pair_excluded_with_old_ledger_format(self):
        v, a = reviewed("video"), reviewed("audio")
        history = {"old": {"assets": {"date": "2026-09-20",
                    "video": {"pexels_id": 1}, "audio": {"freesound_id": 1}}}}
        with self.assertRaises(RuntimeError):
            choose_pair([v], [a], history, random.Random(1))

    def test_unused_individuals_preferred(self):
        v1, v2 = reviewed("video", 1), reviewed("video", 2)
        a1, a2 = reviewed("audio", 1), reviewed("audio", 2)
        history = {"old": {"assets": {"date": "2026-09-20", "video": v1, "audio": a1}}}
        v, a, why = choose_pair([v1, v2], [a1, a2], history, random.Random(1))
        self.assertEqual((v["pexels_id"], a["id"]), (2, 2))
        self.assertEqual(why["rotation_score"][0], 0)

    def test_legacy_fingerprint_preserved(self):
        import hashlib
        expected = hashlib.sha256(json.dumps(["123", "456"]).encode()).hexdigest()
        self.assertEqual(fingerprint({"video": {"pexels_id": 123},
                                      "audio": {"freesound_id": 456}}), expected)

    def test_external_fingerprint_is_distinct(self):
        a = {"video": {"asset_id": "local:study"}, "audio": {"freesound_id": 456}}
        b = copy.deepcopy(a); b["video"]["asset_id"] = "local:garden"
        self.assertNotEqual(fingerprint(a), fingerprint(b))

class DiscoveryTests(unittest.TestCase):
    def test_native_resolution_and_duration(self):
        video = {"id": 5, "url": "https://pexels.com/video/5", "duration": 20,
                 "video_files": [{"file_type": "video/mp4", "width": 1280, "height": 720, "link": "low"}]}
        self.assertIsNone(video_record(video))
        video["video_files"].append({"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "good"})
        candidate = video_record(video)
        self.assertEqual(candidate["download_url"], "good")
        self.assertFalse(candidate["review"]["approved"])
        video["duration"] = 4
        self.assertIsNone(video_record(video))

    def test_refresh_cannot_silently_replace_clip(self):
        response = Mock()
        response.json.return_value = {"id": 99, "url": "https://pexels.com/video/99", "duration": 20,
            "video_files": [{"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "file"}]}
        with patch("discover_assets.requests.get", return_value=response):
            with self.assertRaises(RuntimeError):
                refresh_video({"pexels_id": 1}, "test")

    def test_search_cannot_publish(self):
        import select_assets
        with patch.dict(os.environ, {"PIPELINE_MODE": "publish", "ASSET_SELECTION": "search"}, clear=True), \
             patch.object(select_assets, "Ledger"), patch.object(select_assets, "pick_scene_video") as pick:
            with self.assertRaisesRegex(ValueError, "preview-only"):
                select_assets.main()
            pick.assert_not_called()

    def test_search_rejects_ignored_exact_video_override(self):
        import select_assets
        with patch.dict(os.environ, {"PIPELINE_MODE": "preview", "ASSET_SELECTION": "search", "VIDEO_ID": "pexels:1"}, clear=True), \
             patch.object(select_assets, "Ledger"), patch.object(select_assets, "pick_scene_video") as pick:
            with self.assertRaisesRegex(ValueError, "require curated"):
                select_assets.main()
            pick.assert_not_called()

    def test_search_preview_excludes_rejected_audio(self):
        import select_assets
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metadata.json").write_text(json.dumps([
                {"id": 1, "filename": "1.mp3", "review": {"status": "rejected"}},
                {"id": 2, "filename": "2.mp3", "review": {"approved": False}}]))
            (root / "2.mp3").write_bytes(b"test")
            with patch.object(select_assets, "AUDIO_DIR", root), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(select_assets.pick_audio_track(random.Random(1))["id"], 2)

    def test_balanced_audio_preserves_old_reviews(self):
        import fetch_audio_pool as fetch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "data").mkdir(); (root / "audio").mkdir()
            (root / "data/audio_discovery.json").write_text(json.dumps({"forest": ["rain forest"], "roof": ["rain roof"]}))
            old = {"id": 9, "review": {"approved": True, "notes": "Keep this"}}
            (root / "audio/metadata.json").write_text(json.dumps([old]))
            def search(query, key, page):
                number = 1 if "forest" in query else 2
                return {"results": [{"id": number, "name": "rain", "license": "Creative Commons 0"}]}
            with patch.object(fetch, "ROOT", root), patch.object(fetch, "AUDIO_DIR", root/"audio"), \
                 patch.object(fetch, "METADATA_PATH", root/"audio/metadata.json"), \
                 patch.object(fetch, "FREESOUND_API_KEY", "test"), \
                 patch.object(fetch, "search_tag", side_effect=search), \
                 patch.object(fetch, "download_preview", return_value=True), \
                 patch.dict(os.environ, {"AUDIO_NEW_LIMIT": "2"}):
                fetch.main()
            pool = json.loads((root/"audio/metadata.json").read_text())
            self.assertEqual(pool[0], old)
            self.assertEqual({a["discovery_category"] for a in pool[1:]}, {"forest", "roof"})
            self.assertTrue(all(not a["review"]["approved"] for a in pool[1:]))

class ReviewTests(unittest.TestCase):
    def test_invalid_approval_does_not_overwrite_existing_review(self):
        import review_assets as review
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "audio").mkdir(); (root / "data").mkdir()
            original = [{"id": 1, "review": {"approved": False, "notes": "preserve"}}]
            metadata = root / "audio/metadata.json"
            metadata.write_text(json.dumps(original))
            edits = root / "edits.json"
            edits.write_text(json.dumps([{"kind": "audio", "id": "1", "review": {"approved": True}}]))
            with patch.object(review, "ROOT", root):
                with self.assertRaises(ValueError):
                    review.apply(edits)
            self.assertEqual(json.loads(metadata.read_text()), original)

    def test_candidate_import_preserves_existing_reviews(self):
        import review_assets as review
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; bundle = Path(tmp) / "bundle"
            for base in (root, bundle):
                (base / "audio").mkdir(parents=True); (base / "data").mkdir()
            original = {"id": 1, "filename": "1.mp3", "review": {"approved": True, "notes": "preserve"}}
            (root / "audio/metadata.json").write_text(json.dumps([original]))
            (root / "audio/1.mp3").write_bytes(b"original")
            (bundle / "audio/metadata.json").write_text(json.dumps([
                {"id": 1, "filename": "1.mp3"}, {"id": 2, "filename": "2.mp3", "review": {"approved": True}}]))
            (bundle / "audio/2.mp3").write_bytes(b"new")
            with patch.object(review, "ROOT", root):
                review.import_candidates(bundle)
            result = json.loads((root / "audio/metadata.json").read_text())
            self.assertEqual(result[0], original)
            self.assertFalse(result[1]["review"]["approved"])
            self.assertEqual((root / "audio/1.mp3").read_bytes(), b"original")

    def test_missing_candidate_leaves_no_partial_files(self):
        import review_assets as review
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; bundle = Path(tmp) / "bundle"
            for base in (root, bundle):
                (base / "audio").mkdir(parents=True); (base / "data").mkdir()
            (bundle / "audio/metadata.json").write_text(json.dumps([
                {"id": 1, "filename": "1.mp3"}, {"id": 2, "filename": "2.mp3"}]))
            (bundle / "audio/1.mp3").write_bytes(b"new")
            with patch.object(review, "ROOT", root):
                with self.assertRaises(ValueError):
                    review.import_candidates(bundle)
            self.assertFalse((root / "audio/1.mp3").exists())

if __name__ == "__main__":
    unittest.main()
