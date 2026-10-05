"""
Phase 8 tests: albums, locations (coordinate clustering), timeline
grouping, favorite toggling, and the "delete all my data" settings action.
"""
import io

import piexif
from PIL import Image

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


def _jpeg(color=(150, 150, 150), date_str=None, lat=None, lon=None) -> bytes:
    img = Image.new("RGB", (300, 200), color=color)
    buf = io.BytesIO()
    if date_str or lat is not None:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}}
        if date_str:
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str.encode()
        if lat is not None and lon is not None:
            def dms(deg):
                d = int(deg)
                m = int((deg - d) * 60)
                s = int((((deg - d) * 60) - m) * 60 * 100)
                return ((d, 1), (m, 1), (s, 100))

            exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = b"N" if lat >= 0 else b"S"
            exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = dms(abs(lat))
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = b"E" if lon >= 0 else b"W"
            exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = dms(abs(lon))
        img.save(buf, "jpeg", exif=piexif.dump(exif_dict))
    else:
        img.save(buf, "jpeg")
    return buf.getvalue()


def _upload(token, **kwargs):
    filename = kwargs.pop("filename", "photo.jpg")
    files = [("files", (filename, _jpeg(**kwargs), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    return res.json()["results"][0]["photo_id"]


# --- Albums ---


def test_create_album_and_add_photos():
    token = _register_and_login()
    photo_id = _upload(token, filename="a.jpg")

    album = client.post("/api/albums", headers=_auth(token), json={"name": "Trip"}).json()
    assert album["photo_count"] == 0

    res = client.post(f"/api/albums/{album['id']}/photos", headers=_auth(token), json={"photo_ids": [photo_id]})
    assert res.status_code == 200
    assert res.json()["photo_count"] == 1
    assert res.json()["cover_photo_id"] == photo_id

    photos = client.get(f"/api/albums/{album['id']}/photos", headers=_auth(token)).json()
    assert photos["total"] == 1
    assert photos["items"][0]["id"] == photo_id


def test_albums_isolated_per_user():
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")
    album = client.post("/api/albums", headers=_auth(token_a), json={"name": "Mine"}).json()

    assert client.get(f"/api/albums/{album['id']}/photos", headers=_auth(token_b)).status_code == 404
    assert client.delete(f"/api/albums/{album['id']}", headers=_auth(token_b)).status_code == 404
    assert client.get("/api/albums", headers=_auth(token_b)).json() == []


def test_cannot_add_another_users_photo_to_album():
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")
    photo_b = _upload(token_b, filename="b.jpg")

    album = client.post("/api/albums", headers=_auth(token_a), json={"name": "Mine"}).json()
    res = client.post(f"/api/albums/{album['id']}/photos", headers=_auth(token_a), json={"photo_ids": [photo_b]})
    assert res.status_code == 404  # not "silently succeeds with 0 added"


# --- Locations ---


def test_locations_cluster_by_rounded_coordinates():
    token = _register_and_login()
    _upload(token, lat=26.8467, lon=80.9462, filename="lucknow1.jpg")
    _upload(token, lat=26.8468, lon=80.9463, filename="lucknow2.jpg")  # same cluster (rounds the same)
    _upload(token, lat=28.7041, lon=77.1025, filename="delhi.jpg")  # different cluster

    clusters = client.get("/api/locations", headers=_auth(token)).json()
    assert len(clusters) == 2
    counts = sorted(c["photo_count"] for c in clusters)
    assert counts == [1, 2]


def test_photos_without_gps_excluded_from_locations():
    token = _register_and_login()
    _upload(token, filename="no_gps.jpg")  # no lat/lon at all
    assert client.get("/api/locations", headers=_auth(token)).json() == []


# --- Timeline ---


def test_timeline_groups_by_year_and_month():
    token = _register_and_login()
    _upload(token, date_str="2025:08:15 10:00:00", filename="aug1.jpg")
    _upload(token, date_str="2025:08:20 10:00:00", filename="aug2.jpg")
    _upload(token, date_str="2025:03:01 10:00:00", filename="mar.jpg")

    timeline = client.get("/api/photos/timeline", headers=_auth(token)).json()
    by_month = {(e["year"], e["month"]): e["count"] for e in timeline}
    assert by_month[(2025, 8)] == 2
    assert by_month[(2025, 3)] == 1


def test_photos_filtered_by_capture_year_and_month():
    token = _register_and_login()
    aug_photo = _upload(token, date_str="2025:08:15 10:00:00", filename="aug.jpg")
    _upload(token, date_str="2025:03:01 10:00:00", filename="mar.jpg")

    res = client.get("/api/photos", headers=_auth(token), params={"capture_year": 2025, "capture_month": 8}).json()
    assert res["total"] == 1
    assert res["items"][0]["id"] == aug_photo


# --- Favorites ---


def test_toggle_favorite():
    token = _register_and_login()
    photo_id = _upload(token, filename="a.jpg")

    res = client.patch(f"/api/photos/{photo_id}/favorite", headers=_auth(token), params={"is_favorite": True})
    assert res.json()["is_favorite"] is True

    res2 = client.patch(f"/api/photos/{photo_id}/favorite", headers=_auth(token), params={"is_favorite": False})
    assert res2.json()["is_favorite"] is False


# --- Delete all data ---


def test_delete_all_data_wipes_everything_but_keeps_the_account():
    token = _register_and_login()
    _upload(token, filename="a.jpg")
    album = client.post("/api/albums", headers=_auth(token), json={"name": "Trip"}).json()

    res = client.post("/api/settings/delete-all-data", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["deleted_photos"] == 1

    assert client.get("/api/photos", headers=_auth(token)).json()["total"] == 0
    assert client.get("/api/albums", headers=_auth(token)).json() == []
    # The account itself still works
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 200


def test_delete_all_data_only_affects_the_requesting_user():
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")
    _upload(token_a, filename="a.jpg")
    photo_b = _upload(token_b, filename="b.jpg")

    client.post("/api/settings/delete-all-data", headers=_auth(token_a))

    assert client.get("/api/photos", headers=_auth(token_b)).json()["total"] == 1
    assert client.get(f"/api/photos/{photo_b}", headers=_auth(token_b)).status_code == 200
